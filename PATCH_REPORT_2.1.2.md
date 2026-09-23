# MusicalScumme 2.1.2 audio runtime repair

## Failure

The v2.1.1 installer completed the large Basic Pitch/TensorFlow download, then validation failed with:

```text
ModuleNotFoundError: No module named 'pkg_resources'
```

## Root cause

The bootstrap step upgraded setuptools to 83.0.0. setuptools 82 and newer removed `pkg_resources`. Basic Pitch 0.4.0 installs resampy 0.4.2, which still imports `pkg_resources` during Basic Pitch inference startup.

## Repair

Version 2.1.2 pins setuptools 80.10.2 inside the optional audio virtual environment and enforces that pin with a constraints file. Rerunning the installer repairs the existing environment in place, so the already-downloaded TensorFlow and Basic Pitch packages are retained.

Run:

```powershell
.\install_audio_tools.ps1
```

Or double-click `Repair Audio Tools.bat`. The standalone `Repair Existing Audio Runtime v2.1.2.bat` performs only the compatibility repair and validation. Do not use `-Reinstall` for this failure unless the runtime is otherwise corrupted.

## Scope

The pin does not change the user's system Python, PATH, main MusicalScumme environment, or SCUM.
