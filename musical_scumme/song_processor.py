from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

import mido

from .midi_engine import load_midi, selected_track_indices
from .model import MidiNote, midi_note_name

MIDI_EXTENSIONS = {".mid", ".midi"}


@dataclass(frozen=True, slots=True)
class SongProcessorProfile:
    label: str
    description: str
    support_voices: int
    core_range_semitones: int = 31
    onset_tolerance_ms: int = 28
    minimum_note_ms: int = 80
    outlier_max_duration_ms: int = 350
    outlier_max_velocity: int = 75
    stabilize_octave_spikes: bool = True


SONG_PROCESSOR_PROFILES: dict[str, SongProcessorProfile] = {
    "band_backing": SongProcessorProfile(
        label="Band backing · up to three voices",
        description="Keeps detected backing harmony with up to three voices; does not assume the band is a guitar solo.",
        support_voices=2,
        core_range_semitones=48,
        onset_tolerance_ms=25,
        stabilize_octave_spikes=False,
    ),
    "guitar_arpeggio": SongProcessorProfile(
        label="Guitar / arpeggio stem (recommended)",
        description=(
            "Cleans rapid transcription artifacts while preserving recurring bass-to-treble picking resets."
        ),
        support_voices=0,
        onset_tolerance_ms=65,
        stabilize_octave_spikes=False,
    ),
    "melody_focus": SongProcessorProfile(
        label="Smooth lead / vocal",
        description=(
            "Consolidates transcription double-attacks, stabilizes isolated octave spikes, "
            "and builds one globally continuous lead line for source-aware Optimal Sounding playback."
        ),
        support_voices=0,
        onset_tolerance_ms=65,
    ),
    "melody_bass": SongProcessorProfile(
        label="Melody + light support",
        description="Keeps the global lead plus one useful bass or harmony note when a real chord is detected.",
        support_voices=1,
        onset_tolerance_ms=55,
    ),
    "fuller": SongProcessorProfile(
        label="Fuller playable arrangement",
        description="Keeps the global lead plus up to two support notes. Best for clean source stems.",
        support_voices=2,
        onset_tolerance_ms=40,
        outlier_max_duration_ms=260,
        outlier_max_velocity=65,
        stabilize_octave_spikes=False,
    ),
}


@dataclass(frozen=True, slots=True)
class SongProcessingResult:
    lead_notes: tuple[MidiNote, ...]
    support_notes: tuple[MidiNote, ...]
    source_notes: int
    removed_percussion: int
    removed_short: int
    removed_outliers: int
    corrected_octaves: int
    stabilized_octaves: int
    collapsed_duplicates: int
    removed_arrangement: int
    core_low: int
    core_high: int
    large_leaps: int
    profile_name: str
    warnings: tuple[str, ...]
    removed_ghosts: int = 0
    consolidated_strums: int = 0
    estimated_bpm: float = 120.0

    @property
    def notes(self) -> tuple[MidiNote, ...]:
        return tuple(sorted((*self.lead_notes, *self.support_notes), key=lambda note: (note.start_ms, note.pitch)))

    @property
    def retained_notes(self) -> int:
        return len(self.lead_notes) + len(self.support_notes)

    @property
    def core_range_text(self) -> str:
        return f"{midi_note_name(self.core_low)}–{midi_note_name(self.core_high)}"


@dataclass(frozen=True, slots=True)
class _Candidate:
    source: MidiNote
    pitch: int
    corrected: bool
    base_quality: float


def _note_weight(note: MidiNote) -> float:
    return min(note.duration_ms, 1800.0) * (0.35 + note.velocity / 127.0)


def _detect_core_range(notes: list[MidiNote], width: int) -> tuple[int, int, float]:
    minimum = min(note.pitch for note in notes)
    maximum = max(note.pitch for note in notes)
    if maximum - minimum <= width:
        return minimum, maximum, 1.0

    # Aggregate fixed note weights once. The previous window search scanned
    # every source note and recalculated its duration/velocity weight for each
    # possible low pitch, which dominated processing on dense scores.
    weight_by_pitch = [0.0] * 128
    weighted_pitch_total = 0.0
    total_weight = 0.0
    for note in notes:
        weight = _note_weight(note)
        weight_by_pitch[note.pitch] += weight
        weighted_pitch_total += note.pitch * weight
        total_weight += weight
    weighted_center = weighted_pitch_total / max(total_weight, 1e-9)
    best: tuple[float, float, int, int] | None = None
    for low in range(max(0, minimum - width), min(127 - width, maximum) + 1):
        high = low + width
        captured = sum(weight_by_pitch[low : high + 1])
        candidate = (captured, -abs((low + high) / 2.0 - weighted_center), low, high)
        if best is None or candidate > best:
            best = candidate
    assert best is not None
    return best[2], best[3], best[0] / max(total_weight, 1e-9)


