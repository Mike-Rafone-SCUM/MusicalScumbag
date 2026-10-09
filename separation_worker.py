"""Isolated UVR-compatible two-stem separation worker for MusicalScumme."""

from __future__ import annotations

import argparse
import gc
import inspect
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".ogg", ".wav", ".flac", ".m4a"}
EXPECTED_STEMS = ("Vocals", "Instrumental")
QUALITY_PRESETS = {"fast": (4, (0.0,)), "balanced": (8, (0.0,)), "best": (12, (0.0, 0.37, 0.73))}
CLEANUP_PRESETS = ("none", "dereverb", "full")
# These stereo 44.1 kHz, `dry`-target models are in audio-separator 0.44.3's
# bundled registry. The DeEcho/DeReverb model is trained on vocals, including
# harmony removal: applying it to the band would erase real instruments.
DEREVERB_MODEL = "dereverb-echo_mel_band_roformer_sdr_13.4843_v2.ckpt"
DENOISE_MODEL = "denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt"
DENOISE_BLEND = 0.75
INFERENCE_SEGMENT_SIZE = 256
INFERENCE_HOP_LENGTH = 441
INFERENCE_SEGMENT_SECONDS = INFERENCE_HOP_LENGTH * (INFERENCE_SEGMENT_SIZE - 1) / 44100


def _overlap_value(demix, quality):
    # audio-separator 0.44.3 RoFormer uses seconds between windows;
    # newer implementations use the documented number of overlapping windows.
    implementation = inspect.getsource(demix)
    if "desired_step = int(self.overlap *" in implementation:
        return {"fast": 4.0, "balanced": 2.0, "best": 1.0}[quality]
    return QUALITY_PRESETS[quality][0]


