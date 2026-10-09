from dataclasses import replace
from random import Random

import pytest

from musical_scumme.arranger import arrange_notes
from musical_scumme.config import CURRENT_SCUM_PROFILE, AppSettings
from musical_scumme.cover_layers import infer_cover_layers
from musical_scumme.model import MidiNote
from musical_scumme.planner import build_playback_plan


def cover_settings(**kwargs):
    return replace(AppSettings(
        performance_preset="custom", arrangement_mode="cover_song", max_polyphony=3,
        min_source_note_ms=0, min_retrigger_ms=0, max_notes_per_second=240,
        arrangement_lead_track=0,
    ), **kwargs)


def rock_song():
    vocal = [MidiNote(0, 0, 64, 75, 0, 2000), MidiNote(0, 0, 67, 75, 2500, 4000)]
    bass = [MidiNote(1, 1, 40, 85, 0, 2000)]
    rhythm = [MidiNote(2, 2, 59, 80, t, t + 150) for t in range(250, 2000, 250)]
    pad = [MidiNote(3, 3, 55, 110, 0, 2000)]
    fill = [MidiNote(4, 4, 72, 90, 2100, 2300)]
    return vocal + bass + rhythm + pad + fill, {
        0: "Main Vocal", 1: "Bass", 2: "Rhythm Guitar", 3: "Strings", 4: "Lead Guitar",
    }


def test_cover_reserves_offbeat_riff_before_earlier_loud_pad():
    source, names = rock_song()
    result = arrange_notes(source, cover_settings(), track_names=names)
    assert {n for n in source if n.track_index in {0, 1, 2, 4}} == set(result.notes)
    assert all(n.track_index != 3 for n in result.notes)
    assert result.contextual_peak_voices == 3
    assert any("Rhythm Guitar = rhythm" in warning for warning in result.warnings)
    assert {n for n in source if n.track_index == 0} <= set(result.lead_notes)


def test_cover_fills_unused_space_with_harmony_when_rhythm_absent():
    source, names = rock_song()
    source = [n for n in source if n.track_index != 2]
    result = arrange_notes(source, cover_settings(), track_names=names)
    assert set(result.notes) == set(source)


@pytest.mark.parametrize("limit", [1, 2, 3, 6])
def test_cover_source_provenance_determinism_and_full_duration_ceiling(limit):
    source, names = rock_song()
    before = tuple(source)
    result = arrange_notes(source, cover_settings(max_polyphony=limit), track_names=names)
    Random(15).shuffle(source)
    assert result == arrange_notes(source, cover_settings(max_polyphony=limit), track_names=names)
    assert set(result.notes) <= set(before)
    sounding = 0
    for _, change in sorted((t, d) for n in result.notes for t, d in [(n.start_ms, 1), (n.end_ms, -1)]):
        sounding += change
        assert sounding <= min(limit, 3)


def test_cover_accepts_rhythm_above_low_vocal_without_replacing_singer():
    source, names = rock_song()
    source = [replace(n, pitch=69) if n.track_index == 2 else n for n in source]
    result = arrange_notes(source, cover_settings(), track_names=names)
    assert {n for n in source if n.track_index == 2} <= set(result.notes)
    assert all(n.track_index == 0 for n in result.lead_notes if n.start_ms < 2000)


def test_cover_rejects_support_that_would_mask_future_vocal():
    source = [MidiNote(0, 0, 67, 90, 0, 500), MidiNote(0, 0, 60, 90, 500, 1000),
              MidiNote(1, 1, 60, 100, 0, 900)]
    result = arrange_notes(source, cover_settings(), track_names={0: "Vocal", 1: "Rhythm"})
    assert result.notes == tuple(source[:2])
    assert result.contextual_collision_rejected == 1


def test_layer_inference_uses_articulation_and_token_safe_names():
    source = [MidiNote(0, 0, 72, 80, 0, 2000)]
    source += [MidiNote(1, 1, 60, 90, t, t + 150) for t in range(0, 2000, 250)]
    source += [MidiNote(2, 2, 48, 80, 0, 2000), MidiNote(3, 3, 64, 80, 0, 2000)]
    assert infer_cover_layers(source, 0, {3: "Bassoon"}) == {
        0: "lead", 1: "rhythm", 2: "bass", 3: "harmony",
    }