def _group_onsets(candidates: list[_Candidate], tolerance_ms: int) -> list[list[_Candidate]]:
    ordered = sorted(candidates, key=lambda item: (item.source.start_ms, item.pitch, item.source.end_ms))
    if not ordered:
        return []
    groups: list[list[_Candidate]] = []
    current = [ordered[0]]
    anchor = ordered[0].source.start_ms
    for candidate in ordered[1:]:
        if candidate.source.start_ms - anchor <= tolerance_ms:
            current.append(candidate)
        else:
            groups.append(current)
            current = [candidate]
            anchor = candidate.source.start_ms
    groups.append(current)
    return groups


def _candidate_quality(note: MidiNote, corrected: bool) -> float:
    velocity = note.velocity / 127.0
    duration = min(note.duration_ms, 1200.0) / 1200.0
    original_register = 0.12 if not corrected else -0.08
    return 0.48 * velocity + 0.40 * duration + original_register


def _fold_outlier_pitch(
    note: MidiNote,
    low: int,
    high: int,
    local_median: float | None,
) -> int:
    target = local_median if local_median is not None else (low + high) / 2.0
    same_class = [pitch for pitch in range(low, high + 1) if pitch % 12 == note.pitch % 12]
    if not same_class:
        return max(low, min(high, note.pitch))
    return min(same_class, key=lambda pitch: (abs(pitch - target), abs(pitch - note.pitch)))


class _SlidingPitchMedian:
    """Median pitches in ascending-time windows without per-query lists or sorts."""

    __slots__ = ("_counts", "_left", "_notes", "_right", "_size")

    def __init__(self, notes: list[MidiNote]) -> None:
        self._notes = notes
        self._counts = [0] * 128
        self._left = 0
        self._right = 0
        self._size = 0

    def at(self, start_ms: float, radius_ms: float = 900.0) -> float | None:
        lower = start_ms - radius_ms
        upper = start_ms + radius_ms
        while self._right < len(self._notes) and self._notes[self._right].start_ms <= upper:
            pitch = self._notes[self._right].pitch
            self._counts[pitch] += 1
            self._size += 1
            self._right += 1
        while self._left < self._right and self._notes[self._left].start_ms < lower:
            pitch = self._notes[self._left].pitch
            self._counts[pitch] -= 1
            self._size -= 1
            self._left += 1
        if not self._size:
            return None

        lower_rank = (self._size - 1) // 2
        upper_rank = self._size // 2
        seen = 0
        lower_pitch = upper_pitch = 0
        for pitch, count in enumerate(self._counts):
            next_seen = seen + count
            if seen <= lower_rank < next_seen:
                lower_pitch = pitch
            if seen <= upper_rank < next_seen:
                upper_pitch = pitch
                break
            seen = next_seen
        return (lower_pitch + upper_pitch) / 2.0


def _collapse_group_duplicates(groups: list[list[_Candidate]]) -> tuple[list[list[_Candidate]], int]:
    result: list[list[_Candidate]] = []
    collapsed = 0
    for group in groups:
        by_pitch: dict[int, _Candidate] = {}
        for candidate in group:
            current = by_pitch.get(candidate.pitch)
            if current is None or (
                candidate.base_quality,
                candidate.source.velocity,
                candidate.source.duration_ms,
            ) > (current.base_quality, current.source.velocity, current.source.duration_ms):
                if current is not None:
                    collapsed += 1
                by_pitch[candidate.pitch] = candidate
            else:
                collapsed += 1
        result.append(sorted(by_pitch.values(), key=lambda item: item.pitch))
    return result, collapsed


