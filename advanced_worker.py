"""Isolated YourMT3+ inference. No Qt, playback, scheduler or input imports."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from collections import defaultdict
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

REVISION = "5e66c1ea173a8186e0d20432b841d3180cc015b5"
MODEL_NAME = "mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b36_nops"
CHECKPOINT = f"amt/logs/2024/{MODEL_NAME}/checkpoints/last.ckpt"
CHECKPOINT_SHA256 = "ae38e415c79efd5592dcb9b658cdb99ddb11d4c4e1eaa364cab04a052473fc25"
EVIDENCE_VERSION = 2
PROGRAM_NAMES = {
    0: "Acoustic piano", 2: "Electric piano", 8: "Chromatic percussion", 16: "Organ",
    24: "Clean guitar", 30: "Distortion guitar", 33: "Bass", 48: "Strings",
    56: "Brass", 64: "Reed", 72: "Pipe", 80: "Synth lead", 88: "Synth pad",
    100: "Vocals", 101: "Backing vocals", 128: "Drums",
}


def instrument_program(program: int) -> int | None:
    """Use the upstream extended instrument classes, including singing tokens."""
    if program in {100, 101, 128}:
        return program
    if 0 <= program < 8:
        return 2 if program in {2, 4, 5} else 0
    if 8 <= program < 24:
        return 8 if program < 16 else 16
    if 24 <= program < 32:
        return 24 if program < 28 else 30
    if 32 <= program < 40:
        return 33
    if 40 <= program < 56:
        return 48
    for lower in (56, 64, 72, 80, 88):
        if lower <= program < lower + 8:
            return lower
    return None


@dataclass(frozen=True)
class TranscribedNote:
    program: int
    pitch: int
    onset: float
    offset: float
    velocity: int = 1
    is_drum: bool = False


def emit(event: str, **payload) -> None:
    print(json.dumps({"event": event, **payload}), flush=True)


def _configure_numba_cache(runtime: Path) -> Path:
    """Select a writable process-local cache before lazy librosa/Numba imports."""
    cache = runtime.resolve() / "cache" / "numba"
    probe = cache / f".write-check-{os.urandom(8).hex()}"
    created = False
    try:
        cache.mkdir(parents=True, exist_ok=True)
        # Direct exclusive creation fails promptly on Windows. tempfile can
        # retry thousands of names when ACLs deny an apparently writable path.
        with probe.open("xb") as output:
            created = True
            output.write(b"ready")
        probe.unlink()
    except OSError as exc:
        if created:
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass
        raise RuntimeError(
            f"The advanced inference cache is not writable: {cache}. "
            "Move or repair the advanced runtime in a writable folder."
        ) from exc
    # This changes only this isolated worker's environment, never user settings
    # or the installed packages' cache directories.
    os.environ["NUMBA_CACHE_DIR"] = str(cache)
    return cache


def valid_notes(notes, duration: float, *, role: str = "full", include_drums: bool = False):
    """Filter roles and invalid/padded predictions without musical rewriting."""
    if role not in {"full", "vocals", "instrumental"} or not math.isfinite(duration) or duration <= 0:
        raise ValueError("Invalid role or source duration")
    result = []
    seen = set()
    for note in notes:
        drum = bool(note.is_drum) or note.program == 128
        vocal = note.program in {100, 101}
        if drum and not include_drums:
            continue
        if role == "vocals" and not vocal or role == "instrumental" and vocal:
            continue
        program = 128 if drum else instrument_program(note.program)
        if program is None:
            continue
        if not 0 <= note.pitch <= 127:
            continue
        onset = float(note.onset)
        offset = onset + 0.12 if drum else float(note.offset)
        if not math.isfinite(onset) or not math.isfinite(offset):
            continue
        onset, offset = max(0.0, onset), min(duration, offset)
        if offset <= onset:
            continue
        key = (program, note.pitch, onset, offset)
        if key in seen:
            continue
        seen.add(key)
        velocity = 88 if note.velocity == 1 else max(1, min(127, int(note.velocity)))
        result.append(TranscribedNote(program, note.pitch, onset, offset, velocity, drum))
    return sorted(result, key=lambda n: (n.onset, n.program, n.pitch, n.offset))


def write_native_midi(notes, destination: Path, *, audio_checked: bool = False) -> None:
    """Keep instrument tracks and absolute seconds; write atomically to this exact path."""
    import mido

    if not notes:
        raise ValueError("No usable notes detected; the previous output has been preserved.")
    grouped = defaultdict(list)
    for note in notes:
        grouped[note.program].append(note)
    midi = mido.MidiFile(type=1, ticks_per_beat=1000)
    tempo = mido.MidiTrack()
    title = "Audio-checked transcription" if audio_checked else "YourMT3+ transcription"
    tempo.append(mido.MetaMessage("track_name", name=title, time=0))
    if audio_checked:
        tempo.append(mido.MetaMessage("text", text="Monophonic vocal F0; backing spectral support is approximate. "
                                     "Backing program is an audition sound, not instrument identification.", time=0))
    tempo.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    midi.tracks.append(tempo)
    channels = iter(c for c in range(16) if c != 9)
    order = sorted(grouped, key=lambda p: (0 if p == 100 else 1 if p == 101 else 2, p))
    for program in order:
        channel = 9 if program == 128 else next(channels)
        track = mido.MidiTrack()
        name = "Backing (unlabelled)" if audio_checked and program == 0 else PROGRAM_NAMES[program]
        track.append(mido.MetaMessage("track_name", name=name, time=0))
        # The model reserves GM FX programs 100/101 for singing. Use GM choir for audition.
        if program != 128:
            gm = 53 if program == 100 else 54 if program == 101 else program
            track.append(mido.Message("program_change", program=gm, channel=channel, time=0))
        events = []
        for note in grouped[program]:
            start, end = round(note.onset * 2000), round(note.offset * 2000)
            if end <= start:
                end = start + 1
            events.append((start, 1, note.pitch, note.velocity))
            events.append((end, 0, note.pitch, 0))
        previous = 0
        for tick, on, pitch, velocity in sorted(events):
            track.append(mido.Message("note_on" if on else "note_off", channel=channel,
                                      note=pitch, velocity=velocity, time=tick - previous))
            previous = tick
        midi.tracks.append(track)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".mid", delete=False) as handle:
            temporary = Path(handle.name)
        midi.save(temporary)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_model(runtime: Path):
    """Load the pinned upstream model offline, with restricted checkpoint deserialization."""
    vendor = runtime / "vendor"
    checkpoint = vendor / CHECKPOINT
    with checkpoint.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if digest != CHECKPOINT_SHA256:
        raise ValueError("YourMT3+ checkpoint failed verification. Repair the advanced runtime.")
    os.environ["WANDB_MODE"] = "disabled"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    sys.path.insert(0, str(vendor))
    sys.path.insert(0, str(vendor / "amt/src"))
    import model_helper
    import numpy as np
    import torch
    from config.config import shared_cfg
    from utils.event_codec import FastCodec
    from utils.note_event_dataclasses import Event, EventRange
    from utils.task_manager import TaskManager
    from utils.tokenizer import NoteEventTokenizer

    def initialize(args, stage="test"):
        cfg = deepcopy(shared_cfg)
        cfg["WANDB"]["mode"] = "disabled"
        return None, None, {"lightning_dir": str(checkpoint.parent.parent),
                            "last_ckpt_path": str(checkpoint)}, cfg

    original_load, original_initialize = torch.load, model_helper.initialize_trainer

    def safe_load(*args, **kwargs):
        kwargs["weights_only"] = True
        with torch.serialization.safe_globals([
            TaskManager, NoteEventTokenizer, FastCodec, Event, EventRange,
            np.core.multiarray._reconstruct, np.core.multiarray.scalar,
            np.ndarray, np.dtype, type(np.dtype("float64")), type(np.dtype("int64")),
        ]):
            return original_load(*args, **kwargs)

    arguments = [MODEL_NAME + "@last.ckpt", "-p", "2024", "-tk", "mc13_full_plus_256",
                 "-dec", "multi-t5", "-nl", "26", "-enc", "perceiver-tf", "-sqr", "1",
                 "-ff", "moe", "-wf", "4", "-nmoe", "8", "-kmoe", "2", "-act", "silu",
                 "-epe", "rope", "-rp", "1", "-ac", "spec", "-hop", "300", "-atc", "1", "-pr", "32"]
    try:
        torch.load, model_helper.initialize_trainer = safe_load, initialize
        # Upstream prints configuration; keep structured progress on stdout.
        with redirect_stdout(sys.stderr):
            model = model_helper.load_model_checkpoint(args=arguments, device="cpu")
    finally:
        torch.load, model_helper.initialize_trainer = original_load, original_initialize
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return model.to(device).eval(), device


def infer(model, device: str, source: Path, second_input: Path | None = None, limit: float | None = None):
    import librosa
    import numpy as np
    import torch
    from utils.audio import slice_padded_array
    from utils.event2note import merge_zipped_note_events_and_ties_to_notes
    from utils.note2event import mix_notes

    rate, frames = model.audio_cfg["sample_rate"], model.audio_cfg["input_frames"]
    audio, _ = librosa.load(source, sr=rate, mono=True, duration=limit)
    if second_input:
        other, _ = librosa.load(second_input, sr=rate, mono=True, duration=limit)
        if len(other) != len(audio):
            raise ValueError("Stem durations differ; they cannot be synchronized safely.")
        audio += other
    if len(audio) == 0 or not np.isfinite(audio).all():
        raise ValueError("The source is empty or contains non-finite samples.")
    peak = np.max(np.abs(audio))
    if peak > 1:
        audio /= peak
    duration = len(audio) / rate
    segments = slice_padded_array(audio[None, :], frames, frames)
    tokens = []
    batch_size = 2 if device == "cuda" else 1
    with torch.inference_mode(), torch.autocast(device, dtype=torch.float16, enabled=device == "cuda"):
        for index in range(0, len(segments), batch_size):
            batch = torch.from_numpy(segments[index:index + batch_size].astype("float32")).unsqueeze(1).to(device)
            predicted, _ = model.inference_file(bsz=batch_size, audio_segments=batch)
            tokens.extend(predicted)
            emit("status", message=f"Transcribed {min(index + batch_size, len(segments))}/{len(segments)} segments",
                 current=min(index + batch_size, len(segments)), total=len(segments))
    starts = [frames * i / rate for i in range(len(segments))]
    all_notes = []
    for channel in range(model.task_manager.num_decoding_channels):
        zipped, _, _ = model.task_manager.detokenize_list_batches(
            [arr[:, channel, :] for arr in tokens], starts, return_events=True)
        notes, _ = merge_zipped_note_events_and_ties_to_notes(zipped)
        all_notes.append(notes)
    return mix_notes(all_notes), duration


def transcribe_parts(model, device: str, source: Path, second_input: Path | None,
                     limit: float | None, role: str, stem_passes: bool):
    if not stem_passes:
        notes, duration = infer(model, device, source, second_input, limit)
        return valid_notes(notes, duration, include_drums=True), valid_notes(notes, duration, role=role)
    if second_input is None:
        raise ValueError("Independent stem transcription needs both synchronized stems.")
    emit("status", message="Pass 1/2: recognizing the isolated vocal melody…")
    vocals, duration = infer(model, device, source, limit=limit)
    emit("status", message="Pass 2/2: recognizing the isolated backing instruments…")
    backing, backing_duration = infer(model, device, second_input, limit=limit)
    if abs(duration - backing_duration) > 1 / model.audio_cfg["sample_rate"]:
        raise ValueError("Stem durations differ; previous MIDI outputs have been preserved.")
    raw = valid_notes(vocals + backing, duration, include_drums=True)
    selected = []
    if role in {"full", "vocals"}:
        selected.extend(valid_notes(vocals, duration, role="vocals"))
    if role in {"full", "instrumental"}:
        selected.extend(valid_notes(backing, duration, role="instrumental"))
    return raw, sorted(selected, key=lambda n: (n.onset, n.program, n.pitch, n.offset))


def evidence_module():
    # -I intentionally omits the script directory. Load this exact bundled
    # sibling, independently of upstream vendor files or the user's PYTHONPATH.
    import importlib.util

    name = "musicalscumme_worker_audio_evidence"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("audio_evidence.py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def checked_parts(device: str, source: Path, second_input: Path | None,
                  limit: float | None, role: str, stem_passes: bool, native_notes,
                  *, recover_quiet_notes: bool = False, diagnostics: dict | None = None):
    """Use the appropriate source stem for each audio check, never a full mix's F0."""
    import librosa

    if role == "full" and not stem_passes:
        raise ValueError("Audio-checked covers need both synchronized stems; use the native comparison for a full mix.")
    if second_input is not None and not stem_passes:
        raise ValueError("Audio checking requires independent passes for paired stems.")
    evidence = evidence_module()
    prepared = []
    if diagnostics is not None:
        diagnostics["recovery_enabled"] = recover_quiet_notes
    if role in {"full", "vocals"}:
        emit("status", message="Checking the vocal fundamental against the isolated vocal audio…")
        audio, rate = librosa.load(source, sr=16000, mono=True, duration=limit)
        frequency, confidence, energy, hop = evidence.track_vocal_audio(
            audio, rate, device, status=lambda message: emit("status", message=message))
        hints = [n.onset for n in native_notes if n.program in {100, 101}]
        regions = [(n.onset, n.offset) for n in native_notes if n.program in {100, 101}]
        vocals = evidence.vocal_notes_from_track(
            frequency, confidence, energy, hop_s=hop, duration=len(audio) / rate,
            attack_hints=hints, vocal_regions=regions, recover_quiet_notes=recover_quiet_notes)
        if not vocals:
            raise ValueError("Could not confirm a vocal melody from vocal activity and pitch evidence; previous outputs preserved.")
        if diagnostics is not None:
            # Compare policies using the same measured F0/RMS. Model inference
            # is never repeated just to obtain these note-count diagnostics.
            standard = evidence.vocal_notes_from_track(
                frequency, confidence, energy, hop_s=hop, duration=len(audio) / rate,
                attack_hints=hints, vocal_regions=regions) if recover_quiet_notes else vocals
            diagnostics["vocals"] = {"standard_notes": len(standard), "output_notes": len(vocals),
                                      "note_count_change": len(vocals) - len(standard)}
        prepared.extend(vocals)
    if role in {"full", "instrumental"}:
        emit("status", message="Screening backing pitches against competing fundamentals and overtones…")
        backing_source = second_input if stem_passes else source
        if backing_source is None:
            raise ValueError("The backing stem is missing")
        audio, rate = librosa.load(backing_source, sr=16000, mono=True, duration=limit)
        pitches, coefficients, hop = evidence.harmonic_activations(audio, rate, device=device)
        backing = evidence.supported_backing_notes(
            native_notes, pitches, coefficients, hop_s=hop, recover_quiet_notes=recover_quiet_notes)
        if diagnostics is not None:
            standard = evidence.supported_backing_notes(
                native_notes, pitches, coefficients, hop_s=hop) if recover_quiet_notes else backing
            diagnostics["backing"] = {"standard_notes": len(standard), "output_notes": len(backing),
                                       "note_count_change": len(backing) - len(standard)}
        prepared.extend(backing)
    return sorted(prepared, key=lambda n: (n.onset, n.program, n.pitch, n.offset))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--second-input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--prepared-output", type=Path)
    parser.add_argument("--role", choices=["full", "vocals", "instrumental"], default="full")
    parser.add_argument("--stem-passes", action="store_true")
    parser.add_argument("--audio-checked", action="store_true")
    parser.add_argument("--recover-quiet-notes", action="store_true",
                        help="Recover strongly supported quiet/brief notes during audio checking")
    parser.add_argument("--duration", type=float)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.validate:
            if not args.input or not args.output or not args.prepared_output or not args.input.is_file():
                raise ValueError("Choose an existing audio source and both MIDI destinations.")
            sources = [p.resolve() for p in (args.input, args.second_input) if p]
            outputs = [p.resolve() for p in (args.output, args.prepared_output)]
            if outputs[0] == outputs[1] or any(p in sources for p in outputs):
                raise ValueError("MIDI destinations must be separate from the sources and each other.")
            if any(p.suffix.lower() not in {".mid", ".midi"} for p in outputs):
                raise ValueError("Destinations must end in .mid or .midi.")
            if args.duration is not None and (not math.isfinite(args.duration) or args.duration <= 0):
                raise ValueError("Duration must be positive.")
            if args.stem_passes and args.second_input is None:
                raise ValueError("Independent stem passes require both stems.")
            if args.audio_checked and args.role == "full" and not args.stem_passes:
                raise ValueError("Audio-checked covers require both synchronized stems.")
            if args.audio_checked and args.second_input is not None and not args.stem_passes:
                raise ValueError("Audio checking requires independent passes for paired stems.")
            if args.recover_quiet_notes and not args.audio_checked:
                raise ValueError("Quiet-note recovery requires audio checking.")
        _configure_numba_cache(args.runtime_dir)
        emit("status", message="Loading YourMT3+ multi-instrument model…")
        model, device = load_model(args.runtime_dir)
        if args.validate:
            import torch
            # Exercise actual generation without writing user audio or MIDI.
            sample = torch.zeros(1, 1, model.audio_cfg["input_frames"], device=device)
            with torch.inference_mode(), torch.autocast(device, dtype=torch.float16, enabled=device == "cuda"):
                model.inference_file(bsz=1, audio_segments=sample)
            import numpy as np

            # Also exercise packaged pitch weights. Installing only YourMT3+
            # must not mark the new audio-checking pipeline as usable.
            time = np.arange(16000, dtype=np.float32) / 16000
            tone = .2 * np.sin(2 * np.pi * 220 * time)
            evidence = evidence_module()
            frequency, probability, energy, hop = evidence.track_vocal_audio(tone, 16000, device)
            voiced = evidence.vocal_notes_from_track(frequency, probability, energy, hop_s=hop, duration=1)
            if not voiced or not all(n.pitch == 57 for n in voiced):
                raise ValueError("CREPE pitch inference failed the known-tone validation.")
            marker = args.runtime_dir / ".musicalscumme-advanced-ready-v1"
            marker.write_text(json.dumps({"revision": REVISION, "backend": device,
                                          "evidence_version": EVIDENCE_VERSION}), encoding="utf-8")
            emit("complete", operation="validation", backend=device)
            return 0
        emit("status", message=f"Recognizing instrument parts on {device}…")
        raw, prepared = transcribe_parts(model, device, args.input, args.second_input,
                                        args.duration, args.role, args.stem_passes)
        completion_details = {}
        if args.audio_checked:
            diagnostics = {}
            prepared = checked_parts(device, args.input, args.second_input, args.duration,
                                     args.role, args.stem_passes, prepared,
                                     recover_quiet_notes=args.recover_quiet_notes, diagnostics=diagnostics)
            completion_details["audio_evidence"] = diagnostics
        if not prepared:
            raise ValueError("No usable notes for the requested role; previous MIDI outputs were preserved.")
        write_native_midi(raw, args.output)
        write_native_midi(prepared, args.prepared_output, audio_checked=args.audio_checked)
        emit("complete", notes=len(prepared), tracks=len({n.program for n in prepared}),
             output=str(args.prepared_output.resolve()), backend=device, **completion_details)
        return 0
    except Exception as exc:
        emit("error", message=str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
