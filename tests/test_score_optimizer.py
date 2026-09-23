import math
import random
from pathlib import Path

from musical_scumme.config import CURRENT_SCUM_PROFILE, AppSettings
from musical_scumme.model import MidiNote, MidiProject, MidiTrack
from musical_scumme.planner import build_playback_plan
from musical_scumme.score_optimizer import analyse_notes, analyse_project, optimal_settings_for_notes


def test_linear_onset_affinity_matches_exhaustive_nearest_attack_search():
    from musical_scumme.score_optimizer import _onset_affinity

    randomizer = random.Random(330)
    for tolerance in (0.0, 12.0, 45.0, 45.000000001):
        for _ in range(20):
            left = [note(0, 60, randomizer.randrange(50) * 12.5, 1000) for _ in range(40)]
            right = [note(1, 64, randomizer.randrange(50) * 12.5 + tolerance, 1000) for _ in range(35)]
            a = {n.start_ms for n in left}
            b = {n.start_ms for n in right}
            expected = math.sqrt(
                (sum(any(abs(x - y) <= tolerance for y in b) for x in a) / len(a))
                * (sum(any(abs(y - x) <= tolerance for x in a) for y in b) / len(b))
            )
            assert _onset_affinity(left, right, tolerance) == expected
    assert _onset_affinity([], right) == 0.0


def note(track: int, pitch: int, start: float, end: float, *, channel: int = 0) -> MidiNote:
    return MidiNote(track, channel, pitch, 100, start, end)


def project_with_roles(tmp_path: Path) -> MidiProject:
    notes = [
        *[note(1, 67 + index % 3, index * 240, index * 240 + 180) for index in range(8)],
        *[
            note(2, pitch, onset, onset + 500)
            for onset in (0, 500, 1000, 1500)
            for pitch in (55, 60, 64)
        ],
        *[note(3, 40 + index % 2, index * 480, index * 480 + 400) for index in range(4)],
        *[note(4, 36, index * 120, index * 120 + 60, channel=9) for index in range(12)],
        *[note(5, 84, index * 80, index * 80 + 40) for index in range(10)],
    ]
    tracks = [
        MidiTrack(0, "Conductor", 0, None, None, 0),
        MidiTrack(1, "Lead Vocal", 8, 67, 69, 1860),
        MidiTrack(2, "Piano Chords", 12, 55, 64, 2000),
        MidiTrack(3, "Electric Bass", 4, 40, 41, 1840),
        MidiTrack(4, "Drums", 12, 36, 36, 1380, percussion_note_count=12),
        MidiTrack(5, "FX Noise", 10, 84, 84, 760),
    ]
    return MidiProject(tmp_path / "roles.mid", 480, tracks, notes, 2000, 120)


def test_import_analysis_selects_lead_bass_and_harmonic_support(tmp_path: Path):
    analysis = analyse_project(project_with_roles(tmp_path))

    assert analysis.recommended_track_indices == (1, 2, 3)
    assert "relationship-aware playable set" in analysis.rationale
    rejected = {track.name for track in analysis.tracks if track.rejected_as_noise}
    assert rejected == {"FX Noise"}
    assert "Drums" not in {track.name for track in analysis.tracks}


def test_import_analysis_recognises_prepared_transposer_tracks(tmp_path: Path):
    notes = [note(1, 64, 0, 200), note(2, 52, 0, 400)]
    project = MidiProject(
        tmp_path / "prepared.mid",
        480,
        [
            MidiTrack(0, "Conductor", 0, None, None, 0),
            MidiTrack(1, "Lead Melody", 1, 64, 64, 200),
            MidiTrack(2, "Light Support", 1, 52, 52, 400),
        ],
        notes,
        400,
        120,
    )

    analysis = analyse_project(project)

    assert analysis.recommended_track_indices == (1, 2)
    assert "prepared Lead Melody + Light Support" in analysis.rationale


def test_optimal_sound_policy_uses_pitch_match_for_a_single_melody():
    source = [note(1, 45 + index % 8, index * 220, index * 220 + 170) for index in range(16)]
    original = AppSettings(performance_preset="optimal", mapping_mode="strict", max_polyphony=8)

    optimal, analysis = optimal_settings_for_notes(source, original)

    assert analysis.texture == "melody"
    assert optimal.arrangement_mode == "melody"
    assert optimal.mapping_mode == "match3_adaptive"
    assert optimal.max_polyphony == 1
    assert optimal.chord_spread_ms == 0
    assert original.mapping_mode == "strict"
    assert original.max_polyphony == 8


def test_optimal_sound_policy_uses_each_instruments_sustain_ceiling():
    source = [note(1, 60 + index % 3, index * 4000, index * 4000 + 3000) for index in range(8)]

    expected = {"guitar": 2000, "harmonica": 4000, "banjo": 1000}
    for instrument, maximum_ms in expected.items():
        optimal, _analysis = optimal_settings_for_notes(
            source,
            AppSettings(performance_preset="optimal", target_instrument=instrument),
        )
        assert optimal.max_hold_ms == maximum_ms


