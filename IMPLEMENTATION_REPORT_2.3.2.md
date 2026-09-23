# MusicalScumme 2.3.2 audio-worker diagnostic repair

## Reported output

```text
WARNING:root:Coremltools is not installed...
WARNING:root:tflite-runtime is not installed...
WARNING:root:onnxruntime is not installed...
Analysing audio� This can take several minutes for a full song.
I tensorflow/core/platform/cpu_feature_guard.cc:182] This TensorFlow binary is optimized...
```

## Root causes

- Basic Pitch probes every supported inference backend during import. MusicalScumme uses its validated TensorFlow `nmp` SavedModel, so CoreML, TFLite, and ONNX are optional and intentionally absent.
- TensorFlow writes an informational CPU capability banner from native code when inference first loads the model.
- Redirected Python 3.11 output on this Windows installation defaults to `cp1252`; Qt decodes the worker protocol as UTF-8. The `cp1252` ellipsis byte therefore became a replacement character.

## Repair

- Configure logging and `TF_CPP_MIN_LOG_LEVEL=2` before importing Basic Pitch.
- Preserve actual error-level logs, worker exceptions, and non-zero exits.
- Launch the worker with `-I -X utf8`.
- Emit ASCII-safe newline-delimited JSON so Unicode messages and paths survive any transport boundary.

## Real-file validation

The repaired source worker processed:

`E:\Users\james\Downloads\the-animals-the-house-of-the-rising-sun_bs6stem_mt_0_guitar.mp3`

Result:

- Duration: approximately 4:22.
- Inference wall time: 36 seconds.
- Raw MIDI notes: 1,328.
- Optional-backend warnings: none.
- TensorFlow CPU banner: absent.
- Replacement characters: absent.
- Temporary validation MIDI removed after inspection.

## Packaged-build validation

- PyInstaller 6.21.0 built the Windows onedir package with Python 3.12.10.
- The packaged validator confirmed Python 3.11.9, Basic Pitch 0.4.0, Mido 1.3.3, setuptools 80.10.2, and the `nmp` model.
- The packaged `_internal/audio_worker.py` completed the same full guitar MP3 with the same 1,328 notes and 10,014-byte MIDI result, without the reported diagnostics.
- All required audio resources and both `musical_scumme.audio_tools` and `musical_scumme.song_processor` were present.
- The EXE passed a four-second launch smoke test and every test process was stopped afterward.
- The 231-entry Windows release ZIP passed a complete integrity read-through with all required resources and portable entry names.
