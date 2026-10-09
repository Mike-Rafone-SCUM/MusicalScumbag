from __future__ import annotations

import math
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, replace
from functools import lru_cache
from statistics import median
from typing import Iterable

from .arrangement_options import ARRANGEMENT_RECIPES, ArrangementRecipe
from .arrangement_processing import process_contextual_arrangement
from .config import AppSettings
from .cover_layers import infer_cover_layers
from .gm import describe_program
from .model import MidiNote


@dataclass(frozen=True, slots=True)
class SoloSegment:
    start_ms: float
    end_ms: float
    track_index: int
    confidence: float
    onset_count: int


@dataclass(frozen=True, slots=True)
class ArrangementResult:
    notes: tuple[MidiNote, ...]
    source_notes: int
    dropped_percussion: int
    dropped_short: int
    dropped_retrigger: int
    dropped_density: int
    dropped_arrangement: int
    chord_groups: int
    performed_chord_groups: int
    chord_notes_aligned: int
    chord_alignment_ms: float
    chord_detection_window_ms: float
    melody_track: int | None
    warnings: tuple[str, ...]
    melody_phrase_count: int = 0
    melody_track_switches: int = 0
    melody_large_leaps: int = 0
    solo_segments: tuple[SoloSegment, ...] = ()
    solo_notes: int = 0
    solo_accompaniment_dropped: int = 0
    solo_density_dropped: int = 0
    solo_landmarks_preserved: int = 0
    melody_landmarks_preserved: int = 0
    contextual_capacity_rejected: int = 0
    contextual_collision_rejected: int = 0
    contextual_phrase_resets: int = 0
    contextual_peak_voices: int = 0
    lead_notes: tuple[MidiNote, ...] = ()

    @property
    def retained_notes(self) -> int:
        return len(self.notes)

    @property
    def dropped_notes(self) -> int:
        return self.source_notes - self.retained_notes


@dataclass(frozen=True, slots=True)
class _TrackProfile:
    melody_score: float
    average_pitch: float
    monophony: float
    melodic_continuity: float
    activity: float


@dataclass(frozen=True, slots=True)
class _MelodyPath:
    notes: tuple[MidiNote, ...]
    phrase_count: int
    track_switches: int
    large_leaps: int


@dataclass(frozen=True, slots=True)
class _Selected:
    note: MidiNote
    priority: float
    role: str
    landmark: bool = False


AUTO_CHORD_MAX_WINDOW_MS = 45.0
AUTO_CHORD_RHYTHM_FRACTION = 0.35
AUTO_CHORD_MIN_SHARED_MS = 30.0


def _group_onsets(notes: list[MidiNote], tolerance_ms: int) -> list[list[MidiNote]]:
    if not notes:
        return []
    groups: list[list[MidiNote]] = []
    current = [notes[0]]
    anchor = notes[0].start_ms
    for note in notes[1:]:
        if note.start_ms - anchor <= tolerance_ms:
            current.append(note)
        else:
            groups.append(current)
            current = [note]
            anchor = note.start_ms
    groups.append(current)
    return groups


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * max(0.0, min(1.0, fraction))
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _automatic_chord_window(notes: list[MidiNote], base_tolerance_ms: int) -> float:
    """Estimate a conservative performed-chord window from the score rhythm.

    A fixed wide window damages fast MIDI by collapsing real sequential notes.
    The upper-quartile inter-onset gap is a robust local pulse proxy: dense Rush
    material stays at the legacy tolerance, while slower scored/performed songs
    gain enough room for independently played chord voices.
    """

    starts = sorted({note.start_ms for note in notes})
    positive_gaps = [
        later - earlier
        for earlier, later in zip(starts, starts[1:], strict=False)
        if later > earlier
    ]
    rhythmic_gap = _percentile(positive_gaps, 0.75)
    return min(
        AUTO_CHORD_MAX_WINDOW_MS,
        max(float(base_tolerance_ms), rhythmic_gap * AUTO_CHORD_RHYTHM_FRACTION),
    )


def _looks_like_sustained_chord(notes: list[MidiNote], base_tolerance_ms: int) -> bool:
    if len(notes) < 2:
        return False
    starts = [note.start_ms for note in notes]
    if max(starts) - min(starts) <= base_tolerance_ms:
        return True
    if len({note.pitch % 12 for note in notes}) < 2:
        return False

    latest_attack = max(starts)
    shared_release = min(note.end_ms for note in notes)
    shared_sustain = shared_release - latest_attack
    shortest_duration = min(note.duration_ms for note in notes)
    required_shared = min(90.0, max(AUTO_CHORD_MIN_SHARED_MS, shortest_duration * 0.35))
    return shared_sustain >= required_shared


def _group_score_onsets(
    notes: list[MidiNote],
    base_tolerance_ms: int,
    recognition_mode: str,
    protected_solos: tuple[SoloSegment, ...] = (),
) -> tuple[list[list[MidiNote]], float]:
    if recognition_mode != "auto":
        return _group_onsets(notes, base_tolerance_ms), float(base_tolerance_ms)

    window_ms = _automatic_chord_window(notes, base_tolerance_ms)
    if window_ms <= base_tolerance_ms or not notes:
        return _group_onsets(notes, base_tolerance_ms), window_ms

    groups: list[list[MidiNote]] = []
    index = 0
    while index < len(notes):
        anchor = notes[index].start_ms
        candidates = [notes[index]]
        cursor = index + 1
        while cursor < len(notes) and notes[cursor].start_ms - anchor <= window_ms:
            candidates.append(notes[cursor])
            cursor += 1

        base_count = 1
        while (
            base_count < len(candidates)
            and candidates[base_count].start_ms - anchor <= base_tolerance_ms
        ):
            base_count += 1
        chosen_count = base_count
        # Evaluate every growing prefix incrementally.  The former implementation
        # sliced and rescanned each prefix through _looks_like_sustained_chord,
        # producing cubic work and many temporary lists for dense passages.
        # These accumulators are the exact min/set values used by that predicate.
        pitch_classes = {note.pitch % 12 for note in candidates[:base_count]}
        shared_release = min(note.end_ms for note in candidates[:base_count])
        shortest_duration = min(note.duration_ms for note in candidates[:base_count])
        for candidate_count in range(base_count + 1, len(candidates) + 1):
            candidate = candidates[candidate_count - 1]
            # A legato solo attack is not a rolled chord merely because the
            # preceding note is still sounding. Keep detected solo attacks as
            # separate onset groups; exact simultaneous source notes remain
            # eligible for ordinary chord reduction.
            if any(
                segment.track_index == candidate.track_index
                and segment.start_ms - base_tolerance_ms <= candidate.start_ms <= segment.end_ms
                for segment in protected_solos
            ):
                break
            pitch_classes.add(candidate.pitch % 12)
            shared_release = min(shared_release, candidate.end_ms)
            shortest_duration = min(shortest_duration, candidate.duration_ms)
            required_shared = min(
                90.0,
                max(AUTO_CHORD_MIN_SHARED_MS, shortest_duration * 0.35),
            )
            if (
                len(pitch_classes) >= 2
                and shared_release - candidate.start_ms >= required_shared
            ):
                chosen_count = candidate_count

        groups.append(candidates[:chosen_count])
        index += chosen_count
    return groups, window_ms


def recognised_score_onsets(
    notes: Iterable[MidiNote],
    base_tolerance_ms: int = 12,
) -> tuple[list[list[MidiNote]], float]:
    """Group exact and clearly performed source chords without creating notes."""

    ordered = sorted(notes, key=lambda note: (note.start_ms, note.pitch, note.end_ms))
    return _group_score_onsets(ordered, base_tolerance_ms, "auto")


VOCAL_TOKENS = {
    "vocal",
    "vocals",
    "vox",
    "voice",
    "sing",
    "singer",
    "singing",
    "lyrics",
    "lead_vocal",
    "acapella",
    "soprano",
    "alto",
    "tenor",
    "baritone",
}


@lru_cache(maxsize=128)
def _is_vocal_name(name: str) -> bool:
    tokens = set(re.findall(r"[a-z0-9]+", name.casefold()))
    return bool(tokens.intersection(VOCAL_TOKENS))


