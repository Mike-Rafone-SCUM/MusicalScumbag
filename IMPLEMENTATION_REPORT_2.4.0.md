# MusicalScumme 2.4.0 Implementation Report

Date: 2026-07-13

## Outcome

Version 2.4.0 adds a dedicated Guitar Smooth playback path and fixes the three causes found in the user's live configuration: both processed tracks were selected in Faithful mode, transcription notes as short as 5 ms were allowed, and short Smart three-octave/register plus physical retrigger decisions could produce disruptive tiny notes.

## Musical and planner changes

- Added the Guitar Smooth preset: inferred lead track only, Smart three-octave mapping, one note at a time, 90 ms source rejection, 65 ms retrigger cleanup, 12 starts/s, 105 ms minimum hold, 35 ms key-up gap, and 30/45 ms modifier release/settle timing.
- Added track activity to lead inference and made Lead melody only exclude every non-lead track before onset selection.
- Added a post-DP register guard for enclosed one-to-three-onset excursions that return within 1.2 seconds.
- Preserved sustained four-or-more-note register phrases and phrase-boundary register changes.
- Changed physical same-key handling to delay the following attack instead of violating the configured minimum hold.
- Added warnings for multitrack Faithful playback, sub-35 ms source filters, and sub-45 ms played-note settings.
- Made the recommended Song Transposer choice apply Guitar Smooth automatically when its processed output is loaded.

## Audio conversion polish

- Confirmed fresh isolated Basic Pitch inference for the full 4:22 MP3: 1,328 notes in 29.7 seconds.
- Confirmed representative 30-second WAV and M4A inference: 148 and 151 notes.
- Suppressed only the harmless successful M4A fallback/deprecation notices; decode failures and unrelated warnings remain visible.
- Confirmed the packaged worker converts M4A to a strictly readable MIDI.

## Reference-song results

- Exact raw guitar transcription: 1,328 notes.
- Smooth processor: 865 monophonic notes in D2-A4, 230 outliers removed, 29 octave repairs including nine phrase stabilizations, zero overlaps, and 65 remaining structural large jumps.
- Guitar Smooth playback: 787 notes, 1,594 key events, 36 short register groups folded, 19 modifier-state changes, five same-key retriggers delayed, and a 105 ms minimum physical note.
- Active 851-note Melody + light support output: Guitar Smooth retains 649 Track 1 lead notes, rejects 87 short attacks and all 115 support notes, and stabilizes 13 short register groups.

## Validation

- `python -m compileall -q .`: passed.
- `python -m pytest`: 60 passed.
- `ruff check .`: passed.
- Focused song processor, planner, arranger, audio, installer, and offscreen Qt suite: 48 passed.
- Main window, Audio Convert dialog, and Song Transposer constructed offscreen.
- Packaged EXE remained running during a five-second hidden smoke test.
- Packaged audio validator passed from `_internal` with isolated Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model.
- Release ZIP: 231 entries completely read, required resources present, no backslash entry names.

## Deliverables

- `dist/MusicalScumme/MusicalScumme.exe`
- `dist/MusicalScumme_2.4.0_Windows.zip`
- `dist/MusicalScumme_2.4.0_SHA256.txt`
- `E:/Users/james/Downloads/the-animals-the-house-of-the-rising-sun_MusicalScumme_2.4.0_GuitarSmooth.mid`
- `E:/Users/james/Downloads/the-animals-the-house-of-the-rising-sun_MusicalScumme_2.4.0_GuitarSmooth_keyplan.csv`

## Remaining live limitation

Static planning and real audio inference are validated. The result is not yet confirmed inside the current SCUM build; focus-loss cleanup, F8 emergency stop, SendInput acceptance, and subjective guitar quality still require the user's in-game audition.
