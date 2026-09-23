# MusicalScumme 2.9.0 implementation report

Date: 2026-07-16

## Outcome

Version 2.9.0 adds deterministic multi-range playback and reduces scheduler/input overhead without changing source conversion, SCUM mappings, focus safety, or the full-song result when no ranges are configured.

## Playback section model

`musical_scumme/playback_sections.py` owns source-time selection:

- Play ranges are merged into the included source-time union.
- With no Play ranges, the complete source duration is included.
- Omit ranges are merged and subtracted from the included union.
- Notes overlapping a retained interval are clipped to its boundaries.
- One sustained note crossing an omission may become two source-backed fragments.
- Resolved intervals are placed sequentially with a configurable 0-5000 ms gap.
- Saved ranges are validated and clipped to the loaded MIDI duration.

The transformed notes enter the normal arranger and planner. This intentionally avoids slicing a completed keyboard plan, which could otherwise inherit an unknown octave-bank state or incomplete release guards at a selection boundary.

## User interface

- Added a Playback sections table with Play/Omit action, source start, source end, and length.
- Added `HH:mm:ss.zzz` source-time controls and Add Play, Add Omit, Remove selected, and Clear ranges actions.
- Added a configurable inter-section/repeat gap and user-controlled Loop prepared playback option.
- Range state persists per resolved MIDI path.
- Prepare and Play labels explicitly change when ranges are active.
- Selection diagnostics report resolved interval count, original/dropped/clipped notes, source span, output span, and gap.
- Track, range, Prepare, and export controls are disabled while a plan is running.

## Scheduler and input performance

- Timestamp batches and integer nanosecond offsets are compiled once before countdown and reused for every loop.
- Equal-timestamp events are sent through one backend batch while preserving canonical order. Staggered events remain separate.
- The Windows backend caches key-name, virtual-key, scan-code, and base-flag resolution.
- Playback requests Windows 1 ms timer resolution only for the worker lifetime and restores it in `finally`.
- Looping reuses the immutable plan, performs countdown only once, releases all keys after every completed iteration, and retains Stop/F8/focus cleanup.
- Runtime metrics record events, batches, late events, average/max dispatch lateness, and completed loops.

A deterministic 100-triad zero-stagger fixture produces 600 key events in 200 Windows input batches, a 66.7% call reduction. Default monophonic Rush E and House plans have unique timestamps and therefore remain unbatched; their performance benefit comes from schedule precompilation, cached key resolution, and higher-resolution waits rather than artificial note coalescing.

## Static real-file result

The isolated House guitar transcription was prepared with:

- Play 30-50 seconds;
- Play 90-115 seconds;
- Omit 98-101 seconds;
- 500 ms gap.

It resolved to three intervals: 30-50 s, 90-98 s, and 101-115 s. From 1,328 source notes, 227 fragments remained, 1,101 notes were outside the selection, and 18 sustained notes crossed a boundary. The selected source span was 42 seconds and the rebased span was 43 seconds. Optimal Sounding retained 209 notes and emitted 418 events with a balanced final key state.

## Safety and compatibility

- Full-song playback remains unchanged when no ranges are configured.
- F8, foreground requirement, focus-loss pause/stop, final release, and scan-code default remain unchanged.
- Ctrl/Shift remain standalone 18 ms persistent-bank taps.
- Source files are never modified.
- Range processing never generates notes or harmony.
- SCUM musical quality and runtime timing metrics remain unconfirmed until the packaged release is auditioned in the current game build.

## Packaged validation

- Compileall, Ruff, and all 109 automated tests passed before packaging.
- The PyInstaller onedir folder contains 236 files / 120,577,443 bytes.
- Recursive archive inspection confirmed `playback_sections`, `scheduler`, `input_backend`, `score_optimizer`, `planner`, and `ui`.
- Every required audio/separation installer, validator, worker, and requirements file is present.
- The packaged EXE remained alive through a six-second offscreen smoke launch.
- `MusicalScumme_2.9.0_Windows.zip` passed a complete 236-entry / 120,577,443-byte read-through with one `MusicalScumme/` root and no backslash paths.
- ZIP size: 49,425,234 bytes.
- ZIP SHA-256: `c88f8ad6db57ea5c778633797ce8eaa119932e5c41cba3ba336b169fd8746115`.