def _semantic_track_bias(name: str, arrangement_mode: str = "intelligent") -> float:
    tokens = set(re.findall(r"[a-z0-9]+", name.casefold()))
    is_vocal = bool(tokens.intersection(VOCAL_TOKENS))
    if arrangement_mode == "vocal":
        if is_vocal:
            return 0.50
        if tokens.intersection({"lead", "melody"}):
            return 0.20
    else:
        if tokens.intersection({"lead", "melody", "vocal", "voice"}):
            return 0.18
    if "solo" in tokens:
        # A solo label is powerful section-local evidence, but sparse solo
        # tracks must not automatically become the whole-song primary lead.
        return 0.05
    if tokens.intersection({"bass", "drum", "percussion", "fx", "effect", "noise"}):
        return -0.24
    if tokens.intersection({"support", "chord", "harmony", "pad", "accompaniment"}):
        return -0.10
    return 0.0


def _track_profiles(
    notes: list[MidiNote],
    onset_tolerance_ms: int,
    track_names: dict[int, str] | None = None,
    arrangement_mode: str = "intelligent",
) -> dict[int, _TrackProfile]:
    by_track: dict[int, list[MidiNote]] = defaultdict(list)
    for note in notes:
        by_track[note.track_index].append(note)

    profiles: dict[int, _TrackProfile] = {}
    maximum_note_count = max((len(track_notes) for track_notes in by_track.values()), default=1)
    for track_index, track_notes in by_track.items():
        track_notes.sort(key=lambda note: (note.start_ms, note.pitch))
        groups = _group_onsets(track_notes, onset_tolerance_ms)
        simultaneous_excess = sum(max(0, len(group) - 1) for group in groups)
        monophony = 1.0 / (1.0 + simultaneous_excess / max(1, len(groups)))
        average_pitch = sum(note.pitch for note in track_notes) / len(track_notes)
        average_velocity = sum(note.velocity for note in track_notes) / (127.0 * len(track_notes))
        average_duration = sum(min(note.duration_ms, 1800.0) for note in track_notes) / (1800.0 * len(track_notes))
        pitch_component = max(0.0, min(1.0, (average_pitch - 36.0) / 60.0))
        activity = math.sqrt(len(track_notes) / maximum_note_count)
        representatives = [
            max(group, key=lambda note: (note.velocity, note.duration_ms, note.pitch)).pitch
            for group in groups
        ]
        intervals = [
            abs(right - left)
            for left, right in zip(representatives, representatives[1:], strict=False)
        ]
        melodic_continuity = math.exp(-median(intervals) / 8.0) if intervals else 0.5
        semantic_bias = _semantic_track_bias((track_names or {}).get(track_index, ""), arrangement_mode)
        declared_programs = Counter(
            note.program for note in track_notes if note.program is not None
        )
        if declared_programs:
            primary_program = max(
                declared_programs,
                key=lambda program: (declared_programs[program], -program),
            )
            gm = describe_program(primary_program)
            if gm is not None:
                gm_bias = (
                    0.07 * gm.lead_bias
                    - 0.04 * gm.support_bias
                    - 0.05 * gm.bass_bias
                    - 0.05 * gm.noise_bias
                )
                semantic_bias += max(-0.24, min(0.18, gm_bias))
        melody_score = (
            0.31 * monophony
            + 0.20 * pitch_component
            + 0.13 * average_velocity
            + 0.08 * average_duration
            + 0.13 * activity
            + 0.15 * melodic_continuity
            + semantic_bias
        )
        profiles[track_index] = _TrackProfile(
            melody_score,
            average_pitch,
            monophony,
            melodic_continuity,
            activity,
        )
    return profiles


def _continuity_score(pitch: int, previous_pitch: int | None) -> float:
    if previous_pitch is None:
        return 0.5
    distance = abs(pitch - previous_pitch)
    return math.exp(-distance / 9.0)


def _note_priority(note: MidiNote, profile: _TrackProfile, previous_melody: int | None) -> float:
    velocity = note.velocity / 127.0
    duration = max(0.0, min(1.0, note.duration_ms / 1200.0))
    pitch_height = max(0.0, min(1.0, (note.pitch - 36.0) / 60.0))
    continuity = _continuity_score(note.pitch, previous_melody)
    return (
        0.34 * profile.melody_score
        + 0.22 * velocity
        + 0.16 * duration
        + 0.14 * pitch_height
        + 0.14 * continuity
    )


def _melody_candidates(
    group: list[MidiNote],
    profiles: dict[int, _TrackProfile],
    maximum: int = 14,
) -> list[MidiNote]:
    """Prune dense groups while retaining every musically plausible lead."""

    if len(group) <= maximum:
        return list(group)
    group_low = min(note.pitch for note in group)
    group_span = max(1, max(note.pitch for note in group) - group_low)

    def local_score(note: MidiNote) -> float:
        height = (note.pitch - group_low) / group_span
        return _note_priority(note, profiles[note.track_index], None) + 0.30 * height

    protected: dict[int, MidiNote] = {}
    for note in sorted(group, key=local_score, reverse=True)[:maximum]:
        protected[id(note)] = note
    for note in sorted(group, key=lambda item: (item.pitch, item.velocity), reverse=True)[:3]:
        protected[id(note)] = note
    for note in sorted(group, key=lambda item: (item.velocity, item.duration_ms), reverse=True)[:3]:
        protected[id(note)] = note
    for track_index in {note.track_index for note in group}:
        track_note = max(
            (note for note in group if note.track_index == track_index),
            key=local_score,
        )
        protected[id(track_note)] = track_note
    return sorted(protected.values(), key=lambda note: (note.pitch, note.track_index, note.end_ms))


@lru_cache(maxsize=128)
def _solo_name(name: str) -> bool:
    tokens = set(re.findall(r"[a-z0-9]+", name.casefold()))
    return "solo" in tokens or (
        "lead" in tokens
        and bool(tokens.intersection({"guitar", "violin", "sax", "flute", "synth"}))
    )


