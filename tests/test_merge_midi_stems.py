from pathlib import Path

import mido

from musical_scumme.midi_engine import load_midi
from musical_scumme.model import MidiNote
from musical_scumme.stem_merger import write_cover_midi
from scripts.merge_midi_stems import merge_stems


def _create_simple_midi(path: Path, note_pitches: list[int], track_name: str) -> Path:
    mid = mido.MidiFile(type=0, ticks_per_beat=480)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name=track_name, time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    for pitch in note_pitches:
        track.append(mido.Message("note_on", note=pitch, velocity=64, time=0))
        track.append(mido.Message("note_off", note=pitch, velocity=0, time=480))
    track.append(mido.MetaMessage("end_of_track", time=0))
    mid.tracks.append(track)
    mid.save(path)
    return path


def test_merge_stems_creates_valid_type1_multitrack_midi(tmp_path):
    vocals_file = _create_simple_midi(tmp_path / "vocals.mid", [60, 62, 64], "Vocals Raw")
    instrumental_file = _create_simple_midi(tmp_path / "inst.mid", [48, 52, 55], "Instrumental Raw")
    merged_file = tmp_path / "merged.mid"

    out = merge_stems(
        vocals_path=vocals_file,
        instrumental_path=instrumental_file,
        output_path=merged_file,
        bpm=120.0,
    )

    assert out == merged_file
    assert merged_file.is_file()

    project = load_midi(merged_file)
    assert len(project.tracks) >= 2
    track_names = [t.name for t in project.tracks]
    assert any("Vocals" in name for name in track_names)
    assert any("Guitar" in name or "Instrumental" in name for name in track_names)

    # Check that both parts' notes are present
    notes = list(project.notes)
    pitches = {n.pitch for n in notes}
    assert {60, 62, 64}.issubset(pitches)
    assert {48, 52, 55}.issubset(pitches)

    from musical_scumme.cover_layers import infer_cover_layers
    names = {i: t.name for i, t in enumerate(project.tracks)}
    roles = infer_cover_layers(notes, primary=1, names=names)
    assert roles.get(1) == "lead"
    assert roles.get(2) in ("rhythm", "bass", "harmony")


def test_cover_writer_consumes_each_layer_once_without_materializing_all_layers(tmp_path, monkeypatch):
    from musical_scumme import stem_merger

    consumed = []
    built = []
    original = stem_merger._build_stem_track

    def layer(name, pitch):
        consumed.append(name)
        yield MidiNote(track_index=0, channel=0, pitch=pitch, velocity=80, start_ms=12, end_ms=3012)

    def build(name, *args):
        # Instrumental iteration must wait until after the vocal track is built.
        if name == "Vocals":
            assert consumed == []
        else:
            assert consumed == ["vocals"]
            assert built == ["Vocals"]
        result = original(name, *args)
        built.append(name)
        return result

    monkeypatch.setattr(stem_merger, "_build_stem_track", build)
    output = write_cover_midi(vocals_notes=layer("vocals", 60),
                              instrumental_notes=layer("backing", 24), output_path=tmp_path / "lazy.mid")
    assert consumed == ["vocals", "backing"]
    notes = load_midi(output).notes
    assert sorted(n.pitch for n in notes) == [24, 60]
    assert all(abs(n.start_ms - 12) < 1 and abs(n.end_ms - 3012) < 1 for n in notes)
