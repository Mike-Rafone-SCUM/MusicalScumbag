import random

from musical_scumme.arranger import (
    AUTO_CHORD_MIN_SHARED_MS,
    _automatic_chord_window,
    _group_onsets,
    arrange_notes,
    recognised_score_onsets,
)
from musical_scumme.config import AppSettings
from musical_scumme.model import MidiNote


def note(pitch: int, start: float = 0.0, end: float = 400.0, velocity: int = 90, channel: int = 0, track: int = 0) -> MidiNote:
    return MidiNote(track, channel, pitch, velocity, start, end)


def test_intelligent_arrangement_preserves_top_voice_and_bass():
    settings = AppSettings(arrangement_mode="intelligent", max_polyphony=2, min_source_note_ms=0)
    result = arrange_notes(
        [note(60, velocity=30), note(64, velocity=120), note(67, velocity=50), note(72, velocity=80)],
        settings,
    )
    assert {item.pitch for item in result.notes} == {60, 72}


def test_auto_chord_recognition_aligns_only_source_backed_performed_chords():
    source = []
    for attack in (0.0, 500.0, 1000.0):
        source.extend(
            [
                note(60, start=attack, end=attack + 360),
                note(64, start=attack + 25, end=attack + 385),
                note(67, start=attack + 40, end=attack + 400),
            ]
        )
    settings = AppSettings(
        arrangement_mode="intelligent",
        chord_recognition_mode="auto",
        max_polyphony=3,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_notes_per_second=60,
        onset_group_ms=12,
    )

    result = arrange_notes(source, settings)

    assert [item.start_ms for item in result.notes] == [0.0] * 3 + [500.0] * 3 + [1000.0] * 3
    assert result.chord_groups == 3
    assert result.performed_chord_groups == 3
    assert result.chord_notes_aligned == 6
    assert result.chord_alignment_ms == 195.0
    assert result.chord_detection_window_ms == 45.0
    assert {item.pitch for item in result.notes} == {60, 64, 67}


def test_exact_chord_mode_preserves_performed_attack_offsets():
    source = [
        note(60, start=0, end=300),
        note(64, start=25, end=325),
        note(67, start=40, end=340),
    ]
    result = arrange_notes(
        source,
        AppSettings(
            arrangement_mode="intelligent",
            chord_recognition_mode="exact",
            max_polyphony=3,
            min_source_note_ms=0,
            min_retrigger_ms=0,
            max_notes_per_second=60,
            onset_group_ms=12,
        ),
    )

    assert [item.start_ms for item in result.notes] == [0, 25, 40]
    assert result.performed_chord_groups == 0
    assert result.chord_notes_aligned == 0


def test_auto_chord_recognition_does_not_collapse_a_fast_run():
    source = [note(60 + index, start=index * 20, end=index * 20 + 140) for index in range(12)]
    result = arrange_notes(
        source,
        AppSettings(
            arrangement_mode="intelligent",
            chord_recognition_mode="auto",
            max_polyphony=3,
            min_source_note_ms=0,
            min_retrigger_ms=0,
            max_notes_per_second=60,
            onset_group_ms=12,
        ),
    )

    assert [item.start_ms for item in result.notes] == [index * 20 for index in range(12)]
    assert result.chord_detection_window_ms == 12.0
    assert result.performed_chord_groups == 0


def _legacy_recognised_score_onsets(notes: list[MidiNote], base_tolerance_ms: int = 12):
    ordered = sorted(notes, key=lambda item: (item.start_ms, item.pitch, item.end_ms))
    window_ms = _automatic_chord_window(ordered, base_tolerance_ms)
    if window_ms <= base_tolerance_ms or not ordered:
        return _group_onsets(ordered, base_tolerance_ms), window_ms

    def looks_like_sustained_chord(group: list[MidiNote]) -> bool:
        if len(group) < 2:
            return False
        starts = [item.start_ms for item in group]
        if max(starts) - min(starts) <= base_tolerance_ms:
            return True
        if len({item.pitch % 12 for item in group}) < 2:
            return False
        shared_sustain = min(item.end_ms for item in group) - max(starts)
        shortest_duration = min(item.duration_ms for item in group)
        required_shared = min(90.0, max(AUTO_CHORD_MIN_SHARED_MS, shortest_duration * 0.35))
        return shared_sustain >= required_shared

    groups: list[list[MidiNote]] = []
    index = 0
    while index < len(ordered):
        anchor = ordered[index].start_ms
        candidates = [ordered[index]]
        cursor = index + 1
        while cursor < len(ordered) and ordered[cursor].start_ms - anchor <= window_ms:
            candidates.append(ordered[cursor])
            cursor += 1
        base_count = 1
        while (
            base_count < len(candidates)
            and candidates[base_count].start_ms - anchor <= base_tolerance_ms
        ):
            base_count += 1
        chosen_count = base_count
        for candidate_count in range(base_count + 1, len(candidates) + 1):
            if looks_like_sustained_chord(candidates[:candidate_count]):
                chosen_count = candidate_count
        groups.append(candidates[:chosen_count])
        index += chosen_count
    return groups, window_ms


