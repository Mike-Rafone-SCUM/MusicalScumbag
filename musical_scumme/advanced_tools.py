"""Discovery and subprocess commands for optional multi-instrument transcription."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .audio_tools import AudioToolsStatus, resource_path

MODEL_REVISION = "5e66c1ea173a8186e0d20432b841d3180cc015b5"
READY_MARKER = ".musicalscumme-advanced-ready-v1"
EVIDENCE_VERSION = 2


def advanced_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "MusicalScumme"


def advanced_runtime_dir() -> Path:
    pointer = advanced_data_dir() / "advanced-runtime.path"
    try:
        stored = Path(pointer.read_text(encoding="utf-8-sig").strip())
        if stored.is_absolute():
            return stored
    except (OSError, ValueError):
        pass
    return advanced_data_dir() / "advanced-runtime"


def advanced_tools_status() -> AudioToolsStatus:
    root = advanced_runtime_dir()
    python = root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    worker = resource_path("advanced_worker.py")
    try:
        ready = json.loads((root / READY_MARKER).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        ready = {}
    available = (
        python.is_file() and worker.is_file() and ready.get("revision") == MODEL_REVISION
        and (root / "vendor/model_helper.py").is_file()
        and ready.get("evidence_version") == EVIDENCE_VERSION
        and resource_path("audio_evidence.py").is_file()
    )
    message = (
        f"YourMT3+ / CREPE audio checking installed ({ready.get('backend', 'CPU')})."
        if available else "Optional transcription needs installation or repair for audio checking."
    )
    return AudioToolsStatus(available, python if python.is_file() else None,
                            worker if worker.is_file() else None, message)


def advanced_worker_command(
    input_path: str | Path, raw_output: str | Path, prepared_output: str | Path,
    *, role: str = "full", second_input: str | Path | None = None,
    stem_passes: bool = False,
    audio_checked: bool = False,
    recover_quiet_notes: bool = False,
) -> tuple[str, list[str]]:
    if role not in {"full", "vocals", "instrumental"}:
        raise ValueError("Unknown transcription role")
    if stem_passes and second_input is None:
        raise ValueError("Independent stem passes require both synchronized stems.")
    if audio_checked and role == "full" and not stem_passes:
        raise ValueError("Audio-checked covers require both synchronized stems.")
    if audio_checked and second_input is not None and not stem_passes:
        raise ValueError("Audio checking requires independent passes for paired stems.")
    if recover_quiet_notes and not audio_checked:
        raise ValueError("Quiet-note recovery requires audio checking.")
    sources = [Path(input_path).expanduser().resolve()]
    if second_input is not None:
        sources.append(Path(second_input).expanduser().resolve())
    outputs = [Path(p).expanduser().resolve() for p in (raw_output, prepared_output)]
    if outputs[0] == outputs[1] or any(p in sources for p in outputs):
        raise ValueError("Transcription destinations must be separate from each other and the source.")
    if any(p.suffix.lower() not in {".mid", ".midi"} for p in outputs):
        raise ValueError("Transcription destinations must end in .mid or .midi.")
    status = advanced_tools_status()
    if not status.available or status.python_path is None or status.worker_path is None:
        raise RuntimeError(status.message)
    arguments = ["-I", "-X", "utf8", str(status.worker_path),
                 "--runtime-dir", str(advanced_runtime_dir()),
                 "--input", str(sources[0]), "--output", str(outputs[0]),
                 "--prepared-output", str(outputs[1]), "--role", role]
    if second_input is not None:
        arguments += ["--second-input", str(sources[1])]
    if stem_passes:
        arguments.append("--stem-passes")
    if audio_checked:
        arguments.append("--audio-checked")
    if recover_quiet_notes:
        arguments.append("--recover-quiet-notes")
    return str(status.python_path), arguments
