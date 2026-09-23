# MusicalScumme 2.4.4 Melody Rollback and Optimisation

Date: 2026-07-15

## Outcome

Version 2.4.4 fully removes the rejected 2.4.3 generated-harmony experiment, restores the proven 2.4.2 Lead melody only behavior, preserves the user's successful Game-optimised Rush E plan exactly, and optimises the application's measured hot paths without changing musical output.

## Musical rollback

- Lead melody only again selects exactly one note per onset from one inferred lead track.
- Maximum chord notes does not add notes in Lead melody only, including at values 3 and 8.
- No support-track borrowing, local-triad inference, calculated notes, support diagnostics, or polyphonic Melody contour behavior remains.
- Game-optimised real-source chords remain unchanged. The user's successful current Rush E plan still uses two-note Game-optimised selection.
- The ScoreAccurate House plan is restored exactly: 1,163 notes, 2,774 events, 224 octave-bank taps, and 239,947.043 ms duration.

## Output-equivalent optimisation

### MIDI loading

- Tempo discovery scans existing track messages instead of calling `mido.merge_tracks()`, which cloned and revalidated the complete file.
- Same-tick track precedence and the real tick-zero tempo rule are unchanged.
- Tick-to-millisecond results are cached and overlapping same-pitch note queues use constant-time dequeue.
- Rush E load: 1.9981 to 0.7297 seconds, 63.5% faster.
- Large House score load: 3.5740 to 1.0812 seconds, 69.7% faster.
- Every parsed note in both files is exactly equal to the legacy output.

### Arrangement and planning

- Per-onset note priority is calculated once.
- Retrigger and density replacement use retained-list indexes instead of searching the full accumulated output.
- Dense Rush planning fell from roughly 0.55 seconds to roughly 0.40 seconds.
- The user's complete current Rush plan digest remains `7da04adb61d3a4b8062b0a39b0995c4c79fbfa3917c7e14f30f20cac2f39a1d0`.
- That plan remains 2,420 notes, 5,982 events, 571 octave-bank taps, and 266,453.107143 ms duration.

### Song Transposer

- Core-range detection aggregates weight into the 128 legal MIDI pitches once instead of rescanning the whole score for every candidate window.
- Rush processing: 1.39 to 0.13 seconds.
- Raw House guitar processing: 0.19 to 0.02 seconds.
- Complete processed-note and diagnostic digests are identical to the previous implementation.

## Validation

- `.build-venv\Scripts\python.exe -m compileall -q .`: passed.
- `.build-venv\Scripts\python.exe -m pytest`: 77 passed.
- `.build-venv\Scripts\ruff.exe check .`: passed.
- Main window, Audio Convert dialog, and Song Transposer constructed offscreen through the test suite.
- Packaged EXE remained alive during a five-second hidden/offscreen smoke test.
- Packaged runtime validation passed from `_internal` with Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model.
- Packaged worker converted the supplied WAV into a strict 143-note MIDI without optional-backend warnings, TensorFlow's CPU banner, or corrupted Unicode.
- Release ZIP: all 231 entries / 120,515,458 uncompressed bytes read successfully; required resources are present and no entry uses a backslash path.
- ZIP SHA-256: `e9b5602f7ad421472d881067d9feb2a2c016eb4ec866f9340292abee37893a37`.

## Deliverables

- `dist/MusicalScumme/MusicalScumme.exe`
- `dist/MusicalScumme_2.4.4_Windows.zip`
- `dist/MusicalScumme_2.4.4_SHA256.txt`

## Live limitation

The successful Rush E result is user-confirmed under the current Game-optimised settings. The restored 2.4.4 Lead melody only path and rebuilt executable still require a fresh in-game audition; static equivalence cannot substitute for listening.
