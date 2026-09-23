# MusicalScumme 2.4.2 Octave-Bank Correction

Date: 2026-07-15

## Outcome

Version 2.4.2 replaces the incorrect held-modifier model with SCUM's actual tap-to-change octave-bank behavior. MusicalScumme no longer generates Shift+note or Ctrl+note combinations.

## Confirmed game model

- The 13 note keys form one chromatic C-to-high-C bank.
- The same bank exists in lower, base, and upper octave layers.
- Left Ctrl steps the persistent bank down; Left Shift steps it up.
- The octave key must be tapped without a musical key held.
- SCUM labels sharps, not separate flats. Enharmonic flats use the equivalent sharp.

The user's correction is corroborated by the 2023 Steam guide **Scum Instruments and You**, which lists all 13 chromatic notes, three octaves, and warns against holding another key during octave changes.

## Planner correction

- Release all sounding note keys before a bank transition.
- Wait `modifier_release_ms`.
- Hold each required Ctrl/Shift tap for 18 ms and release it.
- Wait `modifier_settle_ms` before another bank tap or musical note.
- Emit two taps when crossing two layers.
- Emit no octave event while the target bank is unchanged.
- Keep the existing internal `modifier` field as the target bank identifier for compatibility; it no longer means a physically held modifier.

## Static musical results

- Clean House score: 1,163/1,163 notes, 224 bank taps, 2,774 events, 239.947-second plan, zero octave/note overlap.
- Audio-recovered House: 1,025/1,026 notes, 281 bank taps, 2,612 events, 234.513-second plan, zero octave/note overlap.
- Tempo-fixed Rush E: 1,370/1,510 notes, 63 bank taps, 2,866 events, 266.501-second plan, 98.357 ms median attack gap, zero octave/note overlap.
- Every tap is held for exactly 18 ms and every complete plan ends with an empty pressed-key state.

## Validation

- `.build-venv\Scripts\python.exe -m compileall -q .`: passed.
- `.build-venv\Scripts\python.exe -m pytest`: 73 passed.
- `.build-venv\Scripts\ruff.exe check .`: passed.
- Main window, Audio Convert dialog, and Song Transposer constructed offscreen through the full suite.
- Packaged EXE remained running during a five-second hidden/offscreen smoke test.
- Packaged runtime validation passed from `_internal` using isolated Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model.
- Packaged worker converted the user's WAV to a strict 143-note MIDI without optional-backend warnings, TensorFlow's CPU banner, or corrupted Unicode.
- Release ZIP: all 231 entries / 120,515,080 uncompressed bytes read successfully, required resources present, no backslash entry names.
- ZIP SHA-256: `9abdde313115dcacc87b13800fb0fb833db1e8fc574a6feb30f61607ad1f89d6`.

## Deliverables

- `dist/MusicalScumme/MusicalScumme.exe`
- `dist/MusicalScumme_2.4.2_Windows.zip`
- `dist/MusicalScumme_2.4.2_SHA256.txt`
- `E:/Users/james/Downloads/the-animals-the-house-of-the-rising-sun_MusicalScumme_2.4.2_ScoreAccurate.mid`
- `E:/Users/james/Downloads/the-animals-the-house-of-the-rising-sun_MusicalScumme_2.4.2_ScoreAccurate_keyplan.csv`
- `E:/Users/james/Downloads/Rush E_MusicalScumme_2.4.2_TempoFixed.mid`
- `E:/Users/james/Downloads/Rush E_MusicalScumme_2.4.2_TempoFixed_keyplan.csv`

## Live limitation

The event schedule is statically validated, but current-build SCUM must still confirm that entering instrument mode begins in the expected base bank and that the corrected standalone taps behave identically on guitar, banjo, and harmonica.
