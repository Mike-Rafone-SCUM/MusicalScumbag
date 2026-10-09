from __future__ import annotations

import json
import os
import wave
from dataclasses import dataclass
from pathlib import Path

from .audio_tools import AUDIO_EXTENSIONS, resource_path

SEPARATION_RUNTIME_READY_MARKER = ".musicalscumme-separation-ready-v1"
SEPARATION_RUNTIME_POINTER = "separation-runtime.path"
SEPARATION_MODEL_FILENAME = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
SEPARATION_MODEL_LABEL = "BS-RoFormer Viperx-1297"
SEPARATION_SEGMENT_SIZE = 256
SEPARATION_CLEANUP_MODES = {"none", "dereverb", "full"}
SEPARATION_DEREVERB_MODEL = "dereverb-echo_mel_band_roformer_sdr_13.4843_v2.ckpt"
SEPARATION_DENOISE_MODEL = "denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt"


@dataclass(frozen=True, slots=True)
class SeparationToolsStatus:
    available: bool
    python_path: Path | None
    worker_path: Path | None
    model_dir: Path | None
    message: str
    backend: str | None = None


def musicalscumme_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "MusicalScumme"


def separation_runtime_pointer() -> Path:
    return musicalscumme_data_dir() / SEPARATION_RUNTIME_POINTER


def separation_runtime_dir() -> Path:
    override = os.environ.get("MUSICALSCUMME_SEPARATION_RUNTIME", "").strip()
    if override:
        return Path(override).expanduser()
    pointer = separation_runtime_pointer()
    if pointer.is_file():
        try:
            stored = pointer.read_text(encoding="utf-8-sig").strip()
        except OSError:
            stored = ""
        if stored:
            candidate = Path(stored).expanduser()
            if candidate.is_absolute():
                return candidate
    return musicalscumme_data_dir() / "separation-runtime"


def separation_runtime_python() -> Path:
    root = separation_runtime_dir()
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def separation_model_dir() -> Path:
    override = os.environ.get("MUSICALSCUMME_SEPARATION_MODELS", "").strip()
    if override:
        return Path(override).expanduser()
    return separation_runtime_dir() / "models"


def separation_runtime_ready_marker() -> Path:
    return separation_runtime_dir() / SEPARATION_RUNTIME_READY_MARKER


def separation_stem_paths(source: str | Path, output_dir: str | Path) -> tuple[Path, Path]:
    source_path = Path(source).expanduser()
    directory = Path(output_dir).expanduser()
    return (
        directory / f"{source_path.stem}.vocals.wav",
        directory / f"{source_path.stem}.instrumental.wav",
    )


def separation_provenance_path(vocals: str | Path) -> Path:
    return Path(vocals).with_suffix(".uvr.json")


def separation_output_paths(vocals: str | Path, instrumental: str | Path, *, cleanup: str) -> tuple[Path, ...]:
    """List every published file so destination safety and overwrite prompts agree."""
    if cleanup not in SEPARATION_CLEANUP_MODES:
        raise ValueError("Unknown UVR cleanup mode.")
    stems = (Path(vocals), Path(instrumental))
    raw = tuple(path.with_name(f"{path.stem}.raw.wav") for path in stems) if cleanup != "none" else ()
    return (*stems, *raw, separation_provenance_path(vocals))


def reusable_stem(source: Path, stem: Path) -> bool:
    """Reject unreadable/truncated WAVs and stems older than their source."""
    try:
        if stem.stat().st_mtime_ns < source.stat().st_mtime_ns:
            return False
        with wave.open(str(stem), "rb") as audio:
            frames = audio.getnframes()
            frame_size = audio.getnchannels() * audio.getsampwidth()
            if frames <= 0 or audio.getframerate() <= 0:
                return False
            # Check the tail without loading a whole song into the UI process.
            audio.setpos(frames - 1)
            return len(audio.readframes(1)) == frame_size
    except (OSError, EOFError, wave.Error):
        return False


