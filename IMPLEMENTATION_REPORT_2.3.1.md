# MusicalScumme 2.3.1 refinement report

## Why the 2.3.0 result still sounded risky

The 101 remaining octave-sized jumps were not one uniform defect. The supplied guitar transcription contained recurring bass-to-treble arpeggio resets that form the song's picking pattern, but it also contained 83 attacks closer than 80 ms and 13 isolated register spikes. Flattening all large jumps would erase recognizable guitar structure.

## Refinement

- Clear Melody now consolidates likely transcription double-attacks with a 65 ms onset window.
- Isolated octave spikes are eligible only when both adjacent jumps exceed an octave while the phrase endpoints remain within a fifth.
- Consecutive eligible spikes are solved together, shifts are limited to one octave, and a correction must materially improve the complete local contour.
- Guitar / arpeggio stem performs the rapid-attack cleanup but disables phrase stabilization so structural picking resets remain intact.
- Melody + light support and Fuller playable arrangement use progressively less aggressive 55 ms and 40 ms onset windows.

## Supplied reference results

Input:

`E:\Users\james\Downloads\the-animals-the-house-of-the-rising-sun_bs6stem_mt_0_guitar.transcribed.mid`

Clear Melody output:

`E:\Users\james\Downloads\the-animals-the-house-of-the-rising-sun_MusicalScumme_2.3.1_ClearMelody.mid`

- 1,328 source notes; 865 monophonic lead notes in D2–A4.
- 230 overtone/outlier notes removed.
- 29 octave repairs, including nine isolated phrase stabilizations.
- Sub-80 ms attacks reduced from 83 to 23.
- Large jumps reduced from the 2.3.0 result's 101 to 65.
- Zero lead overlaps.
- Balanced planning retains 862 notes, drops three, and emits 1,724 events.

Guitar / arpeggio stem output:

`E:\Users\james\Downloads\the-animals-the-house-of-the-rising-sun_MusicalScumme_2.3.1_GuitarArpeggio.mid`

- 865 monophonic lead notes with zero overlaps.
- 23 sub-80 ms attacks remain.
- No phrase-level octave stabilization.
- 81 octave-sized structural resets are preserved.
- Balanced planning retains 862 notes, drops three, and emits 1,724 events.

## Validation boundary

Both outputs are statically cleaner and exercise different intended contour policies. Which one sounds better for the current SCUM instrument remains a live musical judgment and must be confirmed by auditioning both in the current game build.

## Packaged-build validation

- PyInstaller 6.21.0 built the 2.3.1 Windows onedir application with Python 3.12.10.
- The packaged installer validated Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model from inside the packaged `_internal` directory.
- The packaged audio worker ran in Python isolated mode, all five audio resources were present, and `musical_scumme.song_processor` was present in the packaged Python archive.
- The packaged EXE remained running through a four-second smoke test and every resulting process was stopped afterward.
- The 231-entry `MusicalScumme_2.3.1_Windows.zip` passed a complete integrity read-through with all required resources and portable entry names.