def _local_track_prominence(
    groups: list[list[MidiNote]],
    profiles: dict[int, _TrackProfile],
    track_names: dict[int, str] | None,
    arrangement_mode: str = "intelligent",
) -> list[dict[int, float]]:
    """Measure lead evidence in a rolling musical neighbourhood.

    Global activity is deliberately a weak input here. A solo track may be
    sparse across the complete song while becoming the obvious lead for eight
    bars. The symmetric window supplies deterministic look-ahead, and the
    melody-path dynamic program supplies hysteresis between windows.
    """

    if not groups:
        return []
    starts = [min(note.start_ms for note in group) for group in groups]
    gaps = [right - left for left, right in zip(starts, starts[1:], strict=False) if right > left]
    typical_gap = median(gaps) if gaps else 250.0
    radius_ms = max(650.0, min(1600.0, typical_gap * 6.0))
    track_indices = sorted(profiles)
    size = len(groups)
    attacks = {track: [0] * size for track in track_indices}
    present = {track: [0] * size for track in track_indices}
    velocity = {track: [0.0] * size for track in track_indices}
    pitch = {track: [0.0] * size for track in track_indices}
    for index, group in enumerate(groups):
        by_track: dict[int, list[MidiNote]] = defaultdict(list)
        for note in group:
            by_track[note.track_index].append(note)
        for track, track_notes in by_track.items():
            attacks[track][index] = len(track_notes)
            present[track][index] = 1
            velocity[track][index] = sum(note.velocity for note in track_notes)
            pitch[track][index] = sum(note.pitch for note in track_notes)

    def prefix(values: list[int] | list[float]) -> list[float]:
        result = [0.0]
        for value in values:
            result.append(result[-1] + value)
        return result

    attack_prefix = {track: prefix(attacks[track]) for track in track_indices}
    present_prefix = {track: prefix(present[track]) for track in track_indices}
    velocity_prefix = {track: prefix(velocity[track]) for track in track_indices}
    pitch_prefix = {track: prefix(pitch[track]) for track in track_indices}
    # Prefix sums replace these source buffers for all remaining window work.
    del attacks, present, velocity, pitch
    result: list[dict[int, float]] = []
    left = right = 0
    for index, start in enumerate(starts):
        while left < size and starts[left] < start - radius_ms:
            left += 1
        right = max(right, index + 1)
        while right < size and starts[right] <= start + radius_ms:
            right += 1
        window_groups = max(1, right - left)
        features: dict[int, tuple[float, float, float, float]] = {}
        maximum_presence = 1.0
        pitches: list[float] = []
        for track in track_indices:
            attack_count = attack_prefix[track][right] - attack_prefix[track][left]
            presence_count = present_prefix[track][right] - present_prefix[track][left]
            maximum_presence = max(maximum_presence, presence_count)
            if attack_count:
                average_velocity = (
                    velocity_prefix[track][right] - velocity_prefix[track][left]
                ) / attack_count
                average_pitch = (
                    pitch_prefix[track][right] - pitch_prefix[track][left]
                ) / attack_count
                pitches.append(average_pitch)
            else:
                average_velocity = 0.0
                average_pitch = profiles[track].average_pitch
            local_monophony = presence_count / max(1.0, attack_count)
            features[track] = (
                presence_count,
                average_velocity / 127.0,
                average_pitch,
                local_monophony,
            )
        low_pitch = min(pitches, default=48.0)
        high_pitch = max(pitches, default=72.0)
        pitch_span = max(12.0, high_pitch - low_pitch)
        scores: dict[int, float] = {}
        for track in track_indices:
            presence_count, average_velocity, average_pitch, local_monophony = features[track]
            local_activity = presence_count / maximum_presence
            register = max(0.0, min(1.0, (average_pitch - low_pitch) / pitch_span))
            global_quality = max(0.0, min(1.0, (profiles[track].melody_score + 0.2) / 1.5))
            semantic = 0.24 if _solo_name((track_names or {}).get(track, "")) else 0.0
            if arrangement_mode == "vocal" and _is_vocal_name((track_names or {}).get(track, "")):
                semantic += 0.35
            scores[track] = (
                0.32 * local_activity
                + 0.16 * local_monophony
                + 0.14 * average_velocity
                + 0.14 * register
                + 0.12 * profiles[track].melodic_continuity
                + 0.08 * global_quality
                + 0.04 * min(1.0, presence_count / window_groups * 2.0)
                + semantic
            )
        result.append(scores)
    return result


def _melody_local_score(
    note: MidiNote,
    group: list[MidiNote],
    profile: _TrackProfile,
    local_prominence: float,
    forced_solo_track: int | None,
    group_bounds: tuple[int, int] | None = None,
) -> float:
    if group_bounds is None:
        group_low = min(item.pitch for item in group)
        group_span = max(1, max(item.pitch for item in group) - group_low)
    else:
        group_low, group_span = group_bounds
    height = (note.pitch - group_low) / group_span
    duration = min(1.0, note.duration_ms / 1200.0)
    velocity = note.velocity / 127.0
    return (
        0.25 * profile.melody_score
        + 0.15 * height
        + 0.14 * velocity
        + 0.08 * duration
        + 0.08 * profile.melodic_continuity
        + 0.36 * local_prominence
        + (0.90 if forced_solo_track == note.track_index else 0.0)
        - (0.22 if forced_solo_track is not None and forced_solo_track != note.track_index else 0.0)
    )


def _melody_transition_cost(
    previous: MidiNote,
    current: MidiNote,
    *,
    phrase_break: bool,
    gap_ms: float,
    handoff_advantage: float = 0.0,
    is_vocal_transition: bool = False,
) -> float:
    interval = abs(current.pitch - previous.pitch)
    if is_vocal_transition:
        # In vocal mode, entering the vocal track or bridging between vocal phrases
        # must not be suppressed by accompaniment jumps or track-switch penalties.
        interval_cost = min(0.12, interval * 0.015)
        track_switch = 0.0
    else:
        if interval <= 2:
            interval_cost = interval * 0.025
        elif interval <= 7:
            interval_cost = 0.08 + (interval - 2) * 0.055
        elif interval <= 12:
            interval_cost = 0.36 + (interval - 7) * 0.09
        else:
            interval_cost = 0.90 + (interval - 12) * 0.13
        if phrase_break:
            interval_cost *= 0.12
        elif gap_ms >= 360.0:
            interval_cost *= 0.55
        track_switch = 0.0
        if previous.track_index != current.track_index:
            if phrase_break:
                track_switch = 0.08
            else:
                # Strong section-local evidence can earn a deliberate handoff,
                # while weak evidence retains enough inertia to prevent flicker.
                track_switch = max(0.16, 0.38 - max(0.0, handoff_advantage) * 0.75)
    return interval_cost + track_switch


def _solo_track_at(start_ms: float, segments: tuple[SoloSegment, ...]) -> int | None:
    active = [
        segment for segment in segments if segment.start_ms <= start_ms <= segment.end_ms
    ]
    if not active:
        return None
    # The most recently entered section owns an overlap. This lets a nested
    # explicit solo take over from a broader sparse-primary passage and then
    # hand control back at its source boundary.
    return max(active, key=lambda segment: (segment.start_ms, segment.confidence)).track_index


def _trace_melody_path(
    groups: list[list[MidiNote]],
    profiles: dict[int, _TrackProfile],
    track_names: dict[int, str] | None = None,
    forced_solos: tuple[SoloSegment, ...] = (),
    local_prominence: list[dict[int, float]] | None = None,
    arrangement_mode: str = "intelligent",
) -> _MelodyPath:
    """Select a source-backed lead with whole-phrase dynamic programming."""

    if not groups:
        return _MelodyPath((), 0, 0, 0)
    starts = [min(note.start_ms for note in group) for group in groups]
    gaps = [right - left for left, right in zip(starts, starts[1:], strict=False) if right > left]
    typical_gap = median(gaps) if gaps else 0.0
    phrase_threshold = max(700.0, typical_gap * 4.0)
    phrase_breaks = [False] + [
        starts[index] - starts[index - 1] >= phrase_threshold for index in range(1, len(groups))
    ]
    candidates = [_melody_candidates(group, profiles) for group in groups]
    if local_prominence is None:
        local_prominence = _local_track_prominence(groups, profiles, track_names, arrangement_mode)
    primary_track = max(profiles, key=lambda index: profiles[index].melody_score)
    primary_profile = profiles[primary_track]
    scores: list[list[float]] = []
    parents: list[list[int]] = []

    for group_index, group_candidates in enumerate(candidates):
        forced_solo_track = _solo_track_at(starts[group_index], forced_solos)
        group_low = min(note.pitch for note in groups[group_index])
        group_bounds = (group_low, max(1, max(note.pitch for note in groups[group_index]) - group_low))
        def candidate_local_score(
            note: MidiNote,
            *,
            index: int = group_index,
            forced_track: int | None = forced_solo_track,
            bounds: tuple[int, int] = group_bounds,
        ) -> float:
            score = _melody_local_score(
                note,
                groups[index],
                profiles[note.track_index],
                local_prominence[index].get(note.track_index, 0.0),
                forced_track,
                bounds,
            )
            track_name = (track_names or {}).get(note.track_index, "")
            if arrangement_mode == "vocal":
                if _is_vocal_name(track_name):
                    score += 0.50
                elif note.track_index != primary_track and note.track_index != forced_track:
                    score -= 0.20
            elif (
                note.track_index != primary_track
                and note.track_index != forced_track
                and not _solo_name(track_name)
            ):
                profile = profiles[note.track_index]
                if profile.monophony < 0.55:
                    score -= 0.30
                if profile.average_pitch < primary_profile.average_pitch - 7.0:
                    score -= 0.38
            return score

        local_scores = [candidate_local_score(note) for note in group_candidates]
        if group_index == 0:
            scores.append(local_scores)
            parents.append([-1] * len(group_candidates))
            continue
        gap_ms = starts[group_index] - starts[group_index - 1]
        previous_candidates = candidates[group_index - 1]
        current_scores: list[float] = []
        current_parents: list[int] = []
        for candidate, local in zip(group_candidates, local_scores, strict=True):
            cand_is_vocal = arrangement_mode == "vocal" and _is_vocal_name(
                (track_names or {}).get(candidate.track_index, "")
            )

            def transition_cost(
                previous: MidiNote,
                *,
                current: MidiNote = candidate,
                index: int = group_index,
                current_gap: float = gap_ms,
                target_vocal: bool = cand_is_vocal,
            ) -> float:
                prev_is_vocal = arrangement_mode == "vocal" and _is_vocal_name(
                    (track_names or {}).get(previous.track_index, "")
                )
                advantage = local_prominence[index].get(current.track_index, 0.0) - (
                    local_prominence[index].get(previous.track_index, 0.0)
                )
                return _melody_transition_cost(
                    previous,
                    current,
                    phrase_break=phrase_breaks[index],
                    gap_ms=current_gap,
                    handoff_advantage=advantage,
                    is_vocal_transition=target_vocal or prev_is_vocal,
                )

            transitions = [transition_cost(previous) for previous in previous_candidates]
            best_parent = max(
                range(len(previous_candidates)),
                key=lambda previous_index: (
                    scores[-1][previous_index]
                    - transitions[previous_index],
                    previous_candidates[previous_index].track_index == candidate.track_index,
                    -abs(previous_candidates[previous_index].pitch - candidate.pitch),
                    previous_candidates[previous_index].pitch,
                ),
            )
            transition = transitions[best_parent]
            current_scores.append(scores[-1][best_parent] + local - transition)
            current_parents.append(best_parent)
        # Backtracking needs parent indices, not every historical score row.
        scores[:] = [current_scores]
        parents.append(current_parents)

    final_index = max(
        range(len(candidates[-1])),
        key=lambda index: (
            scores[-1][index],
            candidates[-1][index].pitch,
            candidates[-1][index].velocity,
        ),
    )
    path = [candidates[-1][final_index]]
    for group_index in range(len(groups) - 1, 0, -1):
        final_index = parents[group_index][final_index]
        path.append(candidates[group_index - 1][final_index])
    path.reverse()
    track_switches = sum(
        left.track_index != right.track_index
        for left, right in zip(path, path[1:], strict=False)
    )
    large_leaps = sum(
        abs(left.pitch - right.pitch) > 12
        for left, right in zip(path, path[1:], strict=False)
    )
    return _MelodyPath(
        tuple(path),
        1 + sum(phrase_breaks[1:]),
        track_switches,
        large_leaps,
    )