def _global_melody_path(groups: list[list[_Candidate]]) -> list[_Candidate]:
    pitch_support = Counter(candidate.pitch for group in groups for candidate in group)
    maximum_support = max(pitch_support.values(), default=1)
    costs: list[list[float]] = []
    parents: list[list[int]] = []

    for group_index, group in enumerate(groups):
        current_costs: list[float] = []
        current_parents: list[int] = []
        group_start = min(candidate.source.start_ms for candidate in group)
        previous_start = (
            min(candidate.source.start_ms for candidate in groups[group_index - 1]) if group_index else group_start
        )
        gap_ms = max(1.0, group_start - previous_start)
        continuity_weight = max(0.18, min(1.0, 380.0 / gap_ms))

        for candidate in group:
            support = pitch_support[candidate.pitch] / maximum_support
            local = candidate.base_quality + 0.28 * support
            if group_index == 0:
                current_costs.append(local)
                current_parents.append(-1)
                continue

            best_score = -math.inf
            best_parent = 0
            for previous_index, previous in enumerate(groups[group_index - 1]):
                distance = abs(candidate.pitch - previous.pitch)
                transition_penalty = (distance / 7.0) * continuity_weight
                if distance >= 12 and gap_ms < 600.0:
                    transition_penalty += 0.32
                score = costs[-1][previous_index] + local - transition_penalty
                if score > best_score:
                    best_score = score
                    best_parent = previous_index
            current_costs.append(best_score)
            current_parents.append(best_parent)
        costs[:] = [current_costs]
        parents.append(current_parents)

    current_index = max(range(len(costs[-1])), key=lambda index: costs[-1][index])
    path: list[_Candidate] = []
    for group_index in range(len(groups) - 1, -1, -1):
        path.append(groups[group_index][current_index])
        current_index = parents[group_index][current_index]
    path.reverse()
    return path


def _octave_variants(candidate: _Candidate, low: int, high: int) -> list[int]:
    """Return the original pitch and conservative one-octave alternatives inside the core range."""

    variants = {candidate.pitch}
    for offset in (-12, 12):
        shifted = candidate.pitch + offset
        if low <= shifted <= high:
            variants.add(shifted)
    return sorted(variants)


def _stabilize_isolated_octave_spikes(
    melody: list[_Candidate],
    low: int,
    high: int,
) -> tuple[list[_Candidate], int]:
    """Repair short register spikes without flattening recurring arpeggio resets.

    A candidate is eligible only when both adjacent jumps exceed an octave while
    the notes on either side remain within a fifth. Consecutive eligible notes
    are solved together so one repair cannot merely move the spike to its
    neighbour. Shifts are limited to one octave and must materially improve the
    complete boundary-to-boundary contour.
    """

    if len(melody) < 3:
        return list(melody), 0

    eligible: list[int] = []
    for index in range(1, len(melody) - 1):
        previous = melody[index - 1].pitch
        current = melody[index].pitch
        following = melody[index + 1].pitch
        if (
            abs(current - previous) > 12
            and abs(following - current) > 12
            and abs(following - previous) <= 7
        ):
            eligible.append(index)

    if not eligible:
        return list(melody), 0

    runs: list[tuple[int, int]] = []
    run_start = eligible[0]
    run_end = eligible[0]
    for index in eligible[1:]:
        if index == run_end + 1:
            run_end = index
        else:
            runs.append((run_start, run_end))
            run_start = run_end = index
    runs.append((run_start, run_end))

    repaired = list(melody)
    repair_count = 0
    shift_penalty = 5.0
    minimum_improvement = 8.0
    for start, end in runs:
        left_pitch = repaired[start - 1].pitch
        right_pitch = repaired[end + 1].pitch
        segment = repaired[start : end + 1]

        original_pitches = [candidate.pitch for candidate in segment]
        original_path = [left_pitch, *original_pitches, right_pitch]
        original_cost = sum(
            abs(right - left)
            for left, right in zip(original_path, original_path[1:], strict=False)
        )

        costs: list[dict[int, float]] = []
        parents: list[dict[int, int | None]] = []
        for offset, candidate in enumerate(segment):
            candidate_costs: dict[int, float] = {}
            candidate_parents: dict[int, int | None] = {}
            for pitch in _octave_variants(candidate, low, high):
                local_penalty = shift_penalty if pitch != candidate.pitch else 0.0
                if offset == 0:
                    candidate_costs[pitch] = abs(pitch - left_pitch) + local_penalty
                    candidate_parents[pitch] = None
                    continue
                previous_pitch = min(
                    costs[-1],
                    key=lambda prior: (
                        costs[-1][prior] + abs(pitch - prior),
                        abs(pitch - prior),
                        prior,
                    ),
                )
                candidate_costs[pitch] = costs[-1][previous_pitch] + abs(pitch - previous_pitch) + local_penalty
                candidate_parents[pitch] = previous_pitch
            costs[:] = [candidate_costs]
            parents.append(candidate_parents)

        final_pitch = min(
            costs[-1],
            key=lambda pitch: (costs[-1][pitch] + abs(right_pitch - pitch), abs(right_pitch - pitch), pitch),
        )
        best_cost = costs[-1][final_pitch] + abs(right_pitch - final_pitch)
        if original_cost - best_cost < minimum_improvement:
            continue

        chosen = [final_pitch]
        for offset in range(len(segment) - 1, 0, -1):
            parent = parents[offset][chosen[-1]]
            assert parent is not None
            chosen.append(parent)
        chosen.reverse()
        for offset, pitch in enumerate(chosen):
            if pitch == segment[offset].pitch:
                continue
            candidate = segment[offset]
            repaired[start + offset] = _Candidate(
                source=candidate.source,
                pitch=pitch,
                corrected=True,
                base_quality=candidate.base_quality,
            )
            repair_count += 1

    return repaired, repair_count


