"""Isolated UVR-compatible two-stem separation worker for MusicalScumme."""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".ogg", ".wav", ".flac", ".m4a"}
EXPECTED_STEMS = ("Vocals", "Instrumental")


def emit(event: str, **payload: object) -> None:
    print(json.dumps({"event": event, **payload}, ensure_ascii=True), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Separate a song into UVR vocals and instrumental stems.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--vocals-output", required=True, type=Path)
    parser.add_argument("--instrumental-output", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--model", required=True)
    return parser.parse_args()


def _add_ffmpeg_to_path() -> str | None:
    existing = shutil.which("ffmpeg")
    if existing:
        return existing
    if os.name != "nt":
        return None
    candidates = [
        Path("C:/ffmpeg/bin"),
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "ffmpeg" / "bin",
    ]
    for candidate in candidates:
        executable = candidate / "ffmpeg.exe"
        if executable.is_file():
            os.environ["PATH"] = f"{candidate}{os.pathsep}{os.environ.get('PATH', '')}"
            return str(executable)
    return None


def _locate_generated_stem(directory: Path, requested_base: str, stem: str) -> Path:
    exact = directory / f"{requested_base}.wav"
    if exact.is_file():
        return exact
    matches = [path for path in directory.glob("*.wav") if stem.lower() in path.name.lower()]
    if len(matches) == 1:
        return matches[0]
    raise RuntimeError(f"UVR did not produce an unambiguous {stem} WAV stem.")


def _atomic_publish(source: Path, destination: Path) -> None:
    _validate_wav(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        shutil.copy2(source, temporary)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _validate_wav(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= 44:
        raise RuntimeError(f"UVR produced an empty WAV stem: {path.name}")
    try:
        with wave.open(str(path), "rb") as audio:
            if audio.getnframes() <= 0 or audio.getnchannels() <= 0 or audio.getframerate() <= 0:
                raise RuntimeError(f"UVR produced an invalid WAV stem: {path.name}")
    except (OSError, EOFError, wave.Error) as exc:
        raise RuntimeError(f"UVR produced an unreadable WAV stem: {path.name}") from exc


def _decode_to_pcm_wav(ffmpeg: str, source: Path, destination: Path) -> None:
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        str(source),
        "-ar",
        "44100",
        "-ac",
        "2",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"FFmpeg exited with code {completed.returncode}"
        raise RuntimeError(f"Could not decode the source audio for UVR: {detail}")
    _validate_wav(destination)


def main() -> int:
    args = parse_args()
    source = args.input.expanduser().resolve()
    vocals_output = args.vocals_output.expanduser().resolve()
    instrumental_output = args.instrumental_output.expanduser().resolve()
    model_dir = args.model_dir.expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError("Choose a supported MP3, WAV, FLAC, OGG or M4A input file.")
    if vocals_output.suffix.lower() != ".wav" or instrumental_output.suffix.lower() != ".wav":
        raise ValueError("UVR outputs must end in .wav")
    if vocals_output == instrumental_output:
        raise ValueError("UVR stem outputs must be different files.")

    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    ffmpeg = _add_ffmpeg_to_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg was not found. Install FFmpeg or add ffmpeg.exe to PATH.")

    emit("status", message=f"Loading UVR model {args.model}...")
    try:
        import torch
        from audio_separator.separator import Separator
    except Exception as exc:
        raise RuntimeError("UVR separation runtime is incomplete. Run Install / repair UVR again.") from exc

    cuda = bool(torch.cuda.is_available())
    backend = "CUDA" if cuda else "CPU"
    if cuda:
        device_name = torch.cuda.get_device_name(0)
        emit("status", message=f"Using {device_name} with CUDA autocast.")
    else:
        emit("status", message="CUDA is unavailable; using CPU separation (this will be much slower).")

    model_dir.mkdir(parents=True, exist_ok=True)
    output_parent = vocals_output.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".musicalscumme-uvr-", dir=output_parent) as temporary_text:
        temporary = Path(temporary_text)
        decoded_source = temporary / "musicalscumme_source_pcm.wav"
        emit("status", message="Decoding source to a stable PCM WAV...")
        _decode_to_pcm_wav(ffmpeg, source, decoded_source)
        separator = Separator(
            log_level=logging.WARNING,
            model_file_dir=str(model_dir),
            output_dir=str(temporary),
            output_format="WAV",
            use_soundfile=True,
            use_autocast=cuda,
            mdxc_params={
                "segment_size": 256,
                "override_model_segment_size": False,
                "batch_size": 1,
                "overlap": 8,
                "pitch_shift": 0,
            },
        )
        separator.load_model(model_filename=args.model)
        emit("status", message="Separating vocals and instrumental... This can take several minutes.")
        output_names = {"Vocals": "musicalscumme_vocals", "Instrumental": "musicalscumme_instrumental"}
        separator.separate(str(decoded_source), output_names)
        generated_vocals = _locate_generated_stem(temporary, output_names["Vocals"], "Vocals")
        generated_instrumental = _locate_generated_stem(
            temporary, output_names["Instrumental"], "Instrumental"
        )
        _atomic_publish(generated_vocals, vocals_output)
        _atomic_publish(generated_instrumental, instrumental_output)

    emit(
        "complete",
        operation="separation",
        model=args.model,
        backend=backend,
        vocals=str(vocals_output),
        instrumental=str(instrumental_output),
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        emit("error", message=str(exc), error_type=type(exc).__name__)
        raise SystemExit(1) from exc