def _detect_solo_segments(
    path: _MelodyPath,
    groups: list[list[MidiNote]],
    profiles: dict[int, _TrackProfile],
    primary_track: int | None,
    track_names: dict[int, str] | None,
    local_prominence: list[dict[int, float]] | None = None,
) -> tuple[SoloSegment, ...]:
    """Convert stable alternate lead runs into protected solo intervals."""

    if primary_track is None or not groups:
        return ()
    if local_prominence is None:
        local_prominence = _local_track_prominence(groups, profiles, track_names)
    segments: list[SoloSegment] = []

    # A deliberate solo can coexist with a sustained vocal/pad at every
    # attack, so the single best-note path may correctly retain the primary
    # voice while still exposing a second, clearly sectional lead. Discover
    # those local runs directly instead of requiring a hard path switch.
    all_starts = [min(note.start_ms for note in group) for group in groups]
    for track_index, profile in profiles.items():
        sectional_primary = track_index == primary_track
        if profile.monophony < (0.75 if sectional_primary else 0.62):
            continue
        present_indices = [
            index
            for index, group in enumerate(groups)
            if any(note.track_index == track_index for note in group)
        ]
        if len(present_indices) < 3:
            continue
        if sectional_primary and (
            len(profiles) < 2 or len(present_indices) / max(1, len(groups)) > 0.72
        ):
            continue
        track_gaps = [
            all_starts[right] - all_starts[left]
            for left, right in zip(present_indices, present_indices[1:], strict=False)
            if all_starts[right] > all_starts[left]
        ]
        typical_track_gap = median(track_gaps) if track_gaps else 250.0
        split_gap = max(700.0, min(1600.0, typical_track_gap * 4.0))
        index_runs: list[list[int]] = []
        for group_index in present_indices:
            if (
                not index_runs
                or all_starts[group_index] - all_starts[index_runs[-1][-1]] > split_gap
            ):
                index_runs.append([group_index])
            else:
                index_runs[-1].append(group_index)
        semantic_solo = _solo_name((track_names or {}).get(track_index, ""))
        for index_run in index_runs:
            minimum_onsets = 3 if semantic_solo else 8
            span = all_starts[index_run[-1]] - all_starts[index_run[0]]
            if len(index_run) < minimum_onsets or span < (240.0 if semantic_solo else 1000.0):
                continue
            if sectional_primary:
                mean_advantage = sum(
                    local_prominence[index].get(track_index, 0.0)
                    - max(
                        (
                            score
                            for rival, score in local_prominence[index].items()
                            if rival != track_index
                            and any(note.track_index == rival for note in groups[index])
                        ),
                        default=0.0,
                    )
                    for index in index_run
                ) / len(index_run)
            else:
                mean_advantage = sum(
                    local_prominence[index].get(track_index, 0.0)
                    - local_prominence[index].get(primary_track, 0.0)
                    for index in index_run
                ) / len(index_run)
            exclusive_ratio = sum(
                not any(note.track_index == primary_track for note in groups[index])
                for index in index_run
            ) / len(index_run)
            section_ratio = len(index_run) / max(1, len(groups))
            if sectional_primary:
                if mean_advantage < 0.045:
                    continue
            elif semantic_solo:
                if section_ratio > 0.75 and mean_advantage < 0.08:
                    continue
            else:
                if mean_advantage < 0.045:
                    continue
                candidate_pitches = [
                    note.pitch
                    for index in index_run
                    for note in groups[index]
                    if note.track_index == track_index
                ]
                primary_pitches = [
                    note.pitch
                    for index in index_run
                    for note in groups[index]
                    if note.track_index == primary_track
                ]
                candidate_register = sum(candidate_pitches) / len(candidate_pitches)
                primary_register = (
                    sum(primary_pitches) / len(primary_pitches)
                    if primary_pitches
                    else profiles[primary_track].average_pitch
                )
                if candidate_register < primary_register - 5.0:
                    continue
            if any(
                segment.track_index == track_index
                and all_starts[index_run[0]] <= segment.end_ms
                and all_starts[index_run[-1]] >= segment.start_ms
                for segment in segments
            ):
                continue
            run_notes = [
                max(
                    (note for note in groups[index] if note.track_index == track_index),
                    key=lambda note: (note.velocity, note.duration_ms, note.pitch),
                )
                for index in index_run
            ]
            confidence = max(
                0.0,
                min(
                    1.0,
                    0.48
                    + mean_advantage * 0.75
                    + exclusive_ratio * 0.18
                    + (0.14 if semantic_solo else 0.0),
                ),
            )
            segments.append(
                SoloSegment(
                    run_notes[0].start_ms,
                    max(note.end_ms for note in run_notes),
                    track_index,
                    confidence,
                    len(run_notes),
                )
            )

    # Merge neighbouring phrases from the same solo track. The second
    # arrangement pass still requires an actual solo-track note before forcing
    # ownership, so joining breath-sized gaps cannot manufacture attacks.
    merged: list[SoloSegment] = []
    by_track: dict[int, list[SoloSegment]] = defaultdict(list)
    for segment in segments:
        by_track[segment.track_index].append(segment)
    for track_segments in by_track.values():
        track_merged: list[SoloSegment] = []
        for segment in sorted(track_segments, key=lambda item: item.start_ms):
            can_merge = bool(
                track_merged
                and segment.start_ms - track_merged[-1].end_ms <= 5000.0
                and not any(
                    other.track_index != segment.track_index
                    and other.start_ms <= segment.start_ms
                    and other.end_ms >= track_merged[-1].end_ms
                    for other in segments
                )
            )
            if can_merge:
                previous = track_merged.pop()
                onset_count = previous.onset_count + segment.onset_count
                track_merged.append(
                    SoloSegment(
                        previous.start_ms,
                        max(previous.end_ms, segment.end_ms),
                        segment.track_index,
                        (
                            previous.confidence * previous.onset_count
                            + segment.confidence * segment.onset_count
                        )
                        / onset_count,
                        onset_count,
                    )
                )
            else:
                track_merged.append(segment)
        merged.extend(track_merged)
    return tuple(sorted(merged, key=lambda item: (item.start_ms, -item.confidence, item.track_index)))


