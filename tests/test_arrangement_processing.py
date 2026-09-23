from dataclasses import replace
from random import Random

import pytest

from musical_scumme.arrangement_processing import _VoiceTimeline, process_contextual_arrangement
from musical_scumme.arranger import arrange_notes
from musical_scumme.config import CURRENT_SCUM_PROFILE, AppSettings
from musical_scumme.model import MidiNote
from musical_scumme.planner import build_playback_plan

MODES = ("vocal_director", "vocal_director_pulse", "chamber_director")


def settings(mode="vocal_director", **kwargs):
    return replace(AppSettings(
        performance_preset="custom", arrangement_mode=mode, max_polyphony=3,
        min_source_note_ms=0, min_retrigger_ms=0, max_notes_per_second=240,
        arrangement_lead_track=0,
    ), **kwargs)


def peak(notes):
    events = sorted((time, change) for n in notes for time, change in [(n.start_ms, 1), (n.end_ms, -1)])
    sounding = maximum = 0
    for _, change in events:
        sounding += change
        maximum = max(maximum, sounding)
    return maximum


def dense_source():
    leads = [MidiNote(0, 0, 72 + i % 4, 80, i * 500, (i + 1) * 500) for i in range(12)]
    accompaniment = [
        MidiNote(track, 1, pitch + i % 3, 90, i * 125, i * 125 + 1100)
        for i in range(48) for track, pitch in [(1, 36), (2, 48), (3, 55), (4, 60)]
    ]
    return leads + accompaniment


@pytest.mark.parametrize("seed", range(8))
def test_interval_index_matches_naive_full_duration_voice_counts(seed):
    rng = Random(seed)
    notes = [MidiNote(0, 0, 60, 90, start, start + rng.randint(1, 100))
             for start in (rng.randint(0, 300) for _ in range(120))]
    timeline = _VoiceTimeline(notes)
    occupied = [0] * (len(timeline.times) - 1)
    for note in notes:
        left = timeline.indices[note.start_ms]
        right = timeline.indices[note.end_ms]
        assert timeline.voices(note) == max(occupied[left:right])
        timeline.voices(note, add=True)
        for index in range(left, right):
            occupied[index] += 1
        assert timeline.maximum[0] == max(occupied)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("limit", [1, 2, 3, 8])
def test_contextual_modes_preserve_lead_source_and_full_duration_capacity(mode, limit):
    source = dense_source()
    before = tuple(source)
    result = arrange_notes(source, settings(mode, max_polyphony=limit))
    assert set(n for n in source if n.track_index == 0) <= set(result.notes)
    assert set(result.notes) <= set(source)
    assert peak(result.notes) <= min(limit, 3)
    assert tuple(source) == before
    assert result.contextual_capacity_rejected > 0
    assert result.dropped_notes == (
        result.dropped_percussion + result.dropped_short + result.dropped_arrangement
        + result.dropped_retrigger + result.dropped_density
    )


def test_director_reduces_sustained_pileup_compared_with_onset_ballad():
    source = dense_source()
    old = arrange_notes(source, settings("vocal_ballad"))
    new = arrange_notes(source, settings())
    assert peak(old.notes) > 3
    assert peak(new.notes) <= 3
    assert {n for n in new.notes if n.track_index == 0} == {n for n in old.notes if n.track_index == 0}


def test_future_lead_pitch_rejects_support_before_it_can_mask_the_attack():
    a = MidiNote(0, 0, 72, 80, 0, 500)
    b = MidiNote(0, 0, 60, 80, 500, 1000)
    collision = MidiNote(1, 1, 60, 100, 0, 900)
    safe = MidiNote(2, 1, 48, 90, 0, 900)
    result = arrange_notes([a, b, collision, safe], settings())
    assert collision not in result.notes
    assert {a, b, safe} == set(result.notes)
    assert result.contextual_collision_rejected == 1


def test_future_lead_overlap_is_reserved_before_earlier_support():
    a = MidiNote(0, 0, 72, 80, 0, 750)
    b = MidiNote(0, 0, 76, 80, 500, 1000)
    support = MidiNote(1, 1, 48, 100, 0, 900)
    result = arrange_notes([a, b, support], settings(max_polyphony=2))
    assert set(result.notes) == {a, b}
    assert result.contextual_capacity_rejected == 1


