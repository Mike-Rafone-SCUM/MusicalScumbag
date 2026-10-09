from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}
AUDIO_RUNTIME_READY_MARKER = ".musicalscumme-audio-ready-v1"
RECOMMENDED_ONSET_THRESHOLD = 0.45
RECOMMENDED_FRAME_THRESHOLD = 0.30
RECOMMENDED_MINIMUM_NOTE_MS = 90

# Basic Pitch works better when it is not asked to explain sub-bass rumble or
# very high harmonics that cannot contribute useful SCUM notes. C2-C7 retains
# one octave beyond the playable C3-C6 range in both directions, so the planner
# can still choose a whole-song octave shift without losing source contour.
AUDIO_PITCH_FOCUS_RANGES: dict[str, tuple[str, float | None, float | None]] = {
    "scum": ("SCUM-focused C2-C7 (recommended)", 65.406, 2093.005),
    "guitar": ("Guitar-focused E2-E6", 82.407, 1318.510),
    "vocal_range": ("Vocal melody range C2-C6", 65.406, 1046.502),
    "scum_c2_c7": ("SCUM-focused C2-C7", 65.406, 2093.005),
    "full": ("Full model range", None, None),
}


@dataclass(frozen=True, slots=True)
class AudioToolsStatus:
    available: bool
    python_path: Path | None
    worker_path: Path | None
    message: str


def resource_path(name: str) -> Path:
    """Resolve a project resource in source and PyInstaller builds."""

    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / name
    return Path(__file__).resolve().parent.parent / name


def audio_runtime_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "MusicalScumme" / "audio-runtime"


def audio_runtime_python() -> Path:
    root = audio_runtime_dir()
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def audio_runtime_ready_marker() -> Path:
    return audio_runtime_dir() / AUDIO_RUNTIME_READY_MARKER


def audio_tools_status() -> AudioToolsStatus:
    runtime = audio_runtime_python()
    worker = resource_path("audio_worker.py")
    if not worker.exists():
        return AudioToolsStatus(False, runtime if runtime.exists() else None, None, "Audio worker resource is missing.")
    if not runtime.exists():
        return AudioToolsStatus(
            False,
            None,
            worker,
            "Optional audio transcription runtime is not installed.",
        )
    if not audio_runtime_ready_marker().is_file():
        return AudioToolsStatus(
            False,
            runtime,
            worker,
            "Audio runtime needs validation or repair. Click Install audio tools; existing downloads will be reused.",
        )
    return AudioToolsStatus(True, runtime, worker, "Spotify Basic Pitch audio transcription is installed.")


def audio_worker_command(
    input_path: str | Path,
    output_path: str | Path,
    *,
    onset_threshold: float,
    frame_threshold: float,
    minimum_note_ms: int,
    minimum_frequency: float | None = None,
    maximum_frequency: float | None = None,
    mode: str = "polyphonic",
    vocal_confidence: float = 0.01,
) -> tuple[str, list[str]]:
    if mode not in {"polyphonic", "vocals", "instrumental"}:
        raise ValueError("Unknown transcription mode")
    status = audio_tools_status()
    if not status.available or status.python_path is None or status.worker_path is None:
        raise RuntimeError(status.message)
    arguments = [
        "-I",
        "-X",
        "utf8",
        str(status.worker_path),
        "--input",
        str(Path(input_path).expanduser().resolve()),
        "--output",
        str(Path(output_path).expanduser().resolve()),
        "--onset-threshold",
        f"{onset_threshold:.4f}",
        "--frame-threshold",
        f"{frame_threshold:.4f}",
        "--minimum-note-ms",
        str(int(minimum_note_ms)),
        "--mode",
        mode,
        "--vocal-confidence",
        f"{vocal_confidence:.4f}",
    ]
    if minimum_frequency is not None:
        arguments.extend(["--minimum-frequency", f"{minimum_frequency:.3f}"])
    if maximum_frequency is not None:
        arguments.extend(["--maximum-frequency", f"{maximum_frequency:.3f}"])
    return str(status.python_path), arguments