def _select_group(
    group: list[MidiNote],
    melody: MidiNote,
    settings: AppSettings,
    profiles: dict[int, _TrackProfile],
    previous_support: tuple[int, ...],
    solo_focus: bool = False,
) -> list[_Selected]:
    group_low = min(note.pitch for note in group)
    group_high = max(note.pitch for note in group)
    group_span = max(1, group_high - group_low)

    def lead_score(note: MidiNote) -> float:
        top_voice = (note.pitch - group_low) / group_span
        return priority_by_note[id(note)] + 0.24 * top_voice

    priority_by_note = {
        id(note): _note_priority(note, profiles[note.track_index], melody.pitch)
        for note in group
    }
    selected = [
        _Selected(
            melody,
            lead_score(melody) + (2.4 if solo_focus else 1.0),
            "solo" if solo_focus else "melody",
        )
    ]
    if settings.arrangement_mode in {"melody", "adaptive_lead"} or settings.max_polyphony <= 1:
        return selected

    remaining = [note for note in group if note is not melody and note.pitch != melody.pitch]
    if solo_focus:
        # The exposed lead owns the upper register. Retain at most one quieting
        # foundation voice below it; upper pads and competing melodies are the
        # material most likely to mask or physically displace a solo.
        remaining = [
            note
            for note in remaining
            if note.track_index != melody.track_index and note.pitch <= melody.pitch - 4
        ]
        voice_limit = min(settings.max_polyphony, 2)
    else:
        voice_limit = settings.max_polyphony
    if remaining and settings.max_polyphony >= 2:
        bass_candidates = [note for note in remaining if melody.pitch - note.pitch >= 7]
        if not bass_candidates and not solo_focus:
            bass_candidates = [note for note in remaining if melody.pitch - note.pitch >= 3]
        if bass_candidates:
            def bass_score(note: MidiNote) -> tuple[float, int, int]:
                depth = min(1.0, (melody.pitch - note.pitch) / 18.0)
                continuity = max(
                    (_continuity_score(note.pitch, pitch) for pitch in previous_support),
                    default=0.5,
                )
                profile = profiles[note.track_index]
                register_role = max(0.0, (melody.pitch - profile.average_pitch) / 24.0)
                score = (
                    0.45 * depth
                    + 0.18 * continuity
                    + 0.15 * min(1.0, note.duration_ms / 1000.0)
                    + 0.10 * (note.velocity / 127.0)
                    + 0.12 * min(1.0, register_role)
                )
                return score, -note.pitch, note.velocity

            bass = max(
                bass_candidates,
                key=bass_score,
            )
            selected.append(
                _Selected(
                    bass,
                    0.45 + 0.35 * (bass.velocity / 127.0) + 0.2 * min(1.0, bass.duration_ms / 1000.0),
                    "bass",
                )
            )
            remaining.remove(bass)

    if settings.arrangement_mode == "melody_bass":
        return sorted(selected, key=lambda item: (item.note.pitch, item.note.track_index))

    while remaining and len(selected) < voice_limit:
        selected_pitches = [item.note.pitch for item in selected]

        def harmony_score(
            note: MidiNote, _selected_pitches: tuple[int, ...] = tuple(selected_pitches)
        ) -> tuple[float, int, int]:
            interval_distance = min(abs(note.pitch - pitch) for pitch in _selected_pitches)
            pitch_intervals = {abs(note.pitch - pitch) % 12 for pitch in _selected_pitches}
            base = _note_priority(note, profiles[note.track_index], melody.pitch)
            diversity = min(1.0, interval_distance / 12.0)
            consonance = 1.0 if pitch_intervals.intersection({0, 3, 4, 5, 7, 8, 9}) else 0.45
            voice_leading = max(
                (_continuity_score(note.pitch, pitch) for pitch in previous_support),
                default=0.5,
            )
            compactness = math.exp(-abs(note.pitch - melody.pitch) / 18.0)
            return (
                base
                + 0.18 * diversity
                + 0.13 * consonance
                + 0.14 * voice_leading
                + 0.07 * compactness,
                note.velocity,
                note.pitch,
            )

        scored_remaining = [(harmony_score(note), note) for note in remaining]
        harmony_key, harmony = max(scored_remaining, key=lambda item: item[0])
        score = harmony_key[0]
        selected.append(_Selected(harmony, score, "harmony"))
        remaining = [note for note in remaining if note.pitch != harmony.pitch]

    return sorted(selected, key=lambda item: (item.note.pitch, item.note.track_index))


def _mark_landmarks(selected: list[_Selected]) -> list[_Selected]:
    """Protect the shape of fast solo and melody runs before the physical density cap.

    Endpoints, accents, local extrema, direction changes, and regularly spaced
    phrase landmarks receive deterministic priority. The cap may still reduce
    an unplayable run, but it removes connective notes before its identity.
    """

    lead_items = [item for item in selected if item.role in {"solo", "melody"}]
    if not lead_items:
        return selected

    replacements: dict[int, _Selected] = {}
    for role in ("solo", "melody"):
        items = sorted(
            (item for item in lead_items if item.role == role),
            key=lambda item: (item.note.start_ms, item.note.pitch),
        )
        if not items:
            continue
        gaps = [
            right.note.start_ms - left.note.start_ms
            for left, right in zip(items, items[1:], strict=False)
            if right.note.start_ms > left.note.start_ms
        ]
        typical_gap = median(gaps) if gaps else 250.0
        split_gap = max(320.0, typical_gap * 3.5)
        runs: list[list[_Selected]] = []
        for item in items:
            if not runs or item.note.start_ms - runs[-1][-1].note.start_ms > split_gap:
                runs.append([item])
            else:
                runs[-1].append(item)

        for run in runs:
            velocities = [item.note.velocity for item in run]
            velocity_centre = median(velocities)
            for index, item in enumerate(run):
                bonus = 0.0
                landmark = False
                if index in {0, len(run) - 1}:
                    bonus += 3.0
                    landmark = True
                if item.note.velocity >= velocity_centre + 10:
                    bonus += 0.85
                    landmark = True
                if 0 < index < len(run) - 1:
                    left = run[index - 1].note.pitch
                    current = item.note.pitch
                    right = run[index + 1].note.pitch
                    if (current - left) * (right - current) <= 0 and current not in {left, right}:
                        bonus += 1.65
                        landmark = True
                    elif abs(current - left) >= 7 or abs(right - current) >= 7:
                        bonus += 0.65
                        landmark = True
                if index % 4 == 0:
                    bonus += 0.35
                    landmark = True
                if index and item.note.start_ms - run[index - 1].note.start_ms >= typical_gap * 1.45:
                    bonus += 0.55
                    landmark = True
                if landmark:
                    replacements[id(item)] = replace(
                        item,
                        priority=item.priority + bonus,
                        landmark=True,
                    )
    return [replacements.get(id(item), item) for item in selected]


_mark_solo_landmarks = _mark_landmarks


def _apply_retrigger_filter(selected: list[_Selected], minimum_gap_ms: int) -> tuple[list[_Selected], int]:
    if minimum_gap_ms <= 0:
        return selected, 0
    result: list[_Selected | None] = []
    last_by_pitch: dict[int, tuple[_Selected, int]] = {}
    dropped = 0
    for item in sorted(selected, key=lambda value: (value.note.start_ms, -value.priority, value.note.pitch)):
        previous_entry = last_by_pitch.get(item.note.pitch)
        if previous_entry is not None:
            previous, previous_index = previous_entry
        else:
            previous = None
            previous_index = -1
        if previous is not None and item.note.start_ms - previous.note.start_ms < minimum_gap_ms:
            if item.priority <= previous.priority:
                dropped += 1
                continue
            result[previous_index] = None
            dropped += 1
        result_index = len(result)
        result.append(item)
        last_by_pitch[item.note.pitch] = (item, result_index)
    kept = [item for item in result if item is not None]
    kept.sort(key=lambda value: (value.note.start_ms, value.note.pitch, value.note.track_index))
    return kept, dropped


