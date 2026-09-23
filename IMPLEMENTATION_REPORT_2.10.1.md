# MusicalScumme 2.10.1 implementation report

Date: 2026-07-18

## Outcome

Version 2.10.1 makes untouched MIDI downloads the clear primary workflow, fixes standards-compliant MIDI note release handling, keeps both main-window panes usable at the maintained 1080×720 size, and closes a Pause/Stop input-cleanup race. It preserves SCUM bindings, mapping policy, supervised playback, optional conversion tools, and the existing architecture boundaries.

## Original MIDI workflow

- The primary row now asks for the original `.mid` or `.midi` file and presents **Open MIDI** as the main action.
- Song Transposer and Audio to MIDI remain available from the File menu instead of competing with direct MIDI import.
- Source files remain read-only: three representative `[MIDIfind.com]` downloads retained identical SHA-256 hashes across parse, analysis, arrangement, and planning.
- The real-file sample covered 3-15 tracks, 452-8,473 source notes, 110-421 seconds, melody/support/bass recommendation, dense and chordal analysis, and 365-1,696 planned notes. Every produced plan ended with a balanced key state.

## MIDI correctness

- Every legal `note_off` now closes its active note regardless of release velocity.
- Sustain still defers that closure until pedal release.
- A zero-velocity `note_on` retains its standard note-release meaning.
- Regression tests cover ordinary non-zero release velocity, non-zero release velocity under sustain, zero-velocity `note_on`, and source-byte preservation.

## Responsive main window

- The left workflow pane now scrolls independently when vertical room is tight.
- Playback-range controls use compact rows, long forms wrap, and combo boxes no longer force the splitter wider than the window.
- At 1080×720, the offscreen geometry test retains the requested window size, allocates 613 px to the source pane and 435 px to settings, and shows no settings-pane horizontal scrollbar.
- Main-window, Audio to MIDI, and Song Transposer construction remain covered offscreen.

## Scheduler cleanup safety

- Backend batch dispatch and cleanup now share the scheduler lock.
- Pause and Stop recheck their state inside that lock before a pending batch can send.
- A deterministic blocking-backend regression races Pause against an in-flight key-down and proves that Pause returns only after the final key state is empty.
- A real Interstellar MIDI with overlapping Play and Omit ranges resolved to 10-25 s, 30-60 s, and 68-90 s. From 452 selected notes it produced 222 fragments, dropped 230 notes, clipped 17, and built 150 planned notes / 300 events / 300 batches with a balanced final key state.

## Validation and package

- `python -m compileall -q .` passed.
- `python -m pytest` passed all 114 tests with `QT_QPA_PLATFORM=offscreen`.
- `ruff check .` passed.
- `build_exe.ps1 -OutputRoot release-staging\2.10.1` produced the standard Windows onedir package with PyInstaller 6.21.0 and Python 3.12.10.
- The staged bundle contains 236 files / 120,583,252 bytes. All required audio installer, validator, worker, and requirements resources are present.
- The packaged executable remained alive through an eight-second hidden/offscreen startup with isolated settings and logged a clean `Starting MusicalScumme 2.10.1` line.
- `MusicalScumme-2.10.1-Windows.zip` passed a complete 240-entry read-through with one `MusicalScumme/` root, no backslash paths, no CRC failure, and no missing required resources. ZIP size: 49,431,745 bytes. SHA-256: `ad61381e6ec4a99c85d6c94b3c9c55c2a1a19b4d9a0397cf3ac3c890382f7bd8`.
- This build is not SCUM tested until playback, focus-loss cleanup, Pause/Stop, and F8 are supervised in the current Windows game build. No audio pipeline code changed; fresh MP3/WAV/M4A conversion was outside this release's direct-MIDI scope.
