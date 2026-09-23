# Fidelity and UI audit — 6 September 2026

The enhanced-mapping rebuild is complete. The following are next-pass findings,
not additional musical changes included in that EXE. All reproductions use
in-memory MIDI notes and simulated event interpretation; none sends game input.

## 1. Restore octave state when seeking — highest priority

The scheduler releases keys and jumps to the first batch at/after the requested
time. It does not reconstruct the persistent octave bank. Releasing Ctrl/Shift
or the note keys does not restore the base bank.

Reproduction: prepare G3 at 0 ms, G5 at 500 ms, and G5 at 1,000 ms with Enhanced
Contour. Jump from the lower-bank passage to 1,000 ms. The skipped events contain
both upward bank taps. Event-slice simulation resumes key K in bank -1 instead
of +1: MIDI 55 instead of 79, a two-octave error.

Proposed fix: track successfully dispatched bank taps and reconstruct the bank
required immediately before the destination batch. Restore it using the existing
standalone release/tap/settle sequence under foreground, pause, stop, and F8 guards.
Do not emit restoration while paused. Audit loop restarts and interrupted taps at
the same time: those also depend on persistent bank state.

Acceptance: forward/backward seeks, paused seeks, seeks inside taps, custom octave
keys, loop boundaries, and cancellation must preserve expected pitch and zero
musical-key/modifier overlap. The current seek tests check event skipping, not
musical bank state. Relevant implementation: scheduler.py seek handling around
lines 279–325.

## 2. Distinguish doubled parts from real octave voices

Enhanced Fold still treats two identical source Cs as an octave collision it can
spread. Two simultaneous C4 notes on separate tracks, using Faithful arrangement
and two-note polyphony, produce C4 plus C5. A doubled unison becomes an octave.

Proposed fix: deduplicate identical source pitches before allocating C4/C5.
Spread only distinct octave-separated source Cs; retain the strongest source
representative deterministically. Preserve the newly corrected C5/C6 ordering.

Acceptance: exact track doubles remain one pitch, genuine octave pairs retain
both voices, reversed input order gives the same plan, and the rule holds after
manual transposition. Relevant implementation: planner.py `_map_group`.

## 3. Give enhanced mappings an honest fidelity readout

`automatic_pitch_shift_semitones`, `pitch_match_exact_notes`, and
`pitch_match_octave_folded_notes` are only populated for base `match3`.
An Enhanced Pitch Match probe confirms all three are absent despite the mode
performing an automatic shift. The UI mainly reports note retention and warnings,
which cannot distinguish retained attacks from correctly retained register.

Proposed UI: show notes retained, register-exact notes after global shift, folded
notes, octave taps, and timing displacement as separate quantities. Include the
effective mapping name and whole-song shift. Never label a high retention count
as measured musical quality.

Acceptance: enhanced/base metrics use the same denominators; empty plans and
strict omissions are handled; no metric changes note selection or scheduling.
Relevant implementation: planner.py diagnostic construction around lines
1506–1518 and 1623–1631; ui.py prepared summary around line 3532.

## 4. Compare enhanced mappings before committing

Once those metrics are reliable, an in-memory comparison panel could prepare the
five enhanced mappings against the same selected MIDI section and settings.
Show the musical/timing tradeoffs side by side, then let the user apply one.
An asynchronous preparation worker should keep Qt responsive; comparing plans
must never send input, rewrite MIDI, or silently change saved settings.

Prioritise the first two correctness fixes, then the shared fidelity metrics,
then the comparison panel. Current-build SCUM audition remains necessary.
