"""Public-plan checks for optional phrase timing and connected articulation."""

from collections import defaultdict
from dataclasses import replace
from random import Random

import pytest

from musical_scumme.config import CURRENT_SCUM_PROFILE, ENHANCED_MAPPING_MODES, AppSettings
from musical_scumme.instrument_profiles import INSTRUMENT_PROFILES
from musical_scumme.model import MidiNote
from musical_scumme.planner import build_playback_plan


def settings(**changes):
    values = {
        "performance_preset": "custom",
        "arrangement_mode": "melody",
        "mapping_mode": "fold_smart",
        "min_source_note_ms": 0,
        "min_retrigger_ms": 0,
        "max_notes_per_second": 240,
        "max_polyphony": 3,
        "onset_group_ms": 1,
        "chord_spread_ms": 0,
        "hold_ratio": 0.60,
        "min_hold_ms": 20,
        "max_hold_ms": 1500,
        "velocity_expression": 0.0,
        "key_retrigger_gap_ms": 22,
        "fluid_phrasing": 0,
    }
    values.update(changes)
    return AppSettings(**values)


def melody(*, start=0.0, count=12, spacing=250.0, gate=0.8):
    pitches = (60, 62, 64, 65, 67, 69, 71, 72, 71, 69, 67, 65)
    return [
        MidiNote(0, 0, pitches[index % len(pitches)], 90, start + index * spacing,
                 start + (index + gate) * spacing)
        for index in range(count)
    ]


def plan(source, config, *, names=None):
    return build_playback_plan(source, config, CURRENT_SCUM_PROFILE, track_names=names)


def identities(result):
    return [
        (note.source_pitch, note.mapped_pitch, note.base_pitch, note.modifier,
         note.key, note.score_group, note.voice_index)
        for note in result.planned_notes
    ]


def assert_safe_events(result, retrigger_gap):
    assert result.retained_notes == len(result.planned_notes) > 0
    assert result.event_count > 0
    assert [event.at_ms for event in result.events] == sorted(event.at_ms for event in result.events)
    assert all(note.start_ms >= 0 and note.end_ms > note.start_ms for note in result.planned_notes)
    modifier_keys = {CURRENT_SCUM_PROFILE.octave_up, CURRENT_SCUM_PROFILE.octave_down}
    active = set()
    last_release = {}
    for event in result.events:
        if event.action == "down":
            assert event.key not in active
            if event.key in modifier_keys:
                assert not active
            else:
                assert not active.intersection(modifier_keys)
                if event.key in last_release:
                    assert event.at_ms - last_release[event.key] >= retrigger_gap - 0.001
            active.add(event.key)
        else:
            assert event.key in active
            active.remove(event.key)
            if event.key not in modifier_keys:
                last_release[event.key] = event.at_ms
    assert not active


def peak_voices(result):
    changes = defaultdict(int)
    for note in result.planned_notes:
        changes[note.start_ms] += 1
        changes[note.end_ms] -= 1
    sounding = peak = 0
    for time in sorted(changes):
        sounding += changes[time]
        peak = max(peak, sounding)
    return peak


def test_zero_fluidity_keeps_the_source_attacks_and_existing_hold_policy():
    source = melody()
    result = plan(source, settings())

    assert result.retained_notes == len(source)
    assert [note.start_ms for note in result.planned_notes] == [note.start_ms for note in source]
    assert [note.end_ms - note.start_ms for note in result.planned_notes] == pytest.approx(
        [note.duration_ms * 0.60 for note in source]
    )
    assert result.diagnostics.get("fluid_phrasing", 0) == 0
    assert result.diagnostics.get("fluid_shifted_groups", 0) == 0
    assert result.diagnostics.get("fluid_connected_notes", 0) == 0
    assert result.diagnostics.get("fluid_added_hold_ms", 0.0) == 0.0


@pytest.mark.parametrize("intensity", [65, 100])
@pytest.mark.parametrize("arrangement", ["melody", "faithful", "intelligent"])
def test_fluidity_preserves_notes_and_is_deterministic_without_mutating_source(intensity, arrangement):
    source = melody()
    untouched = tuple(source)
    config = settings(arrangement_mode=arrangement)
    baseline = plan(source, config)
    fluid_config = replace(config, fluid_phrasing=intensity)
    first = plan(source, fluid_config)
    shuffled = list(source)
    Random(163).shuffle(shuffled)
    second = plan(shuffled, fluid_config)

    assert first.planned_notes == second.planned_notes
    assert first.events == second.events
    assert first.diagnostics == second.diagnostics
    assert tuple(source) == untouched
    assert config.fluid_phrasing == 0
    assert fluid_config.fluid_phrasing == intensity
    assert first.retained_notes == baseline.retained_notes == len(source)
    assert identities(first) == identities(baseline)
    assert first.diagnostics["fluid_phrasing"] == intensity
    assert first.diagnostics["fluid_phrase_count"] > 0


