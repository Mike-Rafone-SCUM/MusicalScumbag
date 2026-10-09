"""Integration regressions for restored cover modes with optional fluid phrasing."""

from collections import Counter, defaultdict
from dataclasses import replace
from random import Random

import pytest

from musical_scumme.arranger import arrange_notes
from musical_scumme.config import CURRENT_SCUM_PROFILE, ENHANCED_MAPPING_MODES, AppSettings
from musical_scumme.input_backend import DryRunBackend
from musical_scumme.model import MidiNote
from musical_scumme.planner import build_playback_plan


def cover_settings(mode, **changes):
    return replace(AppSettings(
        performance_preset="custom", arrangement_mode=mode,
        arrangement_lead_track=0, mapping_mode="fold_smart",
        min_source_note_ms=0, min_retrigger_ms=0, max_notes_per_second=240,
        max_polyphony=3, onset_group_ms=1, chord_spread_ms=0,
        hold_ratio=1.0, min_hold_ms=30, max_hold_ms=2000,
        velocity_expression=0.0, key_retrigger_gap_ms=22,
        fluid_phrasing=100,
    ), **changes)


def ensemble():
    source = []
    for index in range(10):
        pitches = ((72, 40, 57, 62), (71, 43, 59, 64),
                   (69, 40, 55, 62), (67, 43, 53, 64))[index % 4]
        for track, pitch in enumerate(pitches):
            source.append(MidiNote(track, track, pitch, 80 + track * 10,
                                   index * 500, (index + 1) * 500))
    return source, {0: "Main Vocal", 1: "Bass", 2: "Rhythm Guitar", 3: "Strings"}


def identities(plan):
    return [(n.source_pitch, n.mapped_pitch, n.base_pitch, n.modifier,
             n.key, n.score_group, n.voice_index) for n in plan.planned_notes]


def peak_voices(notes):
    changes = defaultdict(int)
    for note in notes:
        changes[note.start_ms] += 1
        changes[note.end_ms] -= 1
    sounding = peak = 0
    for time in sorted(changes):
        sounding += changes[time]
        peak = max(peak, sounding)
    return peak


def assert_safe_events(plan, settings):
    backend = DryRunBackend()
    held = set()
    releases = {}
    banks = {CURRENT_SCUM_PROFILE.octave_down, CURRENT_SCUM_PROFILE.octave_up}
    allowed = set(CURRENT_SCUM_PROFILE.base_notes) | banks
    assert [e.at_ms for e in plan.events] == sorted(e.at_ms for e in plan.events)
    for event in plan.events:
        assert event.key in allowed
        assert event.key != "W"
        if event.action == "down":
            assert event.key not in held
            if event.key in banks:
                assert not held
            else:
                assert not held & banks
                if event.key in releases:
                    assert event.at_ms - releases[event.key] >= settings.key_retrigger_gap_ms - 0.001
            held.add(event.key)
            backend.key_down(event.key)
        else:
            assert event.key in held
            held.remove(event.key)
            backend.key_up(event.key)
            if event.key not in banks:
                releases[event.key] = event.at_ms
    assert not held
    assert not backend.pressed
    assert ("down", "W") not in backend.history


@pytest.mark.parametrize("mode", ["cover_song", "cover_riff"])
@pytest.mark.parametrize("lead", [0, 2], ids=["chosen-singer", "chosen-guitar"])
@pytest.mark.parametrize("layers", [1, 2, 3, 6])
def test_restored_covers_keep_explicit_lead_source_provenance_and_capacity_with_fluidity(mode, lead, layers):
    source, names = ensemble()
    untouched = tuple(source)
    settings = cover_settings(mode, arrangement_lead_track=lead, max_polyphony=layers)
    arrangement = arrange_notes(source, settings, track_names=names)
    assert arrangement.lead_notes
    assert all(note.track_index == lead for note in arrangement.lead_notes)
    assert set(arrangement.notes) <= set(untouched)
    assert peak_voices(arrangement.notes) <= min(layers, 3)
    baseline = build_playback_plan(source, replace(settings, fluid_phrasing=0),
                                   CURRENT_SCUM_PROFILE, track_names=names)
    flowing = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE, track_names=names)
    shuffled = list(source)
    Random(104).shuffle(shuffled)
    repeated = build_playback_plan(shuffled, settings, CURRENT_SCUM_PROFILE, track_names=names)

    assert tuple(source) == untouched
    assert flowing.planned_notes == repeated.planned_notes
    assert flowing.events == repeated.events
    assert identities(flowing) == identities(baseline)
    assert flowing.retained_notes == baseline.retained_notes > 0
    assert flowing.diagnostics["fluid_phrasing"] == 100
    assert flowing.diagnostics["fluid_shifted_groups"] > 0
    assert Counter(n.source_pitch for n in flowing.planned_notes) <= Counter(n.pitch for n in arrangement.notes)
    assert peak_voices(flowing.planned_notes) <= min(layers, 3)
    assert_safe_events(flowing, settings)


@pytest.mark.parametrize("mode", ["cover_song", "cover_riff"])
def test_fluid_cover_preserves_bass_or_riff_priority_in_full_duration_two_voice_budget(mode):
    vocal = [MidiNote(0, 0, 72, 75, index * 500, index * 500 + 400) for index in range(8)]
    bass = [MidiNote(1, 1, 40, 127, 0, 4000)]
    riff = [MidiNote(2, 2, 45 + index % 2, 80, index * 125, index * 125 + 100, 30)
            for index in range(32)]
    source = vocal + bass + riff
    names = {0: "Main Vocal", 1: "Bass", 2: "Rhythm Guitar"}
    settings = cover_settings(mode, max_polyphony=2, target_instrument="harmonica", max_hold_ms=4000)
    arranged = arrange_notes(source, settings, track_names=names)
    expected = vocal + (bass if mode == "cover_song" else riff)
    assert set(arranged.notes) == set(expected)
    baseline = build_playback_plan(source, replace(settings, fluid_phrasing=0),
                                   CURRENT_SCUM_PROFILE, track_names=names)
    flowing = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE, track_names=names)

    assert identities(flowing) == identities(baseline)
    assert Counter(n.source_pitch for n in flowing.planned_notes) == Counter(n.pitch for n in expected)
    assert peak_voices(flowing.planned_notes) <= 2
    assert_safe_events(flowing, settings)


@pytest.mark.parametrize("mode", ["cover_song", "cover_riff"])
@pytest.mark.parametrize("mapping", sorted(ENHANCED_MAPPING_MODES))
def test_restored_fluid_covers_keep_repeated_key_and_octave_events_safe_and_never_send_w(mode, mapping):
    source = [MidiNote(0, 0, pitch, 90, index * 250, index * 250 + 225)
              for index, pitch in enumerate((48, 48, 60, 60, 72, 72, 84, 84, 67, 55, 79, 60))]
    source += [MidiNote(1, 1, 43, 80, index * 250, index * 250 + 100) for index in range(12)]
    settings = cover_settings(mode, mapping_mode=mapping)
    plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE,
                               track_names={0: "Main Vocal", 1: "Rhythm Guitar"})

    assert plan.planned_notes
    assert plan.diagnostics["fluid_phrasing"] == 100
    assert all(n.mapped_pitch == n.base_pitch + 12 * n.modifier for n in plan.planned_notes)
    assert_safe_events(plan, settings)