def test_optimal_sound_policy_preserves_source_chords_without_generating_notes():
    source = [
        note(1, pitch, onset, onset + 420)
        for onset in (0, 500, 1000, 1500)
        for pitch in (48, 60, 64, 67)
    ]

    optimal, analysis = optimal_settings_for_notes(source, AppSettings())

    assert analysis.texture == "chordal"
    assert optimal.arrangement_mode == "chamber_director"
    assert optimal.chord_recognition_mode == "auto"
    assert optimal.mapping_mode == "smart3_harmonic"
    assert optimal.max_polyphony == 3
    assert optimal.chord_spread_ms == 12


def test_dense_source_receives_stricter_polyphony_and_density_limits():
    source = [
        note(1, 48 + voice * 4, onset, onset + 180)
        for onset in range(0, 800, 50)
        for voice in range(5)
    ]

    optimal, analysis = optimal_settings_for_notes(source, AppSettings())

    assert analysis.texture == "dense"
    assert analyse_notes(source).peak_starts_per_second > 24
    assert optimal.max_polyphony == 2
    assert optimal.max_notes_per_second == 16
    assert optimal.chord_spread_ms == 6


def test_analysis_separates_physical_note_load_from_musical_onset_rate():
    source = [
        note(1, pitch, onset, onset + 360)
        for onset in range(0, 2000, 250)
        for pitch in (48, 60, 64, 67)
    ]

    analysis = analyse_notes(source)

    assert analysis.peak_starts_per_second == 16
    assert analysis.peak_onsets_per_second == 4
    assert analysis.sounding_polyphony_p95 == 8
    assert analysis.overlap_ratio > 0.5
    assert analysis.phrase_count == 1


def test_semantic_track_names_use_tokens_instead_of_substrings(tmp_path: Path):
    notes = [note(1, 67 + index % 3, index * 300, index * 300 + 220) for index in range(8)]
    project = MidiProject(
        tmp_path / "slow.mid",
        480,
        [MidiTrack(1, "Slow Strings", len(notes), 67, 69, 2320)],
        notes,
        2320,
        120,
    )

    analysis = analyse_project(project)

    assert analysis.tracks[0].role != "Bass"


def test_two_lead_tracks_do_not_force_the_second_track_into_bass(tmp_path: Path):
    notes = [
        *[note(1, 72 + index % 3, index * 300, index * 300 + 220) for index in range(8)],
        *[note(2, 67 + index % 3, index * 300, index * 300 + 220) for index in range(8)],
    ]
    project = MidiProject(
        tmp_path / "two-leads.mid",
        480,
        [
            MidiTrack(1, "Lead Flute", 8, 72, 74, 2320),
            MidiTrack(2, "Solo Violin", 8, 67, 69, 2320),
        ],
        notes,
        2320,
        120,
    )

    analysis = analyse_project(project)

    assert len(analysis.recommended_track_indices) == 1
    assert all(track.role != "Bass" for track in analysis.tracks)


def test_relationship_analysis_rejects_an_exact_doubled_support_track(tmp_path: Path):
    lead = [note(1, 67 + index % 4, index * 300, index * 300 + 220) for index in range(8)]
    doubled = [note(2, item.pitch, item.start_ms, item.end_ms) for item in lead]
    project = MidiProject(
        tmp_path / "doubled.mid",
        480,
        [
            MidiTrack(1, "Lead Melody", 8, 67, 70, 2320),
            MidiTrack(2, "Piano Chords", 8, 67, 70, 2320),
        ],
        [*lead, *doubled],
        2320,
        120,
    )

    analysis = analyse_project(project)

    assert analysis.recommended_track_indices == (1,)


def test_import_analysis_keeps_a_sparse_sectional_solo_handoff(tmp_path: Path):
    lead = [
        note(1, 65 + index % 4, index * 250, index * 250 + 200)
        for index in (*range(8), *range(16, 24))
    ]
    solo = [
        note(2, 72 + index % 6, (8 + index) * 250, (8 + index) * 250 + 190)
        for index in range(8)
    ]
    bass = [note(3, 40 + index % 2, index * 500, index * 500 + 420) for index in range(12)]
    support = [
        note(4, pitch, onset, onset + 450)
        for onset in range(0, 6000, 500)
        for pitch in (55, 60, 64)
    ]
    project = MidiProject(
        tmp_path / "sectional-solo.mid",
        480,
        [
            MidiTrack(1, "Lead Vocal", len(lead), 65, 68, 5950),
            MidiTrack(2, "Electric Guitar Solo", len(solo), 72, 77, 3950),
            MidiTrack(3, "Electric Bass", len(bass), 40, 41, 5920),
            MidiTrack(4, "Piano Chords", len(support), 55, 64, 5950),
        ],
        [*lead, *solo, *bass, *support],
        6000,
        120,
    )

    analysis = analyse_project(project)

    assert analysis.recommended_track_indices == (1, 2, 3, 4)
    assert "solo handoff=Electric Guitar Solo" in analysis.rationale


def test_rolled_sustained_source_chords_trigger_chord_policy_and_alignment():
    source = [
        note(1, pitch, phrase + offset, phrase + 420)
        for phrase in (0, 500, 1000)
        for pitch, offset in ((60, 0), (64, 20), (67, 40))
    ]
    settings = AppSettings(performance_preset="custom", arrangement_mode="intelligent",
                           chord_recognition_mode="auto")

    plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)

    assert analyse_notes(source).texture == "chordal"
    assert plan.diagnostics["performed_chord_groups"] == 3
    assert plan.diagnostics["score_chord_groups"] == 3
    assert plan.retained_notes == len(source)