def _apply_density_limit(
    selected: list[_Selected],
    maximum_per_second: int,
) -> tuple[list[_Selected], int, int]:
    if maximum_per_second <= 0:
        return selected, 0, 0

    kept: list[_Selected | None] = []
    window: deque[tuple[_Selected, int]] = deque()
    dropped = 0
    solo_dropped = 0
    for item in sorted(selected, key=lambda value: (value.note.start_ms, -value.priority, value.note.pitch)):
        cutoff = item.note.start_ms - 1000.0
        while window and window[0][0].note.start_ms < cutoff:
            window.popleft()

        if len(window) < maximum_per_second:
            kept_index = len(kept)
            kept.append(item)
            window.append((item, kept_index))
            continue

        replaceable = [
            entry for entry in window if entry[0].role not in {"melody", "solo"}
        ]
        weakest_entry = min(replaceable, key=lambda entry: entry[0].priority, default=None)
        if (
            item.role in {"melody", "solo"}
            and weakest_entry is not None
            and item.priority > weakest_entry[0].priority
        ):
            window.remove(weakest_entry)
            kept[weakest_entry[1]] = None
            kept_index = len(kept)
            kept.append(item)
            window.append((item, kept_index))
            dropped += 1
        elif item.role == "solo":
            weakest_solo = min(
                (entry for entry in window if entry[0].role == "solo"),
                key=lambda entry: entry[0].priority,
                default=None,
            )
            if weakest_solo is not None and item.priority > weakest_solo[0].priority:
                window.remove(weakest_solo)
                kept[weakest_solo[1]] = None
                kept_index = len(kept)
                kept.append(item)
                window.append((item, kept_index))
            solo_dropped += 1
            dropped += 1
        elif item.role == "melody":
            weakest_melody = min(
                (entry for entry in window if entry[0].role == "melody"),
                key=lambda entry: entry[0].priority,
                default=None,
            )
            if weakest_melody is not None and item.priority > weakest_melody[0].priority:
                window.remove(weakest_melody)
                kept[weakest_melody[1]] = None
                kept_index = len(kept)
                kept.append(item)
                window.append((item, kept_index))
            dropped += 1
        else:
            dropped += 1

    result = [item for item in kept if item is not None]
    result.sort(key=lambda value: (value.note.start_ms, value.note.pitch, value.note.track_index))
    return result, dropped, solo_dropped


def _suite_arrangement(
    working: list[MidiNote], settings: AppSettings, profiles: dict[int, _TrackProfile],
    track_names: dict[int, str] | None, recipe: ArrangementRecipe,
) -> tuple[list[_Selected], _MelodyPath, int, list[str], dict[str, int]]:
    """Reduce all selected layers around an owned lead; never manufacture notes."""
    names = track_names or {}
    warnings: list[str] = []
    preferred = settings.arrangement_lead_track
    if preferred not in profiles:
        preferred = -1
    if preferred < 0 and recipe.lead == "vocal":
        vocal_tracks = [track for track in profiles if _is_vocal_name(names.get(track, ""))]
        def vocal_rank(track: int) -> tuple[float, float, int]:
            tokens = set(re.findall(r"[a-z0-9]+", names.get(track, "").casefold()))
            label = float(bool(tokens & {"lead", "main", "solo"}))
            label -= float(bool(tokens & {"backing", "background", "choir", "harmony"}))
            return label, profiles[track].melody_score, -track
        if vocal_tracks:
            preferred = max(vocal_tracks, key=vocal_rank)
        else:
            warnings.append("No named vocal track found; using inferred melody. Choose Lead track to target an unnamed vocal part.")
    primary = preferred if preferred >= 0 else max(profiles, key=lambda t: (profiles[t].melody_score, -t))
    if recipe.processing == "contextual":
        # Stable ownership also applies to unnamed/instrumental primary tracks.
        preferred = primary
    groups = _group_onsets(working, settings.onset_group_ms)
    # Forced candidates retain phrase optimization within a polyphonic lead
    # track while preventing a loud orchestral layer from stealing its attack.
    is_cover = recipe.texture in {"cover", "cover_riff"}
    roles = infer_cover_layers(working, primary, names) if is_cover else None
    candidates = []
    for group in groups:
        owned = [n for n in group if n.track_index == preferred]
        alternatives = group
        if roles is not None:
            fills = [n for n in group if roles[n.track_index] == "fill"]
            riffs = [n for n in group if roles[n.track_index] == "rhythm"]
            alternatives = fills or riffs or group
        candidates.append(owned or alternatives)
    path = _trace_melody_path(candidates, profiles, names)
    limit = min(recipe.layers, settings.max_polyphony)
    if recipe.processing == "contextual":
        processed = process_contextual_arrangement(groups, path.notes, primary, limit, recipe.texture, roles)
        if roles is not None:
            warnings.append("Cover source layers (inferred): " + "; ".join(
                f"{names.get(track, f'Track {track}')} = {role}" for track, role in sorted(roles.items())
            ) + (". Rhythm reserves space before bass and harmony; missing parts are not generated."
                 if recipe.texture == "cover_riff" else
                 ". Bass and rhythm reserve space before harmony; missing parts are not generated."))
            if preferred >= 0 and set(re.findall(r"[a-z0-9]+", names.get(primary, "").casefold())) & {"backing", "background", "choir", "harmony"}:
                warnings.append("Chosen lead is labelled as backing/harmony. Use Lead track to choose the main singer if it has an unfamiliar name.")
        selected = [_Selected(n, 5.0 + n.velocity / 127.0, "melody") for n in processed.leads]
        selected.extend(_Selected(n, 0.6 + n.velocity / 254.0, "harmony") for n in processed.support)
        selected.sort(key=lambda item: (item.note.start_ms, item.note.pitch, item.note.track_index))
        actual = processed.leads
        path = _MelodyPath(
            actual,
            1 + sum(b.start_ms - a.end_ms >= 750 for a, b in zip(actual, actual[1:], strict=False)) if actual else 0,
            sum(a.track_index != b.track_index for a, b in zip(actual, actual[1:], strict=False)),
            sum(abs(a.pitch - b.pitch) > 12 for a, b in zip(actual, actual[1:], strict=False)),
        )
        warnings.append(
            f"{recipe.label}: duration-aware support with {limit} total voice slots; "
            f"{processed.capacity_rejected:,} support candidates omitted for held/future voice capacity and "
            f"{processed.collision_rejected:,} for overlapping same-pitch voices."
        )
        if processed.peak_voices > limit:
            warnings.append("Source lead notes overlap beyond the voice ceiling; preserved source releases. Physical planning may simplify them.")
        warnings.append(f"Suite lead: {names.get(primary, f'Track {primary}')}. Exact source attacks; no generated harmony.")
        return selected, path, primary, warnings, {
            "contextual_capacity_rejected": processed.capacity_rejected,
            "contextual_collision_rejected": processed.collision_rejected,
            "contextual_phrase_resets": processed.phrase_resets,
            "contextual_peak_voices": processed.peak_voices,
        }
    selected: list[_Selected] = []
    previous_support: tuple[int, ...] = ()
    held_lead: MidiNote | None = None
    audible_leads: list[MidiNote] = []
    for group, traced in zip(groups, path.notes, strict=True):
        owned_attack = any(n.track_index == preferred for n in group)
        under_lead = (
            not owned_attack and held_lead is not None
            and min(n.start_ms for n in group) < held_lead.end_ms
        )
        lead = held_lead if under_lead else traced
        assert lead is not None
        if not under_lead:
            selected.append(_Selected(lead, 5.0 + lead.velocity / 127.0, "melody"))
            audible_leads.append(lead)
            if owned_attack:
                held_lead = lead
        used = {lead.pitch}
        support: list[MidiNote] = []
        available = [n for n in group if n is not lead and n.pitch not in used]
        # Vocal textures stay below the singer, except choir/wide textures
        # where nearby or spread source harmony is explicitly requested.
        if recipe.texture not in {"choir", "wide"}:
            available = [n for n in available if n.pitch <= lead.pitch - 3]
        bass = [n for n in available if n.pitch <= lead.pitch - 7]
        if limit > 1 and bass and recipe.texture not in {"choir", "arpeggio", "tight", "jazz"}:
            foundation = min(bass, key=lambda n: (n.pitch, -n.velocity, n.track_index))
            support.append(foundation)
            used.add(foundation.pitch)
        def support_score(
            n: MidiNote, lead: MidiNote = lead,
            previous_support: tuple[int, ...] = previous_support,
            support: list[MidiNote] = support,
        ) -> tuple[float, int, int, int]:
            distance = abs(n.pitch - lead.pitch)
            interval = distance % 12
            compact = math.exp(-distance / 16.0)
            sustain = min(n.duration_ms / 1200.0, 1.0)
            accent = n.velocity / 127.0
            continuity = max((_continuity_score(n.pitch, p) for p in previous_support), default=0.5)
            consonance = float(interval in {0, 3, 4, 5, 7, 8, 9})
            score = 0.35 * consonance + 0.20 * continuity + 0.15 * accent
            occupied_pitch_classes = {lead.pitch % 12} | {
                existing.pitch % 12 for existing in support
            }
            score += 0.22 if n.pitch % 12 not in occupied_pitch_classes else -0.45
            if recipe.texture == "bass":
                score += min(distance / 24.0, 1.0)
            elif recipe.texture == "warm":
                score += 0.75 * sustain + 0.35 * compact
            elif recipe.texture == "tight":
                score += 0.95 * compact
            elif recipe.texture == "power":
                score += 1.2 * float(interval in {0, 7}) + 0.3 * accent
            elif recipe.texture in {"pulse", "arpeggio"}:
                score += 0.8 * (1.0 - sustain) + (0.6 * accent if recipe.texture == "pulse" else 0.6 * compact)
            elif recipe.texture == "choir":
                score += 1.4 * float(_is_vocal_name(names.get(n.track_index, ""))) + 0.6 * compact
            elif recipe.texture == "jazz":
                score += 0.8 * float(interval in {3, 4, 8, 9, 10, 11}) + 0.6 * compact
            elif recipe.texture == "wide":
                spacing = min((abs(n.pitch - x.pitch) for x in support), default=distance)
                score += 0.6 * min(spacing / 18.0, 1.0) + 0.5 * sustain
            return score, n.velocity, -n.track_index, n.pitch
        while len(support) < limit - 1:
            remaining = [n for n in available if n.pitch not in used]
            if not remaining:
                break
            chosen = max(remaining, key=support_score)
            support.append(chosen)
            used.add(chosen.pitch)
        selected.extend(_Selected(n, 0.6 + n.velocity / 254.0, "harmony") for n in support)
        previous_support = tuple(n.pitch for n in support)
    # Report the actual emitted lead, excluding suppressed accompaniment attacks.
    path = _MelodyPath(
        tuple(audible_leads), path.phrase_count,
        sum(a.track_index != b.track_index for a, b in zip(audible_leads, audible_leads[1:], strict=False)),
        sum(abs(a.pitch - b.pitch) > 12 for a, b in zip(audible_leads, audible_leads[1:], strict=False)),
    )
    warnings.append(f"{recipe.label}: up to {limit} source layers per attack (recipe {recipe.layers}, Maximum chord notes {settings.max_polyphony}).")
    if recipe.layers > 3:
        warnings.append("Four or more layers are experimental; SCUM key collisions and bank limits can reduce the final texture.")
    warnings.append(f"Suite lead: {names.get(primary, f'Track {primary}')}. Exact source attacks; no generated harmony.")
    return selected, path, primary, warnings, {}