def test_incremental_chord_recognition_is_output_equivalent_to_legacy_prefix_scans():
    generator = random.Random(2102)
    for _case in range(120):
        source: list[MidiNote] = []
        start = 0.0
        for _index in range(generator.randint(8, 80)):
            start += generator.choice((0.0, 4.0, 9.0, 13.0, 20.0, 48.0, 120.0))
            duration = generator.choice((20.0, 35.0, 80.0, 140.0, 360.0))
            source.append(
                note(
                    generator.randint(36, 96),
                    start=start,
                    end=start + duration,
                    velocity=generator.randint(1, 127),
                )
            )

        expected_groups, expected_window = _legacy_recognised_score_onsets(source)
        actual_groups, actual_window = recognised_score_onsets(source)

        assert actual_window == expected_window
        assert actual_groups == expected_groups


def test_melody_mode_keeps_one_lead_note_per_onset_regardless_of_polyphony():
    settings = AppSettings(arrangement_mode="melody", max_polyphony=4, min_source_note_ms=0)
    result = arrange_notes(
        [
            note(60, start=0, end=300, velocity=100),
            note(72, start=0, end=300, velocity=90),
            note(62, start=500, end=800, velocity=100),
            note(74, start=500, end=800, velocity=90),
        ],
        settings,
    )
    assert [item.pitch for item in result.notes] == [72, 74]


def test_percussion_and_short_noise_are_reported():
    settings = AppSettings(ignore_percussion=True, min_source_note_ms=50)
    result = arrange_notes(
        [note(36, channel=9), note(60, end=20), note(64, end=200)],
        settings,
    )
    assert [item.pitch for item in result.notes] == [64]
    assert result.dropped_percussion == 1
    assert result.dropped_short == 1


def test_faithful_mode_does_not_apply_density_or_retrigger_reduction():
    settings = AppSettings(
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=500,
        max_notes_per_second=4,
    )
    source = [note(60 + index % 5, start=index * 20, end=index * 20 + 100) for index in range(12)]
    result = arrange_notes(source, settings)
    assert len(result.notes) == len(source)
    assert result.dropped_density == 0
    assert result.dropped_retrigger == 0


def test_melody_mode_stays_on_inferred_lead_track():
    notes: list[MidiNote] = []
    for index in range(12):
        start = index * 300.0
        notes.append(MidiNote(1, 0, 55 + index % 4, 88, start, start + 220.0))
        if index in {1, 5, 9}:
            notes.append(MidiNote(2, 0, 43, 94, start, start + 1500.0))

    result = arrange_notes(
        notes,
        AppSettings(arrangement_mode="melody", min_source_note_ms=0, max_polyphony=1),
    )

    assert result.melody_track == 1
    assert {item.track_index for item in result.notes} == {1}


def test_retrigger_filter_replaces_weaker_earlier_note_without_changing_order():
    result = arrange_notes(
        [
            note(60, start=0, end=180, velocity=30),
            note(60, start=20, end=200, velocity=120),
            note(64, start=200, end=380, velocity=90),
        ],
        AppSettings(
            arrangement_mode="intelligent",
            max_polyphony=1,
            min_source_note_ms=0,
            min_retrigger_ms=50,
            max_notes_per_second=60,
            onset_group_ms=1,
        ),
    )

    assert [(item.pitch, item.start_ms) for item in result.notes] == [(60, 20), (64, 200)]
    assert result.dropped_retrigger == 1