def _as_processed_note(candidate: _Candidate, track_index: int, start_ms: float | None = None) -> MidiNote:
    start = candidate.source.start_ms if start_ms is None else start_ms
    duration = max(80.0, min(1800.0, candidate.source.duration_ms))
    return MidiNote(
        track_index=track_index,
        channel=0,
        pitch=candidate.pitch,
        velocity=candidate.source.velocity,
        start_ms=start,
        end_ms=start + duration,
    )


def _make_monophonic(notes: list[MidiNote]) -> list[MidiNote]:
    """End each lead note before the next attack so the exported melody is truly monophonic."""

    result: list[MidiNote] = []
    for index, note in enumerate(notes):
        end_ms = note.end_ms
        if index + 1 < len(notes):
            next_start = notes[index + 1].start_ms
            gap_ms = max(1.0, next_start - note.start_ms)
            articulation_gap = min(18.0, gap_ms * 0.25)
            end_ms = min(end_ms, max(note.start_ms + 10.0, next_start - articulation_gap))
        result.append(
            MidiNote(
                track_index=note.track_index,
                channel=note.channel,
                pitch=note.pitch,
                velocity=note.velocity,
                start_ms=note.start_ms,
                end_ms=end_ms,
            )
        )
    return result


def _suppress_harmonic_ghosts(notes: list[MidiNote], profile_name: str) -> tuple[list[MidiNote], int]:
    """Remove acoustic body overtones (+12, +19, +24 st) and sub-bass rumble."""
    if not notes:
        return [], 0

    ghost_ids: set[int] = set()
    overtone_intervals = {12, 19, 24}
    guitar_like = profile_name in {"guitar_arpeggio", "melody_focus", "melody_bass"}

    for i, note in enumerate(notes):
        cutoff_pitch = 40 if guitar_like else 36
        if note.pitch < cutoff_pitch and (note.velocity < 70 or note.duration_ms < 200.0):
            ghost_ids.add(id(note))
            continue

        window_start = note.start_ms - 80.0
        window_end = note.start_ms + 40.0
        for j in range(max(0, i - 15), min(len(notes), i + 15)):
            if i == j:
                continue
            other = notes[j]
            if other.start_ms < window_start or other.start_ms > window_end:
                continue
            interval = note.pitch - other.pitch
            if interval in overtone_intervals:
                if note.velocity <= other.velocity * 0.82 or note.velocity < other.velocity - 18:
                    if note.duration_ms <= other.duration_ms * 1.25:
                        ghost_ids.add(id(note))
                        break

    kept = [note for note in notes if id(note) not in ghost_ids]
    return kept, len(ghost_ids)


