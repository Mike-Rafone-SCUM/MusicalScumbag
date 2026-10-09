import random
from pathlib import Path
from statistics import median

import mido
import pytest

from musical_scumme.midi_engine import load_midi
from musical_scumme.model import MidiNote
from musical_scumme.song_processor import (
    _consolidate_micro_strums,
    _detect_core_range,
    _note_weight,
    _SlidingPitchMedian,
    _suppress_harmonic_ghosts,
    estimate_tempo_bpm,
    process_midi_file,
    process_song_notes,
    write_processed_midi,
)


def _note(index: int, pitch: int, *, velocity: int = 82, duration_ms: float = 260.0) -> MidiNote:
    start = index * 220.0
    return MidiNote(0, 0, pitch, velocity, start, start + duration_ms)


def test_band_backing_preserves_chord_support_instead_of_one_guitar_line():
    notes = [MidiNote(0, 0, pitch, 90, 0, 300) for pitch in (48, 64, 67)]
    result = process_song_notes(notes, "band_backing")
    assert {note.pitch for note in result.notes} == {48, 64, 67}
    assert result.retained_notes == 3


def test_core_range_histogram_matches_legacy_note_scan() -> None:
    notes = [
        _note(index, 28 + index % 73, velocity=45 + index % 80, duration_ms=90 + index % 700)
        for index in range(800)
    ]
    width = 31
    total_weight = sum(_note_weight(note) for note in notes)
    weighted_center = sum(note.pitch * _note_weight(note) for note in notes) / total_weight
    minimum = min(note.pitch for note in notes)
    maximum = max(note.pitch for note in notes)
    legacy_best: tuple[float, float, int, int] | None = None
    for low in range(max(0, minimum - width), min(127 - width, maximum) + 1):
        high = low + width
        captured = sum(_note_weight(note) for note in notes if low <= note.pitch <= high)
        candidate = (captured, -abs((low + high) / 2.0 - weighted_center), low, high)
        if legacy_best is None or candidate > legacy_best:
            legacy_best = candidate
    assert legacy_best is not None

    low, high, coverage = _detect_core_range(notes, width)

    assert (low, high) == legacy_best[2:]
    assert coverage == pytest.approx(legacy_best[0] / total_weight)


def test_sliding_pitch_median_matches_per_query_lists() -> None:
    generator = random.Random(2102)
    core_notes = sorted(
        (
            MidiNote(
                0,
                0,
                generator.randint(24, 108),
                80,
                generator.uniform(0.0, 60_000.0),
                61_000.0,
            )
            for _index in range(2_000)
        ),
        key=lambda item: item.start_ms,
    )
    window = _SlidingPitchMedian(core_notes)
    for start_ms in sorted(generator.uniform(0.0, 60_000.0) for _index in range(500)):
        pitches = [
            item.pitch
            for item in core_notes
            if start_ms - 900.0 <= item.start_ms <= start_ms + 900.0
        ]
        expected = float(median(pitches)) if pitches else None
        assert window.at(start_ms) == expected


def test_song_processor_removes_overtone_ghosts_and_repairs_octaves() -> None:
    melody = [57, 60, 64, 60] * 6
    notes = [_note(index, pitch) for index, pitch in enumerate(melody)]
    notes.extend(
        [
            _note(3, 98, velocity=48, duration_ms=150.0),
            _note(9, 100, velocity=50, duration_ms=160.0),
            _note(15, 97, velocity=105, duration_ms=800.0),
        ]
    )

    result = process_song_notes(notes, "melody_focus")

    assert result.removed_outliers == 2
    assert result.corrected_octaves == 1
    assert len(result.lead_notes) == len(melody)
    assert not result.support_notes
    assert all(result.core_low <= note.pitch <= result.core_high for note in result.lead_notes)
    assert max(note.pitch for note in result.lead_notes) < 90
    assert all(
        left.end_ms <= right.start_ms
        for left, right in zip(result.lead_notes, result.lead_notes[1:], strict=False)
    )


def test_song_processor_can_keep_light_support() -> None:
    notes: list[MidiNote] = []
    for index, lead_pitch in enumerate([60, 62, 64, 65]):
        notes.append(_note(index, lead_pitch, velocity=95))
        notes.append(_note(index, lead_pitch - 12, velocity=75, duration_ms=500.0))

    result = process_song_notes(notes, "melody_bass")

    assert len(result.lead_notes) == 4
    assert len(result.support_notes) == 4
    assert all(note.track_index == 1 for note in result.lead_notes)
    assert all(note.track_index == 2 for note in result.support_notes)


def test_clear_melody_consolidates_micro_attacks() -> None:
    notes = [
        MidiNote(0, 0, 60, 90, 0.0, 300.0),
        MidiNote(0, 0, 67, 70, 40.0, 260.0),
        MidiNote(0, 0, 62, 90, 240.0, 520.0),
    ]

    result = process_song_notes(notes, "melody_focus")

    assert len(result.lead_notes) == 2
    assert result.removed_arrangement == 1


