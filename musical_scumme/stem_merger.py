"""Deterministic stem MIDI merger for multi-track cover arrangement in MusicalScumbag."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import mido

from .midi_engine import load_midi
from .model import MidiNote

PROGRAM_VOCALS = 53  # General MIDI Voice Oohs
PROGRAM_GUITAR = 25  # General MIDI Acoustic Guitar (steel)
PROGRAM_BASS = 33    # General MIDI Electric Bass (finger)


def _build_stem_track(
    name: str,
    notes: Iterable[MidiNote],
    channel: int,
    program: int,
    ticks_per_beat: int,
    tempo: int,
) -> mido.MidiTrack:
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name=name, time=0))
    track.append(mido.Message("program_change", program=program, channel=channel, time=0))

    events: list[tuple[int, int, int, int]] = []
    for note in notes:
        start_tick = round(mido.second2tick(note.start_ms / 1000.0, ticks_per_beat, tempo))
        end_tick = max(start_tick + 1, round(mido.second2tick(note.end_ms / 1000.0, ticks_per_beat, tempo)))
        events.append((start_tick, 1, note.pitch, note.velocity))
        events.append((end_tick, 0, note.pitch, 0))

    events.sort(key=lambda event: (event[0], event[1], event[2]))
    last_tick = 0
    for tick, action, pitch, velocity in events:
        delta = max(0, tick - last_tick)
        last_tick = tick
        message_type = "note_on" if action else "note_off"
        track.append(mido.Message(message_type, note=pitch, velocity=velocity, channel=channel, time=delta))

    track.append(mido.MetaMessage("end_of_track", time=0))
    return track


def write_cover_midi(
    *,
    vocals_notes: Iterable[MidiNote] | None = None,
    instrumental_notes: Iterable[MidiNote] | None = None,
    bass_notes: Iterable[MidiNote] | None = None,
    output_path: Path | str,
    bpm: float = 120.0,
    overwrite: bool = True,
) -> Path:
    out = Path(output_path).expanduser().resolve()
    if out.suffix.lower() not in {".mid", ".midi"}:
        raise ValueError("Output file must have .mid or .midi extension")
    if out.exists() and not overwrite:
        raise FileExistsError(f"Output file already exists: {out}")

    # Keep the source iterable instead of duplicating large note collections.
    # Each layer is consumed exactly once when its MIDI track is built.
    parts: list[tuple[str, Iterable[MidiNote], int, int]] = []
    if vocals_notes is not None:
        parts.append(("Vocals", vocals_notes, 0, PROGRAM_VOCALS))
    if instrumental_notes is not None:
        parts.append(("Guitar / Instrumental", instrumental_notes, 1, PROGRAM_GUITAR))
    if bass_notes is not None:
        parts.append(("Bass", bass_notes, 2, PROGRAM_BASS))

    if not parts:
        raise ValueError("At least one note layer must be provided to create a cover MIDI.")

    ticks_per_beat = 480
    tempo = mido.bpm2tempo(max(20.0, min(300.0, float(bpm))))
    midi = mido.MidiFile(type=1, ticks_per_beat=ticks_per_beat)

    meta_track = mido.MidiTrack()
    meta_track.append(mido.MetaMessage("track_name", name="MusicalScumbag Cover Arrangement", time=0))
    meta_track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
    meta_track.append(mido.MetaMessage("end_of_track", time=0))
    midi.tracks.append(meta_track)

    for name, notes, channel, program in parts:
        midi.tracks.append(_build_stem_track(name, notes, channel, program, ticks_per_beat, tempo))

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.unlink(missing_ok=True)
    try:
        midi.save(tmp)
        tmp.replace(out)
    finally:
        tmp.unlink(missing_ok=True)

    return out


def merge_stems(
    *,
    vocals_path: Path | str | None = None,
    instrumental_path: Path | str | None = None,
    bass_path: Path | str | None = None,
    output_path: Path | str,
    bpm: float = 120.0,
    overwrite: bool = True,
) -> Path:
    v_notes = load_midi(vocals_path).notes if vocals_path else None
    i_notes = load_midi(instrumental_path).notes if instrumental_path else None
    b_notes = load_midi(bass_path).notes if bass_path else None

    return write_cover_midi(
        vocals_notes=v_notes,
        instrumental_notes=i_notes,
        bass_notes=b_notes,
        output_path=output_path,
        bpm=bpm,
        overwrite=overwrite,
    )