def _consolidate_micro_strums(notes: list[MidiNote], max_strum_span_ms: float = 35.0) -> tuple[list[MidiNote], int]:
    """Align near-simultaneous strummed attacks (15-35 ms) to the anchor onset."""
    if len(notes) < 2:
        return list(notes), 0

    ordered = sorted(notes, key=lambda n: (n.start_ms, n.pitch))
    result: list[MidiNote] = []
    consolidated_count = 0
    strum_group: list[MidiNote] = [ordered[0]]

    for note in ordered[1:]:
        if (note.start_ms - strum_group[0].start_ms <= max_strum_span_ms) and (
            note.start_ms - strum_group[-1].start_ms <= 25.0
        ):
            strum_group.append(note)
        else:
            if len(strum_group) > 1:
                anchor_start = strum_group[0].start_ms
                for item in strum_group:
                    if item.start_ms != anchor_start:
                        consolidated_count += 1
                        result.append(
                            MidiNote(
                                track_index=item.track_index,
                                channel=item.channel,
                                pitch=item.pitch,
                                velocity=item.velocity,
                                start_ms=anchor_start,
                                end_ms=anchor_start + item.duration_ms,
                            )
                        )
                    else:
                        result.append(item)
            else:
                result.append(strum_group[0])
            strum_group = [note]

    if len(strum_group) > 1:
        anchor_start = strum_group[0].start_ms
        for item in strum_group:
            if item.start_ms != anchor_start:
                consolidated_count += 1
                result.append(
                    MidiNote(
                        track_index=item.track_index,
                        channel=item.channel,
                        pitch=item.pitch,
                        velocity=item.velocity,
                        start_ms=anchor_start,
                        end_ms=anchor_start + item.duration_ms,
                    )
                )
            else:
                result.append(item)
    elif strum_group:
        result.append(strum_group[0])

    result.sort(key=lambda n: (n.start_ms, n.pitch))
    return result, consolidated_count


def estimate_tempo_bpm(notes: list[MidiNote], default_bpm: float = 120.0) -> float:
    """Estimate musical BPM from inter-onset intervals (IOI)."""
    if len(notes) < 6:
        return default_bpm

    onsets = sorted({round(n.start_ms, 1) for n in notes})
    if len(onsets) < 6:
        return default_bpm

    iois: list[float] = []
    for i in range(len(onsets) - 1):
        gap = onsets[i + 1] - onsets[i]
        if 80.0 <= gap <= 1200.0:
            iois.append(gap)

    if len(iois) < 5:
        return default_bpm

    best_bpm = default_bpm
    best_score = -1.0

    for candidate_bpm in range(60, 181):
        beat_ms = 60_000.0 / candidate_bpm
        subdivisions = (beat_ms * 2.0, beat_ms, beat_ms / 2.0, beat_ms / 3.0, beat_ms / 4.0)
        score = 0.0
        for ioi in iois:
            min_dev = min(abs(ioi - sub) / sub for sub in subdivisions)
            if min_dev < 0.08:
                score += (1.0 - min_dev / 0.08)
        bpm_prior = 1.0 - abs(candidate_bpm - 120.0) * 0.001
        composite_score = score * bpm_prior
        if composite_score > best_score:
            best_score = composite_score
            best_bpm = float(candidate_bpm)

    return best_bpm


def _support_for_group(group: list[_Candidate], lead: _Candidate, limit: int) -> list[_Candidate]:
    if limit <= 0:
        return []
    remaining = [
        candidate
        for candidate in group
        if candidate.source is not lead.source and candidate.pitch != lead.pitch
    ]
    selected: list[_Candidate] = []
    while remaining and len(selected) < limit:
        used_pitches = [lead.pitch, *(candidate.pitch for candidate in selected)]

        def score(
            candidate: _Candidate,
            _used_pitches: tuple[int, ...] = tuple(used_pitches),
        ) -> tuple[float, float, int]:
            interval = min(abs(candidate.pitch - pitch) for pitch in _used_pitches)
            pitch_class_interval = min((candidate.pitch - pitch) % 12 for pitch in _used_pitches)
            consonance = 0.22 if pitch_class_interval in {3, 4, 5, 7, 8, 9} else 0.0
            bass_bonus = 0.18 if candidate.pitch <= lead.pitch - 5 else 0.0
            separation = min(1.0, interval / 12.0)
            return (candidate.base_quality + consonance + bass_bonus + 0.14 * separation, -candidate.pitch, candidate.pitch)

        chosen = max(remaining, key=score)
        if min(abs(chosen.pitch - pitch) for pitch in used_pitches) < 3:
            remaining.remove(chosen)
            continue
        selected.append(chosen)
        remaining.remove(chosen)
    return selected


