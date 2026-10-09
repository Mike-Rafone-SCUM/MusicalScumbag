from __future__ import annotations

import argparse
import importlib.metadata as metadata
import logging
import os
import platform
import warnings
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate MusicalScumme's isolated Basic Pitch runtime."
    )
    parser.add_argument(
        "--expected-setuptools",
        default="80.10.2",
        help="Required setuptools version for pkg_resources compatibility.",
    )
    return parser.parse_args()


def installed_version(distribution: str) -> str:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError as exc:
        raise SystemExit(f"Required package is not installed: {distribution}") from exc


def validate_model_path(model_path: Path) -> None:
    """Accept a model file or a complete TensorFlow SavedModel directory."""

    if model_path.is_file():
        return
    if model_path.is_dir() and (model_path / "saved_model.pb").is_file():
        return
    raise SystemExit(f"Basic Pitch model is missing or incomplete: {model_path}")


def main() -> int:
    args = parse_args()

    # Keep validation output focused on actionable failures. These settings are applied
    # before importing TensorFlow through Basic Pitch.
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    logging.basicConfig(level=logging.ERROR)
    warnings.filterwarnings(
        "ignore",
        message="pkg_resources is deprecated as an API.*",
        category=UserWarning,
    )

    setuptools_version = installed_version("setuptools")
    if setuptools_version != args.expected_setuptools:
        raise SystemExit(
            "Incompatible setuptools version: "
            f"expected {args.expected_setuptools}, found {setuptools_version}"
        )

    # resampy 0.4.2 still imports this module while Basic Pitch 0.4.0 starts.
    import mido  # noqa: PLC0415
    import pkg_resources  # noqa: F401, PLC0415
    from basic_pitch.inference import ICASSP_2022_MODEL_PATH, predict  # noqa: PLC0415

    if not hasattr(mido, "MidiFile"):
        raise SystemExit("Mido imported but its MIDI reader is unavailable.")

    if not callable(predict):
        raise SystemExit("Basic Pitch inference entry point is unavailable.")

    model_path = Path(ICASSP_2022_MODEL_PATH)
    validate_model_path(model_path)

    print(
        "Audio runtime validated:",
        f"Python={platform.python_version()}",
        f"BasicPitch={installed_version('basic-pitch')}",
        f"Mido={installed_version('mido')}",
        f"Setuptools={setuptools_version}",
        f"Model={model_path.name}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
