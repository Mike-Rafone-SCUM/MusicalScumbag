# MusicalScumme 2.8.0 implementation report

Date: 2026-07-15

## Outcome

Version 2.8.0 replaces source-specific preset guesses and blanket track selection with one deterministic analysis-to-score pipeline. A MIDI is analysed immediately after parsing, visible track roles are recommended, and Optimal Sounding derives a bounded SCUM policy from the selected notes.

## New analysis layer

`musical_scumme/score_optimizer.py` is pure application logic. It has no Qt, audio-runtime, scheduler, or input dependency.

For each track it measures:

- activity and note count;
- median register;
- monophony versus real chord attacks;
- lead, bass, support, and noise/effect name evidence.

For the selected score it measures:

- exact and clearly rolled sustained chords;
- 95th-percentile attack polyphony;
- peak starts in a one-second window;
- median onset gap and note duration;
- short-note 10th percentile;
- track count and pitch span.

The resulting texture is melody, light polyphony, chord-led, dense, or empty.

## Adaptive policy

- Melody: Lead melody, SCUM Pitch Match, one voice, zero chord roll, flowing holds, short standalone bank timing.
- Light polyphony: Game-optimised, automatic source chords, Safe fold, two voices.
- Chord-led: Game-optimised, automatic source chords, Safe fold, three voices and a 10 ms per-note roll.
- Dense: Game-optimised, automatic source chords, Safe fold, two voices, 16 starts/s, and a 14 ms per-note roll.

Source-duration and retrigger thresholds are derived from robust duration/gap percentiles. Hold ratio, minimum/maximum hold, velocity expression, key gap, and modifier timing also adapt within explicit SCUM-safe limits. No policy changes the user's transpose outside the established planner or changes source tempo except through the explicit speed control.

## Removed and consolidated

- Removed timing jitter from configuration, planning, UI, and saved-setting schema.
- Removed the Guitar Smooth-only Song Transposer branch.
- Removed Guitar Smooth, Balanced, and Maximum Fidelity from the visible preset list.
- Added migration aliases from all three obsolete identities to Optimal Sounding.
- Kept SCUM Safe and Custom.
- Hid advanced arrangement and physical-timing controls until Custom is selected.
- Replaced the old README's repeated historical release notes with the maintained current workflow.

## Compatibility and safety

- Current/historical/custom SCUM key profiles are unchanged.
- Scan-code, virtual-key fallback, Dry run, foreground checks, focus-loss pause, cleanup, and F8 stop are unchanged.
- The persistent three-bank Ctrl/Shift model and exact 18 ms standalone tap hold are unchanged.
- Lead melody remains monophonic and source-backed. Generated/borrowed harmony remains forbidden.
- Game-optimised automatic chords remain source-backed and require meaningful shared sustain for offset attacks.
- Audio and separation runtimes remain isolated from the main application and from each other.

## Validation summary

- Automated unit/integration/UI tests: 100 passing.
- Ruff: passing.
- Compileall: passing.
- Real source analysis exercised the malformed Rush E MIDI, three large House variants, the isolated-guitar transcription, packaged-worker outputs, and the repository SCUM test scale.
- The onedir application contains 236 files / 120,561,329 bytes and remained alive through a six-second offscreen smoke launch.
- Recursive archive inspection confirmed the optimiser and complete conversion/playback modules are embedded. All required optional-runtime resources are present.
- `MusicalScumme_2.8.0_Windows.zip` passed a complete 236-entry read-through with one portable root and no backslash paths.
- ZIP SHA-256: `3bfbe59801ffb04d2286f94650031ac1201372e17b8aa2dca011dd135589fb59`.
- Current-build in-game SCUM audition remains required; static evidence is not reported as live musical confirmation.
