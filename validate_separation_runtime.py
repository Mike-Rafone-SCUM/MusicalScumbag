from __future__ import annotations

import argparse
import json
import shutil
from importlib import metadata
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate MusicalScumme's isolated UVR separation runtime.")
    parser.add_argument("--runtime-dir", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--model", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    import onnxruntime
    import torch
    from audio_separator.separator import Separator  # noqa: F401

    model_stem = Path(args.model).stem
    model_files = sorted(path for path in args.model_dir.glob(f"{model_stem}.*") if path.is_file())
    if not model_files:
        raise RuntimeError(f"UVR model is missing from {args.model_dir}: {args.model}")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg and Path("C:/ffmpeg/bin/ffmpeg.exe").is_file():
        ffmpeg = "C:/ffmpeg/bin/ffmpeg.exe"
    if not ffmpeg:
        raise RuntimeError("FFmpeg was not found")
    cuda = bool(torch.cuda.is_available())
    backend = "cuda" if cuda else "cpu"
    payload = {
        "runtime": str(args.runtime_dir.resolve()),
        "audio_separator": metadata.version("audio-separator"),
        "torch": metadata.version("torch"),
        "onnxruntime_gpu": metadata.version("onnxruntime-gpu"),
        "backend": backend,
        "cuda_device": torch.cuda.get_device_name(0) if cuda else None,
        "onnx_providers": onnxruntime.get_available_providers(),
        "model": args.model,
        "model_files": [path.name for path in model_files],
        "ffmpeg": ffmpeg,
    }
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
