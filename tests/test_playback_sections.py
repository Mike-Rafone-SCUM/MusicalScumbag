from musical_scumme.model import MidiNote
from musical_scumme.playback_sections import (
    PlaybackSection,
    apply_playback_sections,
    resolve_playback_intervals,
    sections_from_dicts,
)


def note(pitch: int, start: float, end: float) -> MidiNote:
    return MidiNote(0, 0, pitch, 100, start, end)


def test_multiple_include_ranges_are_merged_rebased_and_joined_with_a_gap():
    source = [
        note(60, 0, 200),
        note(62, 800, 1200),
        note(64, 2000, 2200),
    ]
    result = apply_playback_sections(
        source,
        [
            PlaybackSection("include", 900, 1400, "Verse"),
            PlaybackSection("include", 1300, 1500, "Overlapping verse"),
            PlaybackSection("include", 1900, 2300, "Chorus"),
        ],
        source_duration_ms=2500,
        gap_ms=500,
    )

    assert [(interval.start_ms, interval.end_ms) for interval in result.intervals] == [
        (900, 1500),
        (1900, 2300),
    ]
    assert [(item.pitch, item.start_ms, item.end_ms) for item in result.notes] == [
        (62, 0, 300),
        (64, 1200, 1400),
    ]
    assert result.dropped_source_notes == 1
    assert result.clipped_source_notes == 1
    assert result.source_span_ms == 1000
    assert result.output_duration_ms == 1500


def test_no_ranges_preserve_the_complete_source_note_timeline():
    source = [note(60, 0, 200), note(64, 400, 900)]

    result = apply_playback_sections(
        source,
        [],
        source_duration_ms=1000,
        gap_ms=500,
    )

    assert list(result.notes) == source
    assert result.dropped_source_notes == 0
    assert result.clipped_source_notes == 0
    assert result.output_duration_ms == 1000


def test_omit_range_splits_a_sustained_note_and_removes_contained_notes():
    result = apply_playback_sections(
        [note(60, 200, 800), note(64, 450, 550)],
        [PlaybackSection("omit", 400, 600, "Skip")],
        source_duration_ms=1000,
        gap_ms=100,
    )

    assert [(interval.start_ms, interval.end_ms) for interval in result.intervals] == [
        (0, 400),
        (600, 1000),
    ]
    assert [(item.pitch, item.start_ms, item.end_ms) for item in result.notes] == [
        (60, 200, 400),
        (60, 500, 700),
    ]
    assert result.dropped_source_notes == 1
    assert result.clipped_source_notes == 1


def test_omissions_are_subtracted_from_the_union_of_play_ranges():
    intervals = resolve_playback_intervals(
        5000,
        [
            PlaybackSection("include", 1000, 4000),
            PlaybackSection("include", 3500, 4500),
            PlaybackSection("omit", 2000, 2500),
            PlaybackSection("omit", 2400, 3000),
        ],
    )

    assert [(interval.start_ms, interval.end_ms) for interval in intervals] == [
        (1000, 2000),
        (3000, 4500),
    ]


def test_invalid_or_out_of_bounds_saved_sections_are_safely_filtered():
    sections = sections_from_dicts(
        [
            {"mode": "include", "start_ms": -100, "end_ms": 2000, "label": "Valid clipped"},
            {"mode": "omit", "start_ms": 9000, "end_ms": 10000},
            {"mode": "bad", "start_ms": 0, "end_ms": 100},
            {"mode": "include", "start_ms": 500, "end_ms": 400},
            "not a section",
        ],
        1000,
    )

    assert sections == [PlaybackSection("include", 0, 1000, "Valid clipped")]
