import json
import sys
import warnings
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import mido

ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location("musical_scumme_audio_worker", ROOT / "audio_worker.py")
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_merge_note_events_joins_overlaps_and_small_gaps():
    events = [
        MODULE.NoteEvent(0.0, 0.20, 60, 50),
        MODULE.NoteEvent(0.22, 0.40, 60, 55),
        MODULE.NoteEvent(0.0, 0.10, 64, 70),
    ]
    merged = MODULE.merge_note_events(events, gap_s=0.03)
    c = next(event for event in merged if event.pitch == 60)
    assert c.start_s == 0.0
    assert c.end_s == 0.40
    assert c.velocity == 55


def test_merge_note_events_preserves_confident_same_pitch_reattack():
    events = [
        MODULE.NoteEvent(0.882, 1.393, 60, 46),
        MODULE.NoteEvent(1.393, 1.579, 60, 63),
    ]
    merged = MODULE.merge_note_events(events)
    assert [(event.start_s, event.end_s, event.velocity) for event in merged] == [
        (0.882, 1.393, 46), (1.393, 1.579, 63),
    ]


def test_stem_modes_preserve_equal_strength_reattacks_without_mutation():
    events = [MODULE.NoteEvent(0, 0.2, 60, 70), MODULE.NoteEvent(0.2, 0.4, 60, 70)]
    result = MODULE.merge_detected_notes(events)
    assert len(result) == 2
    assert result[0] is not events[0]


def test_detected_reattack_trims_small_overlap_so_old_note_off_cannot_cut_new_note():
    notes = MODULE.merge_detected_notes([MODULE.NoteEvent(0, 0.21, 60, 70), MODULE.NoteEvent(0.2, 0.4, 60, 70)])
    assert [(note.start_s, note.end_s) for note in notes] == [(0, 0.2), (0.2, 0.4)]


def test_vocal_defaults_preserve_low_probability_frames_already_marked_voiced():
    notes = MODULE.pitch_track_notes([440] * 3, [0.02] * 3, [1] * 3,
                                    hop_s=0.1, duration_s=0.3, minimum_note_ms=90)
    assert len(notes) == 1
    assert notes[0].pitch == 69


def test_instrumental_detection_reduces_transients_and_disables_residual_expansion(tmp_path, monkeypatch):
    calls = {}

    def predict(path, **kwargs):
        calls.update(kwargs)
        assert path.name == "harmonic.wav"
        return {}, None, [(0, 0.2, 60, 0.6, None), (0.2, 0.4, 60, 0.6, None)]

    monkeypatch.setitem(sys.modules, "basic_pitch", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "basic_pitch.inference", SimpleNamespace(predict=predict))
    monkeypatch.setitem(sys.modules, "librosa", SimpleNamespace(
        load=lambda *args, **kwargs: ([0, 1], 22050),
        effects=SimpleNamespace(harmonic=lambda audio, margin: audio),
    ))
    monkeypatch.setitem(sys.modules, "soundfile", SimpleNamespace(write=lambda *args, **kwargs: None))
    args = SimpleNamespace(mode="instrumental", onset_threshold=0.45, frame_threshold=0.3,
                           minimum_note_ms=90, minimum_frequency=65, maximum_frequency=2000)
    notes = MODULE.transcribe_polyphonic(tmp_path / "band.wav", args)
    assert calls["melodia_trick"] is False
    assert len(notes) == 2


def test_vocal_pitch_track_rejects_silence_and_low_confidence_without_bridging():
    result = MODULE.pitch_track_notes(
        [440] * 3 + [float("nan")] + [440] * 3 + [440] * 3,
        [0.9] * 7 + [0.2] * 3, [1] * 10,
        hop_s=0.1, duration_s=1, minimum_note_ms=90,
        confidence=0.5,
    )
    assert [(event.pitch, round(event.start_s, 2), round(event.end_s, 2)) for event in result] == [
        (69, 0, 0.3), (69, 0.4, 0.7),
    ]


def test_vocal_hysteresis_avoids_vibrato_semitone_chatter_and_keeps_real_change():
    frequencies = [440 * 2 ** (offset / 12) for offset in (0, 0.53, -0.52, 0.2, 2, 2, 2)]
    result = MODULE.pitch_track_notes(frequencies, [0.9] * 7, [1] * 7, hop_s=0.1, duration_s=0.7, minimum_note_ms=90)
    assert [event.pitch for event in result] == [69, 71]
    assert result[-1].end_s == 0.7

def test_merge_note_events_does_not_promote_a_fragment_chain_to_reattacks():
    events = [
        MODULE.NoteEvent(0.00, 0.14, 45, 50),
        MODULE.NoteEvent(0.14, 0.28, 45, 55),
        MODULE.NoteEvent(0.28, 0.50, 45, 75),
    ]

    merged = MODULE.merge_note_events(events)

    assert len(merged) == 1
    assert (merged[0].start_s, merged[0].end_s, merged[0].velocity) == (0.0, 0.5, 75)


def test_write_midi_produces_readable_atomic_file(tmp_path):
    destination = tmp_path / "audio.mid"
    MODULE.write_midi([MODULE.NoteEvent(0.0, 0.25, 60, 100)], destination)
    midi = mido.MidiFile(destination)
    note_messages = [message for track in midi.tracks for message in track if message.type in {"note_on", "note_off"}]
    assert destination.exists()
    assert [message.type for message in note_messages] == ["note_on", "note_off"]


def test_emit_uses_ascii_safe_json_without_losing_unicode(capsys):
    MODULE.emit("status", message="Analysing audio…")

    output = capsys.readouterr().out
    output.encode("ascii")
    assert json.loads(output) == {"event": "status", "message": "Analysing audio…"}


def test_runtime_hides_only_known_successful_m4a_fallback_warnings():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        MODULE.configure_inference_runtime()
        warnings.warn("PySoundFile failed. Trying audioread instead.", UserWarning, stacklevel=2)
        warnings.warn(
            "librosa.core.audio.__audioread_load\nDeprecated fallback",
            FutureWarning,
            stacklevel=2,
        )
        warnings.warn("real decoder problem", UserWarning, stacklevel=2)

    assert [str(item.message) for item in caught] == ["real decoder problem"]
