"""Python-friendly wrapper for the PowerShell EXE build script.

Use: python build_exe.py [--one-file] [--clean-environment]
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if os.name != "nt":
        print("The MusicalScumbag Windows EXE must be built on Windows.", file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parent
    script = root / "build_exe.ps1"
    shell = shutil.which("pwsh.exe") or shutil.which("powershell.exe")
    if not shell:
        print("PowerShell was not found.", file=sys.stderr)
        return 2

    translated: list[str] = []
    for argument in sys.argv[1:]:
        if argument == "--one-file":
            translated.append("-OneFile")
        elif argument == "--clean-environment":
            translated.append("-CleanEnvironment")
        else:
            print(f"Unknown argument: {argument}", file=sys.stderr)
            return 2

    command = [
        shell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        *translated,
    ]
    return subprocess.call(command, cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())
