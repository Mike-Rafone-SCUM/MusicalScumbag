# MusicalScumme 3.2.0 - Guided Command Deck UX

## Outcome

Version 3.2.0 is a complete workflow, feedback, accessibility, and quality-of-life pass over the 3.1.0 Instrument Prep and Dynamic Solo Director release. It changes how the product communicates state and prevents dead ends without changing any MIDI selection, arrangement, planning, timing, input, or cleanup result.

## Guided workflow

- A persistent Load MIDI → Review Tracks → Prepare → Play rail marks completed, active, and upcoming stages.
- A command-deck readiness pill reports Load MIDI, Select Tracks, Prepare, Ready, Playing, Paused, or Live Armed.
- Concise guidance states the next safe action, including a distinct Dry run message.
- Prepare, Play, and the two exports are disabled until an existing MIDI contains at least one selected populated track.
- Play retains the convenient auto-prepare path after settings change.
- Preparation displays an indeterminate progress state and wait cursor while remaining a no-output operation.

## Source and section workflow

- Track filtering searches track number, name, detected role, note count, and pitch range without changing selection.
- Selected/populated and filter-visible counts remain visible.
- Empty tracks cannot be checked.
- Double-click toggles a populated source track.
- Every row exposes a source summary and whether it is currently recommended.
- Auto-select musical restores the relationship-aware primary lead, sectional solo, bass, and support recommendation.
- Delete removes the selected playback section; existing Play/Omit semantics and persistence are unchanged.

## Readability and feedback

- Prepared results use three scannable lines for duration/speed, retained notes/events/chords, and effective policy.
- Instrument preparation, playback-section changes, dropped notes, solo direction, bank preparation, mapping evidence, and warnings are separate selectable bullet advisories.
- Score and physical-event exports use compact Score CSV and Events CSV command labels with complete accessible descriptions.
- The compact playback HUD hides editor-only commands and remains below the maintained 580 px width.

## Conversion dialogs

- Audio-to-MIDI validates the source file, MIDI destination, runtime, and running state inline.
- Song Transposer validates source existence/type, processed destination, source-overwrite protection, raw/processed separation, audio runtime, UVR runtime, and stem folder inline.
- Operation inputs lock while asynchronous installers, separation, or transcription workers run.
- Song Transposer settings scroll vertically at 880×720 with no horizontal scrollbar; the progress bar, log, and final actions remain continuously reachable.
- Custom-key Save validates Windows key names before the dialog closes and leaves an actionable inline correction when invalid.

## Keyboard and accessibility

- Ctrl+P prepares the SCUM score.
- Ctrl+L focuses and selects the MIDI path.
- F1 opens a four-step Quick Start.
- Delete removes the selected playback section.
- Existing Ctrl+O, Ctrl+R, F8, F9, and F11 behavior is preserved.
- Primary paths, tables, readiness state, live status, summaries, progress, actions, and key fields have accessible names and descriptions.
- Actions include status tips and high-risk controls retain explicit safety tooltips.

## Preserved boundaries

- The arranger, score optimiser, planner, instrument profiles, input backend, live MIDI service, scheduler, and audio workers are unchanged.
- Dynamic Solo Director, Optimal Sounding, Custom settings, Instrument Prep ceilings, SCUM bindings, persistent octave-bank behavior, focus protection, F8 cleanup, and immutable source MIDI behavior are unchanged.
- The maintained 1080×720 two-pane HUD, always-on-top frameless behavior, native drag/resize/chrome, electric-cyan visual system, and compact playback overlay remain release constraints.

## Regression coverage

- Initial workflow readiness and prerequisite-aware actions.
- Track filtering, visible/selected counts, empty-track protection, double-click selection, recommendation restore, and prepared Ready state.
- Inline audio path validation and custom-key correction.
- Existing active-playback control locking, live MIDI mutual exclusion, compact HUD restoration, ranges, Instrument Prep disclosure, and complete Qt construction.
- Main HUD remains exactly 1080×720 with usable 618/439 px panes and no settings horizontal scrollbar.
- Song Transposer remains usable at 880×720 through a vertical settings viewport with no horizontal scrollbar.

## Release artifact

- Source checks: compileall passed, Ruff passed, and all 181 tests passed.
- Windows onedir: 237 files / 121,035,295 bytes; packaged EXE remained alive through an eight-second offscreen smoke launch.
- Packaged EXE: 4,421,399 bytes; SHA-256 `7e794414d4059ac02542b3ef8c76078459761f30020601ce919a237231d32d19`.
- Packaged optional-runtime validation: Basic Pitch 0.4.0 / Python 3.11.9 passed; Viperx UVR / CUDA on the RTX 2070 SUPER passed.
- Portable ZIP: `release-staging\3.2.0\MusicalScumme-3.2.0-Windows.zip`.
- ZIP verification: one `MusicalScumme/` root, 237 files, zero backslash paths, every required resource present, and all 121,035,295 uncompressed bytes read successfully.
- ZIP size: 49,634,805 bytes; SHA-256 `e5dbfdaf688f1e28ff03488a084fd19f253a00e2d610df47f0bc845ef65493c5`.

## Validation boundary

Offscreen construction and automated interaction tests validate layout and behavior, not live readability over every SCUM scene. Current-build SCUM focus cleanup, F8 behavior, compact-HUD readability, and musical output still require supervised in-game confirmation.