def process_song_notes(
    notes: Iterable[MidiNote],
    profile_name: str = "melody_focus",
    *,
    onset_tolerance_ms: int | None = None,
) -> SongProcessingResult:
    profile = SONG_PROCESSOR_PROFILES.get(profile_name)
    if profile is None:
        raise ValueError(f"Unknown song processor profile: {profile_name}")

    source = sorted(notes, key=lambda note: (note.start_ms, note.pitch, note.end_ms))
    if not source:
        raise ValueError("The selected MIDI contains no notes.")

    removed_percussion = sum(note.channel == 9 for note in source)
    non_percussion = [note for note in source if note.channel != 9]
    cleaned_notes, removed_ghosts = _suppress_harmonic_ghosts(non_percussion, profile_name)
    cleaned_notes, consolidated_strums = _consolidate_micro_strums(cleaned_notes)
    removed_short = sum(note.duration_ms < profile.minimum_note_ms for note in cleaned_notes)
    working = [note for note in cleaned_notes if note.duration_ms >= profile.minimum_note_ms]
    if not working:
        raise ValueError("No usable notes remain after removing percussion and ultra-short transcription noise.")

    core_low, core_high, coverage = _detect_core_range(working, profile.core_range_semitones)
    core_notes = sorted(
        (note for note in working if core_low <= note.pitch <= core_high),
        key=lambda note: note.start_ms,
    )
    local_pitch_median = _SlidingPitchMedian(core_notes)
    candidates: list[_Candidate] = []
    removed_outliers = 0
    corrected_octaves = 0
    for note in working:
        corrected = False
        pitch = note.pitch
        if not core_low <= pitch <= core_high:
            if (
                note.duration_ms < profile.outlier_max_duration_ms
                and note.velocity < profile.outlier_max_velocity
            ):
                removed_outliers += 1
                continue
            pitch = _fold_outlier_pitch(
                note,
                core_low,
                core_high,
                local_pitch_median.at(note.start_ms),
            )
            corrected = pitch != note.pitch
            corrected_octaves += int(corrected)
        candidates.append(_Candidate(note, pitch, corrected, _candidate_quality(note, corrected)))

    if not candidates:
        raise ValueError("No usable notes remain after suppressing transcription outliers.")

    effective_onset_tolerance_ms = (
        profile.onset_tolerance_ms
        if onset_tolerance_ms is None
        else max(1, min(profile.onset_tolerance_ms, int(onset_tolerance_ms)))
    )
    groups = _group_onsets(candidates, effective_onset_tolerance_ms)
    groups, collapsed_duplicates = _collapse_group_duplicates(groups)
    melody = _global_melody_path(groups)
    stabilized_octaves = 0
    if profile.stabilize_octave_spikes:
        melody, stabilized_octaves = _stabilize_isolated_octave_spikes(melody, core_low, core_high)
        corrected_octaves += stabilized_octaves
    lead_notes: list[MidiNote] = []
    support_notes: list[MidiNote] = []
    for group, lead in zip(groups, melody, strict=True):
        lead_note = _as_processed_note(lead, track_index=1)
        lead_notes.append(lead_note)
        for support in _support_for_group(group, lead, profile.support_voices):
            support_notes.append(_as_processed_note(support, track_index=2, start_ms=lead_note.start_ms))
    lead_notes = _make_monophonic(lead_notes)

    retained = len(lead_notes) + len(support_notes)
    removed_arrangement = max(0, len(candidates) - retained - collapsed_duplicates)
    leaps = [abs(right.pitch - left.pitch) for left, right in zip(lead_notes, lead_notes[1:], strict=False)]
    large_leaps = sum(distance > 12 for distance in leaps)
    warnings: list[str] = []
    if coverage < 0.85:
        warnings.append("The source has an unusually broad pitch range; inspect the processed melody before playback.")
    if large_leaps and profile_name == "guitar_arpeggio":
        warnings.append(
            f"Preserved {large_leaps:,} octave-sized register resets expected in picked or arpeggiated material."
        )
    elif large_leaps:
        warnings.append(
            f"The lead still contains {large_leaps:,} leaps larger than one octave; some may be genuine arpeggio resets."
        )

    return SongProcessingResult(
        lead_notes=tuple(lead_notes),
        support_notes=tuple(support_notes),
        source_notes=len(source),
        removed_percussion=removed_percussion,
        removed_short=removed_short,
        removed_outliers=removed_outliers,
        corrected_octaves=corrected_octaves,
        stabilized_octaves=stabilized_octaves,
        collapsed_duplicates=collapsed_duplicates,
        removed_arrangement=removed_arrangement,
        core_low=core_low,
        core_high=core_high,
        large_leaps=large_leaps,
        profile_name=profile_name,
        warnings=tuple(warnings),
        removed_ghosts=removed_ghosts,
        consolidated_strums=consolidated_strums,
        estimated_bpm=estimate_tempo_bpm(source, default_bpm=120.0),
    )