def emit(event: str, **payload: object) -> None:
    print(json.dumps({"event": event, **payload}, ensure_ascii=True), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Separate a song into UVR vocals and instrumental stems.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--vocals-output", required=True, type=Path)
    parser.add_argument("--instrumental-output", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--quality", choices=QUALITY_PRESETS, default="best")
    parser.add_argument("--cleanup", choices=CLEANUP_PRESETS, default="none")
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
            audio.setpos(audio.getnframes() - 1)
            if len(audio.readframes(1)) != audio.getnchannels() * audio.getsampwidth():
                raise RuntimeError(f"UVR produced a truncated WAV stem: {path.name}")
    except (OSError, EOFError, wave.Error) as exc:
        raise RuntimeError(f"UVR produced an unreadable WAV stem: {path.name}") from exc


def _decode_to_pcm_wav(ffmpeg: str, source: Path, destination: Path) -> None:
    candidate_commands = [
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(source), "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(destination)],
        [ffmpeg, "-y", "-i", str(source), "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(destination)],
        [ffmpeg, "-y", "-i", str(source), "-ar", "44100", "-ac", "2", str(destination)],
    ]
    last_error = ""
    for command in candidate_commands:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if completed.returncode == 0 and destination.is_file() and destination.stat().st_size > 44:
            _validate_wav(destination)
            return
        last_error = completed.stderr.strip() or f"FFmpeg exited with code {completed.returncode}"
    raise RuntimeError(f"Could not decode the source audio for UVR: {last_error}")


def _aligned_average(predictions, offsets, frames):
    """Undo inference padding exactly, rejecting truncated or nonfinite predictions."""
    import numpy as np

    if not predictions or len(predictions) != len(offsets):
        raise RuntimeError("Missing separation passes.")
    result = None
    for prediction, offset in zip(predictions, offsets, strict=True):
        aligned = prediction[offset:offset + frames]
        if len(aligned) != frames or not np.isfinite(aligned).all():
            raise RuntimeError("Separation produced truncated or nonfinite audio.")
        if result is None:
            result = aligned.astype(np.float64)
        elif aligned.shape != result.shape:
            raise RuntimeError("Separation passes have inconsistent channels.")
        else:
            result += aligned
    return (result / len(predictions)).astype(np.float32)


def _separate_passes(separator, decoded_source, temporary, quality):
    import numpy as np
    import soundfile as sf

    mix, rate = sf.read(decoded_source, always_2d=True, dtype="float32")
    offsets = [round(seconds * rate) for seconds in QUALITY_PRESETS[quality][1]]
    predictions = {stem: [] for stem in EXPECTED_STEMS}
    for index, offset in enumerate(offsets):
        emit("status", message=f"Separation pass {index + 1}/{len(offsets)} ({quality})...", progress=index / len(offsets))
        padded = temporary / f"pass_{index}.wav"
        # The pinned RoFormer implementation cannot overlap-add clips shorter
        # than its window. Keep the model window intact, then trim exactly.
        tail = max(0, 12 * rate - len(mix) - offset)
        sf.write(padded, np.pad(mix, ((offset, tail), (0, 0))), rate, subtype="FLOAT")
        names = {stem: f"pass_{index}_{stem.lower()}" for stem in EXPECTED_STEMS}
        separator.separate(str(padded), names)
        for stem in EXPECTED_STEMS:
            path = _locate_generated_stem(temporary, names[stem], stem)
            audio, stem_rate = sf.read(path, always_2d=True, dtype="float32")
            if stem_rate != rate or audio.shape[1] != mix.shape[1]:
                raise RuntimeError("Separation changed the sample rate or channel count.")
            predictions[stem].append(audio)
    generated = []
    for stem in EXPECTED_STEMS:
        audio = _aligned_average(predictions[stem], offsets, len(mix))
        path = temporary / f"final_{stem.lower()}.wav"
        sf.write(path, audio, rate, subtype="PCM_24")
        _validate_wav(path)
        generated.append(path)
    return generated


def _release_model(separator) -> None:
    """Drop weights before loading the next stage, including on stage failure."""
    separator.model_instance = None
    gc.collect()
    torch = sys.modules.get("torch")
    if torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()


def _loaded_model_device(separator) -> str:
    device = str(next(separator.model_instance.model_run.parameters()).device)
    torch = sys.modules.get("torch")
    if torch is not None and torch.cuda.is_available() and not device.startswith("cuda"):
        raise RuntimeError("UVR selected CUDA but the learned model was not loaded on CUDA.")
    return device


def _configure_numba_cache(model_dir: Path) -> Path:
    """Avoid Windows' repeated permission retries in library __pycache__ dirs."""
    cache = model_dir / ".musicalscumme-numba-cache"
    probe = cache / f".write-check-{os.urandom(8).hex()}"
    try:
        cache.mkdir(parents=True, exist_ok=True)
        # Path.open raises immediately for a denied directory. Windows'
        # tempfile helper can otherwise retry tens of thousands of names.
        with probe.open("xb") as output:
            output.write(b"ready")
    except OSError as exc:
        raise RuntimeError(f"The UVR inference cache is not writable: {cache}") from exc
    finally:
        if probe.is_file():
            probe.unlink()
    os.environ["NUMBA_CACHE_DIR"] = str(cache.resolve())
    return cache


def _run_treatment_stage(separator, source: Path, temporary: Path, *, stage: str,
                         model: str, blend: float) -> Path:
    """Run a learned vocal stage and trim only the explicit trailing padding."""
    import numpy as np
    import soundfile as sf

    audio, rate = sf.read(source, always_2d=True, dtype="float32")
    if rate != 44100 or audio.shape[1] != 2 or not len(audio) or not np.isfinite(audio).all():
        raise RuntimeError("Vocal cleanup requires finite synchronized 44.1 kHz stereo stems.")
    if not 0 < blend <= 1:
        raise ValueError("Invalid vocal cleanup blend.")
    stage_dir = temporary / stage
    stage_dir.mkdir()
    padded = stage_dir / "input.wav"
    # Keep the real model window intact for short test clips and final tails.
    padded_frames = max(len(audio), 12 * rate)
    sf.write(padded, np.pad(audio, ((0, padded_frames - len(audio)), (0, 0))), rate, subtype="FLOAT")
    name = f"vocal_{stage}_dry"
    emit("status", message=f"Vocal {stage}: loading {model} and processing the learned dry stem...")
    _release_model(separator)
    separator.output_dir = str(stage_dir)
    separator.output_single_stem = "dry"
    # A 256-frame window is ~2.55 s for these models. Keep one inference window
    # on the GPU at a time, leaving room for the user's open game and overlay.
    if hasattr(separator, "arch_specific_params"):
        separator.arch_specific_params["MDXC"] = {
            **separator.arch_specific_params["MDXC"], "segment_size": INFERENCE_SEGMENT_SIZE,
            "override_model_segment_size": True, "batch_size": 1,
        }
    try:
        separator.load_model(model_filename=model)
        device = _loaded_model_device(separator)
        emit("status", message=f"Vocal {stage} uses {INFERENCE_SEGMENT_SIZE}-frame ({INFERENCE_SEGMENT_SECONDS:.2f}s) windows on {device}.")
        separator.separate(str(padded), {"dry": name})
        generated = _locate_generated_stem(stage_dir, name, "dry")
        dry, output_rate = sf.read(generated, always_2d=True, dtype="float32")
        if output_rate != rate or dry.shape != (padded_frames, audio.shape[1]):
            raise RuntimeError("Learned cleanup changed the sample rate, channels or frame count.")
        if not np.isfinite(dry).all():
            raise RuntimeError("Learned cleanup produced nonfinite audio.")
        treated = blend * dry[:len(audio)] + (1 - blend) * audio
        # PCM export must never clip a learned prediction silently.
        if np.max(np.abs(treated)) > 1.0:
            raise RuntimeError("Learned cleanup produced clipping audio.")
        destination = stage_dir / "synchronized.wav"
        sf.write(destination, treated, rate, subtype="PCM_24")
        _validate_wav(destination)
        return destination
    except (Exception, SystemExit) as exc:
        raise RuntimeError(f"UVR vocal {stage} failed; cleaned stems were not published: {exc}") from exc
    finally:
        _release_model(separator)


def _treat_vocals(separator, vocals: Path, temporary: Path, cleanup: str):
    """Treat the vocal only, retaining the complete untreated band separately."""
    if cleanup not in CLEANUP_PRESETS:
        raise ValueError("Unknown vocal cleanup preset.")
    treatment = []
    for stage, model, blend in (
        ("dereverb", DEREVERB_MODEL, 1.0),
        ("denoise", DENOISE_MODEL, DENOISE_BLEND),
    ):
        if cleanup == "none" or stage == "denoise" and cleanup != "full":
            continue
        vocals = _run_treatment_stage(separator, vocals, temporary, stage=stage, model=model, blend=blend)
        treatment.append({"stage": stage, "model": model, "stems": ["vocals"], "blend": blend})
    return vocals, treatment


def _raw_stem_path(destination: Path) -> Path:
    return destination.with_name(f"{destination.stem}.raw.wav")


def _stat_record(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {"path": str(path.resolve()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _wav_record(path: Path) -> dict[str, object]:
    _validate_wav(path)
    with wave.open(str(path), "rb") as audio:
        return {**_stat_record(path), "rate": audio.getframerate(),
                "frames": audio.getnframes(), "channels": audio.getnchannels()}


def _validate_output_paths(source: Path, vocals: Path, instrumental: Path, cleanup: str) -> list[Path]:
    outputs = [vocals, instrumental]
    if cleanup != "none":
        outputs += [_raw_stem_path(vocals), _raw_stem_path(instrumental)]
    if len(set(outputs)) != len(outputs):
        raise ValueError("Final and raw stem outputs must use different files.")
    if source in outputs:
        raise ValueError("Final and raw stem outputs must not overwrite the source audio.")
    return outputs


def _publish_stems(source_metadata, generated: list[Path], destinations: list[Path], *,
                   model: str, quality: str, cleanup: str, treatment) -> Path:
    """Validate every synchronized stage before publishing any WAV or receipt."""
    if len(generated) != len(destinations):
        raise ValueError("Missing generated UVR output.")
    records = [_wav_record(path) for path in generated]
    headers = {(r["rate"], r["frames"], r["channels"]) for r in records}
    if len(headers) != 1:
        raise RuntimeError("UVR outputs lost synchronization; no stems were published.")
    if _stat_record(Path(source_metadata["path"])) != source_metadata:
        raise RuntimeError("Source audio changed during separation; no stems were published.")
    for candidate, destination in zip(generated, destinations, strict=True):
        _atomic_publish(candidate, destination)
    sidecar = destinations[0].with_suffix(".uvr.json")
    metadata = {"version": 1, "source": source_metadata, "model": model,
                "quality": quality, "cleanup": cleanup, "treatment": treatment,
                "segment_size": INFERENCE_SEGMENT_SIZE,
                "segment_seconds": INFERENCE_SEGMENT_SECONDS,
                "outputs": [_wav_record(path) for path in destinations]}
    temporary = sidecar.with_suffix(".json.tmp")
    try:
        temporary.write_text(json.dumps(metadata, ensure_ascii=True, indent=2), encoding="utf-8")
        temporary.replace(sidecar)
    finally:
        temporary.unlink(missing_ok=True)
    return sidecar


def _preserve_raw_stems(source_metadata, generated: list[Path], destinations: list[Path]) -> None:
    """Save the expensive base inference even if a later learned stage fails."""
    records = [_wav_record(path) for path in generated]
    if len(records) != 2 or len({(r["rate"], r["frames"], r["channels"]) for r in records}) != 1:
        raise RuntimeError("Raw UVR stems lost synchronization; no raw stems were published.")
    if _stat_record(Path(source_metadata["path"])) != source_metadata:
        raise RuntimeError("Source audio changed during separation; no raw stems were published.")
    for candidate, destination in zip(generated, destinations, strict=True):
        _atomic_publish(candidate, destination)
    emit("status", message="Untreated raw WAV stems saved for comparison; learned vocal cleanup is still pending.")


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
    if source in (vocals_output, instrumental_output):
        raise ValueError("Stem outputs must not overwrite the source audio.")
    destinations = _validate_output_paths(source, vocals_output, instrumental_output, args.cleanup)
    source_metadata = _stat_record(source)

    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    ffmpeg = _add_ffmpeg_to_path()
    if not ffmpeg:
        raise RuntimeError("FFmpeg was not found. Install FFmpeg or add ffmpeg.exe to PATH.")

    emit("status", message=f"Loading UVR model {args.model}...")
    _configure_numba_cache(model_dir)
    try:
        import torch
        from audio_separator.separator import Separator
        from audio_separator.separator.architectures.mdxc_separator import MDXCSeparator
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
            normalization_threshold=1.0,
            amplification_threshold=0.0,
            mdxc_params={
                "segment_size": INFERENCE_SEGMENT_SIZE,
                "override_model_segment_size": True,
                "batch_size": 1,
                "overlap": _overlap_value(MDXCSeparator.demix, args.quality),
                "pitch_shift": 0,
            },
        )
        separator.load_model(model_filename=args.model)
        model_device = _loaded_model_device(separator)
        emit("status", message=f"Inference uses {INFERENCE_SEGMENT_SIZE}-frame ({INFERENCE_SEGMENT_SECONDS:.2f}s) windows on {model_device}.")
        emit("status", message="Separating vocals and instrumental... This can take several minutes.")
        generated_vocals, generated_instrumental = _separate_passes(separator, decoded_source, temporary, args.quality)
        _release_model(separator)
        if args.cleanup != "none":
            # A previous receipt must not advertise the new raw pair as a
            # successfully cleaned result if a later stage fails.
            vocals_output.with_suffix(".uvr.json").unlink(missing_ok=True)
            _preserve_raw_stems(source_metadata, [generated_vocals, generated_instrumental], destinations[2:])
        treated_vocals, treatment = _treat_vocals(separator, generated_vocals, temporary, args.cleanup)
        generated = [treated_vocals, generated_instrumental]
        if args.cleanup != "none":
            generated += [generated_vocals, generated_instrumental]
        sidecar = _publish_stems(source_metadata, generated, destinations, model=args.model,
                                 quality=args.quality, cleanup=args.cleanup, treatment=treatment)

    emit(
        "complete",
        operation="separation",
        model=args.model,
        backend=backend,
        quality=args.quality,
        segment_size=INFERENCE_SEGMENT_SIZE,
        segment_seconds=INFERENCE_SEGMENT_SECONDS,
        cleanup=args.cleanup,
        treatment=treatment,
        raw_vocals=str(destinations[2]) if args.cleanup != "none" else None,
        raw_instrumental=str(destinations[3]) if args.cleanup != "none" else None,
        provenance=str(sidecar),
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
