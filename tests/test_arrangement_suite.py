"""Audition-oriented regressions for selecting an entire MIDI ensemble."""

from collections import Counter
from dataclasses import replace
from random import Random

import pytest

from musical_scumme.arrangement_options import ARRANGEMENT_OPTIONS, ARRANGEMENT_RECIPES
from musical_scumme.arranger import arrange_notes
from musical_scumme.config import CURRENT_SCUM_PROFILE, AppSettings
from musical_scumme.model import MidiNote
from musical_scumme.planner import build_playback_plan

VOCAL_RECIPES = [mode for mode, recipe in ARRANGEMENT_RECIPES.items() if recipe.lead == "vocal"]


def layered_ensemble(track_count):
    """An audible low vocal against progressively more high, loud accompaniment."""
    names = {0: "Lead Vocal"}
    source = []
    melody = (65, 67, 69, 67, 65, 63, 65, 70)
    support = (43, 50, 56, 60, 72, 76, 79, 83, 87, 90, 94, 97, 101, 104, 108)
    for index, pitch in enumerate(melody):
        source.append(MidiNote(0, 0, pitch, 76, index * 500, index * 500 + 280))
        for track in range(1, track_count):
            names[track] = "Bass" if track == 1 else f"Accompaniment {track}"
            source.append(MidiNote(track, 1, support[track - 1], 110, index * 500, index * 500 + 320))
        source.append(MidiNote(99, 9, 36, 127, index * 500, index * 500 + 100))
    return source, names


def audition_settings(mode, **overrides):
    return replace(
        AppSettings(
            performance_preset="custom",
            arrangement_mode=mode,
            chord_recognition_mode="exact",
            max_polyphony=8,
            min_source_note_ms=0,
            min_retrigger_ms=0,
            max_notes_per_second=240,
        ),
        **overrides,
    )


@pytest.mark.parametrize("mode", ARRANGEMENT_OPTIONS)
@pytest.mark.parametrize("track_count", [1, 2, 4, 8, 16])
def test_all_tracks_selected_preserves_source_and_is_order_independent(mode, track_count):
    source, names = layered_ensemble(track_count)
    source_before = tuple(source)
    result = arrange_notes(source, audition_settings(mode), track_names=names)
    shuffled = list(source)
    Random(921 + track_count).shuffle(shuffled)

    assert result == arrange_notes(shuffled, audition_settings(mode), track_names=names)
    assert tuple(source) == source_before
    assert result.notes
    assert set(result.notes) <= set(source)
    assert all(note.channel != 9 for note in result.notes)
    assert result.dropped_percussion == 8
    assert result.source_notes == len(source)
    assert result.chord_notes_aligned == 0
    if mode != "faithful":
        assert max(Counter(note.start_ms for note in result.notes).values()) <= 8


@pytest.mark.parametrize("mode", ARRANGEMENT_OPTIONS)
def test_every_arrangement_handles_unnamed_single_track_material(mode):
    source = [MidiNote(5, 0, pitch, 90, index * 500, index * 500 + 300)
              for index, pitch in enumerate((60, 64, 62, 67, 69, 65, 64, 60))]
    result = arrange_notes(source, audition_settings(mode))
    assert result.notes == tuple(source)
    assert result.melody_track == 5


@pytest.mark.parametrize("mode", [mode for mode in ARRANGEMENT_OPTIONS if mode != "faithful"])
def test_every_intelligent_style_respects_user_one_note_limit(mode):
    source, names = layered_ensemble(16)
    result = arrange_notes(source, audition_settings(mode, max_polyphony=1), track_names=names)
    assert len(result.notes) == 8
    assert len({note.start_ms for note in result.notes}) == 8


@pytest.mark.parametrize("mode", [mode for mode in ARRANGEMENT_OPTIONS if mode != "faithful"])
def test_style_filters_percussion_and_source_noise_before_selection(mode):
    melody = [MidiNote(0, 0, 65 + index, 80, index * 500, index * 500 + 300) for index in range(4)]
    percussion = [MidiNote(1, 9, 36, 127, index * 500, index * 500 + 100) for index in range(4)]
    noise = [MidiNote(2, 1, 110, 127, index * 500 + 100, index * 500 + 105) for index in range(4)]
    result = arrange_notes(
        melody + percussion + noise,
        audition_settings(mode, min_source_note_ms=35),
        track_names={0: "Lead Vocal", 2: "Noise"},
    )
    assert set(result.notes) == set(melody)
    assert result.dropped_percussion == 4
    assert result.dropped_short == 4


@pytest.mark.parametrize("mode", ARRANGEMENT_RECIPES)
@pytest.mark.parametrize("user_limit", [1, 2, 3, 8])
def test_recipe_and_user_layer_ceilings_both_apply(mode, user_limit):
    source, names = layered_ensemble(16)
    result = arrange_notes(source, audition_settings(mode, max_polyphony=user_limit), track_names=names)
    maximum = min(user_limit, ARRANGEMENT_RECIPES[mode].layers)
    assert result.notes
    assert max(Counter(note.start_ms for note in result.notes).values()) <= maximum


@pytest.mark.parametrize("mode", VOCAL_RECIPES)
def test_vocal_recipes_keep_every_vocal_attack_among_sixteen_selected_tracks(mode):
    source, names = layered_ensemble(16)
    result = arrange_notes(source, audition_settings(mode), track_names=names)
    assert {note for note in source if note.track_index == 0} <= set(result.notes)
    assert result.melody_track == 0


