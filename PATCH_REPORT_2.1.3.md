# MusicalScumme 2.1.3 audio validation repair

## Failure

The v2.1.2 dependency repair completed successfully, but its final validation failed with:

```text
NameError: name 'basic' is not defined
```

## Root cause

The validation program itself was valid Python. The problem was how it was transported: Windows PowerShell 5.1 passed a multiline program through `python -c` and removed the embedded quotes around `"basic-pitch"`. Python therefore received the equivalent of:

```python
metadata.version(basic-pitch)
```

instead of:

```python
metadata.version("basic-pitch")
```

The installed audio runtime was already present and usable; only the validation command was corrupted.

## Repair

Version 2.1.3 adds `validate_audio_runtime.py` and runs that file directly. The installer and standalone repair script now share this validator, eliminating fragile nested command-line quoting.

The validator checks:

- the exact compatible setuptools version;
- `pkg_resources` availability;
- Mido installation;
- Basic Pitch inference import;
- the bundled Basic Pitch model file;
- installed Python, Basic Pitch, Mido, and setuptools versions.

## Run

No redownload is required. Run:

```powershell
.\install_audio_tools.ps1
```

or double-click:

```text
Repair Existing Audio Runtime v2.1.3.bat
```

Do not use `-Reinstall` for this error.