def reusable_stems(
    source: Path, vocals: Path, instrumental: Path, *, quality: str, cleanup: str,
) -> bool:
    """Require the same complete treatment run; legacy WAV reuse is separation-only."""
    if quality not in {"fast", "balanced", "best"} or cleanup not in SEPARATION_CLEANUP_MODES:
        return False
    provenance = separation_provenance_path(vocals)
    if not provenance.exists():
        return cleanup == "none" and all(reusable_stem(source, stem) for stem in (vocals, instrumental))
    metadata = _ready_metadata(provenance)
    try:
        source_stat = source.stat()
        if metadata.get("version") != 1 or metadata.get("source") != {
            "path": str(source.resolve()), "size": source_stat.st_size, "mtime_ns": source_stat.st_mtime_ns,
        }:
            return False
        if (metadata.get("model"), metadata.get("quality"), metadata.get("cleanup")) != (
            SEPARATION_MODEL_FILENAME, quality, cleanup,
        ):
            return False
        if metadata.get("segment_size") != SEPARATION_SEGMENT_SIZE:
            return False
        treatment = []
        if cleanup != "none":
            treatment.append({"stage": "dereverb", "model": SEPARATION_DEREVERB_MODEL,
                              "stems": ["vocals"], "blend": 1.0})
        if cleanup == "full":
            treatment.append({"stage": "denoise", "model": SEPARATION_DENOISE_MODEL,
                              "stems": ["vocals"], "blend": 0.75})
        if metadata.get("treatment") != treatment:
            return False
        expected = separation_output_paths(vocals, instrumental, cleanup=cleanup)[:-1]
        outputs = metadata.get("outputs")
        if not isinstance(outputs, list) or len(outputs) != len(expected):
            return False
        headers = []
        for stem, recorded in zip(expected, outputs, strict=True):
            if not reusable_stem(source, stem):
                return False
            file_stat = stem.stat()
            with wave.open(str(stem), "rb") as audio:
                header = (audio.getframerate(), audio.getnframes(), audio.getnchannels())
            if recorded != {"path": str(stem.resolve()), "size": file_stat.st_size,
                            "mtime_ns": file_stat.st_mtime_ns,
                            "rate": header[0], "frames": header[1], "channels": header[2]}:
                return False
            headers.append(header)
        return all(header == headers[0] for header in headers)
    except (OSError, EOFError, wave.Error, TypeError, ValueError):
        return False


def _ready_metadata(marker: Path) -> dict[str, object]:
    try:
        payload = json.loads(marker.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def separation_tools_status() -> SeparationToolsStatus:
    runtime = separation_runtime_python()
    worker = resource_path("separation_worker.py")
    model_dir = separation_model_dir()
    marker = separation_runtime_ready_marker()
    if not worker.exists():
        return SeparationToolsStatus(False, runtime if runtime.exists() else None, None, model_dir, "UVR worker resource is missing.")
    if not runtime.exists():
        return SeparationToolsStatus(
            False,
            None,
            worker,
            model_dir,
            "Optional UVR separation runtime is not installed.",
        )
    if not marker.is_file():
        return SeparationToolsStatus(
            False,
            runtime,
            worker,
            model_dir,
            "UVR runtime needs installation or repair; existing model downloads will be reused.",
        )
    metadata = _ready_metadata(marker)
    if metadata.get("model") != SEPARATION_MODEL_FILENAME:
        return SeparationToolsStatus(
            False,
            runtime,
            worker,
            model_dir,
            "UVR runtime has a stale model marker and needs repair.",
        )
    backend = str(metadata.get("backend", "unknown")).upper()
    return SeparationToolsStatus(
        True,
        runtime,
        worker,
        model_dir,
        f"UVR {SEPARATION_MODEL_LABEL} is ready ({backend}).",
        backend=backend,
    )


def separation_worker_command(
    input_path: str | Path,
    vocals_output: str | Path,
    instrumental_output: str | Path,
    *, quality: str = "best", cleanup: str = "none",
) -> tuple[str, list[str]]:
    if quality not in {"fast", "balanced", "best"}:
        raise ValueError("Unknown separation quality preset.")
    if cleanup not in SEPARATION_CLEANUP_MODES:
        raise ValueError("Unknown UVR cleanup mode.")
    status = separation_tools_status()
    if (
        not status.available
        or status.python_path is None
        or status.worker_path is None
        or status.model_dir is None
    ):
        raise RuntimeError(status.message)
    source = Path(input_path).expanduser().resolve()
    vocals = Path(vocals_output).expanduser().resolve()
    instrumental = Path(instrumental_output).expanduser().resolve()
    if source.suffix.lower() not in AUDIO_EXTENSIONS:
        raise ValueError("UVR input must be a supported audio file.")
    if vocals.suffix.lower() != ".wav" or instrumental.suffix.lower() != ".wav":
        raise ValueError("UVR stem outputs must be WAV files.")
    if vocals == instrumental:
        raise ValueError("Vocals and instrumental stems must use different output files.")
    if source in (vocals, instrumental):
        raise ValueError("Stem outputs must not overwrite the source audio.")
    outputs = separation_output_paths(vocals, instrumental, cleanup=cleanup)
    if len(set(outputs)) != len(outputs):
        raise ValueError("UVR stems, raw stems and provenance must use different output files.")
    if source in outputs:
        raise ValueError("UVR raw stem outputs must not overwrite the source audio.")
    arguments = [
        "-I",
        "-X",
        "utf8",
        str(status.worker_path),
        "--input",
        str(source),
        "--vocals-output",
        str(vocals),
        "--instrumental-output",
        str(instrumental),
        "--model-dir",
        str(status.model_dir.resolve()),
        "--model",
        SEPARATION_MODEL_FILENAME,
        "--quality",
        quality,
        "--cleanup",
        cleanup,
    ]
    return str(status.python_path), arguments