@pytest.mark.parametrize("intensity", [65, 100])
def test_connected_source_melody_fills_playback_gaps_with_fixed_phrase_endpoints(intensity):
    source = melody()
    baseline = plan(source, settings())
    fluid = plan(source, settings(fluid_phrasing=intensity))

    assert fluid.diagnostics["fluid_connected_notes"] > 0
    assert fluid.diagnostics["fluid_added_hold_ms"] > 0
    assert fluid.diagnostics["fluid_shifted_groups"] > 0
    assert fluid.diagnostics["fluid_max_shift_ms"] > 0
    assert fluid.planned_notes[0].start_ms == baseline.planned_notes[0].start_ms
    assert fluid.planned_notes[-1].start_ms == baseline.planned_notes[-1].start_ms
    assert sum(note.end_ms - note.start_ms for note in fluid.planned_notes) > sum(
        note.end_ms - note.start_ms for note in baseline.planned_notes
    )
    assert [note.start_ms for note in fluid.planned_notes] == sorted(
        note.start_ms for note in fluid.planned_notes
    )


def test_chord_rolls_follow_one_shared_shift_without_changing_voice_offsets():
    source = [
        MidiNote(track, track, pitch, 90, index * 320.0, index * 320.0 + 256.0)
        for index in range(10)
        for track, pitch in ((0, 72), (1, 60), (2, 67))
    ]
    names = {0: "Lead melody", 1: "Bass", 2: "Piano accompaniment"}
    config = settings(arrangement_mode="intelligent", chord_spread_ms=12)
    baseline = plan(source, config, names=names)
    fluid = plan(source, replace(config, fluid_phrasing=100), names=names)
    original_groups = defaultdict(list)
    fluid_groups = defaultdict(list)
    for note in baseline.planned_notes:
        original_groups[note.score_group].append(note)
    for note in fluid.planned_notes:
        fluid_groups[note.score_group].append(note)

    assert identities(fluid) == identities(baseline)
    assert any(len(group) > 1 for group in original_groups.values())
    assert fluid.diagnostics["fluid_shifted_groups"] > 0
    for group_id, original in original_groups.items():
        rewritten = fluid_groups[group_id]
        offsets = [note.start_ms - original[0].start_ms for note in original]
        assert [note.start_ms - rewritten[0].start_ms for note in rewritten] == pytest.approx(offsets)
    for group_id in (min(original_groups), max(original_groups)):
        assert fluid_groups[group_id][0].start_ms == original_groups[group_id][0].start_ms


def test_phrase_breath_remains_silent_and_next_phrase_starts_on_its_source_attack():
    source = melody(count=4) + melody(start=2500.0, count=8)
    baseline = plan(source, settings())
    fluid = plan(source, settings(fluid_phrasing=100))

    assert fluid.diagnostics["fluid_phrase_count"] >= 2
    assert fluid.planned_notes[3].start_ms == baseline.planned_notes[3].start_ms
    assert fluid.planned_notes[3].end_ms == baseline.planned_notes[3].end_ms
    assert fluid.planned_notes[4].start_ms == baseline.planned_notes[4].start_ms == 2500.0
    assert fluid.planned_notes[4].start_ms - fluid.planned_notes[3].end_ms > 1500.0


def test_short_staccato_is_not_connected_across_deliberate_silence():
    source = melody(gate=0.12)
    baseline = plan(source, settings())
    fluid = plan(source, settings(fluid_phrasing=100))

    assert fluid.diagnostics["fluid_connected_notes"] == 0
    assert fluid.diagnostics["fluid_added_hold_ms"] == 0
    assert [note.end_ms - note.start_ms for note in fluid.planned_notes] == pytest.approx(
        [note.end_ms - note.start_ms for note in baseline.planned_notes]
    )


