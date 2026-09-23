# MusicalScumme 2.7.0 Professional SCUM Score Conversion

Date: 2026-07-15

## Outcome

Version 2.7.0 upgrades Game-optimised MIDI conversion with conservative source-backed performed-chord recognition and adds a first-class auditable SCUM-score export. It is built directly from the validated 2.6.0 source tree.

## Musical conversion

- Automatic recognition derives a 12-45 ms chord window from the score's upper-quartile inter-onset spacing instead of applying one wide fixed threshold to every song.
- An expanded group must contain at least two pitch classes and retain meaningful shared sustain after its latest attack.
- Only real selected MIDI notes may enter a chord. Accepted offsets align to the chord attack while every note retains its source duration.
- Lead melody only remains one inferred monophonic voice. Faithful / legacy retains source timing. The rejected generated-harmony and support-borrowing experiment remains absent.
- Exact MIDI attacks only is available as the legacy grouping fallback.

## SCUM score artifact

- The new score CSV records score group, voice order, chord size, attack/release/duration, source note, mapped note, persistent octave bank, SCUM key, and velocity.
- Score CSV publication is atomic through a same-destination temporary file.
- The existing low-level key-event CSV remains a separate export.

## Static musical evidence

- The current selected Rush E fixture is automatic/exact equivalent: 4,289 planned notes, 9,064 key events, 243 octave-bank taps, and 299,292.575 ms duration. Its adaptive window remains 12 ms and aligns no false chords.
- Selected House tracks 0/2/4 use the capped 45 ms window and align six additional sustained source-backed chord groups without changing total duration.
- A prepared monophonic Bob Marley fixture retains 622 one-note score groups and introduces no chords.
- The raw House guitar reference still processes to 865 monophonic lead notes in D2-A4 under both evaluated profiles. Smooth lead retains 65 large leaps with nine phrase stabilizations; Guitar / arpeggio retains 81 structural resets with no phrase stabilization. Both retain zero overlaps and plan to 865 notes / 1,730 events under Balanced settings.

## Validation

- `.build-venv\Scripts\python.exe -m compileall -q .`: passed.
- `.build-venv\Scripts\python.exe -m pytest`: 93 passed.
- `.build-venv\Scripts\ruff.exe check .`: passed.
- Main window, Audio Convert dialog, and Song Transposer constructed offscreen through the full suite.
- The staged onedir EXE stayed alive through a six-second offscreen smoke test.
- Packaged Basic Pitch and UVR validators passed from `_internal`; UVR exposed CUDA on the NVIDIA GeForce RTX 2070 SUPER.
- Packaged five-second MP3 separation produced two readable 884,968-byte PCM WAV stems. Packaged Basic Pitch produced 23 strict raw MIDI notes, deterministic Song Transposer cleanup retained 20, and SCUM-score export wrote 20 auditable rows.
- `MusicalScumme_2.7.0_Windows.zip` passed a full 236-entry / 120,549,542-byte read-through with one `MusicalScumme/` root, required resources present, and forward-slash-only paths.
- ZIP SHA-256: `41d1e8caa5c11a1bd1748c5884f617c9a204cfbd586296ca6bd552cd2a0e73d2`.

## Live limitation

The conversion and physical key schedule are statically validated. Chord timing and musical quality remain unconfirmed until version 2.7.0 is auditioned in the current SCUM build on Windows; focus-loss cleanup and F8 emergency stop also require that live release check.
