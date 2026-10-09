import importlib.util
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("isolated_audio_evidence", ROOT / "audio_evidence.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
Note = MODULE.EvidenceNote


def frequency(pitch):
    return 440 * 2 ** ((np.asarray(pitch) - 69) / 12)


def test_vocal_vibrato_is_one_note_and_rests_remain_rests():
    time = np.arange(200) * .01
    pitch = 60 + .6 * np.sin(2 * np.pi * 5 * time)
    confidence, energy = np.ones(200), np.ones(200)
    confidence[80:110] = 0
    notes = MODULE.vocal_notes_from_track(frequency(pitch), confidence, energy, hop_s=.01, duration=2)
    assert [(n.pitch, n.onset, n.offset) for n in notes] == [(60, 0, .8), (60, 1.1, 2)]


def test_sustained_pitch_changes_survive_but_brief_octave_error_does_not():
    pitch = np.r_[np.full(40, 60), np.full(3, 72), np.full(27, 60), np.full(50, 62)]
    notes = MODULE.vocal_notes_from_track(frequency(pitch), np.ones(120), np.ones(120), hop_s=.01, duration=1.2)
    assert [n.pitch for n in notes] == [60, 62]
    assert [n.onset for n in notes] == pytest.approx([0, .7])
    assert [n.offset for n in notes] == pytest.approx([.7, 1.2])


def test_vocal_nonfinite_silence_and_weak_pitch_evidence_are_rejected():
    f0 = frequency(np.full(100, 60)).astype(float)
    confidence, energy = np.ones(100), np.ones(100)
    f0[10:30] = np.nan
    confidence[30:50] = .1
    energy[50:70] = 0
    energy[70:80] = np.nan
    notes = MODULE.vocal_notes_from_track(f0, confidence, energy, hop_s=.01, duration=1)
    assert [(n.onset, n.offset) for n in notes] == [(0, .1), (.8, 1)]
    with pytest.raises(ValueError, match="aligned"):
        MODULE.vocal_notes_from_track(f0, confidence[:5], energy, hop_s=.01, duration=1)


def test_model_onsets_do_not_split_a_vocal_without_actual_attack_evidence():
    f0, confidence, energy = frequency(np.full(100, 60)), np.ones(100), np.ones(100)
    hints = [.25, .5, .75]
    held = MODULE.vocal_notes_from_track(f0, confidence, energy, hop_s=.01, duration=1, attack_hints=hints)
    assert len(held) == 1
    energy[46:50] = .3
    split = MODULE.vocal_notes_from_track(f0, confidence, energy, hop_s=.01, duration=1, attack_hints=hints)
    assert [(n.onset, n.offset) for n in split] == [(0, .5), (.5, 1)]


def test_strong_guitar_bleed_outside_vocal_activity_is_not_exported_as_singing():
    # The pitch tracker confidently follows both the singer and later guitar
    # residue. Vocal detection admits only the actual singing interval.
    pitches = np.r_[np.full(100, 60), np.full(100, 80)]
    notes = MODULE.vocal_notes_from_track(frequency(pitches), np.ones(200), np.ones(200),
                                          hop_s=.01, duration=2, vocal_regions=[(.2, .7)])
    assert [n.pitch for n in notes] == [60]
    assert notes[0].onset >= .07 and notes[0].offset <= .83
    assert MODULE.vocal_notes_from_track(frequency(pitches), np.ones(200), np.ones(200),
                                         hop_s=.01, duration=2, vocal_regions=[]) == []
    assert MODULE.vocal_notes_from_track(frequency(pitches), np.ones(200), np.ones(200),
                                         hop_s=.01, duration=2, vocal_regions=[(-2, -1)]) == []


def harmonic_audio(parts):
    time = np.arange(16000) / 16000
    audio = np.zeros_like(time)
    for pitch, amplitude in parts:
        fundamental = float(frequency(pitch))
        for harmonic in range(1, 13):
            audio += amplitude / harmonic * np.sin(2 * np.pi * fundamental * harmonic * time)
    return audio


@pytest.mark.parametrize("parts, expected", [
    ([(48, 1)], {48}),
    ([(48, 1), (52, .7), (55, .8)], {48, 52, 55}),
    ([(48, .8), (60, .8)], {48, 60}),
])
def test_competing_fundamentals_reject_harmonic_ghosts_and_keep_real_octaves(parts, expected):
    pitches, coefficients, hop = MODULE.harmonic_activations(
        harmonic_audio(parts), 16000, pitches=np.arange(36, 85))
    candidates = [Note(program, pitch, .2, .8, 88)
                  for program, pitch in [(0, 48), (24, 52), (48, 55), (16, 60), (56, 67), (88, 72), (2, 61)]]
    selected = MODULE.supported_backing_notes(candidates, pitches, coefficients, hop_s=hop)
    assert {n.pitch for n in selected} == expected
    assert {n.program for n in selected} == {0}


def test_silent_backing_has_no_supported_notes():
    pitches, coefficients, hop = MODULE.harmonic_activations(np.zeros(2000), 16000, pitches=[48, 60])
    assert MODULE.supported_backing_notes([Note(24, 48, 0, .1, 88)], pitches, coefficients, hop_s=hop) == []


def test_cross_instrument_duplicates_merge_but_separate_reattacks_survive_without_overlap():
    coefficients = np.ones((1, 150))
    notes = [Note(24, 60, .1, 1.5, 88), Note(48, 60, .12, 1.3, 88),
             Note(0, 60, .8, 1.8, 88), Note(128, 60, 0, 2, 88, True), Note(100, 60, 0, 2, 88)]
    selected = MODULE.supported_backing_notes(notes, [60], coefficients, hop_s=.02)
    assert [(n.onset, n.offset) for n in selected] == [(.1, .8), (.8, 1.8)]
    assert all(n.program == 0 for n in selected)


def test_backing_note_requires_sustained_support_and_dynamics_follow_audio():
    coefficients = np.zeros((3, 100))
    coefficients[0, :50] = 1
    coefficients[1, 50:] = .4
    coefficients[2, :5] = 1
    notes = [Note(0, 48, .1, 1.5, 88), Note(24, 52, 1.1, 1.9, 88), Note(16, 55, .1, .9, 88)]
    selected = MODULE.supported_backing_notes(notes, [48, 52, 55], coefficients, hop_s=.02)
    assert [n.pitch for n in selected] == [48, 52]
    assert selected[0].offset <= 1.02
    assert selected[0].velocity > selected[1].velocity


def test_nonfinite_spectral_input_is_not_turned_into_notes():
    with pytest.raises(ValueError, match="finite"):
        MODULE.harmonic_activations(np.array([np.nan]), 16000)
    with pytest.raises(ValueError, match="spectral evidence"):
        MODULE.supported_backing_notes([Note(0, 60, 0, 1, 88)], [60], [[np.nan]], hop_s=.02)


def test_vocal_chunks_keep_absolute_alignment_and_clean_tone_confidence(monkeypatch):
    class Tensor:
        def __init__(self, values):
            self.values = np.asarray(values)

        def unsqueeze(self, axis):
            return Tensor(np.expand_dims(self.values, axis))

        def __getitem__(self, index):
            return Tensor(self.values[index])

        def cpu(self):
            return self

        def numpy(self):
            return self.values

    def predict(clip, rate, hop, *args, **kwargs):
        count = len(clip.values[0]) // hop + 1
        # Encode the source's absolute position in the returned pitch track.
        positions = 100 + clip.values[0, 0] + np.arange(count) * hop / rate
        return Tensor(positions[None]), Tensor(np.full((1, count), .9))

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        from_numpy=Tensor, inference_mode=nullcontext))
    # Deliberately no optional spectral "Silence" gate: it must not erase tones.
    monkeypatch.setitem(sys.modules, "torchcrepe", SimpleNamespace(
        predict=predict, filter=SimpleNamespace(median=lambda values, size: values)))
    monkeypatch.setitem(sys.modules, "librosa", SimpleNamespace(feature=SimpleNamespace(
        rms=lambda y, **kw: np.ones((1, len(y) // kw["hop_length"] + 1)))))
    audio = np.arange(320037, dtype=np.float32) / 16000
    f0, confidence, energy, hop = MODULE.track_vocal_audio(audio, 16000, "cpu")
    assert len(f0) == len(confidence) == len(energy) == 2001
    assert f0 == pytest.approx(100 + np.arange(2001) * .01, abs=1e-5)
    assert np.all(confidence == .9)
    assert hop == .01


def test_recovery_keeps_a_quiet_vocal_phrase_but_not_silence_or_instrumental_bleed():
    pitch = np.r_[np.full(40, 60), np.full(100, 62), np.full(60, 80)]
    energy = np.r_[np.ones(40), np.full(100, .004), np.ones(60)]
    confidence = np.ones(200)
    energy[80:90] = 0
    energy[100:110] = 9e-6
    kwargs = dict(hop_s=.01, duration=2, vocal_regions=[(0, 1.28)])
    original = MODULE.vocal_notes_from_track(frequency(pitch), confidence, energy, **kwargs)
    assert [n.pitch for n in original] == [60]
    recovered = MODULE.vocal_notes_from_track(
        frequency(pitch), confidence, energy, recover_quiet_notes=True, **kwargs)
    assert [n.pitch for n in recovered] == [60, 62, 62, 62]
    assert [n.onset for n in recovered] == pytest.approx([0, .4, .9, 1.1])
    assert [n.offset for n in recovered] == pytest.approx([.4, .8, 1, 1.4])
    assert MODULE.vocal_notes_from_track(
        frequency(pitch), confidence, energy, hop_s=.01, duration=2,
        vocal_regions=[], recover_quiet_notes=True) == []


def test_quiet_vocal_recovery_requires_stronger_periodicity_than_standard_detection():
    pitch = np.full(200, 60)
    energy = np.r_[np.ones(100), np.full(100, .004)]
    confidence = np.r_[np.ones(100), np.full(100, .5)]
    notes = MODULE.vocal_notes_from_track(
        frequency(pitch), confidence, energy, hop_s=.01, duration=2,
        recover_quiet_notes=True)
    assert [(n.onset, n.offset) for n in notes] == [(0, 1)]


def test_brief_measured_vocal_pitch_survives_without_a_native_attack_hint():
    pitch = np.r_[np.full(40, 60), np.full(5, 62), np.full(55, 64)]
    kwargs = dict(hop_s=.01, duration=1, vocal_regions=[(0, 1)])
    original = MODULE.vocal_notes_from_track(frequency(pitch), np.ones(100), np.ones(100), **kwargs)
    assert [n.pitch for n in original] == [60, 64]
    recovered = MODULE.vocal_notes_from_track(
        frequency(pitch), np.ones(100), np.ones(100), recover_quiet_notes=True, **kwargs)
    assert [(n.pitch, n.onset, n.offset) for n in recovered] == [(60, 0, .4), (62, .4, .45), (64, .45, 1)]


def test_recovery_preserves_a_brief_first_note_without_blending_two_pitches():
    pitch = np.r_[np.full(4, 60), np.full(36, 62)]
    notes = MODULE.vocal_notes_from_track(
        frequency(pitch), np.ones(40), np.ones(40), hop_s=.01, duration=.4,
        recover_quiet_notes=True)
    assert [(n.pitch, n.onset, n.offset) for n in notes] == [(60, 0, .04), (62, .04, .4)]


def test_recovery_does_not_promote_brief_octave_errors_or_vibrato_into_new_notes():
    pitch = np.r_[np.full(40, 60), np.full(5, 72), np.full(55, 60)]
    notes = MODULE.vocal_notes_from_track(
        frequency(pitch), np.ones(100), np.ones(100), hop_s=.01, duration=1,
        recover_quiet_notes=True)
    assert [(n.pitch, n.onset, n.offset) for n in notes] == [(60, 0, 1)]
    for phase in [0, np.pi / 2, -.3]:
        pitch = 60 + .6 * np.sin(2 * np.pi * 5 * np.arange(100) * .01 + phase)
        notes = MODULE.vocal_notes_from_track(
            frequency(pitch), np.ones(100), np.ones(100), hop_s=.01, duration=1,
            recover_quiet_notes=True)
        assert [(n.pitch, n.onset, n.offset) for n in notes] == [(60, 0, 1)]


def test_audio_attacks_recover_short_same_pitch_repeats_without_splitting_a_crescendo():
    pitch = frequency(np.full(60, 60))
    energy = np.ones(60)
    energy[16:20] = .3
    energy[36:40] = .3
    kwargs = dict(hop_s=.01, duration=.6, recover_quiet_notes=True)
    notes = MODULE.vocal_notes_from_track(pitch, np.ones(60), energy, **kwargs)
    assert [(n.onset, n.offset) for n in notes] == [(0, .2), (.2, .4), (.4, .6)]
    crescendo = MODULE.vocal_notes_from_track(pitch, np.ones(60), np.linspace(.03, 1, 60), **kwargs)
    assert [(n.onset, n.offset) for n in crescendo] == [(0, .6)]


def test_recovery_reattacks_in_a_quiet_phrase_are_not_gated_by_a_previous_loud_phrase():
    pitch = frequency(np.full(100, 60))
    energy = np.r_[np.ones(20), np.full(80, .004)]
    energy[46:50] = .0012
    notes = MODULE.vocal_notes_from_track(
        pitch, np.ones(100), energy, hop_s=.01, duration=1, recover_quiet_notes=True)
    assert [(n.onset, n.offset) for n in notes] == [(0, .5), (.5, 1)]
    crescendo = np.r_[np.ones(20), np.linspace(.0003, .004, 80)]
    notes = MODULE.vocal_notes_from_track(
        pitch, np.ones(100), crescendo, hop_s=.01, duration=1, recover_quiet_notes=True)
    assert [(n.onset, n.offset) for n in notes] == [(0, 1)]


def test_quiet_backing_recovery_keeps_a_real_chord_tone_and_rejects_root_overtones():
    pitches, coefficients, hop = MODULE.harmonic_activations(
        harmonic_audio([(48, 1), (52, .1)]), 16000, pitches=np.arange(36, 85))
    candidates = [Note(24, pitch, .2, .8, 88) for pitch in [48, 52, 60, 67, 72]]
    original = MODULE.supported_backing_notes(candidates, pitches, coefficients, hop_s=hop)
    recovered = MODULE.supported_backing_notes(
        candidates, pitches, coefficients, hop_s=hop, recover_quiet_notes=True)
    assert [n.pitch for n in original] == [48]
    assert [n.pitch for n in recovered] == [48, 52]
    assert recovered[0].velocity > recovered[1].velocity
    # Spectral analysis must not create a pitch/attack absent from the model.
    no_candidate = MODULE.supported_backing_notes(
        candidates[:1], pitches, coefficients, hop_s=hop, recover_quiet_notes=True)
    assert [n.pitch for n in no_candidate] == [48]


def test_quiet_backing_recovery_uses_local_dynamics_and_requires_persistent_evidence():
    coefficients = np.zeros((3, 100))
    coefficients[0, :40] = 1
    coefficients[1, 40:90] = .004
    coefficients[2, 95:97] = .2
    candidates = [Note(24, 48, .1, .7, 88), Note(24, 52, .9, 1.7, 88), Note(16, 55, 1.8, 2, 88)]
    assert [n.pitch for n in MODULE.supported_backing_notes(
        candidates, [48, 52, 55], coefficients, hop_s=.02)] == [48]
    recovered = MODULE.supported_backing_notes(
        candidates, [48, 52, 55], coefficients, hop_s=.02, recover_quiet_notes=True)
    assert [n.pitch for n in recovered] == [48, 52]
    assert [(n.onset, n.offset) for n in recovered] == [(.1, .7), (.9, 1.7)]
    assert MODULE.supported_backing_notes(
        candidates, [48, 52, 55], np.zeros((3, 100)), hop_s=.02, recover_quiet_notes=True) == []
