# MusicalScumme 2.3.3 malformed MIDI recovery report

## Reported failure

```text
Could not process the song:

data byte must be in range 0..127
```

The application traceback showed that `mido.MidiFile` failed while reopening:

`E:\Users\james\Downloads\Rush E.mid`

The Song Transposer algorithm had not started yet.

## Root cause

`Rush E.mid` is a five-track third-party MIDI containing 19,043 note attacks. At file offset 25,410, a note-on event encodes pitch 28 and velocity 129. MIDI channel-message data bytes must be `0..127`, so strict Mido parsing correctly rejected the file.

## Repair

- Preserve strict parsing as the first attempt.
- Retry with Mido's supported `clip=True` mode only for the exact out-of-range-data-byte error.
- Record and display that illegal data values were clipped to 127.
- Propagate the warning into Song Transposer output.
- Leave all other structural parse errors fatal.
- Never modify the original source file.

## Actual-file result

Output:

`E:\Users\james\Downloads\Rush E_MusicalScumme_2.3.3_ClearMelody.mid`

- Source notes: 19,043.
- Clear Melody notes: 1,709.
- Detected range: A2–E5.
- Outliers removed: 8,041.
- Octave repairs: 1,109, including four phrase stabilizations.
- Lead overlaps: zero.
- Remaining jumps larger than one octave: 43.
- Balanced plan: 1,624 retained, 85 dropped, 3,248 key events.

The output loads strictly without recovery. Live musical quality in the current SCUM instrument remains unconfirmed until auditioned.

## Packaged-build validation

- PyInstaller 6.21.0 built the Windows onedir package with Python 3.12.10.
- `musical_scumme.midi_engine` and `musical_scumme.song_processor` were present in the packaged Python archive.
- The packaged validator confirmed Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model.
- The EXE passed a four-second launch smoke test and every test process was stopped afterward.
- The 231-entry Windows release ZIP passed a complete integrity read-through with all required resources and portable entry names.
