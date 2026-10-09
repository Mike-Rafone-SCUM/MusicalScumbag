from dataclasses import replace

import pytest

from musical_scumme.model import MidiNote, PlannedNote
from musical_scumme.performance_phrasing import FluidPhrasingStats, apply_fluid_phrasing


def voice(start, duration=200, *, group=1, pitch=67, track=0, played=100, roll=0):
    source = MidiNote(track, track, pitch, 90, start, start + duration)
    note = PlannedNote(pitch, pitch, pitch, 0, str(pitch), 90, start + roll, start + roll + played, group)
    return note, source


def shape(pairs, leads, **kwargs):
    return apply_fluid_phrasing(
        [pair[0] for pair in pairs],
        [pair[1] for pair in pairs],
        set(leads),
        **(
            dict(
                strength=100,
                speed=1.0,
                minimum_hold_ms=30,
                maximum_hold_ms=1000,
                key_gap_ms=22,
                instrument="guitar",
                max_polyphony=3,
            )
            | kwargs
        ),
    )


def test_disabled_is_an_exact_noop_and_empty_is_supported():
    note, _ = voice(0)
    notes = [note]
    result, stats = apply_fluid_phrasing(
        notes,
        [],
        set(),
        strength=0,
        speed=1,
        minimum_hold_ms=30,
        maximum_hold_ms=1000,
        key_gap_ms=22,
        instrument="guitar",
        max_polyphony=3,
    )
    assert result is notes
    assert stats == FluidPhrasingStats()
    assert shape([], [])[0] == []


def test_phrase_curve_moves_support_with_lead_and_keeps_chord_roll():
    pairs = []
    leads = []
    for index in range(7):
        leads.append(len(pairs))
        pairs.extend(
            [voice(index * 250, group=index + 1), voice(index * 250, group=index + 1, pitch=60, track=1, roll=12)]
        )
    before = tuple(pairs)
    result, stats = shape(pairs, leads)
    assert stats.phrase_count == 1
    assert stats.shifted_groups > 0
    assert stats.connected_notes == 6
    assert stats.max_shift_ms <= 20
    assert result[0].start_ms == pairs[0][0].start_ms
    assert result[-2].start_ms == pairs[-2][0].start_ms
    for index in leads:
        assert result[index + 1].start_ms - result[index].start_ms == pytest.approx(12)
        assert 80 < result[index + 1].end_ms - result[index + 1].start_ms < 120
    assert tuple(pairs) == before


def test_capacity_prevents_connected_melody_from_stacking_extra_voices():
    pairs = [voice(0), voice(250, group=3), voice(100, duration=200, group=2, pitch=48, track=1, played=200)]
    result, stats = shape(pairs, [0, 1], max_polyphony=1)
    assert result[0].end_ms == 100
    assert stats.connected_notes == 0
    # With a free voice, connect only until a later held support fills it.
    pairs.append(voice(150, duration=200, group=4, pitch=55, track=2, played=200))
    result, _ = shape(pairs, [0, 1], max_polyphony=2)
    assert result[0].end_ms == 150


def test_sounding_accompaniment_cannot_erase_a_melody_breath():
    pairs = [
        voice(0),
        voice(250, group=2),
        voice(2000, group=4),
        voice(2250, group=5),
        voice(500, duration=1900, group=3, pitch=48, track=1, played=1900),
    ]
    result, stats = shape(pairs, [0, 1, 2, 3], maximum_hold_ms=2500)
    assert stats.phrase_count == 2
    assert stats.shifted_groups == 0
    assert result[1].end_ms == pairs[1][0].end_ms
    assert result[4] == pairs[4][0]


def test_staccato_and_untraced_polyphonic_scores_keep_their_articulation():
    pairs = [voice(index * 250, duration=50, played=50, group=index + 1) for index in range(7)]
    result, stats = shape(pairs, range(7))
    assert stats.connected_notes == 0
    assert all(note.end_ms - note.start_ms == pytest.approx(50) for note in result)
    pairs.append(voice(0, pitch=60, track=1))
    result, stats = shape(pairs, [])
    assert result == [pair[0] for pair in pairs]
    assert stats == FluidPhrasingStats()


def test_single_line_faithful_source_can_connect_without_a_traced_lead():
    pairs = [voice(index * 250, group=index + 1) for index in range(5)]
    result, stats = shape(pairs, [], maximum_hold_ms=130)
    assert stats.connected_notes == 4
    assert all(note.end_ms - note.start_ms <= 130 for note in result)


def test_timing_preserves_dense_support_order_and_distinct_phrase_endpoints():
    pairs = [voice(index * 500, duration=480, group=index * 100 + 1) for index in range(6)]
    pairs += [
        voice(index * 25, duration=20, played=20, group=index * 5 + 2, pitch=48, track=1)
        for index in range(101)
        if index % 20
    ]
    result, stats = shape(pairs, range(6))
    assert stats.max_shift_ms <= 2
    original_order = sorted(range(len(pairs)), key=lambda i: pairs[i][0].start_ms)
    assert [result[i].start_ms for i in original_order] == sorted(result[i].start_ms for i in original_order)


def test_late_rolled_chord_member_cannot_be_overtaken_by_the_next_attack():
    pairs = [voice(0), voice(0, pitch=60, track=1, roll=24)]
    pairs += [voice(index * 25, group=index + 1, pitch=67 + index) for index in range(1, 4)]
    result, stats = shape(pairs, [0, 2, 3, 4])
    assert stats.shifted_groups > 0
    assert result[1].start_ms < result[2].start_ms
    assert abs(result[2].start_ms - pairs[2][0].start_ms) <= 0.08


def test_minimum_physical_holds_limit_rubato_in_tightly_filled_passages():
    pairs = [voice(index * 100, duration=100, played=100, group=index + 1) for index in range(7)]
    result, stats = shape(pairs, range(7), minimum_hold_ms=100)
    assert stats.shifted_groups == 0
    assert all(note.end_ms - note.start_ms >= 100 for note in result)


def test_same_key_connections_leave_full_release_gap_and_shorten_overlap():
    pairs = [voice(0, played=450), voice(250, group=2)]
    result, stats = shape(pairs, [0, 1])
    assert result[0].end_ms <= result[1].start_ms - 22
    assert stats.released_notes == 1
    assert stats.connected_notes == 0


def test_source_alignment_is_required_when_enabled():
    note, source = voice(0)
    with pytest.raises(ValueError, match="source articulation"):
        apply_fluid_phrasing(
            [replace(note, start_ms=10)],
            [source, source],
            {0},
            strength=100,
            speed=1,
            minimum_hold_ms=30,
            maximum_hold_ms=1000,
            key_gap_ms=22,
            instrument="guitar",
            max_polyphony=3,
        )
