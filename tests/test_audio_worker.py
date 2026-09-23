import json
import sys
import warnings
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

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
        (0.882, 1.393, 46),
        (1.393, 1.579, 63),
    ]


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
