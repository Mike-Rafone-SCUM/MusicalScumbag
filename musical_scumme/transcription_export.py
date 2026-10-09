"""Export transcription without arranging it for game playback."""

import shutil
from pathlib import Path


def copy_source_midi(source: str | Path, destination: str | Path) -> Path:
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()
    if source == destination:
        raise ValueError("MIDI output must not overwrite the source MIDI.")
    if destination.suffix.lower() not in {".mid", ".midi"}:
        raise ValueError("Output file must have .mid or .midi extension")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        shutil.copyfile(source, temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