@pytest.mark.parametrize("name,program", [("Rhythm guitar", None), ("Guitarra", None), ("Part 2", 30)])
def test_low_guitar_is_not_misclassified_as_bass(name, program):
    source = [MidiNote(0, 0, 76, 80, 0, 2000)]
    source += [MidiNote(1, 1, 40, 80, t, t + 90, program) for t in range(0, 2000, 125)]
    assert infer_cover_layers(source, 0, {1: name})[1] == "rhythm"


def test_program_metadata_distinguishes_unnamed_bass_and_strings():
    source = [MidiNote(0, 0, 72, 80, 0, 2000), MidiNote(1, 1, 60, 80, 0, 100, 34),
              MidiNote(2, 2, 48, 80, 0, 100, 48)]
    assert infer_cover_layers(source, 0, {}) == {0: "lead", 1: "bass", 2: "harmony"}


@pytest.mark.parametrize("mode", ["cover_song", "cover_riff"])
def test_cover_keeps_overlapping_fast_solo_attacks_in_vocal_rest(mode):
    vocal = MidiNote(0, 0, 72, 80, 0, 500)
    solo = [MidiNote(1, 1, 72 + i % 5, 80, 600 + i * 100, 750 + i * 100) for i in range(8)]
    bass = [MidiNote(2, 2, 40, 127, n.start_ms, n.start_ms + 90) for n in solo]
    result = arrange_notes([vocal] + solo + bass, cover_settings(arrangement_mode=mode),
                          track_names={0: "Vocal", 1: "Lead guitar", 2: "Bass"})
    assert set(solo) <= set(result.lead_notes)
    assert not set(bass) & set(result.lead_notes)


def test_riff_first_keeps_fast_repeated_attacks_ahead_of_sustained_bass():
    vocal = MidiNote(0, 0, 72, 80, 0, 2000)
    bass = MidiNote(1, 1, 36, 127, 0, 2000)
    riff = [MidiNote(2, 2, 43 + i % 2, 80, i * 125, i * 125 + 100, 30) for i in range(16)]
    source = [vocal, bass] + riff
    names = {0: "Vocal", 1: "Bass", 2: "Rhythm guitar"}
    ordinary = arrange_notes(source, cover_settings(max_polyphony=2), track_names=names)
    driven = arrange_notes(source, cover_settings(arrangement_mode="cover_riff", max_polyphony=2), track_names=names)
    assert set(ordinary.notes) == {vocal, bass}
    assert set(driven.notes) == {vocal, *riff}
    assert driven.contextual_peak_voices == 2
    Random(12).shuffle(source)
    assert driven == arrange_notes(source, cover_settings(arrangement_mode="cover_riff", max_polyphony=2), track_names=names)


def test_cover_warns_when_only_named_vocal_is_backing():
    source = [MidiNote(0, 0, 72, 80, 0, 500), MidiNote(1, 1, 60, 80, 0, 500)]
    result = arrange_notes(source, cover_settings(arrangement_lead_track=-1),
                          track_names={0: "Backing Vocals", 1: "Performer A"})
    assert any("labelled as backing" in warning for warning in result.warnings)


@pytest.mark.parametrize("mapping", ["fold_smart", "strict_auto", "smart3_harmonic", "melody3_contour", "match3_adaptive"])
def test_cover_plan_runs_through_existing_physical_limits(mapping):
    source, names = rock_song()
    settings = cover_settings(mapping_mode=mapping)
    plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE, track_names=names)
    assert plan.planned_notes
    held = set()
    banks = {CURRENT_SCUM_PROFILE.octave_down, CURRENT_SCUM_PROFILE.octave_up}
    for event in plan.events:
        if event.action == "down":
            assert event.key not in held
            assert not held if event.key in banks else not held & banks
            held.add(event.key)
        else:
            assert event.key in held
            held.remove(event.key)
    assert not held
