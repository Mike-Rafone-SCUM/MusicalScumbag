# MusicalScumme 2.10.0 implementation report

Date: 2026-07-17

## Outcome

Version 2.10.0 improves daily file and section editing while closing a UI-state gap during active playback. It does not change MIDI parsing, musical selection, SCUM mappings, keyboard event timing, or scheduler execution.

## Active-playback state safety

- File loading, reload, drag/drop, audio conversion, Song Transposer, track selection, playback ranges, key profiles, input mode, conversion policy, mapping, timing, export, and settings reset are disabled while the scheduler runs.
- `load_file`, drag/drop, and both conversion-dialog entry points retain direct guards so a shortcut or future caller cannot bypass the widget lock.
- Pause, Stop, F8, focus-loss handling, application exit, and key cleanup remain available.
- Completion or stop restores the controls without changing the project or prepared plan.

## Recent MIDI workflow

- The File menu lists the ten most recently loaded MIDI files, newest first.
- Only successful loads are recorded. Resolved paths are deduplicated and persisted in the existing atomic settings file.
- A temporarily missing file stays visible but disabled instead of being removed automatically.
- The menu includes a clear action. Ctrl+O opens a MIDI and Ctrl+R reloads the current file.

## Playback-section editing

- Selecting a range loads its source start and end into the existing time editors.
- **Update selected** replaces the boundaries without changing the range's Play/Omit role or label.
- The replacement is sorted back into source order, invalidates the old plan, and is persisted for that MIDI.
- Remove remains selection-dependent and Clear ranges retains the full-song fallback.

## Validation

- The pre-change baseline passed all 109 tests in the project build environment.
- Focused config/UI checks passed after implementation.
- The expanded suite passes 111 tests, including offscreen construction of the main window, Audio to MIDI dialog, and Song Transposer dialog.
- Compileall and Ruff pass for the changed source and tests.
- `build_exe.ps1 -OutputRoot release-staging\2.10.0` produced the standard Windows onedir application with PyInstaller 6.21.0 and Python 3.12.10.
- The staged folder contains 236 files / 120,582,311 bytes. Recursive archive inspection found the UI, config, playback-section, scheduler, input, analyser, planner, Song Transposer, audio, and separation modules plus every required worker, installer, validator, and requirements file.
- The packaged EXE remained alive through a six-second hidden/offscreen smoke launch using isolated temporary settings.
- The packaged Basic Pitch validator passed under isolated Python 3.11.9 with Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model. The packaged separation validator passed with the CUDA RTX 2070 SUPER runtime, `audio-separator` 0.44.3, PyTorch 2.11.0+cu128, ONNX Runtime GPU 1.27.0, FFmpeg, and the Viperx model/config.
- The packaged audio worker converted representative five-second MP3, WAV, and AAC/M4A inputs into strict 23-note MIDI files without optional-backend warnings, TensorFlow banner noise, malformed Unicode, or worker errors. Guitar / arpeggio cleanup retained 20 notes; Optimal Sounding produced 20 planned notes / 64 events and a balanced 20-row SCUM-score CSV.
- `MusicalScumme_2.10.0_Windows.zip` passed a complete 236-entry / 120,582,311-byte read-through with one `MusicalScumme/` root, no backslash paths, and all required resources. ZIP size: 49,430,942 bytes. SHA-256: `b8e92693f0ca34cc117ea6e35a23a093e01d120214b71a597539992e8b42ff83`.
- The regenerated source `SHA256SUMS.txt` contains 94 verified entries and includes this 2.10.0 implementation report while excluding environments, caches, builds, and staged releases.
- The executable is not Authenticode-signed. Current-build SCUM audition remains required before calling the release SCUM tested.
