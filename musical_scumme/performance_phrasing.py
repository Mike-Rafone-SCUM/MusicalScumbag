"""Deterministic ensemble phrasing, before SCUM's physical timing guards."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass, replace
from math import pi, sin
from statistics import median

from .model import MidiNote, PlannedNote


@dataclass(frozen=True, slots=True)
class FluidPhrasingStats:
    phrase_count: int = 0
    shifted_groups: int = 0
    max_shift_ms: float = 0.0
    connected_notes: int = 0
    released_notes: int = 0
    added_hold_ms: float = 0.0

    def diagnostics(self, strength: int) -> dict[str, int | float]:
        return {
            "fluid_phrasing": strength,
            "fluid_phrase_count": self.phrase_count,
            "fluid_connected_notes": self.connected_notes,
            "fluid_released_notes": self.released_notes,
            "fluid_shifted_groups": self.shifted_groups,
            "fluid_max_shift_ms": round(self.max_shift_ms, 3),
            "fluid_added_hold_ms": round(self.added_hold_ms, 3),
        }


def apply_fluid_phrasing(
    notes: list[PlannedNote],
    sources: list[MidiNote],
    lead_indices: set[int],
    *,
    strength: int,
    speed: float,
    minimum_hold_ms: float,
    maximum_hold_ms: float,
    key_gap_ms: float,
    instrument: str,
    max_polyphony: int,
) -> tuple[list[PlannedNote], FluidPhrasingStats]:
    """Shape a phrase together without quantisation or accumulating tempo drift.

    Source notes remain immutable. Phrase ends are pinned; accompaniment shares
    the lead's continuous timing curve. Only already connected source melody
    receives longer holds. Physical retrigger/bank guards must run afterward.
    """
    if not strength or not notes:
        return notes, FluidPhrasingStats()
    if len(notes) != len(sources):
        raise ValueError("Every performed note needs its source articulation.")
    amount = min(100, max(0, strength)) / 100.0
    groups: dict[int, list[int]] = defaultdict(list)
    for index, note in enumerate(notes):
        groups[note.score_group].append(index)
    group_ids = sorted(groups, key=lambda group: min(notes[i].start_ms for i in groups[group]))
    starts = {group: min(notes[i].start_ms for i in groups[group]) for group in group_ids}
    if not lead_indices:
        # Faithful single-line sources have no traced lead. A polyphonic score
        # needs an actual traced voice rather than a guessed top chord tone.
        parts = {(source.track_index, source.channel) for source in sources}
        if len(parts) == 1 and all(len(indices) == 1 for indices in groups.values()) and sources[0].channel != 9:
            lead_indices = set(range(len(notes)))
    lead_by_group = {
        group: max(
            (i for i in indices if i in lead_indices),
            key=lambda i: (sources[i].velocity, sources[i].duration_ms, sources[i].pitch),
        )
        for group, indices in groups.items()
        if any(i in lead_indices for i in indices)
    }
    leads = [lead_by_group[group] for group in group_ids if group in lead_by_group]
    if not leads:
        return notes, FluidPhrasingStats()
    intervals = [sources[b].start_ms - sources[a].start_ms for a, b in zip(leads, leads[1:], strict=False)]
    typical = median([interval for interval in intervals if interval > 0]) if intervals else 500.0
    phrases: list[list[int]] = [[leads[0]]]
    for previous, current in zip(leads, leads[1:], strict=False):
        a, b = sources[previous], sources[current]
        rest = b.start_ms - a.end_ms
        handoff = (a.track_index, a.channel) != (b.track_index, b.channel)
        boundary = (
            rest >= max(140.0, typical * 0.5)
            or (b.start_ms - a.start_ms >= max(900.0, typical * 3.5) and rest >= 40.0)
            or (handoff and rest >= max(60.0, typical * 0.25))
        )
        if boundary:
            phrases.append([])
        phrases[-1].append(current)

    # Bound movement by nearby ensemble attacks, including individual rolled
    # chord members. Preserve their order even when a roll reaches another group.
    local_limits = {}
    for position, group in enumerate(group_ids):
        previous = starts[group_ids[position - 1]] if position else None
        following = starts[group_ids[position + 1]] if position + 1 < len(group_ids) else None
        spacing = [abs(starts[group] - time) for time in (previous, following) if time is not None]
        local_limits[group] = min(24.0, min(spacing, default=300.0) * 0.08) * amount
    attacks = sorted((note.start_ms, note.score_group) for note in notes)
    for (previous_time, previous_group), (time, group) in zip(attacks, attacks[1:], strict=False):
        if previous_group != group:
            limit = (time - previous_time) * 0.08 * amount
            local_limits[previous_group] = min(local_limits[previous_group], limit)
            local_limits[group] = min(local_limits[group], limit)
    offsets = dict.fromkeys(group_ids, 0.0)
    group_times = [starts[group] for group in group_ids]
    for phrase in phrases:
        if len(phrase) < 3:
            continue
        first = starts[notes[phrase[0]].score_group]
        last = starts[notes[phrase[-1]].score_group]
        if last <= first:
            continue
        left, right = bisect_left(group_times, first), bisect_right(group_times, last)
        amplitude = min(24.0, typical / speed * 0.08) * amount
        for group in group_ids[left:right]:
            phase = (starts[group] - first) / (last - first)
            curve = -amplitude * sin(2 * pi * phase)
            offsets[group] = max(-local_limits[group], min(local_limits[group], curve))
        offsets[notes[phrase[0]].score_group] = 0.0
        offsets[notes[phrase[-1]].score_group] = 0.0
    # Warp releases through the same monotonic timeline as attacks. Translating
    # each whole span independently makes abutting source chords overlap when
    # the next chord moves earlier, defeating full-duration voice budgeting.
    anchors = {time: offsets[group] for time, group in attacks}
    anchor_times = sorted(anchors)

    def release_offset(time: float) -> float:
        right = bisect_right(anchor_times, time)
        if right == 0 or right == len(anchor_times):
            return anchors[anchor_times[0 if right == 0 else -1]]
        left_time, right_time = anchor_times[right - 1], anchor_times[right]
        fraction = (time - left_time) / (right_time - left_time)
        return anchors[left_time] + fraction * (anchors[right_time] - anchors[left_time])

    release_offsets = [release_offset(note.end_ms) for note in notes]
    scale = 1.0
    for note, end_offset in zip(notes, release_offsets, strict=True):
        compression = offsets[note.score_group] - end_offset
        if compression > 0:
            slack = max(0.0, note.end_ms - note.start_ms - minimum_hold_ms)
            scale = min(scale, slack / compression)
    # Fully occupied minimum-length passages have no safe room for rubato.
    # Connection can still operate; physical holds take priority over movement.
    if scale < 1e-9:
        scale = 0.0
    offsets = {group: offset * scale for group, offset in offsets.items()}
    shaped = []
    for note, end_offset in zip(notes, release_offsets, strict=True):
        start = note.start_ms + offsets[note.score_group]
        end = min(note.end_ms + end_offset * scale, start + maximum_hold_ms)
        shaped.append(
            replace(note, start_ms=start, end_ms=end) if start != note.start_ms or end != note.end_ms else note
        )

    # A sweep makes extension capacity checks logarithmic, even in long scores.
    # Lead extension tails end before the next lead and cannot overlap one
    # another; the baseline occupancy is sufficient for these disjoint tails.
    events: dict[float, int] = defaultdict(int)
    for note in shaped:
        events[note.start_ms] += 1
        events[note.end_ms] -= 1
    times = sorted(events)
    occupancy: list[int] = []
    sounding = 0
    for time in times:
        sounding += events[time]
        occupancy.append(sounding)
    full_times = [time for time, voices in zip(times, occupancy, strict=True) if voices >= max_polyphony]
    connected = released = 0
    added_hold = 0.0
    connection_amount = amount * {"guitar": 0.9, "harmonica": 1.0, "banjo": 0.55}.get(instrument, 0.9)
    articulation_gap = {"guitar": 8.0, "harmonica": 12.0, "banjo": 16.0}.get(instrument, 8.0)
    for phrase in phrases:
        for current, following in zip(phrase, phrase[1:], strict=False):
            source, next_source = sources[current], sources[following]
            note, next_note = shaped[current], shaped[following]
            interval = next_source.start_ms - source.start_ms
            source_gap = next_source.start_ms - source.end_ms
            if interval <= 0 or source_gap > min(160.0, interval * 0.4):
                continue
            if source.channel == 9 or next_source.channel == 9:
                continue
            gap = max(articulation_gap, key_gap_ms) if note.key == next_note.key else articulation_gap
            ceiling = min(note.start_ms + maximum_hold_ms, next_note.start_ms - gap)
            if ceiling < note.start_ms + minimum_hold_ms:
                continue
            target = note.end_ms + (ceiling - note.end_ms) * connection_amount
            target = min(ceiling, max(note.start_ms + minimum_hold_ms, target))
            if target > note.end_ms:
                segment = max(0, bisect_right(times, note.end_ms) - 1)
                if occupancy[segment] >= max_polyphony:
                    target = note.end_ms
                else:
                    full_index = bisect_left(full_times, note.end_ms)
                    if full_index < len(full_times):
                        target = min(target, full_times[full_index])
            change = target - note.end_ms
            if change > 0.001:
                connected += 1
                added_hold += change
            elif change < -0.001:
                released += 1
            if abs(change) > 0.001:
                shaped[current] = replace(note, end_ms=target)
    shifted = [abs(offset) for offset in offsets.values() if abs(offset) > 0.001]
    return shaped, FluidPhrasingStats(
        phrase_count=len(phrases),
        shifted_groups=len(shifted),
        max_shift_ms=max(shifted, default=0.0),
        connected_notes=connected,
        released_notes=released,
        added_hold_ms=added_hold,
    )
