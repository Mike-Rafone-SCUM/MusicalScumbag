"""Audio checks used only inside the isolated transcription worker.

Pitch tracking is monophonic. Spectral support is a conservative screen, not
instrument identification or proof that a polyphonic transcription is correct.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class EvidenceNote:
    program: int
    pitch: int
    onset: float
    offset: float
    velocity: int
    is_drum: bool = False


def vocal_notes_from_track(frequencies, probabilities, energies, *, hop_s: float,
                           duration: float, attack_hints=(), vocal_regions=None,
                           recover_quiet_notes: bool = False):
    """Quantize sustained F0 changes, preserving silence and supported reattacks.

    Confidence here is CREPE periodicity, not pYIN/Basic Pitch probability.
    Neither model labels nor a song's assumed key can override measured F0.
    """
    import numpy as np

    if not math.isfinite(hop_s) or hop_s <= 0 or not math.isfinite(duration) or duration <= 0:
        raise ValueError("Invalid pitch-track timing")
    frequency, probability, energy = [np.asarray(a, dtype=float) for a in (frequencies, probabilities, energies)]
    if any(a.ndim != 1 for a in (frequency, probability, energy)) or not (len(frequency) == len(probability) == len(energy)):
        raise ValueError("Pitch-track arrays must be aligned")
    if not len(frequency):
        return []
    peak = float(np.max(np.where(np.isfinite(energy), energy, 0)))
    floor = max(1e-5, peak * .015)
    voiced = (np.isfinite(frequency) & (frequency > 0) & np.isfinite(probability)
              & (probability >= .3) & np.isfinite(energy) & (energy > floor))
    if recover_quiet_notes:
        # A loud chorus must not set the detection floor for a quiet verse.
        # Only strong periodicity earns this local RMS check; ordinary frames
        # retain the existing gate and every frame still needs vocal activity.
        width = max(1, math.ceil(.1 / hop_s))
        finite_energy = np.where(np.isfinite(energy), energy, 0)
        local_level = np.median(np.lib.stride_tricks.sliding_window_view(
            np.pad(finite_energy, (width, width), mode="edge"), 2 * width + 1), axis=1)
        voiced |= (np.isfinite(frequency) & (frequency > 0) & np.isfinite(probability)
                   & (probability >= .65) & np.isfinite(energy)
                   & (energy > np.maximum(1e-5, local_level * .015)))
    if vocal_regions is not None:
        activity = np.zeros(len(frequency), dtype=bool)
        for onset, offset in vocal_regions:
            if not math.isfinite(onset) or not math.isfinite(offset) or offset <= onset:
                continue
            # The classifier supplies activity only, never its guessed pitch.
            # Context tolerates imperfect syllable boundaries; RMS/F0 still
            # decide whether that interval contains a usable sounding note.
            first = max(0, math.floor((onset - .12) / hop_s))
            last = max(0, min(len(activity), math.ceil((offset + .12) / hop_s)))
            activity[first:last] = True
        voiced &= activity
    pitch = np.zeros(len(frequency))
    pitch[voiced] = 69 + 12 * np.log2(frequency[voiced] / 440)
    voiced &= (pitch >= 0) & (pitch <= 127)
    boundaries = np.flatnonzero(np.diff(np.r_[False, voiced, False]))
    minimum = max(1, math.ceil(.06 / hop_s))
    short_minimum = max(1, math.ceil(.04 / hop_s))
    change_frames = max(1, math.ceil(.08 / hop_s))
    result = []

    def append(start, end, value):
        end_s = min(duration, end * hop_s)
        strong_short = (recover_quiet_notes and end - start >= short_minimum
                        and np.all(probability[start:end] >= .8)
                        and np.ptp(pitch[start:end]) <= .45)
        if (end - start < minimum and not strong_short) or end_s <= start * hop_s:
            return
        strength = float(np.sqrt(np.median(energy[start:end]) / max(peak, 1e-9)))
        result.append(EvidenceNote(100, value, start * hop_s, end_s,
                                   max(25, min(115, round(35 + 80 * strength)))))

    for begin, end in zip(boundaries[::2], boundaries[1::2], strict=True):
        if end - begin < (short_minimum if recover_quiet_notes else minimum):
            continue
        # Filter within a voiced run only: never smooth a pitch across a rest.
        section = pitch[begin:end]
        padded = np.pad(section, (2, 2), mode="edge")
        smooth = np.median(np.lib.stride_tricks.sliding_window_view(padded, 5), axis=1)
        current = round(float(np.median(smooth[:min(change_frames, len(smooth))])))
        initial = round(float(smooth[0]))
        initial_frames = section[:short_minimum]
        if (recover_quiet_notes and len(initial_frames) >= short_minimum
                and np.all(probability[begin:begin + short_minimum] >= .8)
                and np.ptp(initial_frames) <= .45
                and np.median(np.abs(initial_frames - initial)) <= .3):
            # Retain a stable brief first note without starting on a vibrato
            # extremum merely because it is the run's first sample.
            current = initial
        start, pending_start, pending_pitch = begin, None, None
        for relative, value in enumerate(smooth):
            index = begin + relative
            candidate = round(float(value))
            if abs(value - current) <= .7 or candidate == current:
                pending_start, pending_pitch = None, None
            else:
                if candidate != pending_pitch:
                    pending_start, pending_pitch = index, candidate
                required = change_frames
                if (recover_quiet_notes and 0 < abs(candidate - current) < 10
                        and index - pending_start + 1 >= short_minimum
                        and np.all(probability[pending_start:index + 1] >= .8)
                        and np.ptp(pitch[pending_start:index + 1]) <= .45):
                    # A stable, strongly periodic brief change is measured F0,
                    # even if YourMT3 missed its attack. Octave jumps retain the
                    # longer confirmation to reject brief tracker errors.
                    required = short_minimum
                if index - pending_start + 1 >= required:
                    append(start, pending_start, current)
                    start, current = pending_start, pending_pitch
                    pending_start, pending_pitch = None, None
        append(start, end, current)

    # A model onset is only a hint: split a held same-pitch note when the audio
    # contains a local amplitude valley followed by an actual renewed attack.
    hints = sorted({float(t) for t in attack_hints if math.isfinite(t) and t > 0})
    split = []
    width = max(1, round(.04 / hop_s))
    if recover_quiet_notes:
        # Detect a renewed attack missed by the note model. Requiring a valley
        # below both surrounding levels prevents a simple crescendo from
        # becoming a sequence of invented same-pitch attacks.
        for index in range(3 * width, len(energy) - width):
            before = energy[index - 3 * width:index - 2 * width]
            valley = energy[index - width:index]
            after = energy[index:index + width]
            if (np.isfinite(before).all() and np.isfinite(valley).all() and np.isfinite(after).all()
                    and energy[index] > 1.5 * max(float(energy[index - 1]), 1e-5)
                    and np.mean(valley < .55 * np.median(before)) >= .5
                    and np.median(after) >= 1.8 * max(float(np.mean(valley)), 1e-5)
                    and np.median(after) >= .7 * np.median(before)
                    and np.all(probability[index:index + width] >= .8)):
                hints.append(index * hop_s)
        hints = sorted(set(hints))
    for note in result:
        start = note.onset
        for hint in hints:
            repeat_minimum = .06 if recover_quiet_notes else .12
            if hint - start < repeat_minimum or note.offset - hint < repeat_minimum:
                continue
            index = round(hint / hop_s)
            a, b = max(round(start / hop_s), index - width), min(len(energy), index + width)
            before, after = energy[a:index], energy[index:b]
            if not len(before) or not len(after):
                continue
            attack_floor = 1e-5 if recover_quiet_notes else floor
            if np.mean(after) >= 1.6 * max(float(np.mean(before)), attack_floor):
                split.append(replace(note, onset=start, offset=hint))
                start = hint
        split.append(replace(note, onset=start))
    return split


def track_vocal_audio(audio, rate: int, device: str, status=None):
    """Run packaged CREPE weights with overlapping context at chunk boundaries."""
    import librosa
    import numpy as np
    import torch
    import torchcrepe

    if rate != 16000 or len(audio) == 0 or not np.isfinite(audio).all():
        raise ValueError("Pitch inference needs finite 16 kHz mono audio")
    hop, chunk, context = 160, 20 * rate, 3200
    pitches, probabilities = [], []
    with torch.inference_mode():
        for start in range(0, len(audio), chunk):
            end = min(len(audio), start + chunk)
            left, right = max(0, start - context), min(len(audio), end + context)
            clip = torch.from_numpy(audio[left:right].astype("float32")).unsqueeze(0)
            if status:
                status(f"Tracking vocal pitch: {start / rate:.0f}/{len(audio) / rate:.0f} seconds")
            frequency, confidence = torchcrepe.predict(
                clip, rate, hop, 50, 1100, "full", batch_size=128,
                device=device, return_periodicity=True)
            confidence = torchcrepe.filter.median(confidence, 3)
            # CREPE's optional A-weighted gate averages spectral dB over all
            # bins, classifying even a loud clean sustained tone as silence.
            # The aligned RMS/periodicity gate below handles actual silence.
            first, count = (start - left) // hop, math.ceil((end - start) / hop)
            pitches.append(frequency[0, first:first + count].cpu().numpy())
            probabilities.append(confidence[0, first:first + count].cpu().numpy())
    frequency, confidence = np.concatenate(pitches), np.concatenate(probabilities)
    energy = librosa.feature.rms(y=audio, frame_length=512, hop_length=hop)[0][:len(frequency)]
    return frequency, confidence, energy, hop / rate


def harmonic_activations(audio, rate: int, *, device: str | None = None, pitches=None):
    """Fit competing fundamentals, so a lower note can explain its overtones.

    Two harmonic envelopes allow both mellow and bright tones. A local spectral
    floor rejects broadband percussion; sparse nonnegative fitting competes
    across pitches rather than testing each overtone as an independent note.
    Returns approximate amplitude evidence, never instrument/velocity truth.
    """
    import numpy as np

    audio = np.asarray(audio, dtype=np.float32)
    if rate != 16000 or audio.ndim != 1 or not len(audio) or not np.isfinite(audio).all():
        raise ValueError("Spectral checks need finite 16 kHz mono audio")
    size, hop = 4096, 320
    pitches = np.arange(21, 109) if pitches is None else np.asarray(pitches, dtype=int)
    if pitches.ndim != 1 or not len(pitches) or np.any((pitches < 0) | (pitches > 127)):
        raise ValueError("Invalid spectral pitch dictionary")
    windows = np.lib.stride_tricks.sliding_window_view(np.pad(audio, (size // 2, size // 2)), size)[::hop]
    spectrum = np.empty((size // 2 + 1, len(windows)), dtype=np.float32)
    window = np.hanning(size)
    for start in range(0, len(windows), 128):
        block = np.abs(np.fft.rfft(windows[start:start + 128] * window, axis=1)).T
        padded = np.pad(block, ((4, 4), (0, 0)), mode="edge")
        noise = np.median(np.lib.stride_tricks.sliding_window_view(padded, 9, axis=0), axis=-1)
        spectrum[:, start:start + 128] = np.maximum(block - noise, 0)
    frequencies = np.fft.rfftfreq(size, 1 / rate)
    templates = []
    for pitch in pitches:
        fundamental = 440 * 2 ** ((int(pitch) - 69) / 12)
        for power in (.7, 1.5):
            template = np.zeros_like(frequencies)
            for harmonic in range(1, 19):
                center = harmonic * fundamental
                if center > min(rate / 2, 5000):
                    break
                width = max(rate / size * .8, center * .01)
                template += np.exp(-.5 * ((frequencies - center) / width) ** 2) / harmonic ** power
            templates.append(template / max(float(np.linalg.norm(template)), 1e-9))
    basis = np.asarray(templates, dtype=np.float32).T
    if device is None:
        dot, gram = basis.T @ spectrum, basis.T @ basis
        coefficient = np.maximum(dot, 1e-5)
        penalty = np.max(dot, axis=0, keepdims=True) * .015 + 1e-6
        for _ in range(100):
            coefficient *= dot / (gram @ coefficient + penalty)
    else:
        import torch

        with torch.inference_mode():
            matrix, values = torch.as_tensor(basis, device=device), torch.as_tensor(spectrum, device=device)
            dot, gram = matrix.T @ values, matrix.T @ matrix
            coefficient = dot.clamp_min(1e-5)
            penalty = dot.amax(dim=0, keepdim=True) * .015 + 1e-6
            for _ in range(100):
                coefficient *= dot / (gram @ coefficient + penalty)
            coefficient = coefficient.cpu().numpy()
    return pitches, coefficient.reshape(len(pitches), 2, -1).sum(axis=1), hop / rate


def supported_backing_notes(notes, pitches, coefficients, *, hop_s: float,
                            recover_quiet_notes: bool = False):
    """Screen notes against competing spectral evidence and consolidate unisons.

    No pitches or attacks are added. Optional recovery admits existing quiet
    candidates with sustained local support; plausible lower-note overtones
    retain the original stronger threshold. Model labels remain in the raw
    export only. Confirmed same-pitch reattacks terminate the prior hold so one
    MIDI channel cannot contain conflicting overlapping unisons.
    """
    import numpy as np

    pitches, coefficients = np.asarray(pitches), np.asarray(coefficients)
    if (coefficients.ndim != 2 or len(pitches) != len(coefficients)
            or not coefficients.shape[1] or not np.isfinite(coefficients).all()
            or np.any(coefficients < 0) or not math.isfinite(hop_s) or hop_s <= 0):
        raise ValueError("Invalid spectral evidence")
    maximum = coefficients.max(axis=0)
    peak = float(maximum.max())
    if peak <= 0:
        return []
    rows = {int(p): i for i, p in enumerate(pitches)}
    local_level = None
    if recover_quiet_notes:
        width = max(1, math.ceil(.1 / hop_s))
        local_level = np.median(np.lib.stride_tricks.sliding_window_view(
            np.pad(maximum, (width, width), mode="edge"), 2 * width + 1), axis=1)
    retained = []
    for note in notes:
        if note.is_drum or note.program in {100, 101, 128} or note.pitch not in rows:
            continue
        if not math.isfinite(note.onset) or not math.isfinite(note.offset) or note.offset <= note.onset:
            continue
        # Exclude STFT boundary padding and evaluate the interior of the claim.
        first = max(0, round((note.onset + .02) / hop_s))
        last = min(coefficients.shape[1], max(first + 1, round((note.offset - .02) / hop_s)))
        if first >= last:
            continue
        amplitude = coefficients[rows[note.pitch], first:last]
        ratio = amplitude / np.maximum(maximum[first:last], 1e-9)
        support = (ratio >= .15) & (amplitude >= peak * .008)
        if np.mean(support) < .5:
            if not recover_quiet_notes:
                continue
            recovered = ((ratio >= .06) & (amplitude >= local_level[first:last] * .02)
                         & (amplitude >= 1e-3))
            # A small upper-pitch fit can be residual timbre from a stronger
            # lower fundamental. Do not relax screening in those frames, even
            # if the note model guessed the overtone as another instrument.
            for lower, row in rows.items():
                if lower >= note.pitch:
                    continue
                multiple = 2 ** ((note.pitch - lower) / 12)
                harmonic = round(multiple)
                if 2 <= harmonic <= 8 and abs(12 * math.log2(multiple / harmonic)) <= .35:
                    lower_amplitude = coefficients[row, first:last]
                    recovered &= ~((lower_amplitude >= 3 * amplitude)
                                   & (lower_amplitude >= maximum[first:last] * .2))
            # Quiet recovery needs a persistent measurement, not one STFT
            # transient at a predicted onset. Standard supported notes keep
            # their existing, less restrictive duration policy.
            runs = np.flatnonzero(np.diff(np.r_[False, recovered, False]))
            longest = max((end - start for start, end in zip(runs[::2], runs[1::2], strict=True)), default=0)
            if np.mean(recovered) < .75 or longest * hop_s < .12:
                continue
            support = recovered
        # Only shorten a model hold when its tail loses all support for >=120ms.
        last_supported = int(np.flatnonzero(support)[-1]) + first
        offset = note.offset
        if note.offset - last_supported * hop_s > .12:
            offset = min(offset, (last_supported + 1) * hop_s)
        if offset - note.onset < .06:
            continue
        strength = np.sqrt(float(np.median(amplitude[support])) / peak)
        retained.append(EvidenceNote(0, int(note.pitch), float(note.onset), float(offset),
                                     max(25, min(115, round(35 + 80 * strength)))))
    by_pitch = {}
    for note in sorted(retained, key=lambda n: (n.pitch, n.onset, n.offset)):
        group = by_pitch.setdefault(note.pitch, [])
        if group and note.onset - group[-1].onset <= .05:
            prior = group[-1]
            group[-1] = replace(prior, offset=max(prior.offset, note.offset),
                                 velocity=max(prior.velocity, note.velocity))
        else:
            if group and group[-1].offset > note.onset:
                group[-1] = replace(group[-1], offset=note.onset)
            group.append(note)
    return sorted((n for part in by_pitch.values() for n in part if n.offset - n.onset >= .06),
                  key=lambda n: (n.onset, n.pitch, n.offset))