def test_clear_melody_stabilizes_isolated_octave_spike() -> None:
    notes = [_note(index, pitch) for index, pitch in enumerate([60, 41, 65])]

    result = process_song_notes(notes, "melody_focus")

    assert [note.pitch for note in result.lead_notes] == [60, 53, 65]
    assert result.stabilized_octaves == 1
    assert result.corrected_octaves == 1
    assert result.large_leaps == 0


def test_guitar_profile_preserves_structural_arpeggio_reset() -> None:
    notes = [_note(index, pitch) for index, pitch in enumerate([60, 41, 65])]

    result = process_song_notes(notes, "guitar_arpeggio")

    assert [note.pitch for note in result.lead_notes] == [60, 41, 65]
    assert result.stabilized_octaves == 0
    assert result.large_leaps == 2
    assert "Preserved 2 octave-sized register resets" in result.warnings[0]


def test_processed_midi_round_trip_and_overwrite_guard(tmp_path: Path) -> None:
    result = process_song_notes([_note(index, pitch) for index, pitch in enumerate([57, 60, 64, 60])])
    output = tmp_path / "prepared.mid"

    write_processed_midi(result, output, bpm=90.0)
    project = load_midi(output)

    assert output.exists()
    assert [track.name for track in project.tracks[:2]] == ["MusicalScumme Song Transposer", "Lead Melody"]
    assert len(project.notes) == len(result.lead_notes)
    assert project.first_bpm == pytest.approx(90.0)
    with pytest.raises(FileExistsError):
        write_processed_midi(result, output)
    with pytest.raises(ValueError, match="must not overwrite"):
        process_midi_file(output, output, overwrite=True)


def test_processed_midi_reports_recovered_source_data_bytes(tmp_path: Path) -> None:
    source = tmp_path / "invalid.mid"
    output = tmp_path / "recovered.mid"
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    for index, pitch in enumerate([60, 62, 64]):
        track.append(mido.Message("note_on", note=pitch, velocity=90, time=0 if index == 0 else 120))
        track.append(mido.Message("note_off", note=pitch, velocity=0, time=120))
    midi.save(source)
    data = bytearray(source.read_bytes())
    marker = bytes((0x90, 60, 90))
    data[data.index(marker) + 2] = 129
    source.write_bytes(data)

    result = process_midi_file(source, output)

    assert output.exists()
    assert "clipping those values to 127" in result.warnings[0]


def test_fast_midi_scales_micro_onset_window_instead_of_collapsing_real_notes(tmp_path: Path) -> None:
    source = tmp_path / "fast.mid"
    output = tmp_path / "fast.processed.mid"
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(240), time=0))
    track.append(mido.Message("note_on", note=60, velocity=90, time=0))
    track.append(mido.Message("note_on", note=64, velocity=90, time=77))
    track.append(mido.Message("note_off", note=60, velocity=0, time=115))
    track.append(mido.Message("note_off", note=64, velocity=0, time=77))
    midi.save(source)

    result = process_midi_file(source, output, profile_name="guitar_arpeggio")

    assert result.retained_notes == 2


def test_suppress_harmonic_ghosts_and_sub_bass():
    notes = [
        MidiNote(0, 0, 52, 95, 0.0, 500.0),
        MidiNote(0, 0, 64, 50, 10.0, 410.0),
        MidiNote(0, 0, 71, 45, 15.0, 365.0),
        MidiNote(0, 0, 24, 50, 0.0, 100.0),
        MidiNote(0, 0, 55, 90, 0.0, 500.0),
    ]
    cleaned, removed_count = _suppress_harmonic_ghosts(notes, "guitar_arpeggio")
    assert removed_count == 3
    remaining_pitches = {n.pitch for n in cleaned}
    assert remaining_pitches == {52, 55}


def test_consolidate_micro_strums():
    notes = [
        MidiNote(0, 0, 52, 90, 0.0, 400.0),
        MidiNote(0, 0, 55, 88, 16.0, 416.0),
        MidiNote(0, 0, 60, 85, 32.0, 432.0),
    ]
    consolidated, count = _consolidate_micro_strums(notes, max_strum_span_ms=35.0)
    assert count == 2
    assert len(consolidated) == 3
    assert all(n.start_ms == 0.0 for n in consolidated)


def test_estimate_tempo_bpm():
    notes_120 = [MidiNote(0, 0, 60, 80, i * 500.0, (i + 1) * 500.0) for i in range(12)]
    bpm = estimate_tempo_bpm(notes_120)
    assert bpm == pytest.approx(120.0, abs=2.0)

    notes_100 = [MidiNote(0, 0, 60, 80, i * 600.0, (i + 1) * 600.0) for i in range(12)]
    bpm_100 = estimate_tempo_bpm(notes_100)
    assert bpm_100 == pytest.approx(100.0, abs=2.0)
