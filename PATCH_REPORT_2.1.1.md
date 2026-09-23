# MusicalScumme 2.1.1 audio installer repair

## Failure

The v2.1.0 installer checked `py -3.10` and `py -3.11` while `$ErrorActionPreference` was set to `Stop`. On a machine with `py.exe` installed but no matching interpreter, the launcher wrote `No suitable Python runtime found` to stderr. PowerShell promoted that expected probe failure into a terminating `NativeCommandError`, so the script stopped before checking any fallback.

## Repair

- Compatible interpreter probes now suppress native stderr and inspect the actual exit code.
- Detection covers an explicit `-PythonPath`, a previous MusicalScumme private runtime, `py -3.11`, `py -3.10`, PATH, and standard per-user/system Python folders.
- If none exists, the installer downloads the official Python 3.11.9 64-bit Windows installer.
- The downloaded installer must have a valid Authenticode signature from the Python Software Foundation before execution.
- Python is installed privately under `%LOCALAPPDATA%\MusicalScumme\python-3.11.9` without PATH, association, shortcut, launcher, or administrator changes.
- Broken/incomplete audio virtual environments are automatically rebuilt.
- Full installer output is retained under `%LOCALAPPDATA%\MusicalScumme\logs\audio-tools-install.log`.

## Controls

```powershell
# Normal install; self-bootstraps Python when needed
.\install_audio_tools.ps1

# Rebuild only the isolated audio environment
.\install_audio_tools.ps1 -Reinstall

# Force a specific compatible interpreter
.\install_audio_tools.ps1 -PythonPath "C:\Path\To\Python311\python.exe"

# Do not permit automatic Python bootstrap
.\install_audio_tools.ps1 -NoBootstrap
```

## Validation boundary

The Python project compiles and all automated tests pass. The PowerShell/bootstrap path cannot be executed in the Linux build environment, so the signed installer download, Windows silent installation, and Basic Pitch dependency installation still require confirmation on Windows.
