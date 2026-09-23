# MusicalScumme 2.2.1 patch report

## Fixed failure

The packaged 2.2.0 installer correctly created and populated the Python 3.11 Basic Pitch environment, then failed validation with:

```text
ImportError: Module use of python312.dll conflicts with this version of Python.
```

The Python 3.11 process was executing a validator stored in PyInstaller's Python 3.12 `_internal` directory. Normal script startup added that directory to `sys.path`, so `socket` loaded the packaged Python 3.12 `_socket.pyd` instead of Python 3.11's extension.

## Repair

- All relevant child-Python operations now use isolated mode.
- Audio conversion itself uses the same protection as installation and validation.
- The validator accepts Basic Pitch's TensorFlow SavedModel directory.
- A readiness marker prevents a failed validation from appearing as an installed audio feature.
- Existing Basic Pitch and TensorFlow downloads are repaired in place.

## Preserved behaviour

- Python 3.10/3.11 remains isolated from the main app environment.
- `setuptools==80.10.2` remains pinned only inside the audio runtime.
- Python bootstrap remains signed, per-user, non-PATH, and non-admin.
- Qt process orchestration remains asynchronous.
- No SCUM playback, binding, planner, input, safety, or UI-layout behaviour changed.

## Validation

- Python compilation passed.
- 42 tests passed.
- Ruff passed.
- Both Qt windows constructed offscreen.
- The Windows onedir package built successfully.
- The installer bundled in the new Python 3.12 package validated the existing Python 3.11 Basic Pitch runtime from `_internal`.
- The packaged worker started in isolated mode and the packaged EXE passed a hidden launch smoke test.
