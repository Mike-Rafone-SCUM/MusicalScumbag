# MusicalScumme 3.0.0 Implementation Report

Date: 2026-08-03

## Outcome

Version 3.0.0 replaces local MIDI-to-SCUM melody guessing with a deterministic, source-backed whole-phrase conversion policy while retaining the instrument-preparation build's Guitar, Harmonica, and Banjo sustain limits.

The overhaul does not generate notes, infer missing harmony, snap pitches to a key, modify imported MIDI, or weaken the SCUM input safety model.

## Conversion intelligence

- Track names use token-safe semantics, preventing short role words from matching unrelated names.
- Track recommendation measures relationship to the lead: attack affinity, shared time coverage, register separation, and exact duplication.
- Source analysis separates musical onset rate from physical note-start load and adds time-weighted sounding polyphony, overlap, phrase count, and rhythmic variation.
- Lead selection uses dynamic programming across the complete phrase sequence. Local velocity/register salience is balanced against interval motion, source-track continuity, time gaps, and phrase boundaries.
- Bass and harmony remain real source notes and are selected from lead context, prior support voice-leading, consonance, compactness, register role, duration, and velocity.
- Optimal Sounding rolls chords relative to the detected pulse, keeping dense fast material tighter than slower chord-led passages.

## Preserved boundaries

- Strict MIDI parsing and narrow illegal-data-byte recovery.
- Untouched source MIDI as the primary workflow.
- Separate parser, analyser, arranger, planner, input, scheduler, audio, and UI responsibilities.
- Standalone Ctrl/Shift octave-bank taps with no note-key overlap.
- Current and historical key profiles, F8 emergency stop, focus cleanup, atomic settings/exports, live-MIDI isolation, and optional audio-runtime isolation.
- Instrument preparation ceilings: Guitar 2,000 ms, Harmonica 4,000 ms, Banjo 1,000 ms.

## Static musical evidence

Using the maintained real fixtures, whole-phrase tracing reduced lead-path discontinuity relative to the former greedy selector:

| Fixture | Greedy >1-octave transitions | 3.0 global transitions | Greedy mean interval | 3.0 mean interval | Greedy track switches | 3.0 track switches |
|---|---:|---:|---:|---:|---:|---:|
| Rush E selected source | 357 | 54 | 3.716 semitones | 1.592 semitones | 320 | 28 |
| House raw guitar transcription | 437 | 221 | 16.656 semitones | 10.599 semitones | 0 | 0 |

These are structural source metrics, not a claim of in-game musical validation. The current SCUM build still requires supervised audition.

## Validation

- `python -m compileall -q .`: passed.
- `python -m pytest`: 172 passed.
- `ruff check .`: passed.
- Main HUD, Audio-to-MIDI, and Song Transposer offscreen construction: passed through the full suite.
- PyInstaller 6.21.0 / Python 3.12.10 onedir build: passed.
- Eight-second packaged offscreen smoke launch: passed; log reported MusicalScumme 3.0.0.
- Portable ZIP complete read-through: 237 files, one root, zero backslash paths, all required runtime resources present.
- ZIP SHA-256: `3bfd3947c062709245c14ad79bf5d53f7f7a08e16f8c2bcbe17ea3b9c13c1187`.

Current-build SCUM musical quality, focus-loss cleanup, and F8 behavior still require supervised in-game validation.