def test_active_accompaniment_does_not_remove_the_lead_phrase_breath():
    lead = melody(count=4) + melody(start=2500.0, count=8)
    # Sustained support stays audible through the breath. New support attacks
    # would instead become legitimate instrumental lead fills in this recipe.
    accompaniment = [MidiNote(1, 1, pitch, 65, 0.0, 5000.0) for pitch in (48, 55)]
    source = lead + accompaniment
    config = settings(
        arrangement_mode="chamber_director", arrangement_lead_track=0,
        target_instrument="harmonica", max_hold_ms=4000,
    )
    names = {0: "Lead melody", 1: "Accompaniment"}
    baseline = plan(source, config, names=names)
    fluid = plan(source, replace(config, fluid_phrasing=100), names=names)
    originals = [note for note in baseline.planned_notes if note.source_pitch >= 60]
    rewritten = [note for note in fluid.planned_notes if note.source_pitch >= 60]

    assert len(originals) == len(rewritten) == len(lead)
    assert fluid.diagnostics["fluid_phrase_count"] >= 2
    assert originals[3].start_ms == rewritten[3].start_ms == 750.0
    assert originals[3].end_ms == rewritten[3].end_ms
    assert originals[4].start_ms == rewritten[4].start_ms == 2500.0
    assert any(note.source_pitch < 60 and note.end_ms > 2500.0 for note in fluid.planned_notes)


@pytest.mark.parametrize("layers", [1, 2, 3])
@pytest.mark.parametrize("instrument", sorted(INSTRUMENT_PROFILES))
def test_abutting_contextual_chords_keep_the_full_duration_voice_ceiling(layers, instrument):
    chords = ((72, 48, 55), (71, 50, 57), (69, 48, 55), (67, 50, 57)) * 2
    source = [
        MidiNote(track, track, pitch, 90, index * 500.0, (index + 1) * 500.0)
        for index, pitches in enumerate(chords)
        for track, pitch in enumerate(pitches)
    ]
    config = settings(
        arrangement_mode="chamber_director", arrangement_lead_track=0,
        max_polyphony=layers, target_instrument=instrument,
        hold_ratio=1.0, max_hold_ms=2000,
    )
    names = {0: "Lead melody", 1: "Bass", 2: "Harmony"}
    baseline = plan(source, config, names=names)
    fluid = plan(source, replace(config, fluid_phrasing=100), names=names)

    assert peak_voices(baseline) <= layers
    assert peak_voices(fluid) <= layers
    assert fluid.retained_notes == baseline.retained_notes
    assert identities(fluid) == identities(baseline)
    assert fluid.diagnostics["fluid_shifted_groups"] > 0
    assert_safe_events(fluid, config.key_retrigger_gap_ms)


@pytest.mark.parametrize("speed", [0.25, 1.0, 3.0])
@pytest.mark.parametrize("instrument", sorted(INSTRUMENT_PROFILES))
def test_fluid_holds_respect_setting_and_instrument_caps_at_every_speed(speed, instrument):
    source = melody(spacing=5000.0, gate=0.95, count=8)
    config = settings(
        fluid_phrasing=100, speed=speed, target_instrument=instrument,
        max_hold_ms=1350, hold_ratio=0.90,
    )
    result = plan(source, config)
    cap = min(config.max_hold_ms / speed, INSTRUMENT_PROFILES[instrument].max_sustain_ms)

    assert result.retained_notes == len(source)
    assert all(0 < note.end_ms - note.start_ms <= cap + 0.001 for note in result.planned_notes)
    assert_safe_events(result, config.key_retrigger_gap_ms)


@pytest.mark.parametrize("mapping", sorted(ENHANCED_MAPPING_MODES))
@pytest.mark.parametrize("instrument", sorted(INSTRUMENT_PROFILES))
def test_fluid_bank_transitions_and_repeated_keys_keep_events_balanced(mapping, instrument):
    pitches = (48, 48, 60, 60, 72, 72, 84, 84, 67, 55, 79, 60, 60, 72)
    source = [
        MidiNote(0, 0, pitch, 90, index * 180.0, index * 180.0 + 162.0)
        for index, pitch in enumerate(pitches)
    ]
    config = settings(
        fluid_phrasing=100, mapping_mode=mapping, target_instrument=instrument,
        hold_ratio=1.0, min_hold_ms=30, max_hold_ms=1500,
    )
    result = plan(source, config)

    assert_safe_events(result, config.key_retrigger_gap_ms)
    assert result.diagnostics["fluid_phrasing"] == 100
    assert all(
        note.mapped_pitch == note.base_pitch + 12 * note.modifier for note in result.planned_notes
    )


@pytest.mark.parametrize("count", [0, 1, 2])
def test_empty_or_tiny_phrases_produce_valid_plans_without_timing_movement(count):
    source = melody(count=count)
    baseline = plan(source, settings())
    fluid = plan(source, settings(fluid_phrasing=100))

    assert identities(fluid) == identities(baseline)
    assert [note.start_ms for note in fluid.planned_notes] == [note.start_ms for note in baseline.planned_notes]
    assert fluid.diagnostics.get("fluid_shifted_groups", 0) == 0
    if count:
        assert_safe_events(fluid, 22)
    else:
        assert fluid.planned_notes == fluid.events == []
