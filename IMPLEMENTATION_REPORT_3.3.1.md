# MusicalScumme 3.3.1 - Arrangement and Conversion Fidelity Enhancements

## Outcome

Version 3.3.1 implements an essential suite of musical fidelity, scheduling reliability, and transcription processing enhancements. It resolves persistent-bank synchronization on seek, fixes duplicate unison C chord voicing, protects melody contour landmarks under density limits, eliminates transcription overtone artifacts and sub-bass rumble, consolidates micro-strumming rakes, deduces realistic tempo for exported MIDI, and provides side-by-side pitch mapping comparison tooling.

## Key Improvements

### 1. Octave Bank Seek Synchronization
- Post-batch bank states are tracked across the playback timeline (`_ScheduledBatch.bank_after`).
- Active seeking evaluates target destination bank and issues standalone `_sync_octave_bank` taps (`LSHIFT` / `LCTRL`) with configured release and settle delays before playing destination notes.
- Seeking while paused safely defers synchronization until playback resumes, preventing background keystroke leaks.
- Loop restarts reset bank state to zero if the previous loop finished non-zero.

### 2. Unison C Voicing Resolution
- In `fold_smart`, boundary C allocation checks for distinct octave classes in the group.
- Unison attacks (e.g. C4 + C4 across separate voices/tracks) remain unified at C4 rather than splitting into an artificial octave chord C4 + C5.
- Distinct source octaves (e.g. C3 + C4) continue to spread across C4 and C5 boundary keys.

### 3. Melody Contour Landmark Protection
- Generalized contour landmark detection from solos to all lead melody runs (`_mark_landmarks`).
- Local peaks, valleys, cadence endpoints, and accents receive priority bonuses before density limits are enforced.
- Physical retrigger filtering precedes landmark detection to ensure intentional note attacks are not replaced by weak duplicate micro-retriggers.

### 4. Audio-to-MIDI Transcription Cleaning & Strum Consolidation
- `_suppress_harmonic_ghosts` removes acoustic body overtone artifacts (+12, +19, +24 semitones with lower velocity relative to concurrent fundamentals) and sub-bass transcription rumble.
- `_consolidate_micro_strums` aligns near-simultaneous guitar string strum rakes (15–35 ms) to the anchor onset time.
- `estimate_tempo_bpm` estimates musical BPM from inter-onset intervals (IOI) and embeds it into processed MIDI exports instead of the flat 120 BPM default.

### 5. UI Enhancements & Comparative Analysis
- Added "Auto / Recommend" button beside the Transpose control powered by `recommend_optimal_transpose`, finding the semitone shift ($-12 \dots +12$) that maximizes in-bank C4–C5 and 3-octave SCUM range coverage.
- Added `MappingComparisonDialog` via "Compare Mappings…", rendering side-by-side comparative scorecards across all 5 enhanced mapping modes (`fold_smart`, `match3_adaptive`, `strict_auto`, `melody3_contour`, `smart3_harmonic`) with direct "Apply" actions.

## Release Artifacts

- Source validation: `compileall -q .` passed, `ruff check .` passed, all 226 pytest tests passed.
- Windows onedir build: `release-staging\3.3.1\MusicalScumme\MusicalScumme.exe` (219 files / 96,583,136 bytes; 8-second offscreen smoke test passed).
- Executable SHA-256: `8b7e6caef298e9fdd474091eff4cb9829d39bc168d3bfe180e0caab78dd32687`.
- Portable ZIP: `release-staging\3.3.1\MusicalScumme-3.3.1-Windows.zip` (38,841,861 bytes).
- ZIP SHA-256: `53ee5110f4871a2b4fc1cd70d6e117a67c8d3d6b16a2b2cdbfde8fbd31b2401a`.