def test_source_lead_overlap_is_preserved_and_disclosed():
    notes = [MidiNote(0, 0, 72 + i, 80, i * 100, 1000) for i in range(4)]
    result = arrange_notes(notes, settings(max_polyphony=1))
    assert set(result.notes) == set(notes)
    assert any("Source lead notes overlap" in warning for warning in result.warnings)


def test_same_pitch_support_can_restart_at_exact_release_boundary():
    lead = MidiNote(0, 0, 72, 80, 0, 1000)
    a = MidiNote(1, 1, 48, 90, 0, 500)
    b = MidiNote(2, 1, 48, 90, 500, 1000)
    result = arrange_notes([lead, a, b], settings(max_polyphony=2))
    assert set(result.notes) == {lead, a, b}


def test_overlap_duplicates_do_not_spend_two_support_voices():
    lead = MidiNote(0, 0, 72, 80, 0, 1000)
    a = MidiNote(1, 1, 48, 90, 0, 750)
    b = MidiNote(2, 1, 48, 90, 250, 1000)
    result = arrange_notes([lead, a, b], settings())
    assert set(result.notes) == {lead, a}
    assert result.contextual_collision_rejected == 1


def test_instrumental_fill_sustain_is_owned_until_primary_returns():
    primary = MidiNote(0, 0, 65, 80, 1000, 1500)
    fill = MidiNote(1, 1, 72, 90, 0, 900)
    distraction = MidiNote(2, 1, 84, 127, 250, 500)
    result = arrange_notes([primary, fill, distraction], settings(max_polyphony=1))
    assert set(result.notes) == {primary, fill}


def test_support_history_resets_only_after_actual_silence():
    a = MidiNote(0, 0, 72, 80, 0, 500)
    b = MidiNote(0, 0, 74, 80, 1500, 1800)
    gap = process_contextual_arrangement([[a], [b]], (a, b), 0, 3, "warm")
    assert gap.phrase_resets == 1
    held = replace(a, end_ms=1400)
    sounding = process_contextual_arrangement([[held], [b]], (held, b), 0, 3, "warm")
    assert sounding.phrase_resets == 0


def test_rhythm_and_warm_directors_select_different_source_articulation():
    lead = MidiNote(0, 0, 72, 80, 0, 1200)
    bass = MidiNote(1, 1, 36, 90, 0, 1000)
    warm = MidiNote(2, 1, 60, 85, 0, 1200)
    pulse = MidiNote(3, 1, 60, 85, 0, 120)
    source = [lead, bass, warm, pulse]
    sustained = arrange_notes(source, settings())
    rhythmic = arrange_notes(source, settings("vocal_director_pulse"))
    assert set(sustained.notes) == {lead, bass, warm}
    assert set(rhythmic.notes) == {lead, bass, pulse}


@pytest.mark.parametrize("mode", MODES)
def test_identical_onset_pitch_ties_are_input_order_independent(mode):
    source = dense_source() + [MidiNote(8, 2, 48, 90, 0, 1100)]
    expected = arrange_notes(source, settings(mode))
    for seed in range(5):
        Random(seed).shuffle(source)
        assert arrange_notes(source, settings(mode)) == expected


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("mapping", ["fold_smart", "strict_auto", "smart3_harmonic", "melody3_contour", "match3_adaptive"])
def test_contextual_plans_expose_diagnostics_and_keep_standalone_bank_safety(mode, mapping):
    plan = build_playback_plan(dense_source(), settings(mode, mapping_mode=mapping), CURRENT_SCUM_PROFILE)
    assert plan.diagnostics["contextual_peak_voices_before_density"] <= 3
    assert plan.diagnostics["contextual_capacity_rejected"] > 0
    active = set()
    bank_keys = {CURRENT_SCUM_PROFILE.octave_down, CURRENT_SCUM_PROFILE.octave_up}
    for event in plan.events:
        if event.action == "down":
            assert event.key not in active
            assert not active if event.key in bank_keys else not active & bank_keys
            active.add(event.key)
        else:
            assert event.key in active
            active.remove(event.key)
    assert not active