def test_density_limit_replaces_support_in_constant_time_and_protects_melody():
    result = arrange_notes(
        [
            note(60, start=0, end=180, velocity=60),
            note(72, start=0, end=180, velocity=100),
            note(62, start=100, end=280, velocity=60),
            note(74, start=100, end=280, velocity=100),
            note(64, start=200, end=380, velocity=60),
            note(76, start=200, end=380, velocity=100),
        ],
        AppSettings(
            arrangement_mode="intelligent",
            max_polyphony=2,
            min_source_note_ms=0,
            min_retrigger_ms=0,
            max_notes_per_second=4,
            onset_group_ms=1,
        ),
    )

    assert {72, 74, 76}.issubset(item.pitch for item in result.notes)
    assert len(result.notes) == 4
    assert result.dropped_density == 2


def test_whole_phrase_voice_tracing_rejects_loud_register_spikes():
    source: list[MidiNote] = []
    for index, melody_pitch in enumerate((60, 62, 64, 65, 67, 69)):
        start = index * 260.0
        source.append(note(melody_pitch, start=start, end=start + 220, velocity=86, track=1))
        spike_pitch = 86 if index % 2 == 0 else 45
        source.append(note(spike_pitch, start=start, end=start + 70, velocity=122, track=2))

    result = arrange_notes(
        source,
        AppSettings(
            arrangement_mode="intelligent",
            max_polyphony=1,
            min_source_note_ms=0,
            min_retrigger_ms=0,
            max_notes_per_second=60,
        ),
        track_names={1: "Lead Melody", 2: "FX Hits"},
    )

    assert [item.pitch for item in result.notes] == [60, 62, 64, 65, 67, 69]
    assert result.melody_track_switches == 0
    assert result.melody_large_leaps == 0


def test_phrase_boundary_allows_a_real_register_reset():
    source = [
        note(60, start=0, end=240),
        note(62, start=300, end=540),
        note(84, start=2200, end=2440),
        note(86, start=2500, end=2740),
    ]

    result = arrange_notes(
        source,
        AppSettings(
            arrangement_mode="intelligent",
            max_polyphony=1,
            min_source_note_ms=0,
            min_retrigger_ms=0,
            max_notes_per_second=60,
        ),
    )

    assert [item.pitch for item in result.notes] == [60, 62, 84, 86]
    assert result.melody_phrase_count == 2
    assert result.melody_large_leaps == 1


def test_intelligent_chord_reduction_never_creates_a_pitch():
    source = [
        note(pitch, start=onset, end=onset + 420, track=track)
        for onset in (0.0, 500.0, 1000.0)
        for track, pitch in ((1, 48), (2, 60), (2, 64), (2, 67), (3, 74))
    ]
    result = arrange_notes(
        source,
        AppSettings(
            arrangement_mode="intelligent",
            max_polyphony=3,
            min_source_note_ms=0,
            min_retrigger_ms=0,
            max_notes_per_second=60,
        ),
    )

    source_signature = {(item.track_index, item.pitch, item.start_ms, item.end_ms) for item in source}
    assert all(
        (item.track_index, item.pitch, item.start_ms, item.end_ms) in source_signature
        for item in result.notes
    )


def test_dynamic_solo_director_hands_lead_over_without_requiring_silence():
    source: list[MidiNote] = []
    solo_pitches = (72, 74, 76, 77, 79, 81, 79, 76)
    for index in range(20):
        start = index * 250.0
        source.append(note(64 + index % 3, start=start, end=start + 210, velocity=78, track=1))
        source.append(note(40 + index % 2, start=start, end=start + 230, velocity=82, track=3))
        source.append(note(57, start=start, end=start + 420, velocity=66, track=4))
        if 6 <= index < 14:
            source.append(
                note(
                    solo_pitches[index - 6],
                    start=start,
                    end=start + 190,
                    velocity=116,
                    track=2,
                )
            )

    result = arrange_notes(
        source,
        AppSettings(
            arrangement_mode="intelligent",
            chord_recognition_mode="auto",
            max_polyphony=3,
            min_source_note_ms=0,
            min_retrigger_ms=0,
            max_notes_per_second=60,
        ),
        track_names={1: "Lead Vocal", 2: "Electric Guitar Solo", 3: "Bass", 4: "Pad"},
    )

    assert result.melody_track == 1
    assert len(result.solo_segments) == 1
    assert result.solo_segments[0].track_index == 2
    assert result.solo_segments[0].onset_count == len(solo_pitches)
    assert [item.pitch for item in result.notes if item.track_index == 2] == list(solo_pitches)
    for index in range(6, 14):
        at_ms = index * 250.0
        sounding = [item for item in result.notes if item.start_ms == at_ms]
        assert len(sounding) <= 2
        assert any(item.track_index == 2 for item in sounding)
        assert all(item.pitch <= solo_pitches[index - 6] for item in sounding)
    assert result.solo_accompaniment_dropped >= 8


