"""Prevent duplicate UI and global-hotkey listeners within a user session."""

from pathlib import Path

from PySide6.QtCore import QLockFile, QStandardPaths


def acquire_instance_lock(directory: str | None = None) -> QLockFile | None:
    root = Path(directory or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericCacheLocation))
    root = root / "MusicalScumbag"
    root.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(root / "application.lock"))
    # A running player can remain open indefinitely. Qt still detects dead PIDs.
    lock.setStaleLockTime(0)
    if lock.tryLock(0):
        return lock
    if lock.error() == QLockFile.LockError.LockFailedError:
        return None
    raise RuntimeError(f"Cannot create application startup lock: {lock.error()}")
