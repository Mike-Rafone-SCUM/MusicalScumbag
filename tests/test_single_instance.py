import subprocess
import sys

from musical_scumme.single_instance import acquire_instance_lock


def test_duplicate_launch_is_rejected_until_owner_exits(tmp_path):
    owner = acquire_instance_lock(str(tmp_path))
    assert owner is not None
    try:
        assert acquire_instance_lock(str(tmp_path)) is None
    finally:
        owner.unlock()
    replacement = acquire_instance_lock(str(tmp_path))
    assert replacement is not None
    replacement.unlock()


def test_another_process_cannot_acquire_live_lock(tmp_path):
    owner = acquire_instance_lock(str(tmp_path))
    assert owner is not None
    try:
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; from musical_scumme.single_instance import acquire_instance_lock; "
             "assert acquire_instance_lock(sys.argv[1]) is None", str(tmp_path)],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, result.stderr
    finally:
        owner.unlock()


def test_crashed_process_does_not_block_restart(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c",
         "import os, sys; from musical_scumme.single_instance import acquire_instance_lock; "
         "lock = acquire_instance_lock(sys.argv[1]); assert lock is not None; os._exit(0)",
         str(tmp_path)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    recovered = acquire_instance_lock(str(tmp_path))
    assert recovered is not None
    recovered.unlock()


def test_duplicate_ui_start_never_constructs_window(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from musical_scumme import single_instance, ui

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(single_instance, "acquire_instance_lock", lambda: None)

    def unexpected_window():
        raise AssertionError("Duplicate launch constructed a MainWindow")

    monkeypatch.setattr(ui, "MainWindow", unexpected_window)
    assert ui.run() == 0
    assert QApplication.instance() is app