def arrange_notes(
    notes: Iterable[MidiNote],
    settings: AppSettings,
    *,
    prepared_source: bool = False,
    track_names: dict[int, str] | None = None,
) -> ArrangementResult:
    """Reduce arbitrary MIDI material to a game-playable musical arrangement.

    This stage is deliberately independent from SCUM key mapping. It removes
    percussion/noise, preserves a continuous lead voice, and limits density
    before the physical-key planner handles octave state and key collisions.
    """

    settings.normalize()
    source = sorted(notes, key=lambda note: (note.start_ms, note.pitch, note.end_ms))
    source_recipe = ARRANGEMENT_RECIPES.get(settings.arrangement_mode)
    if source_recipe is not None and source_recipe.processing == "contextual":
        source.sort(key=lambda n: (n.start_ms, n.pitch, n.end_ms, n.track_index, n.channel, -n.velocity))
    warnings: list[str] = []
    if not source:
        return ArrangementResult(
            notes=(),
            source_notes=0,
            dropped_percussion=0,
            dropped_short=0,
            dropped_retrigger=0,
            dropped_density=0,
            dropped_arrangement=0,
            chord_groups=0,
            performed_chord_groups=0,
            chord_notes_aligned=0,
            chord_alignment_ms=0.0,
            chord_detection_window_ms=float(settings.onset_group_ms),
            melody_track=None,
            warnings=("No notes were selected.",),
        )

    working: list[MidiNote] = []
    dropped_percussion = 0
    dropped_short = 0
    for note in source:
        if settings.ignore_percussion and note.channel == 9:
            dropped_percussion += 1
            continue
        if not prepared_source and note.duration_ms < settings.min_source_note_ms:
            dropped_short += 1
            continue
        working.append(note)

    if not working:
        warnings.append("All selected notes were removed as percussion or ultra-short noise.")
        return ArrangementResult(
            notes=(),
            source_notes=len(source),
            dropped_percussion=dropped_percussion,
            dropped_short=dropped_short,
            dropped_retrigger=0,
            dropped_density=0,
            dropped_arrangement=0,
            chord_groups=0,
            performed_chord_groups=0,
            chord_notes_aligned=0,
            chord_alignment_ms=0.0,
            chord_detection_window_ms=float(settings.onset_group_ms),
            melody_track=None,
            warnings=tuple(warnings),
        )

    profiles = _track_profiles(
        working,
        settings.onset_group_ms,
        track_names,
        arrangement_mode=settings.arrangement_mode,
    )
    vocal_track: int | None = None
    if settings.arrangement_mode == "vocal":
        for t_idx in sorted(profiles):
            t_name = (track_names or {}).get(t_idx, "")
            if _is_vocal_name(t_name):
                vocal_track = t_idx
                break
        if vocal_track is None:
            # GM Choir Aahs, Voice Oohs and Synth Voice are useful fallback
            # evidence for anonymous karaoke/orchestral exports.  Actual note
            # shape still decided whether the track survived Smart Select.
            for t_idx in sorted(profiles):
                track_programs = Counter(
                    note.program
                    for note in working
                    if note.track_index == t_idx and note.program is not None
                )
                if track_programs:
                    program = max(
                        track_programs,
                        key=lambda value: (track_programs[value], -value),
                    )
                    if program in {52, 53, 54}:
                        vocal_track = t_idx
                        break
    melody_track = (
        vocal_track
        if vocal_track is not None
        else max(profiles, key=lambda index: profiles[index].melody_score, default=None)
    )
    chord_groups = 0
    performed_chord_groups = 0
    chord_notes_aligned = 0
    chord_alignment_ms = 0.0
    chord_detection_window_ms = float(settings.onset_group_ms)
    melody_path = _MelodyPath((), 0, 0, 0)
    solo_segments: tuple[SoloSegment, ...] = ()
    solo_accompaniment_dropped = 0
    solo_density_dropped = 0
    solo_landmarks_preserved = 0
    melody_landmarks_preserved = 0
    recipe = ARRANGEMENT_RECIPES.get(settings.arrangement_mode)
    contextual_metrics: dict[str, int] = {}
    if recipe is not None:
        selected, melody_path, melody_track, recipe_warnings, contextual_metrics = _suite_arrangement(
            working, settings, profiles, track_names, recipe,
        )
        warnings.extend(recipe_warnings)
        chord_groups = sum(count > 1 for count in Counter(n.note.start_ms for n in selected).values())
        dropped_arrangement = len(working) - len(selected)
        selected, dropped_retrigger = _apply_retrigger_filter(selected, settings.min_retrigger_ms)
        selected = _mark_landmarks(selected)
        selected, dropped_density, solo_density_dropped = _apply_density_limit(selected, settings.max_notes_per_second)
        melody_landmarks_preserved = sum(item.role == "melody" and item.landmark for item in selected)
    elif settings.arrangement_mode == "faithful":
        selected = [_Selected(note, note.velocity / 127.0, "source") for note in working]
        dropped_arrangement = 0
        dropped_retrigger = 0
        dropped_density = 0
    else:
        selected = []
        if settings.arrangement_mode == "melody" and melody_track is not None:
            arranged_source = [note for note in working if note.track_index == melody_track]
        else:
            arranged_source = working

        recognition_mode = (
            settings.chord_recognition_mode
            if settings.arrangement_mode in {"intelligent", "vocal"}
            else "exact"
        )
        discovery_groups = _group_onsets(arranged_source, settings.onset_group_ms)
        discovery_prominence = _local_track_prominence(
            discovery_groups,
            profiles,
            track_names,
            arrangement_mode=settings.arrangement_mode,
        )
        discovery_path = _trace_melody_path(
            discovery_groups,
            profiles,
            track_names,
            local_prominence=discovery_prominence,
            arrangement_mode=settings.arrangement_mode,
        )
        if settings.arrangement_mode in {"intelligent", "vocal"}:
            solo_segments = _detect_solo_segments(
                discovery_path,
                discovery_groups,
                profiles,
                melody_track,
                track_names,
                local_prominence=discovery_prominence,
            )
        onset_groups, chord_detection_window_ms = _group_score_onsets(
            arranged_source,
            settings.onset_group_ms,
            recognition_mode,
            solo_segments,
        )
        same_groups = onset_groups == discovery_groups
        if same_groups and not solo_segments:
            melody_path = discovery_path
        else:
            melody_path = _trace_melody_path(
                onset_groups,
                profiles,
                track_names,
                solo_segments,
                local_prominence=discovery_prominence if same_groups else None,
                arrangement_mode=settings.arrangement_mode,
            )
        previous_support: tuple[int, ...] = ()
        for group, melody_note in zip(onset_groups, melody_path.notes, strict=True):
            solo_track = _solo_track_at(melody_note.start_ms, solo_segments)
            solo_focus = solo_track == melody_note.track_index
            chosen = _select_group(
                group,
                melody_note,
                settings,
                profiles,
                previous_support,
                solo_focus,
            )
            if solo_focus:
                solo_accompaniment_dropped += max(0, len(group) - 1 - (len(chosen) - 1))
            previous_support = tuple(
                item.note.pitch for item in chosen if item.role not in {"melody", "solo"}
            )
            selected_pitch_classes = {item.note.pitch % 12 for item in chosen}
            is_chord = len(selected_pitch_classes) >= 2
            performed_chord = (
                is_chord
                and not solo_focus
                and max(item.note.start_ms for item in chosen) - min(item.note.start_ms for item in chosen)
                > settings.onset_group_ms
            )
            if is_chord:
                chord_groups += 1
            if performed_chord:
                performed_chord_groups += 1
                anchor = min(item.note.start_ms for item in chosen)
                aligned: list[_Selected] = []
                for item in chosen:
                    adjustment = item.note.start_ms - anchor
                    if adjustment > 0.001:
                        chord_notes_aligned += 1
                        chord_alignment_ms += adjustment
                        aligned_note = replace(
                            item.note,
                            start_ms=anchor,
                            end_ms=anchor + item.note.duration_ms,
                        )
                        item = replace(item, note=aligned_note)
                    aligned.append(item)
                chosen = aligned
            selected.extend(chosen)
        dropped_arrangement = len(working) - len(selected)
        selected, dropped_retrigger = _apply_retrigger_filter(selected, settings.min_retrigger_ms)
        selected = _mark_landmarks(selected)
        selected, dropped_density, solo_density_dropped = _apply_density_limit(
            selected,
            settings.max_notes_per_second,
        )
        solo_landmarks_preserved = sum(
            item.role == "solo" and item.landmark for item in selected
        )
        melody_landmarks_preserved = sum(
            item.role == "melody" and item.landmark for item in selected
        )

    if dropped_percussion:
        warnings.append(f"Ignored {dropped_percussion:,} MIDI percussion notes from channel 10.")
    if dropped_short:
        warnings.append(f"Removed {dropped_short:,} notes shorter than {settings.min_source_note_ms} ms.")
    if dropped_retrigger:
        warnings.append(f"Removed {dropped_retrigger:,} duplicate retriggers too close together for reliable game input.")
    if dropped_density:
        warnings.append(
            f"Removed {dropped_density:,} low-priority notes to stay under {settings.max_notes_per_second} notes/s."
        )
    if prepared_source:
        warnings.append(
            "Recognised preprocessed lead/support tracks bypass the second source-duration filter; source cleanup was already applied."
        )
    if settings.arrangement_mode == "melody":
        warnings.append("Lead melody only keeps one protected melody note per onset.")
    elif settings.arrangement_mode == "adaptive_lead":
        warnings.append("Adaptive lead only follows one source note per onset across selected tracks.")
    elif settings.arrangement_mode == "melody_bass":
        warnings.append("Melody + bass keeps a traced lead and at most one lower source foundation note.")
    elif settings.arrangement_mode == "vocal":
        vocal_name = (track_names or {}).get(melody_track, f"Track {melody_track}") if melody_track is not None else "primary lead"
        warnings.append(f"Vocal lead focus prioritised vocal phrasing on {vocal_name}.")
    if melody_path.notes:
        warnings.append(
            f"Whole-phrase voice tracing followed {melody_path.phrase_count:,} phrase(s) with "
            f"{melody_path.track_switches:,} source-track change(s) and "
            f"{melody_path.large_leaps:,} transition(s) larger than one octave."
        )
    if solo_segments:
        solo_onsets = sum(segment.onset_count for segment in solo_segments)
        warnings.append(
            f"Dynamic Solo Director protected {len(solo_segments):,} solo section(s) across "
            f"{solo_onsets:,} lead onset(s), ducking {solo_accompaniment_dropped:,} competing "
            "source note(s) and reserving the lead voice."
        )
    if solo_density_dropped:
        warnings.append(
            f"Reduced {solo_density_dropped:,} over-dense solo connector note(s) while preserving "
            f"{solo_landmarks_preserved:,} endpoint, accent, and contour landmark(s)."
        )
    if performed_chord_groups:
        warnings.append(
            f"Automatic chord recognition aligned {chord_notes_aligned:,} source note(s) in "
            f"{performed_chord_groups:,} performed chord(s) without inventing harmony."
        )

    return ArrangementResult(
        notes=tuple(item.note for item in selected),
        source_notes=len(source),
        dropped_percussion=dropped_percussion,
        dropped_short=dropped_short,
        dropped_retrigger=dropped_retrigger,
        dropped_density=dropped_density,
        dropped_arrangement=dropped_arrangement,
        chord_groups=chord_groups,
        performed_chord_groups=performed_chord_groups,
        chord_notes_aligned=chord_notes_aligned,
        chord_alignment_ms=chord_alignment_ms,
        chord_detection_window_ms=chord_detection_window_ms,
        melody_track=melody_track,
        warnings=tuple(warnings),
        melody_phrase_count=melody_path.phrase_count,
        melody_track_switches=melody_path.track_switches,
        melody_large_leaps=melody_path.large_leaps,
        solo_segments=solo_segments,
        solo_notes=sum(item.role == "solo" for item in selected),
        solo_accompaniment_dropped=solo_accompaniment_dropped,
        solo_density_dropped=solo_density_dropped,
        solo_landmarks_preserved=solo_landmarks_preserved,
        melody_landmarks_preserved=melody_landmarks_preserved,
        lead_notes=tuple(
            item.note for item in selected if item.role in {"melody", "solo"}
        ),
        **contextual_metrics,
    )
