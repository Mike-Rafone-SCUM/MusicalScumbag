# MusicalScumme 3.1.0 - Dynamic Solo Director

## Outcome

Version 3.1.0 replaces whole-song-only lead treatment with a deterministic section-aware solo policy. A selected solo track can take lead ownership for a sustained passage even when vocals, pads, bass, or rhythm tracks continue to play.

## Musical intelligence

- Rolling source-time windows measure local activity, monophony, velocity, register, continuity, semantic role, and global track quality.
- Whole-phrase dynamic programming retains pitch and track continuity while allowing a locally dominant alternate lead to overcome switch hysteresis.
- Direct run discovery catches clearly sectional solos that coexist with a sustained primary lead at every attack.
- Stable alternate-lead runs become immutable `SoloSegment` records containing source time, track, confidence, and onset count.
- Import analysis retains one useful solo-handoff track alongside the primary lead, bass, and support when the source contains a real sectional handoff.

## Solo Focus

- The solo note is the protected first voice.
- Competing upper leads and pads are removed during the protected interval.
- At most one source-backed lower foundation voice remains.
- Solo attacks are excluded from performed-chord alignment and planned chord stagger.
- Every retained note still comes from the imported MIDI. No pitch, harmony, scale, or attack is generated.

## Fast-run preservation

When the configured note-start limit cannot represent a complete fast run, the reducer protects:

- phrase endpoints;
- velocity accents;
- local pitch extrema;
- changes of direction;
- large spacing changes; and
- regular phrase landmarks.

Connector notes are removed before these identity-bearing notes. The physical note-start ceiling remains unchanged.

## Solo-adaptive SCUM mapping

Optimal Sounding keeps non-solo accompaniment on the stored Safe Fold policy. Each protected solo section receives:

1. a duration/velocity-weighted whole-octave fit into SCUM's C3-C6 range;
2. melody-contour octave-bank planning inside that fitted register; and
3. the existing standalone Ctrl/Shift release, tap, settle, and no-musical-key-overlap guards.

The setting is plan-local. Saved mapping defaults and Custom mapping behavior are not rewritten.

## Diagnostics

Plans report solo sections, handoffs, protected notes, ducked accompaniment, solo density removals, retained landmarks, suppressed stagger groups, per-section octave shifts, and exact/folded solo mapping. The prepared-plan HUD surfaces a concise Dynamic Solo Director summary.

## Regression coverage

- Continuous-primary-lead handoff to an eight-note guitar solo.
- Solo Focus polyphony and upper-register competition removal.
- Fast-run endpoint, accent, and contour-apex retention under a strict density ceiling.
- Sparse sectional solo-track recommendation without reintroducing doubled-lead selection.
- Plan-local solo-adaptive pitch matching, upper-bank selection, and zero solo stagger.
- Complete existing parser, arranger, planner, instrument, input, scheduler, audio, settings, and offscreen Qt suite.

## Release artifact

- Source checks: compileall passed, Ruff passed, and all 177 tests passed.
- Windows onedir: 237 files / 121,021,765 bytes; packaged EXE remained alive through an eight-second offscreen smoke launch.
- Packaged optional-runtime validation: Basic Pitch 0.4.0 / Python 3.11.9 passed; Viperx UVR / CUDA on the RTX 2070 SUPER passed.
- Portable ZIP: `release-staging\3.1.0\MusicalScumme-3.1.0-Windows.zip`.
- ZIP verification: one `MusicalScumme/` root, zero backslash paths, every required resource present, and every one of the 121,021,765 uncompressed bytes read successfully.
- ZIP SHA-256: `aa4e5f94056dc00b0bd03fbab72753a7bea6753aa86d7c127313b6f5aef0c386`.

## Validation boundary

Static analysis and automated timing tests do not prove musical quality inside SCUM. The release still requires supervised audition in the current game build, including focus loss, F8 cleanup, bank-transition sound, and solo balance on representative multitrack songs.