@pytest.mark.parametrize("mode", VOCAL_RECIPES)
def test_lead_vocal_beats_earlier_louder_backing_vocal(mode):
    source = [
        MidiNote(track, 0, pitch, velocity, onset, onset + 300)
        for onset in range(0, 2000, 500)
        for track, pitch, velocity in [(0, 81, 120), (5, 65, 75), (9, 43, 90)]
    ]
    names = {0: "Backing Vocals Choir", 5: "Main Lead Vocal", 9: "Bass"}
    result = arrange_notes(source, audition_settings(mode, max_polyphony=1), track_names=names)
    assert result.melody_track == 5
    assert {note.track_index for note in result.notes} == {5}


@pytest.mark.parametrize("mode", VOCAL_RECIPES)
def test_vocal_sustain_reserves_a_layer_between_vocal_attacks(mode):
    vocal = MidiNote(0, 0, 65, 80, 0, 1800)
    source = [vocal] + [
        MidiNote(track, 1, pitch, 110, onset, onset + 180)
        for onset in [250, 500, 750, 1000, 1250, 1500]
        for track, pitch in [(1, 43), (2, 55), (3, 84)]
    ]
    result = arrange_notes(
        source, audition_settings(mode),
        track_names={0: "Lead Vocal", 1: "Bass", 2: "Piano", 3: "Lead Synth"},
    )
    assert vocal in result.notes
    intermediate = [note for note in result.notes if note.start_ms > 0]
    if ARRANGEMENT_RECIPES[mode].layers == 1:
        assert not intermediate
    else:
        assert intermediate
        assert max(Counter(note.start_ms for note in intermediate).values()) < ARRANGEMENT_RECIPES[mode].layers


def test_spotlight_fills_actual_vocal_rests_and_returns_to_the_singer():
    intro = MidiNote(1, 1, 76, 110, 0, 300)
    vocal_a = MidiNote(0, 0, 65, 75, 500, 1500)
    distraction = MidiNote(1, 1, 84, 127, 1000, 1250)
    bridge = MidiNote(1, 1, 79, 110, 1750, 1950)
    vocal_b = MidiNote(0, 0, 67, 75, 2000, 2500)
    result = arrange_notes(
        [intro, vocal_a, distraction, bridge, vocal_b], audition_settings("vocal_spotlight"),
        track_names={0: "Lead Vocal", 1: "Guitar Solo"},
    )
    assert set(result.notes) == {intro, vocal_a, bridge, vocal_b}


def test_manual_lead_override_identifies_unnamed_vocal_with_every_track_selected():
    source, names = layered_ensemble(8)
    names[0] = "Track 1"
    names[7] = "Lead Vocal"
    result = arrange_notes(
        source, audition_settings("vocal_spotlight", arrangement_lead_track=0), track_names=names,
    )
    assert result.melody_track == 0
    assert set(result.notes) == {note for note in source if note.track_index == 0}


def test_missing_lead_override_falls_back_to_existing_source():
    source, names = layered_ensemble(4)
    result = arrange_notes(
        source, audition_settings("vocal_spotlight", arrangement_lead_track=999), track_names=names,
    )
    assert result.notes
    assert result.melody_track == 0
    assert set(result.notes) <= set(source)


def test_ballad_and_dance_choose_different_existing_support_textures():
    vocal = MidiNote(0, 0, 72, 80, 0, 1000)
    bass = MidiNote(1, 1, 36, 90, 0, 800)
    warm = MidiNote(2, 1, 64, 76, 0, 1200)
    pulse = MidiNote(3, 1, 67, 115, 0, 120)
    source = [vocal, bass, warm, pulse]
    names = {0: "Lead Vocal", 1: "Bass", 2: "Strings", 3: "Synth"}
    ballad = arrange_notes(source, audition_settings("vocal_ballad"), track_names=names)
    dance = arrange_notes(source, audition_settings("vocal_pulse"), track_names=names)
    assert set(ballad.notes) == {vocal, bass, warm}
    assert set(dance.notes) == {vocal, bass, pulse}


def test_choir_prefers_named_backing_harmony_over_louder_instrument():
    vocal = MidiNote(0, 0, 72, 80, 0, 800)
    backing = MidiNote(1, 1, 69, 70, 0, 800)
    synth = MidiNote(2, 1, 68, 127, 0, 800)
    result = arrange_notes(
        [vocal, backing, synth], audition_settings("vocal_choir", max_polyphony=2),
        track_names={0: "Main Lead Vocal", 1: "Backing Vocal", 2: "Synth"},
    )
    assert set(result.notes) == {vocal, backing}


def test_vocal_foundation_leaves_absent_lower_voice_empty():
    vocal = MidiNote(0, 0, 65, 80, 0, 800)
    high_support = MidiNote(1, 1, 84, 127, 0, 800)
    result = arrange_notes(
        [vocal, high_support], audition_settings("vocal_foundation"),
        track_names={0: "Lead Vocal", 1: "Strings"},
    )
    assert result.notes == (vocal,)


@pytest.mark.parametrize("mode", ["vocal_spotlight", "vocal_ballad", "vocal_wall", "ensemble_max"])
@pytest.mark.parametrize("mapping", ["fold_smart", "melody3_contour", "smart3_harmonic"])
def test_recipe_plans_finish_released_with_standalone_octave_taps(mode, mapping):
    source, names = layered_ensemble(8)
    settings = audition_settings(mode, mapping_mode=mapping, chord_spread_ms=12)
    plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE, track_names=names)
    assert plan.retained_notes > 0
    assert {note.source_pitch for note in plan.planned_notes} <= {note.pitch for note in source}
    active = set()
    octave_keys = {CURRENT_SCUM_PROFILE.octave_down, CURRENT_SCUM_PROFILE.octave_up}
    for event in plan.events:
        if event.action == "down":
            assert event.key not in active
            if event.key in octave_keys:
                assert not active
            else:
                assert not active.intersection(octave_keys)
            active.add(event.key)
        else:
            assert event.key in active
            active.remove(event.key)
    assert not active
