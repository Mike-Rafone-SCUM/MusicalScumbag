"""Isolated optional audio-to-MIDI worker for MusicalScumme.

This file intentionally runs in a separate Python 3.10/3.11 environment so the
large machine-learning dependency stack cannot destabilise the main UI runtime.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import tempfile
import warnings
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".ogg", ".wav", ".flac", ".m4a"}
DEFAULT_ONSET_THRESHOLD = 0.45
DEFAULT_FRAME_THRESHOLD = 0.30
DEFAULT_MINIMUM_NOTE_MS = 90
REATTACK_MINIMUM_CURRENT_S = 0.18
REATTACK_MINIMUM_NEXT_S = 0.10
REATTACK_MINIMUM_VELOCITY_RISE = 12


@dataclass(slots=True)
class NoteEvent:
    start_s: float
    end_s: float
    pitch: int
    velocity: int


def emit(event: str, **payload: object) -> None:
    # Keep the pipe protocol ASCII-safe even when a user path or status message
    # contains Unicode. json.loads restores the original text in the Qt process.
    print(json.dumps({"event": event, **payload}, ensure_ascii=True), flush=True)


def configure_inference_runtime() -> None:
    """Hide known successful-fallback chatter while preserving real inference errors."""

    # The distributed model is the validated TensorFlow SavedModel. Basic Pitch
    # probes CoreML, TFLite, and ONNX during import and logs warnings when those
    # unused optional runtimes are absent. TensorFlow also prints a CPU feature
    # banner from native code unless this is set before its first import.
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
    logging.basicConfig(level=logging.ERROR)
    logging.getLogger("tensorflow").setLevel(logging.ERROR)
    warnings.filterwarnings(
        "ignore",
        message="pkg_resources is deprecated as an API.*",
        category=UserWarning,
    )
    # SoundFile cannot decode every Windows M4A container, but librosa's
    # audioread fallback handles the same file successfully. Hide only the
    # successful fallback/deprecation notices; a failed fallback still raises.
    warnings.filterwarnings(
        "ignore",
        message=r"PySoundFile failed\. Trying audioread instead\.",
        category=UserWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=r"librosa\.core\.audio\.__audioread_load.*",
        category=FutureWarning,
    )


def merge_note_events(events: list[NoteEvent], gap_s: float = 0.045) -> list[NoteEvent]:
    by_pitch: dict[int, list[NoteEvent]] = {}
    for event in events:
        by_pitch.setdefault(event.pitch, []).append(event)

    merged: list[NoteEvent] = []
    for _pitch, pitch_events in by_pitch.items():
        pitch_events.sort(key=lambda item: (item.start_s, item.end_s))
        current: NoteEvent | None = None
        previous_raw: tuple[float, float, int] | None = None
        for event in pitch_events:
            raw_event = (event.start_s, event.end_s, event.velocity)
            if current is None:
                current = event
                previous_raw = raw_event
                continue
            assert previous_raw is not None
            previous_start, previous_end, previous_velocity = previous_raw
            close_boundary = event.start_s <= current.end_s + gap_s
            confident_reattack = (
                event.start_s >= previous_end - 0.020
                and previous_end - previous_start >= REATTACK_MINIMUM_CURRENT_S
                and event.end_s - event.start_s >= REATTACK_MINIMUM_NEXT_S
                and event.velocity - previous_velocity >= REATTACK_MINIMUM_VELOCITY_RISE
            )
            if close_boundary and not confident_reattack:
                current.end_s = max(current.end_s, event.end_s)
                current.velocity = max(current.velocity, event.velocity)
            else:
                merged.append(current)
                current = event
            previous_raw = raw_event
        if current is not None:
            merged.append(current)
    merged.sort(key=lambda item: (item.start_s, item.pitch, item.end_s))
    return merged


def write_midi(events: list[NoteEvent], output_path: Path, tempo_bpm: float = 120.0) -> None:
    import mido

    ticks_per_beat = 480
    tempo = mido.bpm2tempo(tempo_bpm)
    timeline: list[tuple[float, int, int, int]] = []
    for event in events:
        timeline.append((event.start_s, 1, event.pitch, event.velocity))
        timeline.append((event.end_s, 0, event.pitch, 0))
    timeline.sort(key=lambda item: (item[0], item[1], item[2]))

    midi = mido.MidiFile(type=1, ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name="Audio transcription", time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))

    last_tick = 0
    for at_s, action, pitch, velocity in timeline:
        absolute_tick = round(mido.second2tick(max(0.0, at_s), ticks_per_beat, tempo))
        delta = max(0, absolute_tick - last_tick)
        last_tick = absolute_tick
        if action:
            track.append(mido.Message("note_on", note=pitch, velocity=velocity, time=delta))
        else:
            track.append(mido.Message("note_off", note=pitch, velocity=0, time=delta))
    track.append(mido.MetaMessage("end_of_track", time=0))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        midi.save(temporary)
        temporary.replace(output_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert audio to a clean MIDI file for MusicalScumme.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--onset-threshold", type=float, default=DEFAULT_ONSET_THRESHOLD)
    parser.add_argument("--frame-threshold", type=float, default=DEFAULT_FRAME_THRESHOLD)
    parser.add_argument("--minimum-note-ms", type=int, default=DEFAULT_MINIMUM_NOTE_MS)
    parser.add_argument("--minimum-frequency", type=float)
    parser.add_argument("--maximum-frequency", type=float)
    parser.add_argument("--mode", choices=("polyphonic", "vocals", "instrumental"), default="polyphonic")
    parser.add_argument("--vocal-confidence", type=float, default=0.01)
    return parser.parse_args()


def pitch_track_notes(frequencies, probabilities, energies, *, hop_s, duration_s, minimum_note_ms, confidence=0.01):
    """Segment measured vocal fundamentals with hysteresis; never bridge silence."""
    if not (len(frequencies) == len(probabilities) == len(energies)):
        raise ValueError("Vocal pitch arrays have different lengths")
    peak = max(energies, default=0.0)
    floor = max(1e-5, peak * 0.025)
    events = []
    active_pitch = None
    start = 0
    strength = 0.0

    def finish(index):
        if active_pitch is not None:
            end = min(duration_s, index * hop_s)
            if (end - start * hop_s) * 1000 >= minimum_note_ms:
                velocity = max(1, min(127, round(127 * math.sqrt(strength / max(peak, 1e-9)))))
                events.append(NoteEvent(start * hop_s, end, active_pitch, velocity))

    for index, (frequency, probability, energy) in enumerate(zip(frequencies, probabilities, energies, strict=True)):
        valid = math.isfinite(frequency) and frequency > 0 and probability >= confidence and energy >= floor
        measured = 69 + 12 * math.log2(frequency / 440) if valid else None
        pitch = round(measured) if measured is not None else None
        if pitch is not None and active_pitch is not None and abs(measured - active_pitch) <= 0.65:
            pitch = active_pitch
        if pitch is not None and not 0 <= pitch <= 127:
            pitch = None
        if pitch != active_pitch:
            finish(index)
            active_pitch, start, strength = pitch, index, 0.0
        strength = max(strength, energy)
    finish(len(frequencies))
    return events


def transcribe_vocals(path, args):
    import librosa

    audio, rate = librosa.load(path, sr=16000, mono=True)
    hop = 160
    emit("status", message="Tracking the vocal fundamental (pYIN); rejecting unvoiced audio…")
    frequencies, _, probabilities = librosa.pyin(
        audio, sr=rate, fmin=args.minimum_frequency or 65.406,
        fmax=min(args.maximum_frequency or 1046.502, rate / 2 - 1),
        frame_length=2048, hop_length=hop,
    )
    energies = librosa.feature.rms(y=audio, frame_length=2048, hop_length=hop)[0]
    return pitch_track_notes(
        frequencies, probabilities, energies, hop_s=hop / rate, duration_s=len(audio) / rate,
        minimum_note_ms=args.minimum_note_ms, confidence=args.vocal_confidence,
    )


def transcribe_polyphonic(path, args):
    from basic_pitch.inference import predict

    with tempfile.TemporaryDirectory(prefix="musicalscumme-transcribe-") as temporary:
        inference_path = path
        if args.mode == "instrumental":
            import librosa
            import soundfile as sf

            emit("status", message="Reducing drum transients before backing-note detection…")
            audio, rate = librosa.load(path, sr=22050, mono=True)
            harmonic = librosa.effects.harmonic(audio, margin=2.0)
            inference_path = Path(temporary) / "harmonic.wav"
            sf.write(inference_path, harmonic, rate, subtype="FLOAT")
        _, _, raw_events = predict(
            inference_path, onset_threshold=args.onset_threshold, frame_threshold=args.frame_threshold,
            minimum_note_length=float(args.minimum_note_ms), minimum_frequency=args.minimum_frequency,
            maximum_frequency=args.maximum_frequency, multiple_pitch_bends=False,
            melodia_trick=args.mode == "polyphonic", midi_tempo=120.0,
        )
    events = []
    for start_s, end_s, pitch, amplitude, _ in raw_events:
        if not all(math.isfinite(value) for value in (start_s, end_s, pitch, amplitude)) or end_s <= start_s:
            continue
        if not 0 <= pitch <= 127 or amplitude <= 0:
            continue
        events.append(NoteEvent(float(start_s), float(end_s), int(pitch), max(1, min(127, round(amplitude * 127)))))
    # Detector onsets are evidence of reattacks, even at equal velocity.
    # Only overlapping duplicates are merged in the stem-aware modes.
    return merge_note_events(events) if args.mode == "polyphonic" else merge_detected_notes(events)


def merge_detected_notes(events):
    result = []
    for event in sorted(events, key=lambda note: (note.pitch, note.start_s, note.end_s)):
        if result and event.pitch == result[-1].pitch and event.start_s < result[-1].end_s - 0.020:
            result[-1].end_s = max(result[-1].end_s, event.end_s)
            result[-1].velocity = max(result[-1].velocity, event.velocity)
        else:
            if result and event.pitch == result[-1].pitch:
                result[-1].end_s = min(result[-1].end_s, event.start_s)
            result.append(NoteEvent(event.start_s, event.end_s, event.pitch, event.velocity))
    return sorted(result, key=lambda note: (note.start_s, note.pitch))


def main() -> int:
    configure_inference_runtime()
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    if input_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_AUDIO_EXTENSIONS))
        raise ValueError(f"Unsupported audio type. Supported extensions: {supported}")
    if output_path.suffix.lower() not in {".mid", ".midi"}:
        raise ValueError("Output path must end in .mid or .midi")
    if not 0.01 <= args.onset_threshold <= 0.99 or not 0.01 <= args.frame_threshold <= 0.99:
        raise ValueError("Audio thresholds must be between 0.01 and 0.99")
    if not 0.0 <= args.vocal_confidence <= 1.0:
        raise ValueError("Vocal confidence must be between 0 and 1")
    if not 20 <= args.minimum_note_ms <= 2000:
        raise ValueError("Minimum note length must be 20..2000 ms")
    for label, frequency in (
        ("Minimum", args.minimum_frequency),
        ("Maximum", args.maximum_frequency),
    ):
        if frequency is not None and (not math.isfinite(frequency) or frequency <= 0.0):
            raise ValueError(f"{label} frequency must be a positive finite number")
    if (
        args.minimum_frequency is not None
        and args.maximum_frequency is not None
        and args.minimum_frequency >= args.maximum_frequency
    ):
        raise ValueError("Minimum frequency must be below maximum frequency")

    emit("status", message="Loading transcription model…")
    emit("status", message="Analysing audio… This can take several minutes for a full song.")
    events = transcribe_vocals(input_path, args) if args.mode == "vocals" else transcribe_polyphonic(input_path, args)

    emit("status", message="Cleaning transcription for game playback…")
    if not events:
        raise RuntimeError("No usable notes were detected. Try lower onset/frame thresholds or cleaner audio.")
    write_midi(events, output_path)
    duration_s = max(event.end_s for event in events)
    emit(
        "complete",
        output=str(output_path),
        notes=len(events),
        mode=args.mode,
        duration_seconds=round(duration_s, 3),
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        emit("error", message=str(exc), error_type=type(exc).__name__)
        raise SystemExit(1) from exc
