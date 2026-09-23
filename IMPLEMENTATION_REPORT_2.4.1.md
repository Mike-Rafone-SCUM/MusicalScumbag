# MusicalScumme 2.4.1 Implementation Report

Date: 2026-07-15

> Superseded by 2.4.2: the 38 ms Shift pulse still overlapped note-on. The user confirmed Ctrl/Shift are standalone tap-to-change octave-bank controls, so 2.4.2 removes every octave-key/note-key overlap.

## Outcome

Version 2.4.1 fixes the reported lingering Shift/menu interaction and the main cause of practice-speed playback. Upper-octave Shift is now a short attack pulse rather than a phrase latch, while real tick-zero MIDI tempos can no longer be replaced by the synthetic 120 BPM fallback.

## Root causes

- The planner held Left Shift as a global upper-octave state across consecutive notes. Any later `I` or other SCUM key could therefore arrive while Shift was still down and activate a normal game shortcut.
- `_tempo_map` sorted complete `(tick, tempo)` tuples. At tick zero, a fast real tempo sorted before the synthetic 500,000 microseconds-per-beat fallback, so the fallback won and stretched the song to 120 BPM.
- The user's stored Guitar Smooth identity still contained obsolete 2.4.0 practice settings. Named presets were treated as frozen snapshots rather than maintained policies.
- A fixed 65 ms Song Transposer grouping window collapsed valid rapid notes in high-BPM scored MIDI.
- Prepared Lead Melody output passed through the raw source-duration filter a second time, deleting already-approved short articulations.

## Input and pacing changes

- Left Shift is pressed 20 ms before each upper-octave attack and released 18 ms after its final note-on. Under Guitar Smooth, the normal measured hold is 38 ms, and Shift is released before the musical note key is released.
- Left Ctrl remains phrase-scoped; the user reported a Shift-specific menu conflict, and changing Ctrl without evidence would add unnecessary transitions.
- Added Melody contour mapping for monophonic material. It preserves all in-range source pitches and never applies Smart mode's brief-register-excursion folding.
- Guitar Smooth now uses 1.12x speed, 18 starts/s, 40 ms source retrigger filtering, a 90 ms planned hold, a 20 ms physical key gap, and 10/20 ms modifier release/settle timing.
- Named presets refresh their controlled values when loaded. Manual settings remain preserved under the `custom` identity.
- Tempo changes are stably sorted by tick only, allowing the real same-tick event to replace the fallback.
- Song Transposer's onset window scales by `120 / source_bpm`, clamped between 12 ms and the selected profile's maximum.
- Recognized Lead Melody / Light Support selections bypass the arranger's second raw-duration filter.

## Musical evaluation

- The user's 38.02-second in-game recording was mechanically accurate against the old plan—107/107 assessable attacks with no wrong fundamental keypresses—but the old plan removed the defining A3, folded E4 downward, and distorted the opening register contour.
- New 0.45/0.30/90 Basic Pitch defaults recover the missing A3. Reattack cleanup preserves the second C4 only when a strong same-pitch rearticulation is present.
- The recommended clean-score House release contains 1,163 notes. Its prepared Guitar Smooth plan retains all 1,163, emits 2,550 events, and spans 239.911 seconds.
- The automatic audio-recovered House release contains 1,026 notes; it remains an approximation and is less coherent than the clean score.
- `Rush E.mid` now remains 270.00027 BPM. Tempo-relative processing retains 1,510 notes, and Guitar Smooth retains 1,370 after only density limiting. Its plan spans 266.493 seconds with a 98.357 ms median attack gap instead of the roughly 596-second bad path.

## Validation

- `.build-venv\Scripts\python.exe -m compileall -q .`: passed.
- `.build-venv\Scripts\python.exe -m pytest`: 72 passed.
- `.build-venv\Scripts\ruff.exe check .`: passed.
- Focused installer, audio-tools, audio-worker, and Qt process suite: 27 passed.
- Focused Song Transposer and Qt dialog suite: 14 passed.
- Main window, Audio Convert dialog, and Song Transposer constructed offscreen.
- No blocking `QProcess.waitForStarted` or `waitForFinished` calls exist in the application or tests.
- Packaged EXE remained running during a five-second hidden/offscreen smoke test.
- Packaged runtime validation passed from `_internal` using isolated Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model.
- Packaged worker converted the user's WAV to a strict 143-note MIDI without optional-backend warnings, TensorFlow's CPU banner, or corrupted Unicode.
- Release ZIP: all 231 entries / 120,515,236 uncompressed bytes read successfully, required resources present, no backslash entry names.
- ZIP SHA-256: `fce1947e96284aa4fdb3cd322e1f02bd5bc76f9450d638653dd736facd991d0a`.

## Deliverables

- `dist/MusicalScumme/MusicalScumme.exe`
- `dist/MusicalScumme_2.4.1_Windows.zip`
- `dist/MusicalScumme_2.4.1_SHA256.txt`
- `E:/Users/james/Downloads/the-animals-the-house-of-the-rising-sun_MusicalScumme_2.4.1_ScoreAccurate.mid`
- `E:/Users/james/Downloads/the-animals-the-house-of-the-rising-sun_MusicalScumme_2.4.1_ScoreAccurate_keyplan.csv`
- `E:/Users/james/Downloads/the-animals-the-house-of-the-rising-sun_MusicalScumme_2.4.1_AudioRecovered.mid`
- `E:/Users/james/Downloads/Rush E_MusicalScumme_2.4.1_TempoFixed.mid`
- `E:/Users/james/Downloads/Rush E_MusicalScumme_2.4.1_TempoFixed_keyplan.csv`

## Remaining live limitation

Static event timing, real audio inference, and Windows package smoke tests are validated. The new Shift+I behaviour and musical pacing still require auditioning in the current SCUM build. An intentional upper-octave C-sharp still necessarily uses the configured Shift+I instrument binding; this release prevents Shift from leaking into unrelated later notes.
