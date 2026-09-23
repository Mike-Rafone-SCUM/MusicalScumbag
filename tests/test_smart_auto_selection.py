"""Source-selection regressions for vocal-first, whole-ensemble auditions."""

from dataclasses import replace
from pathlib import Path
from random import Random

import pytest

from musical_scumme.config import AppSettings
from musical_scumme.model import MidiNote, MidiProject, MidiTrack
from musical_scumme.score_optimizer import _temporal_overlap, analyse_project


def line(track, pitches, *, gap=500, duration=350, start=0, channel=0, velocity=90):
    return [
        MidiNote(track, channel, pitch, velocity, start + index * gap, start + index * gap + duration)
        for index, pitch in enumerate(pitches)
    ]


def source_project(parts):
    """Build consistent summaries from actual source notes, including mixed MIDI channels."""
    tracks = []
    source = []
    for index, name, notes in parts:
        source.extend(notes)
        tracks.append(
            MidiTrack(
                index,
                name,
                len(notes),
                min((note.pitch for note in notes), default=None),
                max((note.pitch for note in notes), default=None),
                max((note.end_ms for note in notes), default=0),
                percussion_note_count=sum(note.channel == 9 for note in notes),
            )
        )
    return MidiProject(
        Path("smart-auto-selection.mid"), 480, tracks, source,
        max((note.end_ms for note in source), default=0), 120,
    )


def settings(mode, **overrides):
    return replace(
        AppSettings(performance_preset="custom", arrangement_mode=mode, max_polyphony=8),
        **overrides,
    )


def ensemble():
    """Eight concurrent musical sources; none is an exact or octave-doubled part."""
    return source_project([
        (1, "Lead Vocal", line(1, [65, 67, 69, 67, 65, 64, 62, 65])),
        (2, "Bass", line(2, [40, 40, 43, 43, 45, 45, 38, 38])),
        (3, "Piano Chords", line(3, [52, 55, 52, 55, 57, 57, 54, 55])),
        (4, "Warm Pad", line(4, [59, 59, 57, 57, 60, 60, 57, 57], duration=470)),
        (5, "Organ Harmony", line(5, [60, 64, 64, 60, 65, 64, 60, 64])),
        (6, "String Support", line(6, [55, 57, 55, 55, 59, 57, 59, 57], duration=450)),
        (7, "Accompaniment Keys", line(7, [71, 69, 71, 69, 67, 67, 69, 71])),
        (8, "Rhythm Support", line(8, [48, 48, 50, 48, 52, 50, 48, 50], duration=220)),
    ])


@pytest.mark.parametrize("vocal_name", [
    "Lead Vocal", "Main Vox", "Main Voice", "Main Singer", "Main Lyrics", "Lead Tenor",
])
def test_main_vocal_aliases_beat_busier_guitar_and_backing_vocals(vocal_name):
    project = source_project([
        (1, "Lead Guitar", line(1, [70 + index % 3 for index in range(60)], gap=150, duration=140)),
        (2, "Backing Vocals", line(2, [67 + index % 2 for index in range(30)], gap=300, duration=280)),
        (3, vocal_name, line(3, [57, 60, 62, 60, 57, 55], gap=1400, duration=950, velocity=55)),
        (4, "Bass", line(4, [40, 43, 45, 43, 40, 38], gap=1400, duration=1000)),
    ])

    result = analyse_project(project)

    assert result.lead_track_index == 3
    assert 3 in result.recommended_track_indices


def test_manual_suite_lead_is_kept_even_when_a_different_track_is_named_vocal():
    project = ensemble()
    options = settings("vocal_spotlight", arrangement_lead_track=7)
    before = replace(options)

    result = analyse_project(project, settings=options)

    assert result.lead_track_index == 7
    assert result.recommended_track_indices == (7,)
    assert options == before


@pytest.mark.parametrize("stale_index", [-1, 999])
def test_missing_manual_lead_falls_back_to_a_populated_vocal(stale_index):
    result = analyse_project(
        ensemble(), settings=settings("vocal_spotlight", arrangement_lead_track=stale_index),
    )

    assert result.lead_track_index == 1
    assert result.recommended_track_indices == (1,)


@pytest.mark.parametrize(("mode", "expected_count"), [
    ("vocal_spotlight", 1),
    ("vocal_foundation", 2),
    ("melody_bass", 2),
    ("vocal_ballad", 3),
    ("vocal_cinematic", 4),
    ("vocal_wall", 5),
    ("ensemble_max", 6),
])
def test_auto_sources_scale_with_recipe_layers_when_sources_are_complementary(mode, expected_count):
    result = analyse_project(ensemble(), settings=settings(mode))

    assert result.lead_track_index == 1
    assert len(result.recommended_track_indices) == expected_count
    assert 1 in result.recommended_track_indices
    if expected_count > 1:
        assert 2 in result.recommended_track_indices


@pytest.mark.parametrize("maximum", [1, 2, 3])
def test_lower_output_polyphony_preserves_recipe_source_choices_and_user_settings(maximum):
    project = ensemble()
    options = settings("ensemble_max", max_polyphony=maximum)
    original = replace(options)
    full = analyse_project(project, settings=settings("ensemble_max"))
    result = analyse_project(project, settings=options)

    # Source tracks provide alternatives; the arranger enforces the note ceiling.
    assert result.recommended_track_indices == full.recommended_track_indices
    assert result.lead_track_index == 1
    assert options == original


