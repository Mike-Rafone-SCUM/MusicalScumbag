# Agent Instructions

Read `PROJECT_CONTEXT.md` before modifying this project.

## Priorities

1. Preserve safety and current working behaviour.
2. Keep MIDI parsing, intelligent arrangement, SCUM planning, input, scheduler, audio transcription, and UI separated.
3. Add or update tests for every behavioural change.
4. Prefer full, explicit fixes over UI-only workarounds.
5. Update `PROJECT_CONTEXT.md` with durable decisions, confirmed SCUM changes, bugs, mappings, and do-not-change rules.
6. Keep the optional Basic Pitch runtime out of the main application environment and process.

## Mandatory safety boundaries

Do not add game injection, memory access, DLL hooks, anti-cheat bypasses, stealth/evasion, unattended gameplay, combat automation, or automatic game-file edits. MusicalScumme is limited to transparent instrument keyboard playback initiated and supervised by the user.

Audio conversion may read a user-selected audio file and write a user-confirmed MIDI destination only. It must never send input or alter SCUM.

## Architecture boundaries

- `midi_engine.py`: parse source MIDI only.
- `arranger.py`: musical simplification only; deterministic and testable.
- `planner.py`: map arranged notes to SCUM key/modifier events.
- `input_backend.py`: Windows input only.
- `scheduler.py`: timing, focus, pause, stop, cleanup.
- `audio_tools.py`: optional runtime discovery and command construction.
- `audio_worker.py`: isolated Basic Pitch inference and MIDI writing.
- `ui.py`: presentation and process orchestration; no heavy inference or direct worker-thread widget mutation.

## Before a release

Run:

```text
python -m compileall -q .
python -m pytest
ruff check .
```

Also construct the main window and audio dialog with `QT_QPA_PLATFORM=offscreen` when PySide6 is available.

A release is not “SCUM tested” until it has been run on Windows inside the current game build. Audio conversion is not “validated” until Basic Pitch has been installed and tested on Windows with representative MP3, WAV, and M4A files. State those limitations plainly.

- Do not block the Qt GUI thread with process wait calls; use `QProcess` signals and stream output asynchronously.
