# MusicalScumme 3.3.0 - Enhanced Mappings and Resource Optimisation

## Outcome

Version 3.3.0 replaces legacy base pitch-mapping modes with their enhanced counterparts, optimizes arranger DP execution time and memory footprint, speeds up playback seeking via binary search, eliminates unused Qt plugin stacks from the standalone distribution, and establishes comprehensive regression coverage across all enhanced mappings and arrangements.

## Enhanced mappings

- Deprecated and removed legacy base file-playback mappings and migrated saved config names (`fold` -> `fold_smart`, `strict` -> `strict_auto`, `smart3` -> `smart3_harmonic`, `melody3` -> `melody3_contour`, `match3` -> `match3_adaptive`).
- Optimal Sounding and protected solos utilize enhanced mapping components.
- Preserved custom timing, source notes, instrument ceilings, standalone octave taps, focus protection, F8 emergency stop, and separately supervised live MIDI.
- Enhanced Pitch Match additionally exposes global shift and exact/folded note counts in diagnostics.

## Resource and performance optimisation

- Reused equivalent phrase analysis and rolling prominence computations across passes.
- Bounded semantic-name caching to avoid unbounded memory accumulation.
- Traced lead solver retains only current DP score rows rather than retaining the entire historical matrix.
- Released redundant buffers and eliminated unnecessary note/list copies throughout the arrangement pipeline.
- 5,400-note benchmark results: arrangement execution time dropped from 0.40s to 0.16s (~60% improvement), and peak Python memory allocation dropped by ~16%.
- Additional optimizations: linear scan for onset matching (55.5% faster: 0.093s -> 0.041s), bounded per-import track relationship caching (track analysis 19.4% faster: 0.119s -> 0.096s), group register bounds computed once per lead group, constant-time integer octave folding, and private raw MIDI buffer clearing after parsing each track (24.4% lower peak MIDI-import allocation: 7.78 MB -> 5.88 MB).
- Seeking event lookup replaced with binary search, strictly maintaining seek semantics and dispatch accuracy.

## Packaging and binary size

- Packaging hook (`packaging_hooks/hook-PySide6.QtGui.py`) excludes unused Qt PDF (`qpdf.dll`), virtual keyboard (`qtvirtualkeyboardplugin.dll`), and TUIO UDP touch (`qtuiotouchplugin.dll`) plugins.
- PyInstaller spec and build script exclude unused `PySide6.QtNetwork` and unnecessary Mido backend collection.
- Total package file count reduced to 218 files (96,571,318 bytes), yielding a 39.0 MB compressed distribution zip (down from 49.4 MB in 2.10.1).

## Regression coverage

- Added 45 complete-plan regression snapshots covering all enhanced mappings, three arrangements, and three transpositions.
- Complete automated test suite passed with 215 tests.
- Offscreen Qt verification passed for all maintained application windows and dialogs.

## Release artifact

- Source checks: `compileall -q .` passed, `ruff check .` passed, all 215 pytest tests passed.
- Windows onedir: 218 files / 96,571,318 bytes; packaged EXE remained alive through an eight-second offscreen smoke launch.
- Executable SHA-256: `5bc55e4940b58b4983cd383c6e313aa0924f0d1d5fa09ca9be182f573325026d`.
- Portable ZIP: `release-staging\3.3.0\MusicalScumme-3.3.0-Windows.zip`.
- ZIP verification: 218 files, single `MusicalScumme/` root, zero backslash paths, 38,985,843 bytes. SHA-256: `d106aaccf8ecc415f054e216a4b17e327bfd9c169f0a22dadb61c0fb37f724bc`.
- Source manifest `SHA256SUMS.txt` regenerated and verified.

## Validation boundary

Current-build SCUM in-game text contrast, translucent readability, compact-HUD placement, focus cleanup, F8 emergency stop, live-controller behavior, and musical output remain unconfirmed until supervised in-game testing.
