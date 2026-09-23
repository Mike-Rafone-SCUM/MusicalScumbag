from __future__ import annotations

import multiprocessing
import platform
import sys


def main() -> int:
    multiprocessing.freeze_support()
    from . import __version__
    from .logging_setup import configure_logging, install_exception_logging

    logger = configure_logging()
    install_exception_logging(logger)
    logger.info(
        "Starting MusicalScumbag %s on Python %s (%s)",
        __version__,
        platform.python_version(),
        platform.platform(),
    )
    try:
        from .ui import run
    except ImportError as exc:
        logger.exception("UI import failed")
        print("MusicalScumbag could not start.", file=sys.stderr)
        print("Install dependencies with: python -m pip install -r requirements.txt", file=sys.stderr)
        print(exc, file=sys.stderr)
        return 1
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