def test_spotlight_keeps_a_real_instrumental_section_between_vocal_phrases():
    vocal = [*line(1, [65, 67, 69, 67], gap=400), *line(1, [65, 64, 62, 65], start=4000, gap=400)]
    solo = line(2, [72, 74, 76, 77, 76, 74, 72, 71], start=1800, gap=250, duration=190)
    project = source_project([
        (1, "Lead Vocal", vocal),
        (2, "Guitar Solo", solo),
        (3, "Bass", line(3, [40, 43, 40, 43, 40, 43, 40, 43], gap=700)),
    ])

    result = analyse_project(project, settings=settings("vocal_spotlight"))

    assert result.lead_track_index == 1
    assert result.recommended_track_indices == (1, 2)


def test_offbeat_instrument_under_held_vocals_is_not_a_sectional_handoff():
    project = source_project([
        (1, "Lead Vocal", line(1, [65, 67, 65], gap=2400, duration=2300)),
        (2, "Synth Lead", line(2, [72 + index % 4 for index in range(28)], start=125, gap=250, duration=100)),
    ])

    result = analyse_project(project, settings=settings("vocal_spotlight"))

    assert result.lead_track_index == 1
    assert result.recommended_track_indices == (1,)


def test_alternating_parts_do_not_overlap_despite_shared_song_sections():
    left = line(1, [65] * 8, gap=500, duration=250)
    right = line(2, [52] * 8, gap=500, duration=250, start=250)

    assert _temporal_overlap(left, right) == 0.0
    assert _temporal_overlap(right, left) == 0.0


def test_sounding_overlap_merges_chords_without_counting_their_duration_twice():
    left = [MidiNote(1, 0, 60, 90, 0, 300), MidiNote(1, 0, 64, 90, 0, 200)]
    right = [MidiNote(2, 0, 52, 90, 150, 450)]

    assert _temporal_overlap(left, right) == pytest.approx(0.5)
    assert _temporal_overlap(right, left) == pytest.approx(0.5)
    assert _temporal_overlap([], right) == 0.0


@pytest.mark.parametrize("octaves", [0, 1, -1])
def test_duplicate_support_is_rejected_against_every_selected_track(octaves):
    vocal = line(1, [65, 67, 69, 67, 65, 64, 62, 65])
    bass = line(2, [40, 40, 43, 43, 45, 45, 38, 38])
    support = [note for pitch in (52, 55, 60) for note in line(3, [pitch] * 8)]
    doubled = [replace(note, track_index=4, pitch=note.pitch + 12 * octaves) for note in support]
    project = source_project([
        (1, "Lead Vocal", vocal),
        (2, "Bass", bass),
        (3, "Piano Chords", support),
        (4, "Organ Chords", doubled),
    ])

    result = analyse_project(project, settings=settings("ensemble_max"))

    assert {1, 2} <= set(result.recommended_track_indices)
    assert len({3, 4} & set(result.recommended_track_indices)) == 1


def test_parallel_harmony_is_not_mistaken_for_an_octave_double():
    melody = line(1, [65, 67, 69, 67, 65, 64, 62, 65])
    harmony = [replace(note, track_index=2, pitch=note.pitch - 4) for note in melody]
    project = source_project([(1, "Lead Vocal", melody), (2, "Piano Harmony", harmony)])

    result = analyse_project(project, settings=settings("vocal_ballad"))

    assert result.recommended_track_indices == (1, 2)


def test_noise_only_source_does_not_reselect_rejected_effect_tracks():
    project = source_project([
        (1, "FX Noise", line(1, [100] * 10, gap=90, duration=20)),
        (2, "Metronome", line(2, [84] * 10, gap=500, duration=20)),
        (3, "Drums", line(3, [36] * 10, channel=9)),
    ])

    result = analyse_project(project)

    assert result.recommended_track_indices == ()
    assert result.lead_track_index is None
    assert result.selected_notes.note_count == 0


def test_mixed_channel_musical_track_remains_available_but_drum_track_is_excluded():
    project = source_project([
        (1, "Main Vox", [*line(1, [65, 67, 69, 67]), *line(1, [36] * 4, channel=9)]),
        (2, "Drums", line(2, [36] * 8, channel=9)),
    ])

    result = analyse_project(project)

    assert result.recommended_track_indices == (1,)
    assert result.selected_notes.note_count == 4


def test_ordinary_lead_melody_name_does_not_hide_bass_and_support():
    project = source_project([
        (1, "Lead Melody", line(1, [65, 67, 69, 67, 65, 64, 62, 65])),
        (2, "Bass", line(2, [40, 40, 43, 43, 45, 45, 38, 38])),
        (3, "Piano Chords", [note for pitch in (52, 55, 60) for note in line(3, [pitch] * 8)]),
    ])

    result = analyse_project(project)

    assert result.recommended_track_indices == (1, 2, 3)


def test_known_prepared_transposer_pair_retains_both_tracks_without_settings():
    project = source_project([
        (1, "Lead Melody", line(1, [65, 67, 69, 67])),
        (2, "Light Support", line(2, [52, 55, 57, 55])),
    ])

    result = analyse_project(project)

    assert result.recommended_track_indices == (1, 2)


def test_selection_is_deterministic_and_does_not_modify_source_or_settings():
    project = ensemble()
    original_notes = tuple(project.notes)
    original_tracks = tuple(project.tracks)
    options = settings("ensemble_max")
    original_options = replace(options)

    result = analyse_project(project, settings=options)
    shuffled_notes = list(project.notes)
    shuffled_tracks = list(project.tracks)
    randomizer = Random(910)
    randomizer.shuffle(shuffled_notes)
    randomizer.shuffle(shuffled_tracks)
    shuffled = replace(project, notes=shuffled_notes, tracks=shuffled_tracks)
    repeated = analyse_project(shuffled, settings=options)

    assert result.recommended_track_indices == repeated.recommended_track_indices
    assert result.lead_track_index == repeated.lead_track_index
    assert tuple(project.notes) == original_notes
    assert tuple(project.tracks) == original_tracks
    assert options == original_options
    assert result.selection_reasons
