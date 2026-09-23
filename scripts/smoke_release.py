"""Check a Windows release in offscreen dry-run mode, including duplicate launch."""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("data_directory", type=Path)
    args = parser.parse_args()
    executable = args.executable.resolve(strict=True)
    data = args.data_directory.resolve()
    data.mkdir(parents=True, exist_ok=False)
    (data / "settings.json").write_text(json.dumps({
        "input_mode": "dry_run", "last_file": "", "recent_files": [],
        "performance_preset": "custom",
    }), encoding="utf-8")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", MUSICALSCUMME_DATA_DIR=str(data))
    first = subprocess.Popen([str(executable)], env=env, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        time.sleep(8)
        assert first.poll() is None, "Primary release exited during startup"
        second = subprocess.run([str(executable)], env=env, timeout=20,
                                creationflags=subprocess.CREATE_NO_WINDOW, check=False)
        assert second.returncode == 0, f"Duplicate launch exited with {second.returncode}"
        assert first.poll() is None, "Duplicate launch terminated the primary"
        log = (data / "musical_scumme.log").read_text(encoding="utf-8")
        assert "ignoring duplicate launch" in log
        assert "ERROR" not in log and "CRITICAL" not in log, log
        print("PASS: eight-second startup; duplicate exits cleanly; primary remains alive; no logged errors")
    finally:
        if first.poll() is None:
            # Only the process tree created above, never an existing user player.
            subprocess.run(["taskkill", "/PID", str(first.pid), "/T", "/F"],
                           capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            first.wait(timeout=10)


if __name__ == "__main__":
    main()
