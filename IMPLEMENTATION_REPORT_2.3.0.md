# MusicalScumme 2.3.0 implementation report

## Goal

Turn a rough Basic Pitch transcription into an explicitly calculated, inspectable MIDI arrangement before SCUM playback instead of relying on the generic onset selector to interpret transcription artifacts.

## Pipeline

```text
Audio input -> isolated Basic Pitch worker -> user-visible raw MIDI
Raw/existing MIDI -> Song Transposer -> processed Lead Melody / optional support MIDI
Processed MIDI -> Game-optimised reliability limits -> SCUM key plan
```

The stages remain independent. Basic Pitch is never imported by the main process, and the Song Transposer never sends keyboard input.

## Musical processing

- Weighted dominant-register detection.
- Rejection of short, low-confidence notes outside that register.
- Contextual octave repair for stronger outliers.
- Consolidation of near-simultaneous transcription attacks.
- Global dynamic-programming melody continuity.
- Optional consonant bass/harmony support.
- Monophonic lead articulation and atomic MIDI export.

## Reference result

Input:

`E:\Users\james\Downloads\the-animals-the-house-of-the-rising-sun_bs6stem_mt_0_guitar.transcribed.mid`

Processed output:

`E:\Users\james\Downloads\the-animals-the-house-of-the-rising-sun_MusicalScumme_2.3.0.mid`

- 1,328 source notes.
- 924 monophonic lead notes.
- 230 overtone/outlier notes removed.
- 20 octave errors repaired.
- Core register detected as D2–A4.
- Lead jumps larger than one octave reduced from 472 to 101.
- Balanced SCUM plan retains 890 notes and emits 1,780 key events.

## Preserved behavior

- Existing arrangement modes and performance presets.
- Current SCUM bindings and input backends.
- F8, focus-loss cleanup, dry-run, and scheduler behavior.
- Isolated Basic Pitch installation and child-process protections.
- Raw Audio to MIDI remains available as a separate command.

## Build validation

- Python compilation, all 47 automated tests, and Ruff passed.
- Main window, raw audio dialog, and Song Transposer constructed offscreen.
- PyInstaller 6.21.0 built the Windows onedir application with Python 3.12.10.
- The packaged installer validated Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model.
- The packaged worker ran in isolated mode, the song processor was present in the Python archive, and the EXE passed a four-second launch smoke test.
- The 231-entry Windows release ZIP passed a complete integrity read-through with portable entry names.
- Live SCUM audition and representative MP3/WAV/M4A end-to-end transposition remain pending.
