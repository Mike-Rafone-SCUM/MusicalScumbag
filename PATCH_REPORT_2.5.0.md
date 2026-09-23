# MusicalScumme 2.5.0 Pitch Detection and Matching

## Outcome

Version 2.5.0 treats SCUM as a chromatic instrument with a constrained C3-C6 register. It improves Basic Pitch input focus and adds a whole-song register matcher without guessing scales, changing individual chromatic notes, or altering existing custom mapping modes.

## Detection

- Guitar / arpeggio: E2-E6 by default.
- Smooth lead, support, and fuller profiles: C2-C7 by default.
- Full model range: explicit legacy fallback.
- Manual focus choices are sticky while the Song Transposer dialog remains open.
- The isolated worker validates both frequency bounds and retains `-I -X utf8`.

On the full House guitar stem, guitar focus narrowed raw output from MIDI 28-102 to 40-87. Strict time/pitch matches against the clean reference increased from 61 to 74. Automatic transcription is still approximate.

## Matching

`match3` weights arranged notes by duration and velocity, chooses one whole-octave shift that maximises exact C3-C6 coverage, and then uses the existing safe bank planner for residual outliers. It preserves pitch classes, key, direction, and intervals.

| Reference | Legacy exact intervals | Pitch Match exact intervals | Shift | Residual folds | Bank taps |
|---|---:|---:|---:|---:|---:|
| Clean House lead | 1,051 / 1,162 | 1,162 / 1,162 | +12 | 0 | 335 |
| Rough House guitar lead | 660 / 864 | 864 / 864 | +12 | 0 | 427 |

The physical cost is additional safe Ctrl/Shift bank taps. Melody contour remains selectable when fewer transitions sound better than exact interval preservation.

## Preserved behavior

- Current and historical SCUM key bindings.
- Standalone 18 ms Ctrl/Shift bank taps with zero note-key overlap.
- Lead melody only remains monophonic and never generates harmony.
- Existing Fold, Strict, Melody contour, and Smart mapping algorithms.
- The user's currently saved Rush E `melody3` plan is output-identical: 8,502 notes, 18,284 events, 312,900.1885 ms, digest `42d98ff3fed7d88b80e08a1e7276a8555414e651190ef81cf75961de671434f1`.

## Static validation

- `python -m compileall -q .`
- `python -m pytest`
- `ruff check .`
- Real WAV and MP3 Basic Pitch inference in the isolated Windows runtime.
- Representative AAC/M4A inference in the isolated Windows runtime.
- Real House clean-score and transcription comparisons.

Live musical quality for the new Pitch Match mode remains pending an audition in the current SCUM build.

## Release

- `dist/MusicalScumme_2.5.0_Windows.zip`
- `dist/MusicalScumme_2.5.0_SHA256.txt`
- 231 entries, 120,519,073 uncompressed bytes, forward-slash-only paths.
- SHA-256: `77fdb592c84cee49b52ae57ea1611b2f45a991d5b5ca760229241a2c479ef6dd`
