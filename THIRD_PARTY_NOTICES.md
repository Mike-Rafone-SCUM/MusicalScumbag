# Third-party notices

MusicalScumme uses or optionally installs the following third-party software. Each component remains subject to its own licence and copyright notices.

## PySide6 6.11.1

Qt for Python / PySide6. Licence expression published by the installed package: `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. Commercial Qt licensing may also be available from Qt Group. Anyone redistributing a packaged executable is responsible for complying with the applicable Qt licence terms and preserving required notices.

## Mido 1.3.3

Mido is distributed under the MIT License.

## python-rtmidi 1.5.8

Live MIDI keyboard input uses python-rtmidi, an MIT-licensed Python binding for the RtMidi C++ library. The Windows wheel uses the Windows MultiMedia MIDI API.

## Spotify Basic Pitch 0.4.0 — optional

Basic Pitch is not bundled into the core application. The optional installer downloads it into a separate per-user Python environment. Basic Pitch is distributed under the Apache License 2.0.

## Ultimate Vocal Remover 5.6 — optional

Ultimate Vocal Remover is installed separately from its official GitHub release and is distributed under the MIT License. MusicalScumme does not bundle the UVR GUI inside its release archive.

## python-audio-separator 0.44.3 — optional

The Song Transposer's isolated separation runtime uses `audio-separator`, an MIT-licensed programmatic wrapper for models from the UVR ecosystem. Credit belongs to the UVR project, its developers, the audio-separator maintainers, and the individual model authors.

## BS-RoFormer Viperx-1297 model — optional

The selected model file is `model_bs_roformer_ep_317_sdr_12.9755.ckpt`, identified by audio-separator as **BS-RoFormer Viperx-1297**. The model is downloaded into the optional per-user cache and is not bundled in MusicalScumme's application archive. Model weights and training material remain subject to their own terms; review those terms before redistribution.

## PyTorch and ONNX Runtime — optional

The separation environment installs PyTorch and ONNX Runtime GPU packages under their respective licences. NVIDIA systems use PyTorch's official CUDA 12.8 wheel index; these packages are not imported by MusicalScumme's main Qt/playback process.

## Model and transitive dependencies

The optional audio environment installs Basic Pitch and its declared dependencies from Python package indexes. Those packages and model files retain their own licences. Review the installed environment before redistributing it.

## YourMT3+ and torchcrepe — optional

The isolated advanced transcription worker uses [YourMT3+](https://github.com/mimbres/YourMT3) and [torchcrepe](https://github.com/maxrmorrison/torchcrepe). These packages and their checkpoints are downloaded separately; the application executable does not bundle their model weights or the heavy inference runtime. Credit belongs to their authors, and their own software and checkpoint terms apply.

## Additional UVR vocal-treatment models — optional

Selectable vocal treatment downloads DeEcho/DeReverb V2 and Aufr33 denoise model weights into the isolated UVR cache. Credit belongs to the UVR ecosystem and the individual model authors. These model weights are not part of the application executable.

## LRCLIB — optional online lyrics

Automatic and manual lyric searches use [LRCLIB](https://lrclib.net/docs). No lyric collection is bundled with the release; lyrics selected by the user are stored separately from the application.