def test_sparse_primary_lead_is_still_directed_as_a_solo_section():
    source: list[MidiNote] = []
    for index in range(20):
        start = index * 300.0
        source.extend(
            [
                note(48, start=start, end=start + 520, velocity=72, track=2),
                note(55, start=start, end=start + 520, velocity=68, track=2),
                note(60, start=start, end=start + 520, velocity=66, track=2),
            ]
        )
        if 6 <= index < 14:
            source.append(
                note(74 + (index - 6) % 5, start=start, end=start + 220, velocity=118, track=1)
            )

    result = arrange_notes(
        source,
        AppSettings(
            arrangement_mode="intelligent",
            max_polyphony=3,
            min_source_note_ms=0,
            min_retrigger_ms=0,
            max_notes_per_second=60,
        ),
        track_names={1: "Electric Guitar", 2: "Rhythm Chords"},
    )

    assert result.melody_track == 1
    assert len(result.solo_segments) == 1
    assert result.solo_segments[0].track_index == 1
    assert result.solo_segments[0].onset_count == 8
    assert result.solo_notes == 8


def test_fast_solo_density_reduction_preserves_endpoints_and_contour_apex():
    source: list[MidiNote] = []
    for index in range(24):
        start = index * 180.0
        if not 10 <= index < 16:
            source.append(note(62 + index % 3, start=start, end=start + 150, track=1))
    run_pitches = [60 + min(index, 15) for index in range(16)] + [74 - index for index in range(15)]
    for index, pitch in enumerate(run_pitches):
        start = 1800.0 + index * 33.0
        velocity = 127 if index == 15 else (112 if index == len(run_pitches) - 1 else 96)
        source.append(note(pitch, start=start, end=start + 78, velocity=velocity, track=2))

    result = arrange_notes(
        source,
        AppSettings(
            arrangement_mode="intelligent",
            max_polyphony=1,
            min_source_note_ms=0,
            min_retrigger_ms=0,
            max_notes_per_second=10,
            onset_group_ms=8,
        ),
        track_names={1: "Lead Vocal", 2: "Guitar Solo"},
    )

    retained_solo = {(item.start_ms, item.pitch) for item in result.notes if item.track_index == 2}
    assert result.solo_segments
    assert (1800.0, run_pitches[0]) in retained_solo
    assert (1800.0 + 15 * 33.0, run_pitches[15]) in retained_solo
    assert result.solo_density_dropped > 0
    assert result.solo_landmarks_preserved >= 3


def test_arranger_close_voicing_bass_selection():
    # Triad with close voicing: Melody is G4 (67), harmony notes are E4 (64) and C4 (60).
    # G4 - E4 is 3 semitones; G4 - C4 is 7 semitones.
    # Another group with very close voicing: Melody F4 (65), D4 (62, 3 semitones below), C4 (60, 5 semitones below).
    # The lowest note C4 (60) should be recognized and selected as harmonic anchor.
    source = [
        note(65, start=0, end=400, track=1, velocity=100),  # Melody F4
        note(62, start=0, end=400, track=2, velocity=85),   # D4
        note(60, start=0, end=400, track=2, velocity=85),   # C4
    ]
    result = arrange_notes(
        source,
        AppSettings(
            arrangement_mode="intelligent",
            max_polyphony=2,
            min_source_note_ms=0,
            min_retrigger_ms=0,
            max_notes_per_second=60,
        ),
    )
    selected_pitches = {item.pitch for item in result.notes}
    assert 65 in selected_pitches
    assert 60 in selected_pitches


def test_melody_landmarks_preserved_under_density_limit():
    run_pitches = [60, 62, 64, 67, 64, 62, 60]
    source = [
        note(p, start=i * 40.0, end=(i + 1) * 40.0, track=0, velocity=90)
        for i, p in enumerate(run_pitches)
    ]
    result = arrange_notes(
        source,
        AppSettings(
            arrangement_mode="melody",
            max_polyphony=1,
            min_source_note_ms=0,
            min_retrigger_ms=0,
            max_notes_per_second=4,
        ),
    )
    retained_pitches = [item.pitch for item in result.notes]
    assert 67 in retained_pitches
    assert result.melody_landmarks_preserved >= 1


