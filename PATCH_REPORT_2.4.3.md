# MusicalScumme 2.4.3 Lead-Led Smart Chords

Date: 2026-07-15

## Outcome

Version 2.4.3 implements both requested behaviours in one deterministic arrangement mode: preserve the inferred melody, intelligently select useful real notes from every chosen support track, and calculate only the chord tones still missing under the selected voice limit.

## Musical rules

- The inferred lead track owns the output onset timeline and remains the top voice.
- Accompaniment-only onsets, support above the lead, dissonant intervals, distant notes, and duplicate pitch classes are discarded.
- Near-simultaneous consonant source notes are ranked before any note is generated.
- Missing voices use the strongest locally evidenced major/minor triad containing the current melody pitch class.
- Generated tones are compactly voiced below the lead, slightly quieter, and use the lead rhythm.
- Maximum chord notes 1, 2, and 3 produce lead, duet, and three-voice output. Lead-led mode never exceeds three voices.
- Melody contour mapping preserves the lead octave at SCUM bank boundaries and folds only support when an exact cross-bank chord is impossible.

## Static musical results

### Selected three-guitar House score

- Source: `House Of The Rising Sun [ The Animals ].mid`, selected tracks 0, 2, and 4.
- Protected lead: track 4, 1,169 attacks.
- Two voices: 529 real support notes and 631 calculated tones reach the physical plan; 2,323 notes are planned.
- Three voices: 961 real support notes and 1,362 calculated tones reach arrangement filtering; 3,486 notes are physically planned after six duplicate-key folds.
- Setting Maximum chord notes to eight produces the same three-voice ceiling.
- Three-voice duration is 240.12 seconds with a 234.96 ms median lead gap, 212 octave-bank taps, and zero octave-control/musical-key overlap.

### Prepared House lead and Light Support

- Source: 736 Lead Melody notes plus 115 Light Support notes.
- The lead remains track 1 with all 736 onset groups.
- Two voices: 78 real source support notes are used and missing voices are calculated.
- Three voices: 2,145 notes reach the final physical plan after density and duplicate-key safety; duration remains 235.62 seconds.
- Zero octave-control/musical-key overlap.

### Exact raw Basic Pitch guitar reference

- Source: 1,328 notes, MIDI range 28-102.
- Pure lead plans 1,064 notes; two voices plan 2,106; three voices plan 3,019 after the density guard.
- This raw transcription still contains source pitch mistakes. The clean score-derived or processed MIDI remains recommended because calculated harmony cannot make a wrong detected melody note correct.

## Validation

- `.build-venv\Scripts\python.exe -m compileall -q .`: passed.
- `.build-venv\Scripts\python.exe -m pytest`: 78 passed.
- `.build-venv\Scripts\ruff.exe check .`: passed.
- Main window, Audio Convert dialog, and Song Transposer constructed offscreen through the full suite.
- Packaged EXE remained alive during a five-second hidden/offscreen smoke test.
- Packaged runtime validation passed from `_internal` with Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model.
- Packaged worker converted the supplied WAV into a strict 143-note MIDI without optional-backend warnings, TensorFlow's CPU banner, or corrupted Unicode.
- Release ZIP: all 231 entries / 120,521,472 uncompressed bytes read successfully; required resources are present and no entry uses a backslash path.
- ZIP SHA-256: `1cf538a28a1ffcf5cd0751e5887221ac34fbe23d26e0c31cd4e7aa24944de75f`.

## Deliverables

- `dist/MusicalScumme/MusicalScumme.exe`
- `dist/MusicalScumme_2.4.3_Windows.zip`
- `dist/MusicalScumme_2.4.3_SHA256.txt`

## Live limitation

The complete key schedule is statically validated, but chord voicing quality and SCUM's ability to register every two- or three-note attack still require an audition in the current game build. Start with two voices; use three only when the guitar accepts it cleanly.