def _midi_track(name: str, notes: Iterable[MidiNote], ticks_per_beat: int, tempo: int) -> mido.MidiTrack:
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name=name, time=0))
    events: list[tuple[int, int, int, int]] = []
    for note in notes:
        start_tick = round(mido.second2tick(note.start_ms / 1000.0, ticks_per_beat, tempo))
        end_tick = max(start_tick + 1, round(mido.second2tick(note.end_ms / 1000.0, ticks_per_beat, tempo)))
        events.append((start_tick, 1, note.pitch, note.velocity))
        events.append((end_tick, 0, note.pitch, 0))
    events.sort(key=lambda event: (event[0], event[1], event[2]))
    last_tick = 0
    for tick, action, pitch, velocity in events:
        delta = max(0, tick - last_tick)
        last_tick = tick
        message_type = "note_on" if action else "note_off"
        track.append(mido.Message(message_type, note=pitch, velocity=velocity, channel=0, time=delta))
    track.append(mido.MetaMessage("end_of_track", time=0))
    return track


def write_processed_midi(
    result: SongProcessingResult,
    destination: str | Path,
    *,
    bpm: float = 120.0,
    overwrite: bool = False,
) -> Path:
    output_path = Path(destination).expanduser().resolve()
    if output_path.suffix.lower() not in MIDI_EXTENSIONS:
        raise ValueError("Processed output path must end in .mid or .midi")
    if output_path.exists() and not overwrite:
        raise FileExistsError(output_path)

    ticks_per_beat = 480
    tempo = mido.bpm2tempo(max(20.0, min(300.0, float(bpm))))
    midi = mido.MidiFile(type=1, ticks_per_beat=ticks_per_beat)
    metadata = mido.MidiTrack()
    metadata.append(mido.MetaMessage("track_name", name="MusicalScumme Song Transposer", time=0))
    metadata.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
    metadata.append(mido.MetaMessage("text", text=f"Profile: {result.profile_name}", time=0))
    metadata.append(mido.MetaMessage("end_of_track", time=0))
    midi.tracks.append(metadata)
    midi.tracks.append(_midi_track("Lead Melody", result.lead_notes, ticks_per_beat, tempo))
    if result.support_notes:
        midi.tracks.append(_midi_track("Light Support", result.support_notes, ticks_per_beat, tempo))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        midi.save(temporary)
        temporary.replace(output_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return output_path


def process_midi_file(
    source: str | Path,
    destination: str | Path,
    *,
    profile_name: str = "melody_focus",
    overwrite: bool = False,
) -> SongProcessingResult:
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    if source_path == destination_path:
        raise ValueError("Processed MIDI output must not overwrite the source MIDI.")
    project = load_midi(source_path)
    track_indices = selected_track_indices(project, None, prefer_non_percussion=True)
    notes = project.notes_for_tracks(track_indices)
    profile = SONG_PROCESSOR_PROFILES[profile_name]
    # Basic Pitch writes at 120 BPM, so its tested millisecond window is
    # unchanged. For scored MIDI, scale the window to the same fraction of a
    # beat; otherwise a fast 270 BPM passage loses real sequential attacks.
    tempo_scaled_onset_ms = round(profile.onset_tolerance_ms * 120.0 / max(20.0, project.first_bpm))
    result = process_song_notes(
        notes,
        profile_name,
        onset_tolerance_ms=max(12, min(profile.onset_tolerance_ms, tempo_scaled_onset_ms)),
    )
    if project.warnings:
        result = replace(result, warnings=(*project.warnings, *result.warnings))
    output_bpm = result.estimated_bpm if project.first_bpm == 120.0 else project.first_bpm
    write_processed_midi(result, destination_path, bpm=output_bpm, overwrite=overwrite)
    return result
