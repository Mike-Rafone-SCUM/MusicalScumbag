from pathlib import Path

import mido
import pytest

from musical_scumme.midi_engine import _tempo_map, load_midi


def test_multitrack_import_retains_data_after_releasing_raw_message_buffers(tmp_path):
    midi = mido.MidiFile(ticks_per_beat=480)
    for index in range(8):
        track = mido.MidiTrack([mido.MetaMessage("track_name", name=f"Part {index}")])
        if index == 0:
            track.append(mido.MetaMessage("set_tempo", tempo=600_000))
        for _ in range(100):
            track.append(mido.Message("note_on", note=60 + index, channel=index, velocity=90, time=120))
            track.append(mido.Message("note_off", note=60 + index, channel=index, velocity=55, time=360))
        midi.tracks.append(track)
    path = tmp_path / "many_tracks.mid"
    midi.save(path)
    original = path.read_bytes()
    project = load_midi(path)
    assert path.read_bytes() == original
    assert project.first_bpm == 100
    assert len(project.notes) == 800
    assert [t.name for t in project.tracks] == [f"Part {i}" for i in range(8)]
    for index in range(8):
        notes = project.notes_for_tracks([index])
        assert len(notes) == 100
        assert all(n.pitch == 60 + index and n.channel == index and n.velocity == 90 for n in notes)
        assert notes[0].start_ms == pytest.approx(150)
        assert all(n.duration_ms == pytest.approx(450) for n in notes)


def _merged_tempo_map_reference(midi: mido.MidiFile) -> tuple[list[int], list[int]]:
    changes = [(0, 500_000)]
    absolute_tick = 0
    for message in mido.merge_tracks(midi.tracks):
        absolute_tick += int(message.time)
        if message.is_meta and message.type == "set_tempo":
            changes.append((absolute_tick, int(message.tempo)))
    deduped: list[tuple[int, int]] = []
    for tick, tempo in sorted(changes, key=lambda change: change[0]):
        if deduped and deduped[-1][0] == tick:
            deduped[-1] = (tick, tempo)
        else:
            deduped.append((tick, tempo))
    return [tick for tick, _tempo in deduped], [tempo for _tick, tempo in deduped]


def test_tempo_scan_matches_stable_merged_track_precedence():
    midi = mido.MidiFile(ticks_per_beat=480)
    first = mido.MidiTrack()
    second = mido.MidiTrack()
    midi.tracks.extend((first, second))
    first.append(mido.MetaMessage("set_tempo", tempo=500_000, time=0))
    first.append(mido.MetaMessage("set_tempo", tempo=750_000, time=480))
    second.append(mido.MetaMessage("set_tempo", tempo=250_000, time=0))
    second.append(mido.MetaMessage("set_tempo", tempo=600_000, time=480))

    ticks, tempos, _ms_at = _tempo_map(midi)

    assert (ticks, tempos) == _merged_tempo_map_reference(midi)


def test_load_midi_handles_tempo_and_sustain(tmp_path: Path):
    path = tmp_path / "test.mid"
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name="Piano", time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    track.append(mido.Message("control_change", channel=0, control=64, value=127, time=0))
    track.append(mido.Message("note_on", channel=0, note=60, velocity=100, time=0))
    track.append(mido.Message("note_off", channel=0, note=60, velocity=64, time=240))
    track.append(mido.Message("control_change", channel=0, control=64, value=0, time=240))
    midi.save(path)

    project = load_midi(path)
    assert len(project.notes) == 1
    note = project.notes[0]
    assert note.start_ms == 0
    assert 499 <= note.end_ms <= 501
    assert project.tracks[0].name == "Piano"
    assert project.tracks[0].pitch_range_text == "C4–C4"


def test_load_midi_closes_note_off_with_nonzero_release_velocity(tmp_path: Path):
    path = tmp_path / "release-velocity.mid"
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=500_000, time=0))
    track.append(mido.Message("note_on", channel=0, note=60, velocity=100, time=0))
    track.append(mido.Message("note_off", channel=0, note=60, velocity=64, time=480))
    track.append(mido.MetaMessage("end_of_track", time=480))
    midi.save(path)
    source_bytes = path.read_bytes()

    project = load_midi(path)

    assert len(project.notes) == 1
    assert project.notes[0].duration_ms == pytest.approx(500.0)
    assert path.read_bytes() == source_bytes


def test_load_midi_preserves_fast_tempo_declared_at_tick_zero(tmp_path: Path):
    path = tmp_path / "fast.mid"
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    tempo = mido.bpm2tempo(270)
    track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
    track.append(mido.Message("note_on", note=60, velocity=100, time=0))
    track.append(mido.Message("note_off", note=60, velocity=0, time=480))
    midi.save(path)

    project = load_midi(path)

    assert project.first_bpm == pytest.approx(270.0, rel=1e-5)
    assert project.duration_ms == pytest.approx(60_000 / 270, rel=1e-5)


