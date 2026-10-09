import mido
import pytest

from musical_scumme.transcription_export import copy_source_midi


def test_source_export_preserves_all_midi_events_and_source_bytes(tmp_path):
    source = tmp_path / "raw.mid"
    midi = mido.MidiFile()
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.extend([
        mido.MetaMessage("set_tempo", tempo=700000),
        mido.Message("program_change", program=40, channel=3),
        mido.Message("control_change", control=64, value=127, channel=3),
        mido.Message("note_on", note=20, velocity=31, channel=3),
        mido.Message("note_on", note=100, velocity=99, channel=3, time=10),
        mido.MetaMessage("set_tempo", tempo=300000, time=100),
        mido.Message("pitchwheel", pitch=400, channel=3),
        mido.Message("note_off", note=20, channel=3, time=2000),
        mido.Message("note_off", note=100, channel=3),
        mido.Message("note_on", note=35, velocity=80, channel=9),
        mido.Message("note_off", note=35, channel=9, time=20),
    ])
    midi.save(source)
    original = source.read_bytes()
    output = copy_source_midi(source, tmp_path / "export.mid")
    assert output.read_bytes() == original == source.read_bytes()
    assert not output.with_suffix(".mid.tmp").exists()
    with pytest.raises(ValueError, match="overwrite"):
        copy_source_midi(source, source)
