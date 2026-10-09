from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, replace
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

from .arranger import SoloSegment, arrange_notes
from .config import AppSettings
from .instrument_profiles import resolve_instrument_profile
from .model import KeyBindingProfile, KeyEvent, MidiNote, PlannedNote, PlaybackPlan, midi_note_name
from .performance_phrasing import FluidPhrasingStats, apply_fluid_phrasing
from .score_optimizer import NoteAnalysis, optimal_settings_for_notes

OCTAVE_BANK_TAP_HOLD_MS = 18.0


@dataclass(frozen=True, slots=True)
class _MappedCandidate:
    source: MidiNote
    mapped_pitch: int
    base_pitch: int
    modifier: int
    group_index: int
    transpose_applied: int
    is_solo: bool = False
    is_lead: bool = False


def _fold_to_window(pitch: int, low: int, high: int) -> int:
    if pitch < low:
        pitch += ((low - pitch + 11) // 12) * 12
    if pitch > high:
        pitch -= ((pitch - high + 11) // 12) * 12
    return pitch




def _automatic_strict_octave_shift(notes: list[MidiNote], transpose: int) -> int:
    """Choose the best octave shift to fit maximum notes strictly into C4-C5 (60..72)."""

    if not notes:
        return 0
    playable_low = 60
    playable_high = 72
    weighted: list[tuple[int, float]] = []
    for note in notes:
        pitch = max(0, min(127, note.pitch + transpose))
        weight = min(note.duration_ms, 1800.0) * (0.35 + note.velocity / 127.0)
        weighted.append((pitch, weight))

    def score(shift: int) -> tuple[float, float, int, int]:
        exact_weight = 0.0
        dist = 0.0
        for pitch, weight in weighted:
            shifted = pitch + shift
            if playable_low <= shifted <= playable_high:
                exact_weight += weight
            else:
                dist += min(abs(shifted - playable_low), abs(shifted - playable_high)) * weight
        return (exact_weight, -dist, -abs(shift), -shift)

    return max(range(-72, 73, 12), key=score)


def _adaptive_scum_octave_shift(notes: list[MidiNote], transpose: int) -> int:
    """Adaptive multi-objective octave shift optimizer for SCUM 3-octave coverage."""

    if not notes:
        return 0
    playable_low = 48
    playable_high = 84
    weighted: list[tuple[int, float, bool]] = []
    total_weight = 0.0
    for note in notes:
        pitch = max(0, min(127, note.pitch + transpose))
        duration = note.duration_ms
        is_lead = note.velocity >= 80 or duration >= 200.0
        weight = min(duration, 2000.0) * (0.4 + note.velocity / 127.0)
        weighted.append((pitch, weight, is_lead))
        total_weight += weight

    def score(shift: int) -> tuple[float, float, int, float, int]:
        exact_weight = 0.0
        lead_exact_weight = 0.0
        fold_dist = 0.0
        shifted_total = 0.0

        for pitch, weight, is_lead in weighted:
            shifted = pitch + shift
            shifted_total += shifted * weight
            if playable_low <= shifted <= playable_high:
                exact_weight += weight
                if is_lead:
                    lead_exact_weight += weight
            folded = _fold_to_window(shifted, playable_low, playable_high)
            fold_dist += abs(folded - shifted) * weight

        centre = shifted_total / max(total_weight, 1e-9)
        return (
            lead_exact_weight * 1.5 + exact_weight,
            -fold_dist,
            -abs(shift),
            -abs(centre - (playable_low + playable_high) / 2.0),
            -shift,
        )

    return max(range(-120, 121, 12), key=score)



def _group_onsets(notes: list[MidiNote], tolerance_ms: int) -> list[list[MidiNote]]:
    if not notes:
        return []
    groups: list[list[MidiNote]] = []
    current: list[MidiNote] = [notes[0]]
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


def _choose_polyphony(group: list[_MappedCandidate], limit: int) -> list[_MappedCandidate]:
    by_target: dict[tuple[int, int], _MappedCandidate] = {}
    for item in group:
        key = (item.modifier, item.base_pitch)
        current = by_target.get(key)
        if current is None or (
            item.is_solo,
            item.is_lead,
            item.source.velocity,
            item.source.duration_ms,
        ) > (
            current.is_solo,
            current.is_lead,
            current.source.velocity,
            current.source.duration_ms,
        ):
            by_target[key] = item
    unique = list(by_target.values())
    if len(unique) <= limit:
        return sorted(unique, key=lambda item: (item.base_pitch, item.source.pitch))

    ranked = sorted(unique, key=lambda item: (item.source.velocity, item.source.pitch), reverse=True)
    selected: list[_MappedCandidate] = []
    if limit >= 1:
        selected.append(
            max(
                unique,
                key=lambda item: (
                    item.is_solo,
                    item.is_lead,
                    item.source.pitch,
                    item.source.velocity,
                    item.source.duration_ms,
                ),
            )
        )
    if limit >= 2:
        low = min(unique, key=lambda item: item.source.pitch)
        if low not in selected:
            selected.append(low)
    for item in ranked:
        if item not in selected:
            selected.append(item)
        if len(selected) >= limit:
            break
    return sorted(selected[:limit], key=lambda item: (item.base_pitch, item.source.pitch))



@dataclass(frozen=True, slots=True)
class _PerformanceDirectorStats:
    groups: int = 0
    dense_groups_simplified: int = 0
    lead_attacks_protected: int = 0
    source_outer_voices_protected: int = 0
    continuity_transitions: int = 0
    average_voice_leading_semitones: float = 0.0


def _dedupe_mapped_candidates(group: list[_MappedCandidate]) -> list[_MappedCandidate]:
    """Collapse physical-key collisions while keeping the musically strongest source note."""

    by_target: dict[tuple[int, int], _MappedCandidate] = {}
    for item in group:
        key = (item.modifier, item.base_pitch)
        current = by_target.get(key)
        if current is None or (
            item.is_solo,
            item.is_lead,
            item.source.velocity,
            item.source.duration_ms,
            item.source.pitch,
        ) > (
            current.is_solo,
            current.is_lead,
            current.source.velocity,
            current.source.duration_ms,
            current.source.pitch,
        ):
            by_target[key] = item
    return list(by_target.values())


def _candidate_importance(item: _MappedCandidate, *, low_pitch: int, high_pitch: int) -> float:
    velocity = item.source.velocity / 127.0
    duration = min(item.source.duration_ms, 1800.0) / 1800.0
    score = 1.0 + velocity * 1.15 + duration * 0.45
    if item.is_lead:
        score += 4.8
    if item.is_solo:
        score += 3.2
    if item.source.pitch == high_pitch:
        score += 1.8
    if item.source.pitch == low_pitch:
        score += 0.9
    # Folding by several octaves is sometimes unavoidable, but when two source
    # candidates compete for the same physical slot prefer the truer register.
    score -= 0.10 * abs(item.mapped_pitch - item.source.pitch) / 12.0
    return score


def _harmonic_role_bonuses(group: list[_MappedCandidate]) -> dict[_MappedCandidate, float]:
    """Reward source tones that preserve a chord's identity under voice limits.

    This is intentionally conservative: it only ranks notes already present in
    the MIDI.  A likely root is inferred from the observed pitch classes and
    bass, then thirds/sevenths receive more weight than a dispensable fifth or
    octave doubling.  Ambiguous dyads receive very small/no semantic bonuses.
    """

    if len(group) < 3:
        return {}
    pitch_classes = {item.source.pitch % 12 for item in group}
    if len(pitch_classes) < 3:
        return {}
    bass_pc = min(group, key=lambda item: item.source.pitch).source.pitch % 12
    best_root: int | None = None
    best_score = float("-inf")
    for root in pitch_classes:
        intervals = {(pc - root) % 12 for pc in pitch_classes}
        has_minor_third = 3 in intervals
        has_major_third = 4 in intervals
        has_fifth = 7 in intervals
        has_seventh = 10 in intervals or 11 in intervals
        # Require at least a third or fifth before claiming chord function.
        if not (has_minor_third or has_major_third or has_fifth):
            continue
        score = 0.55 * (root == bass_pc)
        score += 2.2 * (has_minor_third or has_major_third)
        score += 1.15 * has_fifth
        score += 0.55 * has_seventh
        if score > best_score:
            best_score = score
            best_root = root
    if best_root is None:
        return {}

    bonuses: dict[_MappedCandidate, float] = {}
    for item in group:
        interval = (item.source.pitch % 12 - best_root) % 12
        if interval == 0:
            bonus = 0.48
        elif interval in {3, 4}:
            bonus = 0.88
        elif interval in {10, 11}:
            bonus = 0.52
        elif interval == 7:
            bonus = 0.20
        else:
            bonus = 0.08
        bonuses[item] = bonus
    return bonuses


def _voicing_local_score(
    option: tuple[_MappedCandidate, ...],
    unique: list[_MappedCandidate],
    *,
    limit: int,
    gap_ms: float,
    harmonic_bonuses: dict[_MappedCandidate, float] | None = None,
) -> float:
    low_pitch = min(item.source.pitch for item in unique)
    high_pitch = max(item.source.pitch for item in unique)
    if harmonic_bonuses is None:
        harmonic_bonuses = _harmonic_role_bonuses(unique)
    score = sum(
        _candidate_importance(item, low_pitch=low_pitch, high_pitch=high_pitch)
        + harmonic_bonuses.get(item, 0.0)
        for item in option
    )
    chosen = set(option)

    # Dropping a traced lead should be almost impossible unless mapping itself
    # made that attack unplayable.
    for item in unique:
        if item not in chosen and item.is_lead:
            score -= 14.0
        elif item not in chosen and item.is_solo:
            score -= 10.0

    source_sorted = sorted(option, key=lambda item: item.source.pitch)
    mapped_sorted = [item.mapped_pitch for item in source_sorted]
    # Penalise inversions introduced by octave folding. A compact inversion can
    # be musically valid, but repeated arbitrary inversions make melodies/chords
    # sound as though the harmony is jumping around.
    inversions = sum(
        mapped_sorted[left] > mapped_sorted[right]
        for left in range(len(mapped_sorted))
        for right in range(left + 1, len(mapped_sorted))
    )
    score -= inversions * 1.6

    if len(option) >= 2:
        mapped = sorted(item.mapped_pitch for item in option)
        spacings = [right - left for left, right in zip(mapped, mapped[1:], strict=False)]
        score += min(mapped[-1] - mapped[0], 16) * 0.045
        score -= sum(max(0, 2 - spacing) * 0.8 for spacing in spacings)
        # Preserve the source's outer voices when there is room. They are the
        # strongest perceptual cues for bass movement and melody contour.
        if any(item.source.pitch == low_pitch for item in option):
            score += 0.75
        if any(item.source.pitch == high_pitch for item in option):
            score += 1.1

    # Fast passages should breathe. The user-selected polyphony remains a hard
    # ceiling, but Automatic is allowed to use fewer accompaniment voices so a
    # rapid line does not become a machine-gun chord stream.
    if gap_ms < 70.0:
        soft_limit = 1
    elif gap_ms < 115.0:
        soft_limit = min(2, limit)
    else:
        soft_limit = limit
    if len(option) > soft_limit:
        score -= (len(option) - soft_limit) * (3.4 if gap_ms < 70.0 else 2.0)
    else:
        score += 0.12 * len(option)

    # Duplicate source pitch classes are usually octave doublings. Once SCUM
    # has only a handful of keys available, harmonic variety is generally more
    # valuable than spending another voice on the same pitch class.
    pitch_classes = {item.source.pitch % 12 for item in option}
    score += len(pitch_classes) * 0.22
    score -= (len(option) - len(pitch_classes)) * 0.28
    return score


def _distinct_voice_leading_distance(previous_pitches: list[int], current_pitches: list[int]) -> float:
    """Minimum one-to-one pitch motion between two small voicings.

    Nearest-neighbour distance lets several new voices all "reuse" one old
    voice, which makes large revoicings look deceptively smooth.  The SCUM
    director normally works with at most three voices, so a tiny bitmask DP
    gives an exact distinct assignment cheaply.
    """

    if not previous_pitches or not current_pitches:
        return 0.0
    left = sorted(previous_pitches)
    right = sorted(current_pitches)
    # Match the smaller set into distinct members of the larger set.
    if len(left) > len(right):
        left, right = right, left
    if len(right) > 8:
        # Custom expert settings can exceed the Automatic voice budget.  Avoid
        # exponential work there; sorted rank matching is a stable fallback.
        common = min(len(left), len(right))
        distance = sum(abs(left[i] - right[i]) for i in range(common))
        distance += abs(len(right) - len(left)) * 4.0
        return distance / max(1, len(right))

    states: dict[int, float] = {0: 0.0}
    for pitch in left:
        next_states: dict[int, float] = {}
        for mask, cost in states.items():
            for index, target in enumerate(right):
                bit = 1 << index
                if mask & bit:
                    continue
                new_mask = mask | bit
                new_cost = cost + abs(pitch - target)
                if new_cost < next_states.get(new_mask, float("inf")):
                    next_states[new_mask] = new_cost
        states = next_states
    best = min(states.values(), default=0.0)
    # Voice entrances/exits are less disruptive than a large leap but still
    # represent a change in physical hand shape, so give them a small cost.
    best += (len(right) - len(left)) * 4.0
    return best / max(1, len(right))


def _voicing_transition_score(
    previous: tuple[_MappedCandidate, ...],
    current: tuple[_MappedCandidate, ...],
    *,
    gap_ms: float,
    settings: AppSettings,
) -> tuple[float, float]:
    if not previous or not current or gap_ms >= 700.0:
        return 0.0, 0.0

    previous_mapped = [item.mapped_pitch for item in previous]
    current_mapped = [item.mapped_pitch for item in current]
    mean_distance = _distinct_voice_leading_distance(previous_mapped, current_mapped)
    score = -mean_distance * 0.115

    previous_lead = max(previous, key=lambda item: (item.is_solo, item.is_lead, item.source.pitch))
    current_lead = max(current, key=lambda item: (item.is_solo, item.is_lead, item.source.pitch))
    source_interval = current_lead.source.pitch - previous_lead.source.pitch
    mapped_interval = current_lead.mapped_pitch - previous_lead.mapped_pitch
    score -= abs(mapped_interval - source_interval) * 0.18

    # Reusing a physical key too quickly is expensive. Do not punish a protected
    # melody nearly as much; rhythmic identity beats accompaniment smoothness.
    fast_retrigger = settings.key_retrigger_gap_ms + 45.0
    if gap_ms < fast_retrigger:
        previous_keys = {(item.modifier, item.base_pitch) for item in previous}
        for item in current:
            if (item.modifier, item.base_pitch) in previous_keys:
                score -= 0.35 if (item.is_lead or item.is_solo) else 1.15

    # Bank movement is already optimised by the mapping stage; this small cost
    # merely stops equivalent voicings from needlessly preferring a transition.
    previous_bank = previous[0].modifier
    current_bank = current[0].modifier
    score -= abs(current_bank - previous_bank) * 0.22
    return score, mean_distance


def _voicing_options(
    group: list[_MappedCandidate],
    limit: int,
    *,
    gap_ms: float,
) -> list[tuple[tuple[_MappedCandidate, ...], float]]:
    unique = _dedupe_mapped_candidates(group)
    if not unique or limit <= 0:
        return []
    if len(unique) == 1:
        option = tuple(unique)
        return [
            (
                option,
                _voicing_local_score(
                    option,
                    unique,
                    limit=limit,
                    gap_ms=gap_ms,
                    harmonic_bonuses={},
                ),
            )
        ]

    low_pitch = min(item.source.pitch for item in unique)
    high_pitch = max(item.source.pitch for item in unique)
    harmonic_bonuses = _harmonic_role_bonuses(unique)
    ranked = sorted(
        unique,
        key=lambda item: (
            _candidate_importance(item, low_pitch=low_pitch, high_pitch=high_pitch)
            + harmonic_bonuses.get(item, 0.0)
        ),
        reverse=True,
    )
    # Bound combinatorics for enormous orchestral attacks while forcing the
    # structural outer/lead candidates into the pool.
    required = [
        item for item in unique
        if item.is_lead or item.is_solo or item.source.pitch in {low_pitch, high_pitch}
    ]
    pool: list[_MappedCandidate] = []
    for item in required + ranked:
        if item not in pool:
            pool.append(item)
        if len(pool) >= 8:
            break

    options: list[tuple[tuple[_MappedCandidate, ...], float]] = []
    maximum = min(limit, len(pool))
    for size in range(1, maximum + 1):
        for combo in combinations(pool, size):
            ordered = tuple(sorted(combo, key=lambda item: (item.base_pitch, item.source.pitch)))
            options.append(
                (
                    ordered,
                    _voicing_local_score(
                        ordered,
                        unique,
                        limit=limit,
                        gap_ms=gap_ms,
                        harmonic_bonuses=harmonic_bonuses,
                    ),
                )
            )
    options.sort(key=lambda entry: entry[1], reverse=True)
    return options[:18]


def _direct_performance_voicings(
    mapped_groups: list[list[_MappedCandidate]],
    settings: AppSettings,
) -> tuple[list[_MappedCandidate], _PerformanceDirectorStats]:
    """Choose a playable voicing path across the whole score.

    The old planner picked each chord independently. This Viterbi-style pass
    keeps the traced lead, retains useful bass/harmony, simplifies dense bursts,
    and prefers smooth physical voice leading between consecutive attacks.
    Back-pointers keep memory linear even for very long MIDI files.
    """

    if not mapped_groups:
        return [], _PerformanceDirectorStats()

    group_starts = [
        min((item.source.start_ms for item in group), default=0.0)
        for group in mapped_groups
    ]
    option_sets: list[list[tuple[tuple[_MappedCandidate, ...], float]]] = []
    for index, group in enumerate(mapped_groups):
        gap_ms = 1000.0 if index == 0 else max(0.0, group_starts[index] - group_starts[index - 1])
        options = _voicing_options(group, settings.max_polyphony, gap_ms=gap_ms)
        option_sets.append(options or [((), -30.0)])

    scores = [local for _option, local in option_sets[0]]
    parent_rows: list[list[int]] = []
    for index in range(1, len(option_sets)):
        gap_ms = max(0.0, group_starts[index] - group_starts[index - 1])
        previous_options = option_sets[index - 1]
        current_options = option_sets[index]
        current_scores: list[float] = []
        current_parents: list[int] = []
        for option, local in current_options:
            best_score = float("-inf")
            best_parent = 0
            for previous_index, (previous, _previous_local) in enumerate(previous_options):
                transition, _distance = _voicing_transition_score(
                    previous, option, gap_ms=gap_ms, settings=settings
                )
                candidate_score = scores[previous_index] + local + transition
                if candidate_score > best_score:
                    best_score = candidate_score
                    best_parent = previous_index
            current_scores.append(best_score)
            current_parents.append(best_parent)
        scores = current_scores
        parent_rows.append(current_parents)

    option_index = max(range(len(scores)), key=scores.__getitem__)
    chosen_indices = [option_index]
    for row in reversed(parent_rows):
        option_index = row[option_index]
        chosen_indices.append(option_index)
    chosen_indices.reverse()
    path = [
        option_sets[index][chosen_indices[index]][0]
        for index in range(len(option_sets))
    ]

    chosen = [item for option in path for item in option]
    dense_simplified = 0
    lead_protected = 0
    outer_protected = 0
    distance_total = 0.0
    transition_count = 0
    previous: tuple[_MappedCandidate, ...] = ()
    for index, (source_group, option) in enumerate(zip(mapped_groups, path, strict=True)):
        unique = _dedupe_mapped_candidates(source_group)
        if len(option) < min(len(unique), settings.max_polyphony):
            dense_simplified += 1
        if any(item.is_lead or item.is_solo for item in unique):
            lead_protected += int(any(item.is_lead or item.is_solo for item in option))
        if unique and option:
            low = min(item.source.pitch for item in unique)
            high = max(item.source.pitch for item in unique)
            outer_protected += int(any(item.source.pitch == low for item in option))
            outer_protected += int(any(item.source.pitch == high for item in option))
        if index:
            gap_ms = max(0.0, group_starts[index] - group_starts[index - 1])
            if previous and option and gap_ms < 700.0:
                _score, distance = _voicing_transition_score(
                    previous, option, gap_ms=gap_ms, settings=settings
                )
                distance_total += distance
                transition_count += 1
        previous = option

    average_distance = distance_total / transition_count if transition_count else 0.0
    return chosen, _PerformanceDirectorStats(
        groups=len(mapped_groups),
        dense_groups_simplified=dense_simplified,
        lead_attacks_protected=lead_protected,
        source_outer_voices_protected=outer_protected,
        continuity_transitions=transition_count,
        average_voice_leading_semitones=average_distance,
    )


def _roll_group(
    group: list[_MappedCandidate], instrument_key: str = "guitar"
) -> list[_MappedCandidate]:
    """Order a short physical chord roll without moving the musical attack.

    A traced lead/solo is always pressed first so melody timing remains exact.
    Pure accompaniment on guitar/banjo uses a low-to-high strum, which sounds
    more intentional than the old top-note-first fallback.
    """

    if len(group) <= 1:
        return list(group)
    protected = [item for item in group if item.is_solo or item.is_lead]
    if not protected:
        if instrument_key in {"guitar", "banjo"}:
            return sorted(
                group,
                key=lambda item: (item.source.pitch, -item.source.velocity, -item.source.duration_ms),
            )
        return sorted(group, key=lambda item: (item.mapped_pitch, item.source.pitch))

    remaining = list(group)
    lead = max(
        protected,
        key=lambda item: (
            item.is_solo,
            item.is_lead,
            item.source.pitch,
            item.source.velocity,
            item.source.duration_ms,
        ),
    )
    ordered = [lead]
    remaining.remove(lead)
    if remaining:
        bass = min(
            remaining,
            key=lambda item: (item.source.pitch, -item.source.velocity, -item.source.duration_ms),
        )
        ordered.append(bass)
        remaining.remove(bass)
    ordered.extend(
        sorted(
            remaining,
            key=lambda item: (item.source.velocity, item.source.duration_ms, item.source.pitch),
            reverse=True,
        )
    )
    return ordered


def _map_group(
    group: list[MidiNote],
    group_index: int,
    settings: AppSettings,
    smart_modifier: int | None = None,
    solo_track_index: int | None = None,
    lead_notes: set[MidiNote] | None = None,
) -> list[_MappedCandidate]:
    lead_notes = lead_notes or set()
    pairs: list[tuple[MidiNote, MidiNote]] = []
    for original in group:
        if settings.transpose == 0 and 0 <= original.pitch <= 127:
            transformed = original
        else:
            transformed = MidiNote(
                track_index=original.track_index,
                channel=original.channel,
                pitch=max(0, min(127, original.pitch + settings.transpose)),
                velocity=original.velocity,
                start_ms=original.start_ms,
                end_ms=original.end_ms,
                program=original.program,
            )
        pairs.append((original, transformed))

    mapped: list[_MappedCandidate] = []
    if settings.mapping_mode == "strict_auto":
        for original, note in pairs:
            if 60 <= note.pitch <= 72:
                mapped.append(
                    _MappedCandidate(
                        note, note.pitch, note.pitch, 0, group_index, settings.transpose,
                        original.track_index == solo_track_index, original in lead_notes,
                    )
                )
        return mapped

    if settings.mapping_mode == "fold_smart":
        sorted_pairs = sorted(pairs, key=lambda pair: (pair[1].pitch, -pair[1].velocity))
        c_pitches = sorted({note.pitch for _original, note in pairs if note.pitch % 12 == 0})
        used_pitches: set[int] = set()
        for original, note in sorted_pairs:
            target = _fold_to_window(note.pitch, 60, 72)
            if len(c_pitches) > 1 and note.pitch % 12 == 0:
                # Allocate boundary Cs by source register, not first available
                # key: C5/C6 must not become C5/C4 and invert the chord.
                target = 60 if note.pitch == c_pitches[0] else 72
            if target in used_pitches and note.pitch % 12 == 0:
                has_distinct_c = any(n.pitch % 12 == 0 and n.pitch != note.pitch for _o, n in pairs)
                if has_distinct_c:
                    if target == 60 and 72 not in used_pitches:
                        target = 72
                    elif target == 72 and 60 not in used_pitches:
                        target = 60
            used_pitches.add(target)
            mapped.append(
                _MappedCandidate(
                    note, target, target, 0, group_index, settings.transpose,
                    original.track_index == solo_track_index, original in lead_notes,
                )
            )
        return mapped

    # Smart three-octave mode. SCUM's octave modifier is global, so every onset
    # group is kept inside one octave window to avoid impossible cross-octave chords.
    transformed = [note for _original, note in pairs]
    if smart_modifier is None:
        anchor = max(transformed, key=lambda n: (n.velocity, n.pitch))
        anchor_pitch = max(48, min(84, anchor.pitch))
        modifier = -1 if anchor_pitch < 60 else (1 if anchor_pitch > 72 else 0)
    else:
        modifier = smart_modifier
    low = 60 + modifier * 12
    high = 72 + modifier * 12

    for original, note in pairs:
        target = _fold_to_window(note.pitch, low, high)
        base_pitch = max(60, min(72, target - modifier * 12))
        mapped.append(
            _MappedCandidate(
                note, target, base_pitch, modifier, group_index, settings.transpose,
                original.track_index == solo_track_index, original in lead_notes,
            )
        )
    return mapped


def _mapping_policy_weights(settings: AppSettings) -> tuple[float, float]:
    """Return register and state-change weights for the selected policy."""

    register_weight, switch_weight = {
        "balanced": (1.0, 1.0),
        "register": (1.35, 0.55),
        "rhythm": (0.85, 1.25),
        "stability": (0.70, 1.65),
    }[settings.fidelity_priority]
    switch_weight *= 0.5 + settings.mapping_stability / 100.0
    return register_weight, switch_weight






def _register_mapping_cost_harmonic(
    group: list[MidiNote],
    modifier: int,
    settings: AppSettings,
    lead_notes: set[MidiNote] | None = None,
) -> float:
    low = 60 + modifier * 12
    high = 72 + modifier * 12
    total_weight = 0.0
    total_cost = 0.0
    min_pitch = min((n.pitch for n in group), default=60)
    max_pitch = max((n.pitch for n in group), default=60)

    for note in group:
        pitch = max(0, min(127, note.pitch + settings.transpose))
        mapped = _fold_to_window(pitch, low, high)
        weight = 0.35 + note.velocity / 127.0
        # Priority to structural outer voices, with the traced lead receiving
        # the strongest register protection.
        if note.pitch == min_pitch or note.pitch == max_pitch:
            weight *= 1.8
        if lead_notes and note in lead_notes:
            weight *= 2.2
        total_weight += weight
        total_cost += weight * (abs(mapped - pitch) / 12.0)
    # Keep the harmonic planner centred on SCUM's base C4-C5 bank when two
    # registers have nearly equal pitch fit. Retain lower/upper banks when
    # their pitch fit is materially better. This is a preference, not a
    # blanket octave reduction for every song.
    total_cost += abs(modifier) * 0.22
    return total_cost / max(total_weight, 1e-9)


def _smart_register_sequence_harmonic(
    groups: list[list[MidiNote]],
    settings: AppSettings,
    lead_notes: set[MidiNote] | None = None,
) -> dict[int, int]:
    """Harmonic-aware register planner with rest discounting and distance-weighted transition costs."""

    if not groups:
        return {}
    states = (-1, 0, 1)
    register_weight, switch_weight = _mapping_policy_weights(settings)
    costs: list[dict[int, float]] = []
    parents: list[dict[int, int]] = []
    sounding_until = 0.0

    for index, group in enumerate(groups):
        group_start = min(note.start_ms for note in group)
        rest_ms = max(0.0, group_start - sounding_until)
        sounding_until = max(sounding_until, max(note.end_ms for note in group))
        current_costs: dict[int, float] = {}
        current_parents: dict[int, int] = {}
        for state in states:
            local = _register_mapping_cost_harmonic(
                group, state, settings, lead_notes
            ) * register_weight
            if index == 0:
                current_costs[state] = local
                current_parents[state] = 0
                continue

            previous_start = min(note.start_ms for note in groups[index - 1])
            gap_ms = max(0.0, group_start - previous_start)

            best_cost = float("inf")
            best_parent = 0
            for previous_state in states:
                step_dist = abs(state - previous_state)
                switch_cost = 0.0
                if step_dist > 0:
                    base_step_cost = 0.65 if step_dist == 1 else 1.45
                    if rest_ms >= 250.0:
                        switch_cost = base_step_cost * 0.25
                    elif gap_ms < 120.0:
                        switch_cost = base_step_cost * (1.0 + (120.0 - gap_ms) / 60.0)
                    else:
                        switch_cost = base_step_cost
                candidate = costs[-1][previous_state] + local + switch_cost * switch_weight
                if candidate < best_cost:
                    best_cost = candidate
                    best_parent = previous_state
            current_costs[state] = best_cost
            current_parents[state] = best_parent
        costs[:] = [current_costs]
        parents.append(current_parents)

    final_state = min(costs[-1], key=costs[-1].get)
    sequence = [final_state]
    for index in range(len(groups) - 1, 0, -1):
        sequence.append(parents[index][sequence[-1]])
    sequence.reverse()
    return {index: state for index, state in enumerate(sequence)}


def _melody_register_sequence_contour(groups: list[list[MidiNote]], settings: AppSettings) -> dict[int, int]:
    """Minimise pitch loss, then interval distortion, then bank movement.

    Lexicographic costs prevent accumulated switch penalties from folding an
    otherwise playable melody attack. Interval costs resolve equivalent fits
    for out-of-range material without inventing pitches or moving attacks.
    """

    if not groups:
        return {}
    states = (-1, 0, 1)
    _, policy_switch_weight = _mapping_policy_weights(settings)
    base_switch_cost = 0.18 * policy_switch_weight
    costs: list[dict[int, tuple[float, float, float]]] = []
    parents: list[dict[int, int]] = []

    melody_pitches = [
        max(0, min(127, max(n.pitch for n in group) + settings.transpose))
        for group in groups
    ]

    for index, group in enumerate(groups):
        group_start = min(note.start_ms for note in group)
        previous_start = (
            min(note.start_ms for note in groups[index - 1]) if index else group_start
        )
        gap_ms = max(0.0, group_start - previous_start)
        pitch = melody_pitches[index]

        step_cost_factor = 0.3 if gap_ms >= 240.0 else (1.5 if gap_ms < 100.0 else 1.0)
        switch_cost = base_switch_cost * step_cost_factor

        current_costs: dict[int, tuple[float, float, float]] = {}
        current_parents: dict[int, int] = {}

        for state in states:
            low, high = 60 + state * 12, 72 + state * 12
            local = sum(
                abs(_fold_to_window(p, low, high) - p) * (0.35 + n.velocity / 127.0)
                for n in group
                for p in [max(0, min(127, n.pitch + settings.transpose))]
            )
            boundary_cost = 0.0
            if settings.c_boundary_preference != "auto" and pitch % 12 == 0:
                boundary_cost = state * 0.001 if settings.c_boundary_preference == "lower" else -state * 0.001

            if index == 0:
                current_costs[state] = (local, 0.0, boundary_cost)
                current_parents[state] = 0
                continue

            transitions = {}
            for previous in states:
                old = costs[-1][previous]
                original_interval = pitch - melody_pitches[index - 1]
                mapped_interval = _fold_to_window(pitch, low, high) - _fold_to_window(
                    melody_pitches[index - 1], 60 + previous * 12, 72 + previous * 12,
                )
                # A genuine phrase break permits a new register relationship.
                distortion = abs(mapped_interval - original_interval) if gap_ms < 1000.0 else 0.0
                transitions[previous] = (
                    old[0] + local,
                    old[1] + distortion,
                    old[2] + switch_cost * abs(state - previous) + boundary_cost,
                )

            best_parent = min(
                states,
                key=lambda previous: (
                    transitions[previous],
                    previous != state,
                    abs(previous),
                ),
            )
            current_costs[state] = transitions[best_parent]
            current_parents[state] = best_parent
        costs[:] = [current_costs]
        parents.append(current_parents)

    final_state = min(states, key=lambda state: (costs[-1][state], abs(state)))
    sequence = [final_state]
    for index in range(len(groups) - 1, 0, -1):
        sequence.append(parents[index][sequence[-1]])
    sequence.reverse()
    return {index: state for index, state in enumerate(sequence)}



def _stabilize_short_modifier_excursions(
    groups: list[list[MidiNote]],
    sequence: dict[int, int],
    *,
    maximum_groups: int = 3,
    maximum_span_ms: float = 1200.0,
) -> tuple[dict[int, int], int, int]:
    """Fold brief Ctrl/Shift detours into the surrounding register.

    A one-to-three-onset excursion is changed only when it is enclosed by the
    same register on both sides and returns within 1.2 seconds. Longer runs and
    phrase-boundary changes remain untouched, so intentional bass passages are
    preserved while isolated source notes cannot cause a modifier blip.
    """

    if len(groups) < 3:
        return dict(sequence), 0, 0

    original = [sequence.get(index, 0) for index in range(len(groups))]
    states = list(original)
    while True:
        runs: list[tuple[int, int, int]] = []
        start = 0
        for index in range(1, len(states) + 1):
            if index == len(states) or states[index] != states[start]:
                runs.append((start, index, states[start]))
                start = index

        changed = False
        for run_index in range(1, len(runs) - 1):
            start, end, _state = runs[run_index]
            left_state = runs[run_index - 1][2]
            right_state = runs[run_index + 1][2]
            if left_state != right_state or end - start > maximum_groups:
                continue
            run_start = min(note.start_ms for note in groups[start])
            return_start = min(note.start_ms for note in groups[end])
            if return_start - run_start > maximum_span_ms:
                continue
            for group_index in range(start, end):
                states[group_index] = left_state
            changed = True
            break
        if not changed:
            break

    changed_groups = [index for index, state in enumerate(states) if state != original[index]]
    changed_notes = sum(len(groups[index]) for index in changed_groups)
    return {index: state for index, state in enumerate(states)}, len(changed_groups), changed_notes


def _enforce_bank_switch_budget(
    groups: list[list[MidiNote]],
    sequence: dict[int, int],
    maximum_taps_per_second: int,
) -> tuple[dict[int, int], int]:
    """Fold transitions that would exceed the opt-in rolling bank-tap budget."""

    if maximum_taps_per_second <= 0 or not groups:
        return dict(sequence), 0
    result = dict(sequence)
    recent_taps: list[float] = []
    previous_state = 0
    folded_groups = 0
    for index, group in enumerate(groups):
        start_ms = min(note.start_ms for note in group)
        recent_taps = [at_ms for at_ms in recent_taps if start_ms - at_ms < 1000.0]
        target_state = result.get(index, 0)
        required_taps = abs(target_state - previous_state)
        if required_taps and len(recent_taps) + required_taps > maximum_taps_per_second:
            result[index] = previous_state
            folded_groups += 1
            continue
        recent_taps.extend([start_ms] * required_taps)
        previous_state = target_state
    return result, folded_groups


def _replace_note(note: PlannedNote, *, start_ms: float | None = None, end_ms: float | None = None) -> PlannedNote:
    return PlannedNote(
        source_pitch=note.source_pitch,
        mapped_pitch=note.mapped_pitch,
        base_pitch=note.base_pitch,
        modifier=note.modifier,
        key=note.key,
        velocity=note.velocity,
        start_ms=note.start_ms if start_ms is None else start_ms,
        end_ms=note.end_ms if end_ms is None else end_ms,
        score_group=note.score_group,
        voice_index=note.voice_index,
        mapping_reason=note.mapping_reason,
    )


def _schedule_modifier_timing(
    planned: list[PlannedNote],
    planned_group_ids: list[int],
    sorted_group_ids: list[int],
    group_modifier: dict[int, int],
    settings: AppSettings,
    *,
    minimum_hold_ms: float,
) -> tuple[list[PlannedNote], dict[int, float], int, float]:
    """Apply octave-bank and same-key timing constraints in one forward pass."""

    mutable = list(planned)
    indices_by_group: dict[int, list[int]] = defaultdict(list)
    for index, gid in enumerate(planned_group_ids):
        indices_by_group[gid].append(index)

    previous_group_latest_start: float | None = None
    previous_group_modifier = 0
    minimum_key_end: dict[str, float] = {}
    group_starts: dict[int, float] = {}
    delayed_groups = 0
    total_delay_ms = 0.0
    audible_floor_ms = max(10.0, minimum_hold_ms)

    for gid in sorted_group_ids:
        indices = indices_by_group[gid]
        nominal_start = min(mutable[index].start_ms for index in indices)
        offsets = {index: mutable[index].start_ms - nominal_start for index in indices}
        required_start = nominal_start
        if previous_group_latest_start is not None:
            required_start = max(required_start, previous_group_latest_start + 1.0)
            octave_taps = abs(group_modifier[gid] - previous_group_modifier)
            if octave_taps:
                required_start = max(
                    required_start,
                    previous_group_latest_start
                    + audible_floor_ms
                    + settings.modifier_release_ms
                    + octave_taps * (OCTAVE_BANK_TAP_HOLD_MS + settings.modifier_settle_ms),
                )
        for index in indices:
            previous_minimum_end = minimum_key_end.get(mutable[index].key)
            if previous_minimum_end is not None:
                required_start = max(
                    required_start,
                    previous_minimum_end + settings.key_retrigger_gap_ms - offsets[index],
                )

        delay_ms = required_start - nominal_start
        if delay_ms > 0.001:
            delayed_groups += 1
            total_delay_ms += delay_ms
            for index in indices:
                note = mutable[index]
                mutable[index] = _replace_note(
                    note,
                    start_ms=note.start_ms + delay_ms,
                    end_ms=note.end_ms + delay_ms,
                )

        current_starts = [mutable[index].start_ms for index in indices]
        group_starts[gid] = min(current_starts)
        previous_group_latest_start = max(current_starts)
        previous_group_modifier = group_modifier[gid]
        for index in indices:
            note = mutable[index]
            minimum_key_end[note.key] = note.start_ms + minimum_hold_ms

    return mutable, group_starts, delayed_groups, total_delay_ms


def _enforce_physical_retrigger_gap(
    planned: list[PlannedNote],
    gap_ms: int,
    minimum_hold_ms: float,
) -> tuple[list[PlannedNote], int, float, int, float]:
    """Guarantee a key-up retrigger window while preferring rhythm over sustain.

    ``minimum_hold_ms`` is the physical/audible floor, not the normal musical
    hold target. Automatic mode therefore shortens an earlier sustain before it
    delays the next attack. Only attacks that physically cannot fit are moved.
    """

    if gap_ms <= 0 or len(planned) < 2:
        return planned, 0, 0.0, 0, 0.0
    mutable = list(planned)
    delayed_notes = 0
    total_delay_ms = 0.0
    shortened_notes = 0
    shortened_ms = 0.0
    by_key: dict[str, list[int]] = defaultdict(list)
    for index, note in enumerate(mutable):
        by_key[note.key].append(index)

    for indices in by_key.values():
        indices.sort(key=lambda index: mutable[index].start_ms)
        for left, right in zip(indices, indices[1:], strict=False):
            previous = mutable[left]
            following = mutable[right]
            latest_previous_end = following.start_ms - gap_ms
            if previous.end_ms <= latest_previous_end:
                continue

            minimum_previous_end = previous.start_ms + max(10.0, minimum_hold_ms)
            if latest_previous_end < minimum_previous_end:
                shift = minimum_previous_end + gap_ms - following.start_ms
                following = _replace_note(
                    following,
                    start_ms=following.start_ms + shift,
                    end_ms=following.end_ms + shift,
                )
                mutable[right] = following
                delayed_notes += 1
                total_delay_ms += shift
                latest_previous_end = following.start_ms - gap_ms

            new_end = max(minimum_previous_end, min(previous.end_ms, latest_previous_end))
            if previous.end_ms - new_end > 0.001:
                shortened_notes += 1
                shortened_ms += previous.end_ms - new_end
            mutable[left] = _replace_note(previous, end_ms=new_end)
    return mutable, delayed_notes, total_delay_ms, shortened_notes, shortened_ms


def _bank_transition_release_at(
    planned: list[PlannedNote],
    group_start_ms: float,
    transition_span_ms: float,
    *,
    extra_settle_cap_ms: float = 60.0,
) -> float:
    """Use an existing rest to prepare an octave-bank change a little early.

    When the previous notes are already silent, finishing Ctrl/Shift before the
    mathematically latest possible instant gives SCUM extra time to settle with
    no musical cost.  If anything is still sounding, keep the original guard
    point so we never shorten a note merely to gain this margin.
    """

    normal = max(0.0, group_start_ms - transition_span_ms)
    previous_ends = [
        note.end_ms
        for note in planned
        if note.start_ms < group_start_ms - 0.25
    ]
    if not previous_ends:
        return max(0.0, normal - extra_settle_cap_ms)
    latest_previous_end = max(previous_ends)
    if latest_previous_end > normal + 0.001:
        return normal
    return max(0.0, latest_previous_end, normal - extra_settle_cap_ms)


def _clip_for_bank_transitions(
    planned: list[PlannedNote],
    group_ids: list[int],
    sorted_group_ids: list[int],
    group_modifiers: dict[int, int],
    settings: AppSettings,
) -> tuple[list[PlannedNote], int, float]:
    """Reflect the physical all-keys-up guard used before an octave-bank tap."""

    if not planned or not sorted_group_ids:
        return planned, 0, 0.0
    mutable = list(planned)
    group_starts = _group_starts(mutable, group_ids)
    current_bank = 0
    clipped = 0
    clipped_ms = 0.0
    for group_id in sorted_group_ids:
        target_bank = group_modifiers[group_id]
        if target_bank == current_bank:
            continue
        tap_count = abs(target_bank - current_bank)
        transition_span = settings.modifier_release_ms + tap_count * (
            OCTAVE_BANK_TAP_HOLD_MS + settings.modifier_settle_ms
        )
        release_at = _bank_transition_release_at(
            mutable, group_starts[group_id], transition_span
        )
        for index, note in enumerate(mutable):
            if note.start_ms < release_at < note.end_ms:
                clipped += 1
                clipped_ms += note.end_ms - release_at
                mutable[index] = _replace_note(note, end_ms=release_at)
        current_bank = target_bank
    return mutable, clipped, clipped_ms


def _event_sort_key(event: KeyEvent) -> tuple[float, int, str]:
    priority = 0 if event.action == "up" else 1
    return (event.at_ms, priority, event.key)


def _canonicalize_events(events: list[KeyEvent]) -> list[KeyEvent]:
    """Remove duplicate ups/downs after safety guards are merged into the timeline."""

    pressed: set[str] = set()
    result: list[KeyEvent] = []
    for event in sorted(events, key=_event_sort_key):
        if event.action == "down":
            if event.key in pressed:
                continue
            pressed.add(event.key)
            result.append(event)
        else:
            if event.key not in pressed:
                continue
            pressed.remove(event.key)
            result.append(event)
    return result


@dataclass(frozen=True, slots=True)
class _PlannedTiming:
    notes: list[PlannedNote]
    group_ids: list[int]
    sorted_group_ids: list[int]
    group_modifiers: dict[int, int]
    group_starts: dict[int, float]
    grouped_candidates: dict[int, list[_MappedCandidate]]
    transition_delays: int
    transition_delay_ms: float
    retrigger_delays: int
    retrigger_delay_ms: float
    rhythm_shortened_notes: int
    rhythm_shortening_ms: float
    bank_guard_clipped_notes: int
    bank_guard_clipped_ms: float
    physical_min_hold_ms: float
    lead_articulation_notes: int
    lead_articulation_ms: float
    sustain_capped_notes: int
    sustain_reduction_ms: float
    effective_min_hold_ms: float
    effective_max_hold_ms: float
    fluid_phrasing: FluidPhrasingStats


@dataclass(frozen=True, slots=True)
class _OctaveEventStats:
    modifier_switches: int
    bank_taps: int
    shift_taps: int
    control_taps: int
    early_preparations: int = 0
    extra_settle_ms: float = 0.0


def _group_starts(notes: list[PlannedNote], group_ids: list[int]) -> dict[int, float]:
    starts: dict[int, float] = {}
    for note, group_id in zip(notes, group_ids, strict=True):
        starts[group_id] = min(starts.get(group_id, note.start_ms), note.start_ms)
    return starts


def _mapping_reason(item: _MappedCandidate) -> str:
    original_pitch = item.source.pitch - item.transpose_applied
    pitch_delta = item.mapped_pitch - item.source.pitch
    if pitch_delta:
        direction = "up" if pitch_delta > 0 else "down"
        mapping = f"folded {direction} {abs(pitch_delta) // 12} octave(s)"
    else:
        mapping = "exact register"
    bank = {-1: "lower", 0: "base", 1: "upper"}[item.modifier]
    role_prefix = (
        "solo lead, " if item.is_solo else "traced lead, " if item.is_lead else ""
    )
    if item.transpose_applied:
        return (
            f"{midi_note_name(original_pitch)}: {role_prefix}transposed "
            f"{item.transpose_applied:+d} semitones, {mapping}, {bank} SCUM bank"
        )
    return f"{midi_note_name(original_pitch)}: {role_prefix}{mapping}, {bank} SCUM bank"


def _build_planned_timing(
    chosen: list[_MappedCandidate],
    settings: AppSettings,
    profile: KeyBindingProfile,
    *,
    uses_bank_mapping: bool,
) -> _PlannedTiming:
    """Turn mapped candidates into timed notes without emitting physical key events."""

    grouped_candidates: dict[int, list[_MappedCandidate]] = defaultdict(list)
    for item in chosen:
        grouped_candidates[item.group_index].append(item)
    sorted_group_ids = sorted(
        grouped_candidates,
        key=lambda group_id: min(item.source.start_ms for item in grouped_candidates[group_id]),
    )
    notes: list[PlannedNote] = []
    phrasing_sources: list[MidiNote] = []
    phrasing_leads: set[int] = set()
    group_ids: list[int] = []
    group_modifiers: dict[int, int] = {}
    instrument = resolve_instrument_profile(settings.target_instrument)
    configured_min_hold_ms = settings.min_hold_ms / settings.speed
    configured_max_hold_ms = settings.max_hold_ms / settings.speed
    effective_max_hold_ms = min(configured_max_hold_ms, instrument.max_sustain_ms)
    effective_min_hold_ms = min(configured_min_hold_ms, effective_max_hold_ms)
    if settings.performance_preset == "optimal":
        base_floor = {"guitar": 34.0, "harmonica": 40.0, "banjo": 28.0}.get(instrument.key, 34.0)
        physical_min_hold_ms = min(
            effective_min_hold_ms,
            min(52.0, max(base_floor, effective_min_hold_ms * 0.48)),
        )
    elif settings.performance_preset == "scum_safe":
        physical_min_hold_ms = min(
            effective_min_hold_ms, max(50.0, effective_min_hold_ms * 0.72)
        )
    else:
        physical_min_hold_ms = effective_min_hold_ms
    lead_group_starts: list[tuple[int, float]] = []
    for group_id in sorted_group_ids:
        group = grouped_candidates[group_id]
        if any(item.is_lead or item.is_solo for item in group):
            lead_group_starts.append(
                (group_id, min(item.source.start_ms for item in group))
            )
    next_lead_start: dict[int, float] = {
        group_id: next_start
        for (group_id, _start), (_next_group, next_start) in zip(
            lead_group_starts, lead_group_starts[1:], strict=False
        )
    }
    sustain_capped_notes = 0
    sustain_reduction_ms = 0.0
    lead_articulation_notes = 0
    lead_articulation_ms = 0.0
    for group_id in sorted_group_ids:
        group = _roll_group(grouped_candidates[group_id], instrument.key)
        group_start = min(item.source.start_ms for item in group)
        group_modifiers[group_id] = group[0].modifier if group else 0
        solo_group = any(item.is_solo for item in group)
        for index, item in enumerate(group):
            stagger = (
                index * settings.chord_spread_ms
                if len(group) > 1 and not solo_group
                else 0.0
            )
            start = max(0.0, (group_start + stagger) / settings.speed)
            velocity_delta = (item.source.velocity - 64.0) / 63.0
            expression = 1.0 + settings.velocity_expression * 0.22 * velocity_delta
            natural_hold_ms = item.source.duration_ms * settings.hold_ratio * expression / settings.speed
            configured_hold_ms = max(
                configured_min_hold_ms,
                min(configured_max_hold_ms, natural_hold_ms),
            )
            hold_ms = min(configured_hold_ms, effective_max_hold_ms)
            if configured_hold_ms - hold_ms > 0.001:
                sustain_capped_notes += 1
                sustain_reduction_ms += configured_hold_ms - hold_ms
            if (
                settings.performance_preset == "optimal"
                and (item.is_lead or item.is_solo)
                and group_id in next_lead_start
            ):
                next_attack_ms = next_lead_start[group_id] / settings.speed
                lead_ceiling_ms = max(
                    physical_min_hold_ms,
                    next_attack_ms - start - min(10.0, settings.key_retrigger_gap_ms * 0.35),
                )
                if hold_ms - lead_ceiling_ms > 0.001:
                    lead_articulation_notes += 1
                    lead_articulation_ms += hold_ms - lead_ceiling_ms
                    hold_ms = lead_ceiling_ms
            notes.append(
                PlannedNote(
                    source_pitch=item.source.pitch - item.transpose_applied,
                    mapped_pitch=item.mapped_pitch,
                    base_pitch=item.base_pitch,
                    modifier=item.modifier,
                    key=profile.key_for_base_pitch(item.base_pitch),
                    velocity=item.source.velocity,
                    start_ms=start,
                    end_ms=start + hold_ms,
                    score_group=group_id + 1,
                    voice_index=index + 1,
                    mapping_reason=_mapping_reason(item),
                )
            )
            group_ids.append(group_id)
            if settings.fluid_phrasing:
                phrasing_sources.append(item.source)
                if item.is_lead or item.is_solo:
                    phrasing_leads.add(len(notes) - 1)

    fluid_stats = FluidPhrasingStats()
    if settings.fluid_phrasing:
        notes, fluid_stats = apply_fluid_phrasing(
            notes, phrasing_sources, phrasing_leads,
            strength=settings.fluid_phrasing,
            speed=settings.speed,
            minimum_hold_ms=physical_min_hold_ms,
            maximum_hold_ms=effective_max_hold_ms,
            key_gap_ms=settings.key_retrigger_gap_ms,
            instrument=instrument.key,
            max_polyphony=settings.max_polyphony,
        )
    group_starts = _group_starts(notes, group_ids)
    transition_delays = 0
    transition_delay_ms = 0.0
    if uses_bank_mapping:
        notes, group_starts, transition_delays, transition_delay_ms = _schedule_modifier_timing(
            notes,
            group_ids,
            sorted_group_ids,
            group_modifiers,
            settings,
            minimum_hold_ms=physical_min_hold_ms,
        )

    first_bank = group_modifiers[sorted_group_ids[0]] if sorted_group_ids else 0
    initial_taps = abs(first_bank)
    pre_roll_ms = (
        settings.modifier_release_ms
        + initial_taps * (OCTAVE_BANK_TAP_HOLD_MS + settings.modifier_settle_ms)
        if initial_taps
        else 0
    )
    if pre_roll_ms:
        notes = [
            _replace_note(note, start_ms=note.start_ms + pre_roll_ms, end_ms=note.end_ms + pre_roll_ms)
            for note in notes
        ]

    (
        notes,
        retrigger_delays,
        retrigger_delay_ms,
        rhythm_shortened_notes,
        rhythm_shortening_ms,
    ) = _enforce_physical_retrigger_gap(
        notes, settings.key_retrigger_gap_ms, physical_min_hold_ms
    )
    bank_guard_clipped_notes = 0
    bank_guard_clipped_ms = 0.0
    if uses_bank_mapping:
        notes, bank_guard_clipped_notes, bank_guard_clipped_ms = _clip_for_bank_transitions(
            notes, group_ids, sorted_group_ids, group_modifiers, settings
        )
    return _PlannedTiming(
        notes=notes,
        group_ids=group_ids,
        sorted_group_ids=sorted_group_ids,
        group_modifiers=group_modifiers,
        group_starts=_group_starts(notes, group_ids),
        grouped_candidates=grouped_candidates,
        transition_delays=transition_delays,
        transition_delay_ms=transition_delay_ms,
        retrigger_delays=retrigger_delays,
        retrigger_delay_ms=retrigger_delay_ms,
        rhythm_shortened_notes=rhythm_shortened_notes,
        rhythm_shortening_ms=rhythm_shortening_ms,
        bank_guard_clipped_notes=bank_guard_clipped_notes,
        bank_guard_clipped_ms=bank_guard_clipped_ms,
        physical_min_hold_ms=physical_min_hold_ms,
        lead_articulation_notes=lead_articulation_notes,
        lead_articulation_ms=lead_articulation_ms,
        sustain_capped_notes=sustain_capped_notes,
        sustain_reduction_ms=sustain_reduction_ms,
        effective_min_hold_ms=effective_min_hold_ms,
        effective_max_hold_ms=effective_max_hold_ms,
        fluid_phrasing=fluid_stats,
    )


def _build_key_events(
    timing: _PlannedTiming,
    settings: AppSettings,
    profile: KeyBindingProfile,
) -> tuple[list[KeyEvent], _OctaveEventStats]:
    """Emit note events and standalone persistent-octave-bank taps."""

    events = [
        event
        for note in timing.notes
        for event in (
            KeyEvent(note.start_ms, "down", note.key, "note start"),
            KeyEvent(note.end_ms, "up", note.key, "note end"),
        )
    ]
    current_bank = 0
    modifier_switches = bank_taps = shift_taps = control_taps = 0
    early_preparations = 0
    extra_settle_ms = 0.0
    note_keys = sorted(set(profile.base_notes))
    for group_id in timing.sorted_group_ids:
        target_bank = timing.group_modifiers[group_id]
        if target_bank == current_bank:
            continue
        bank_delta = target_bank - current_bank
        tap_count = abs(bank_delta)
        tap_key = profile.octave_up if bank_delta > 0 else profile.octave_down
        transition_span = settings.modifier_release_ms + tap_count * (
            OCTAVE_BANK_TAP_HOLD_MS + settings.modifier_settle_ms
        )
        normal_release_at = max(0.0, timing.group_starts[group_id] - transition_span)
        release_at = _bank_transition_release_at(
            timing.notes, timing.group_starts[group_id], transition_span
        )
        if normal_release_at - release_at > 0.001:
            early_preparations += 1
            extra_settle_ms += normal_release_at - release_at
        modifier_switches += 1
        bank_taps += tap_count
        shift_taps += tap_count if bank_delta > 0 else 0
        control_taps += tap_count if bank_delta < 0 else 0
        events.extend(KeyEvent(release_at, "up", key, "octave bank release guard") for key in note_keys)
        tap_at = release_at + settings.modifier_release_ms
        direction = "up" if bank_delta > 0 else "down"
        for _ in range(tap_count):
            events.append(KeyEvent(tap_at, "down", tap_key, f"octave bank {direction} tap"))
            events.append(
                KeyEvent(
                    tap_at + OCTAVE_BANK_TAP_HOLD_MS,
                    "up",
                    tap_key,
                    f"octave bank {direction} tap release",
                )
            )
            tap_at += OCTAVE_BANK_TAP_HOLD_MS + settings.modifier_settle_ms
        current_bank = target_bank

    if settings.restore_base_bank and current_bank:
        release_at = max((note.end_ms for note in timing.notes), default=0.0)
        events.extend(KeyEvent(release_at, "up", key, "final bank restoration guard") for key in note_keys)
        tap_at = release_at + settings.modifier_release_ms
        tap_count = abs(current_bank)
        tap_key = profile.octave_down if current_bank > 0 else profile.octave_up
        direction = "down" if current_bank > 0 else "up"
        for _ in range(tap_count):
            events.append(KeyEvent(tap_at, "down", tap_key, f"restore base bank {direction} tap"))
            events.append(
                KeyEvent(
                    tap_at + OCTAVE_BANK_TAP_HOLD_MS,
                    "up",
                    tap_key,
                    f"restore base bank {direction} tap release",
                )
            )
            tap_at += OCTAVE_BANK_TAP_HOLD_MS + settings.modifier_settle_ms
        modifier_switches += 1
        bank_taps += tap_count
        shift_taps += tap_count if current_bank < 0 else 0
        control_taps += tap_count if current_bank > 0 else 0

    return _canonicalize_events(events), _OctaveEventStats(
        modifier_switches,
        bank_taps,
        shift_taps,
        control_taps,
        early_preparations,
        extra_settle_ms,
    )


def _solo_segment_for_group(
    group: list[MidiNote],
    segments: tuple[SoloSegment, ...],
) -> tuple[int, SoloSegment] | None:
    active = [
        (segment_index, segment)
        for segment_index, segment in enumerate(segments)
        if any(
            segment.start_ms - 1.0 <= note.start_ms <= segment.end_ms + 1.0
            for note in group
        )
    ]
    if not active:
        return None
    owner = max(
        active,
        key=lambda match: (match[1].start_ms, match[1].confidence, -match[0]),
    )
    if not any(note.track_index == owner[1].track_index for note in group):
        return None
    return owner


def build_playback_plan(
    notes: Iterable[MidiNote],
    settings: AppSettings,
    profile: KeyBindingProfile,
    *,
    prepared_source: bool = False,
    track_names: dict[int, str] | None = None,
) -> PlaybackPlan:
    settings = replace(settings)
    settings.normalize()
    original_notes = sorted(notes, key=lambda n: (n.start_ms, n.pitch, n.end_ms))
    score_analysis: NoteAnalysis | None = None
    if settings.performance_preset == "optimal":
        settings, score_analysis = optimal_settings_for_notes(
            original_notes,
            settings,
            prepared_source=prepared_source,
            track_names=track_names,
        )
    arrangement = arrange_notes(
        original_notes,
        settings,
        prepared_source=prepared_source,
        track_names=track_names,
    )
    source_notes = list(arrangement.notes)
    warnings: list[str] = list(arrangement.warnings)
    instrument = resolve_instrument_profile(settings.target_instrument)
    if score_analysis and score_analysis.note_count:
        warnings.insert(
            0,
            f"Automatic identified a {score_analysis.description} and selected "
            f"{settings.arrangement_mode} arrangement, {settings.mapping_mode} mapping, and "
            f"{settings.max_polyphony}-note polyphony.",
        )
    source_track_count = len({note.track_index for note in original_notes})
    if settings.arrangement_mode == "faithful" and source_track_count > 1:
        warnings.append(
            f"Faithful mode is keeping all notes from {source_track_count} selected tracks. "
            "Use Automatic or Lead melody only when accompaniment notes interrupt the lead line."
        )
    if settings.min_source_note_ms < 35:
        warnings.append(
            "The source-note filter is below 35 ms, so tiny source-note blips can reach playback."
        )
    if settings.min_hold_ms < 45:
        warnings.append(
            "The minimum played-note length is below 45 ms; very short guitar notes may sound like clicks."
        )
    if not source_notes:
        effective_max_hold_ms = min(
            settings.max_hold_ms / settings.speed,
            instrument.max_sustain_ms,
        )
        effective_min_hold_ms = min(
            settings.min_hold_ms / settings.speed,
            effective_max_hold_ms,
        )
        return PlaybackPlan(
            [],
            [],
            arrangement.source_notes,
            0,
            arrangement.source_notes,
            0.0,
            warnings or ["No notes were selected."],
            {
                "arrangement_mode": settings.arrangement_mode,
                "chord_recognition_mode": settings.chord_recognition_mode,
                "performance_preset": settings.performance_preset,
                "target_instrument": instrument.key,
                "target_instrument_label": instrument.label,
                "instrument_max_sustain_ms": instrument.max_sustain_ms,
                "instrument_sustain_capped_notes": 0,
                "instrument_sustain_reduction_ms": 0.0,
                "effective_min_hold_ms": round(effective_min_hold_ms, 3),
                "effective_max_hold_ms": round(effective_max_hold_ms, 3),
                "prepared_source": int(prepared_source),
                "percussion_dropped": arrangement.dropped_percussion,
                "short_notes_dropped": arrangement.dropped_short,
                "source_chord_groups": arrangement.chord_groups,
                "performed_chord_groups": arrangement.performed_chord_groups,
                "chord_notes_aligned": arrangement.chord_notes_aligned,
                "chord_detection_window_ms": round(arrangement.chord_detection_window_ms, 3),
                "melody_phrase_count": arrangement.melody_phrase_count,
                "melody_track_switches": arrangement.melody_track_switches,
                "melody_large_leaps": arrangement.melody_large_leaps,
                "solo_segments": 0,
                "solo_notes": 0,
                "solo_protected_lead_notes": 0,
                "solo_accompaniment_dropped": 0,
                "solo_density_dropped": 0,
                "solo_landmarks_preserved": 0,
                "solo_mapping_exact_notes": 0,
                "solo_mapping_folded_notes": 0,
                "score_texture": score_analysis.texture if score_analysis else "custom",
                "effective_mapping_mode": settings.mapping_mode,
                "effective_max_polyphony": settings.max_polyphony,
                "effective_speed": settings.speed,
                **(FluidPhrasingStats().diagnostics(settings.fluid_phrasing) if settings.fluid_phrasing else {}),
            },
        )

    onset_groups = _group_onsets(source_notes, settings.onset_group_ms)
    lead_notes = set(arrangement.lead_notes)
    automatic_pitch_shift = 0
    mapping_settings = settings
    solo_adaptive_mapping = bool(
        settings.performance_preset == "optimal"
        and settings.mapping_mode == "fold_smart"
        and arrangement.solo_segments
    )
    group_solo_segments: dict[int, tuple[int, SoloSegment]] = {}
    group_mapping_settings: dict[int, AppSettings] = {}
    solo_octave_shifts: dict[int, int] = {}
    if solo_adaptive_mapping:
        for group_index, group in enumerate(onset_groups):
            match = _solo_segment_for_group(group, arrangement.solo_segments)
            if match is not None:
                group_solo_segments[group_index] = match
        for segment_index, segment in enumerate(arrangement.solo_segments):
            group_indices = sorted(
                group_index
                for group_index, (matched_index, _segment) in group_solo_segments.items()
                if matched_index == segment_index
            )
            solo_groups = [
                [
                    note
                    for note in onset_groups[group_index]
                    if note.track_index == segment.track_index
                ]
                for group_index in group_indices
            ]
            solo_groups = [group for group in solo_groups if group]
            solo_notes = [note for group in solo_groups for note in group]
            octave_shift = _adaptive_scum_octave_shift(solo_notes, settings.transpose)
            solo_octave_shifts[segment_index] = octave_shift
            segment_settings = replace(
                settings,
                mapping_mode="melody3_contour",
                transpose=settings.transpose + octave_shift,
            )
            for group_index in group_indices:
                solo_group = [
                    note
                    for note in onset_groups[group_index]
                    if note.track_index == segment.track_index
                ]
                if not solo_group:
                    continue
                group_mapping_settings[group_index] = segment_settings
    if settings.mapping_mode == "match3_adaptive":
        automatic_pitch_shift = _adaptive_scum_octave_shift(source_notes, settings.transpose)
        mapping_settings = replace(
            settings,
            transpose=settings.transpose + automatic_pitch_shift,
        )
    elif settings.mapping_mode == "strict_auto":
        automatic_pitch_shift = _automatic_strict_octave_shift(source_notes, settings.transpose)
        mapping_settings = replace(
            settings,
            transpose=settings.transpose + automatic_pitch_shift,
        )
    if settings.mapping_mode == "smart3_harmonic":
        smart_modifiers = _smart_register_sequence_harmonic(
            onset_groups, settings, lead_notes
        )
    elif settings.mapping_mode in {"match3_adaptive", "melody3_contour"}:
        smart_modifiers = _melody_register_sequence_contour(onset_groups, mapping_settings)
    elif solo_adaptive_mapping:
        smart_modifiers = {index: 0 for index in range(len(onset_groups))}
        for segment_index, _segment in enumerate(arrangement.solo_segments):
            group_indices = sorted(
                group_index
                for group_index, (matched_index, _matched_segment) in group_solo_segments.items()
                if matched_index == segment_index and group_index in group_mapping_settings
            )
            solo_groups = [
                [
                    note
                    for note in onset_groups[group_index]
                    if note.track_index == arrangement.solo_segments[segment_index].track_index
                ]
                for group_index in group_indices
            ]
            segment_sequence = _melody_register_sequence_contour(
                solo_groups,
                group_mapping_settings[group_indices[0]],
            ) if group_indices else {}
            for local_index, group_index in enumerate(group_indices):
                smart_modifiers[group_index] = segment_sequence.get(local_index, 0)
    else:
        smart_modifiers = {}
    smoothed_modifier_groups = 0
    smoothed_modifier_notes = 0
    if settings.mapping_mode == "smart3_harmonic":
        smart_modifiers, smoothed_modifier_groups, smoothed_modifier_notes = (
            _stabilize_short_modifier_excursions(onset_groups, smart_modifiers)
        )
    smart_modifiers, budget_folded_groups = _enforce_bank_switch_budget(
        onset_groups,
        smart_modifiers,
        settings.bank_switch_budget_per_second,
    )
    if budget_folded_groups:
        warnings.append(
            f"Folded {budget_folded_groups:,} onset group(s) to keep octave-bank taps within the "
            f"{settings.bank_switch_budget_per_second}/s budget."
        )
    mapped_groups: list[list[_MappedCandidate]] = []
    for group_index, group in enumerate(onset_groups):
        group_settings = group_mapping_settings.get(group_index, mapping_settings)
        solo_track = (
            group_solo_segments[group_index][1].track_index
            if group_index in group_solo_segments
            else None
        )
        mapped_groups.append(
            _map_group(
                group,
                group_index,
                group_settings,
                smart_modifiers.get(group_index),
                solo_track,
                lead_notes,
            )
        )

    performance_stats = _PerformanceDirectorStats()
    if settings.performance_preset == "optimal":
        chosen, performance_stats = _direct_performance_voicings(mapped_groups, settings)
        warnings.append(
            "Performance Director selected voicings across the full score, protecting traced lead attacks, "
            "simplifying over-dense bursts, and preferring smooth physical voice leading between chords."
        )
    else:
        chosen = []
        for mapped in mapped_groups:
            chosen.extend(_choose_polyphony(mapped, settings.max_polyphony))
    planner_dropped = max(0, len(source_notes) - len(chosen))

    if settings.mapping_mode == "smart3_harmonic":
        warnings.append(
            "Smart 3-octave mode preserves register by onset group. Cross-octave chords are folded because SCUM uses a global Ctrl/Shift octave modifier."
        )
        if smoothed_modifier_groups:
            warnings.append(
                f"Folded {smoothed_modifier_notes:,} note(s) in {smoothed_modifier_groups:,} brief octave-transition "
                "group(s) into the surrounding register to prevent Ctrl/Shift blips."
            )
    elif settings.mapping_mode == "match3_adaptive":
        exact_before_folding = sum(
            48 <= note.pitch + mapping_settings.transpose <= 84 for note in source_notes
        )
        direction = f"{automatic_pitch_shift:+d}" if automatic_pitch_shift else "0"
        warnings.append(
            f"SCUM pitch matching applied a {direction}-semitone whole-song octave shift, keeping "
            f"{exact_before_folding:,}/{len(source_notes):,} arranged notes inside C3-C6 before residual folding. "
            "Pitch classes and intervals are not scale-quantised."
        )
    elif settings.mapping_mode == "melody3_contour":
        warnings.append(
            "Melody contour mode prioritises the original register and may use more Ctrl/Shift transitions. "
            "It is intended for one-note guitar or melody playback, not cross-octave chords."
        )
    elif settings.mapping_mode == "strict_auto":
        exact_count = sum(60 <= note.pitch + mapping_settings.transpose <= 72 for note in source_notes)
        direction = f"{automatic_pitch_shift:+d}" if automatic_pitch_shift else "0"
        warnings.append(
            f"Strict auto-centering applied a {direction}-semitone octave shift, keeping "
            f"{exact_count:,}/{len(source_notes):,} notes strictly within C4-C5 without modification."
        )
    elif settings.mapping_mode == "fold_smart":
        warnings.append(
            "Enhanced fold mode resolved octave unison chord collisions within the C4-C5 range."
        )
    if solo_adaptive_mapping:
        warnings.append(
            "Solo-adaptive mapping kept accompaniment on Safe Fold and switched only protected "
            "solo sections to whole-octave pitch matching plus melody-contour banking. Every "
            "Ctrl/Shift transition retains the standalone no-note-overlap guard."
        )
    if settings.max_polyphony > 3:
        warnings.append("SCUM instruments may miss notes when more than three keys are pressed together.")

    timing = _build_planned_timing(
        chosen,
        settings,
        profile,
        uses_bank_mapping=(
            settings.mapping_mode in {
                "match3_adaptive",
                "melody3_contour",
                "smart3_harmonic",
            }
            or solo_adaptive_mapping
        ),
    )
    planned = timing.notes
    if settings.fluid_phrasing:
        fluid = timing.fluid_phrasing
        warnings.append(
            f"Fluid phrasing {settings.fluid_phrasing}% shaped {fluid.phrase_count:,} phrase(s), "
            f"connected {fluid.connected_notes:,} lead hold(s), and moved {fluid.shifted_groups:,} "
            f"ensemble attack group(s) by at most {fluid.max_shift_ms:.1f} ms. "
            "Phrase endpoints, written pitches and source MIDI are preserved; key and octave-bank "
            "safety can shorten these holds or delay physically impossible attacks."
        )
    if timing.transition_delays:
        warnings.append(
            f"Delayed {timing.transition_delays:,} modifier/retrigger timing group(s) by "
            f"{timing.transition_delay_ms:.0f} ms total to preserve note holds, key gaps, and Ctrl/Shift changes."
        )
    if timing.lead_articulation_notes:
        warnings.append(
            f"Lead articulation released {timing.lead_articulation_notes:,} overlapping melody note(s) "
            f"{timing.lead_articulation_ms:.0f} ms earlier in total so successive pitches remain a clear line."
        )
    if timing.rhythm_shortened_notes:
        warnings.append(
            f"Rhythm protection shortened {timing.rhythm_shortened_notes:,} sustain(s) by "
            f"{timing.rhythm_shortening_ms:.0f} ms total so repeated keys stayed on the original attacks."
        )
    if timing.retrigger_delays:
        warnings.append(
            f"Only {timing.retrigger_delays:,} physically impossible same-key retrigger(s) required "
            f"{timing.retrigger_delay_ms:.0f} ms total attack delay after elastic sustain shaping."
        )
    if timing.bank_guard_clipped_notes:
        warnings.append(
            f"Octave-bank transitions released {timing.bank_guard_clipped_notes:,} held note(s) early by "
            f"{timing.bank_guard_clipped_ms:.0f} ms total rather than dragging the following phrase off-time."
        )
    if timing.sustain_capped_notes:
        warnings.append(
            f"Prepared {timing.sustain_capped_notes:,} note(s) for {instrument.label} by limiting each "
            f"sustain to {instrument.max_sustain_ms:,} ms. Note attacks and pitches were preserved."
        )
    if settings.min_hold_ms / settings.speed > instrument.max_sustain_ms:
        warnings.append(
            f"The configured minimum played-note length exceeds the {instrument.label} sustain ceiling; "
            f"the {instrument.max_sustain_ms:,} ms instrument limit takes priority."
        )

    events, event_stats = _build_key_events(timing, settings, profile)
    duration_ms = max((event.at_ms for event in events), default=0.0)
    retained = len(planned)
    dropped_total = max(0, arrangement.source_notes - retained)
    score_chord_groups = sum(len(group) > 1 for group in timing.grouped_candidates.values())
    score_chord_notes = sum(
        len(group) for group in timing.grouped_candidates.values() if len(group) > 1
    )
    initial_bank = (
        timing.group_modifiers[timing.sorted_group_ids[0]] if timing.sorted_group_ids else 0
    )
    final_bank = (
        timing.group_modifiers[timing.sorted_group_ids[-1]] if timing.sorted_group_ids else 0
    )
    solo_candidates = [item for item in chosen if item.is_solo]
    solo_mapping_exact = sum(
        item.mapped_pitch == item.source.pitch for item in solo_candidates
    )
    effective_mapping_mode = "solo_adaptive" if solo_adaptive_mapping else settings.mapping_mode
    diagnostics: dict[str, int | float | str] = {
        "arrangement_mode": settings.arrangement_mode,
        "chord_recognition_mode": settings.chord_recognition_mode,
        "performance_preset": settings.performance_preset,
        "prepared_source": int(prepared_source),
        "melody_track": arrangement.melody_track if arrangement.melody_track is not None else "none",
        "percussion_dropped": arrangement.dropped_percussion,
        "short_notes_dropped": arrangement.dropped_short,
        "retrigger_dropped": arrangement.dropped_retrigger,
        "density_dropped": arrangement.dropped_density,
        "arrangement_dropped": arrangement.dropped_arrangement,
        "planner_dropped": planner_dropped,
        "performance_director_groups": performance_stats.groups,
        "performance_dense_groups_simplified": performance_stats.dense_groups_simplified,
        "performance_lead_attacks_protected": performance_stats.lead_attacks_protected,
        "performance_outer_voices_protected": performance_stats.source_outer_voices_protected,
        "performance_continuity_transitions": performance_stats.continuity_transitions,
        "performance_average_voice_leading_semitones": round(
            performance_stats.average_voice_leading_semitones, 3
        ),
        "source_chord_groups": arrangement.chord_groups,
        "performed_chord_groups": arrangement.performed_chord_groups,
        "chord_notes_aligned": arrangement.chord_notes_aligned,
        "chord_alignment_ms": round(arrangement.chord_alignment_ms, 3),
        "chord_detection_window_ms": round(arrangement.chord_detection_window_ms, 3),
        "melody_phrase_count": arrangement.melody_phrase_count,
        "melody_track_switches": arrangement.melody_track_switches,
        "melody_large_leaps": arrangement.melody_large_leaps,
        "solo_segments": len(arrangement.solo_segments),
        "solo_handoffs": len(arrangement.solo_segments),
        "solo_notes": len(solo_candidates),
        "solo_protected_lead_notes": arrangement.solo_notes,
        "solo_accompaniment_dropped": arrangement.solo_accompaniment_dropped,
        "solo_density_dropped": arrangement.solo_density_dropped,
        "solo_landmarks_preserved": arrangement.solo_landmarks_preserved,
        "solo_chord_stagger_suppressed_groups": len(group_solo_segments),
        "solo_mapping_exact_notes": solo_mapping_exact,
        "solo_mapping_folded_notes": len(solo_candidates) - solo_mapping_exact,
        "solo_segment_octave_shifts": ",".join(
            f"{index + 1}:{shift:+d}"
            for index, shift in sorted(solo_octave_shifts.items())
        ),
        "score_chord_groups": score_chord_groups,
        "score_chord_notes": score_chord_notes,
        "modifier_switches": event_stats.modifier_switches,
        "octave_bank_taps": event_stats.bank_taps,
        "octave_shift_taps": event_stats.shift_taps,
        "octave_control_taps": event_stats.control_taps,
        "octave_early_preparations": event_stats.early_preparations,
        "octave_extra_settle_ms": round(event_stats.extra_settle_ms, 3),
        "octave_tap_hold_ms": OCTAVE_BANK_TAP_HOLD_MS,
        "initial_octave_bank": initial_bank,
        "initial_bank_taps": abs(initial_bank),
        "final_octave_bank_before_restore": final_bank,
        "base_bank_restored": int(settings.restore_base_bank and final_bank != 0),
        "mapping_explanations": len(planned),
        # Retain the old diagnostic names for consumers of exported plan data.
        "upper_modifier_pulses": event_stats.shift_taps,
        "upper_modifier_max_hold_ms": OCTAVE_BANK_TAP_HOLD_MS,
        "modifier_excursion_groups_smoothed": smoothed_modifier_groups,
        "modifier_excursion_notes_folded": smoothed_modifier_notes,
        "bank_switch_budget_per_second": settings.bank_switch_budget_per_second,
        "bank_budget_groups_folded": budget_folded_groups,
        "c_boundary_preference": settings.c_boundary_preference,
        "mapping_stability": settings.mapping_stability,
        "fidelity_priority": settings.fidelity_priority,
        "restore_base_bank": int(settings.restore_base_bank),
        "contour_transition_groups_delayed": timing.transition_delays,
        "contour_transition_delay_ms": round(timing.transition_delay_ms, 3),
        "physical_retriggers_delayed": timing.retrigger_delays,
        "physical_retrigger_delay_ms": round(timing.retrigger_delay_ms, 3),
        "rhythm_shortened_notes": timing.rhythm_shortened_notes,
        "rhythm_shortening_ms": round(timing.rhythm_shortening_ms, 3),
        "bank_guard_clipped_notes": timing.bank_guard_clipped_notes,
        "bank_guard_clipped_ms": round(timing.bank_guard_clipped_ms, 3),
        "physical_min_hold_ms": round(timing.physical_min_hold_ms, 3),
        "lead_articulation_notes": timing.lead_articulation_notes,
        "lead_articulation_ms": round(timing.lead_articulation_ms, 3),
        "target_instrument": instrument.key,
        "target_instrument_label": instrument.label,
        "instrument_max_sustain_ms": instrument.max_sustain_ms,
        "instrument_sustain_capped_notes": timing.sustain_capped_notes,
        "instrument_sustain_reduction_ms": round(timing.sustain_reduction_ms, 3),
        "chord_stagger_ms": settings.chord_spread_ms,
        "chord_roll_style": (
            "lead-first" if any(item.is_lead or item.is_solo for item in chosen)
            else "low-to-high" if instrument.key in {"guitar", "banjo"}
            else "ascending"
        ),
        "physical_retrigger_gap_ms": settings.key_retrigger_gap_ms,
        "modifier_release_ms": settings.modifier_release_ms,
        "modifier_settle_ms": settings.modifier_settle_ms,
        "score_texture": score_analysis.texture if score_analysis else "custom",
        "score_description": score_analysis.description if score_analysis else "custom settings",
        "analysed_track_count": score_analysis.track_count if score_analysis else source_track_count,
        "analysed_onset_count": score_analysis.onset_count if score_analysis else len(onset_groups),
        "analysed_chord_ratio": round(score_analysis.chord_onset_ratio, 4) if score_analysis else 0.0,
        "analysed_peak_starts_per_second": score_analysis.peak_starts_per_second if score_analysis else 0,
        "analysed_peak_onsets_per_second": score_analysis.peak_onsets_per_second if score_analysis else 0,
        "analysed_sounding_polyphony_p95": score_analysis.sounding_polyphony_p95 if score_analysis else 0,
        "analysed_overlap_ratio": round(score_analysis.overlap_ratio, 4) if score_analysis else 0.0,
        "analysed_phrase_count": score_analysis.phrase_count if score_analysis else 0,
        "analysed_rhythmic_variation": (
            round(score_analysis.rhythmic_variation, 4) if score_analysis else 0.0
        ),
        "analysed_median_onset_gap_ms": (
            round(score_analysis.median_onset_gap_ms, 3) if score_analysis else 0.0
        ),
        "analysed_median_note_duration_ms": (
            round(score_analysis.median_note_duration_ms, 3) if score_analysis else 0.0
        ),
        "effective_mapping_mode": effective_mapping_mode,
        "effective_max_polyphony": settings.max_polyphony,
        "effective_max_notes_per_second": settings.max_notes_per_second,
        "effective_min_source_note_ms": settings.min_source_note_ms,
        "effective_min_retrigger_ms": settings.min_retrigger_ms,
        "effective_hold_ratio": settings.hold_ratio,
        "effective_min_hold_ms": round(timing.effective_min_hold_ms, 3),
        "effective_max_hold_ms": round(timing.effective_max_hold_ms, 3),
        "effective_speed": settings.speed,
    }
    if arrangement.contextual_peak_voices:
        diagnostics.update(
            contextual_capacity_rejected=arrangement.contextual_capacity_rejected,
            contextual_collision_rejected=arrangement.contextual_collision_rejected,
            contextual_phrase_resets=arrangement.contextual_phrase_resets,
            contextual_peak_voices_before_density=arrangement.contextual_peak_voices,
        )
    if settings.fluid_phrasing:
        diagnostics.update(timing.fluid_phrasing.diagnostics(settings.fluid_phrasing))
    if settings.mapping_mode == "match3_adaptive":
        exact = sum(
            note.mapped_pitch == max(0, min(127, note.source_pitch + mapping_settings.transpose))
            for note in planned
        )
        diagnostics.update(
            automatic_pitch_shift_semitones=automatic_pitch_shift,
            pitch_match_exact_notes=exact,
            pitch_match_octave_folded_notes=retained - exact,
        )
    return PlaybackPlan(
        events=events,
        planned_notes=sorted(planned, key=lambda note: (note.start_ms, note.base_pitch)),
        source_notes=arrangement.source_notes,
        retained_notes=retained,
        dropped_notes=dropped_total,
        duration_ms=duration_ms,
        warnings=warnings,
        diagnostics=diagnostics,
    )


def export_plan_csv(plan: PlaybackPlan, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_ms", "action", "key", "reason"])
        for event in plan.events:
            writer.writerow([f"{event.at_ms:.3f}", event.action, event.key, event.reason])
    return destination


def export_score_csv(plan: PlaybackPlan, path: str | Path) -> Path:
    """Export the playable SCUM score as musical note/chord rows.

    This complements the low-level key-event export. Each row retains source
    pitch, mapped pitch, persistent octave bank, SCUM key, and chord membership
    so the conversion can be audited without reverse-engineering key-down/up
    pairs.
    """

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    group_sizes: dict[int, int] = defaultdict(int)
    for note in plan.planned_notes:
        group_sizes[note.score_group] += 1

    bank_names = {-1: "lower", 0: "base", 1: "upper"}
    try:
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "score_group",
                    "voice",
                    "chord_size",
                    "attack_ms",
                    "release_ms",
                    "duration_ms",
                    "source_note",
                    "source_midi",
                    "mapped_note",
                    "mapped_midi",
                    "octave_bank",
                    "scum_key",
                    "velocity",
                    "mapping_explanation",
                ]
            )
            for note in sorted(
                plan.planned_notes,
                key=lambda item: (item.score_group, item.voice_index, item.start_ms, item.base_pitch),
            ):
                writer.writerow(
                    [
                        note.score_group,
                        note.voice_index,
                        group_sizes[note.score_group],
                        f"{note.start_ms:.3f}",
                        f"{note.end_ms:.3f}",
                        f"{note.end_ms - note.start_ms:.3f}",
                        midi_note_name(note.source_pitch),
                        note.source_pitch,
                        midi_note_name(note.mapped_pitch),
                        note.mapped_pitch,
                        bank_names.get(note.modifier, str(note.modifier)),
                        note.key,
                        note.velocity,
                        note.mapping_reason,
                    ]
                )
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def recommend_optimal_transpose(
    notes: list[MidiNote],
    settings: AppSettings,
    semitone_range: tuple[int, int] = (-12, 12),
) -> tuple[int, dict[str, Any]]:
    """Analyze pitch coverage and voice leading to recommend the optimal transpose shift."""

    if not notes:
        return 0, {
            "best_shift": 0,
            "in_bank_pct": 0.0,
            "in_range_pct": 0.0,
            "bank_switches": 0,
            "bank_switch_rate": 0.0,
            "average_fold_semitones": 0.0,
            "score": 0.0,
            "candidates": [],
        }

    total_weight = sum(
        min(note.duration_ms, 2000.0) * (0.35 + note.velocity / 127.0)
        for note in notes
    )
    if total_weight <= 0:
        total_weight = float(len(notes))

    groups = _group_onsets(notes, settings.onset_group_ms)
    candidates: list[dict[str, Any]] = []

    for shift in range(semitone_range[0], semitone_range[1] + 1):
        in_bank_w = 0.0
        in_range_w = 0.0
        fold_dist_w = 0.0
        for note in notes:
            p = max(0, min(127, note.pitch + shift))
            w = min(note.duration_ms, 2000.0) * (0.35 + note.velocity / 127.0)
            if 60 <= p <= 72:
                in_bank_w += w
            if 48 <= p <= 84:
                in_range_w += w
            else:
                fold_dist_w += abs(_fold_to_window(p, 48, 84) - p) * w

        bank_switches = 0
        current_bank = 0
        for group in groups:
            avg_pitch = sum(n.pitch + shift for n in group) / len(group)
            target_bank = -1 if avg_pitch < 54 else (1 if avg_pitch > 78 else 0)
            if target_bank != current_bank:
                bank_switches += abs(target_bank - current_bank)
                current_bank = target_bank

        in_bank_pct = (in_bank_w / total_weight) * 100.0
        in_range_pct = (in_range_w / total_weight) * 100.0
        average_fold_semitones = fold_dist_w / total_weight
        bank_switch_rate = bank_switches / max(1, len(groups)) * 100.0
        # Use normalized musical percentages rather than raw duration-weighted
        # totals.  The old score made the fixed bank/transpose penalties almost
        # irrelevant on long songs because note-weight terms grew without bound.
        score = (
            in_range_pct * 0.52
            + in_bank_pct * 0.28
            - average_fold_semitones * 2.5
            - bank_switch_rate * 0.12
            - abs(shift) * 0.35
        )

        candidates.append(
            {
                "shift": shift,
                "in_bank_pct": round(in_bank_pct, 1),
                "in_range_pct": round(in_range_pct, 1),
                "average_fold_semitones": round(average_fold_semitones, 2),
                "bank_switches": bank_switches,
                "bank_switch_rate": round(bank_switch_rate, 1),
                "score": round(score, 2),
            }
        )

    best = max(candidates, key=lambda c: (c["score"], c["in_bank_pct"], -abs(c["shift"])))
    return best["shift"], {
        "best_shift": best["shift"],
        "in_bank_pct": best["in_bank_pct"],
        "in_range_pct": best["in_range_pct"],
        "average_fold_semitones": best["average_fold_semitones"],
        "bank_switches": best["bank_switches"],
        "bank_switch_rate": best["bank_switch_rate"],
        "score": best["score"],
        "candidates": candidates,
    }