def _write_invalid_velocity_midi(path: Path) -> None:
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.Message("note_on", channel=0, note=60, velocity=100, time=0))
    track.append(mido.Message("note_off", channel=0, note=60, velocity=0, time=240))
    midi.save(path)
    data = bytearray(path.read_bytes())
    marker = bytes((0x90, 60, 100))
    offset = data.index(marker)
    data[offset + 2] = 129
    path.write_bytes(data)


def test_load_midi_recovers_only_out_of_range_data_bytes(tmp_path: Path):
    path = tmp_path / "invalid-velocity.mid"
    _write_invalid_velocity_midi(path)

    with pytest.raises(OSError, match="data byte must be in range"):
        mido.MidiFile(path)

    project = load_midi(path)

    assert len(project.notes) == 1
    assert project.notes[0].velocity == 127
    assert "clipping those values to 127" in project.warnings[0]


def test_load_midi_does_not_hide_unrelated_corruption(tmp_path: Path):
    path = tmp_path / "broken.mid"
    path.write_bytes(b"not a MIDI file")

    with pytest.raises(OSError):
        load_midi(path)


@pytest.mark.parametrize("controller,pedal,expected", [
    (120, False, (125, 250)), (120, True, (250, 250)),
    (121, False, (125, 750)), (121, True, (250, 750)),
    (123, False, (125, 250)), (123, True, (500, 500)),
])
def test_channel_controls_respect_pedal_held_notes_and_channel_isolation(tmp_path, controller, pedal, expected):
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack([
        mido.Message("control_change", control=64, value=127 if pedal else 0),
        mido.Message("note_on", note=60, velocity=90),
        mido.Message("note_on", note=64, velocity=100),
        mido.Message("note_on", channel=1, note=67, velocity=80),
        mido.Message("note_off", note=60, time=120),
        mido.Message("control_change", control=controller, value=0, time=120),
        mido.Message("control_change", control=64, value=0, time=240),
        mido.Message("note_off", note=64, time=240),
        mido.Message("note_off", channel=1, note=67),
        mido.MetaMessage("end_of_track", time=480),
    ])
    midi.tracks.append(track)
    path = tmp_path / "controllers.mid"
    midi.save(path)
    original = path.read_bytes()
    notes = load_midi(path).notes
    assert [(n.pitch, n.velocity) for n in notes] == [(60, 90), (64, 100), (67, 80)]
    assert [n.end_ms for n in notes] == pytest.approx([*expected, 750])
    assert path.read_bytes() == original


@pytest.mark.parametrize("controller", [120, 123])
def test_all_notes_controls_close_repeated_attacks_without_duplicate_releases(tmp_path, controller):
    midi = mido.MidiFile(ticks_per_beat=480)
    midi.tracks.append(mido.MidiTrack([
        mido.Message("note_on", note=60, velocity=90),
        mido.Message("note_on", note=60, velocity=100, time=120),
        mido.Message("control_change", control=controller, value=0, time=120),
        mido.Message("note_off", note=60, time=120),
        mido.Message("note_off", note=60),
        mido.Message("note_on", note=60, velocity=80, time=120),
        mido.Message("note_off", note=60, time=120),
    ]))
    path = tmp_path / "repeated.mid"
    midi.save(path)
    notes = load_midi(path).notes
    assert [n.start_ms for n in notes] == pytest.approx([0, 125, 500])
    assert [n.end_ms for n in notes] == pytest.approx([250, 250, 625])


@pytest.mark.parametrize("midi_type,division,tempo,error", [
    (2, 480, 500_000, "independent sequences"),
    (1, 0, 500_000, "positive beat-based timing"),
    (1, -6360, 500_000, "SMPTE"),
    (1, 480, 0, "tempo must be greater than zero"),
])
def test_unsupported_or_invalid_timing_is_rejected_without_rewriting(tmp_path, midi_type, division, tempo, error):
    midi = mido.MidiFile(type=midi_type, ticks_per_beat=division)
    midi.tracks.append(mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=tempo)]))
    path = tmp_path / "timing.mid"
    midi.save(path)
    original = path.read_bytes()
    with pytest.raises(ValueError, match=error):
        load_midi(path)
    assert path.read_bytes() == original


def test_zero_tempo_later_in_song_is_rejected(tmp_path):
    midi = mido.MidiFile()
    midi.tracks.append(mido.MidiTrack([
        mido.MetaMessage("set_tempo", tempo=500_000),
        mido.MetaMessage("set_tempo", tempo=0, time=480),
    ]))
    path = tmp_path / "late-zero.mid"
    midi.save(path)
    with pytest.raises(ValueError, match="tempo must be greater than zero"):
        load_midi(path)
