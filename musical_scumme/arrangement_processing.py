"""Duration-aware source arrangement. No mapping, input or Qt dependencies."""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass

from .model import MidiNote


class _VoiceTimeline:
    """Compressed half-open intervals with logarithmic range-add/range-maximum."""

    def __init__(self, notes: list[MidiNote]):
        self.times = sorted({t for note in notes for t in (note.start_ms, note.end_ms)})
        self.indices = {t: i for i, t in enumerate(self.times)}
        self.size = max(1, len(self.times) - 1)
        self.maximum = [0] * (4 * self.size)
        self.lazy = [0] * (4 * self.size)

    def _visit(self, left: int, right: int, add: int, node: int, low: int, high: int) -> int:
        if left >= high or right <= low:
            return 0
        if left <= low and high <= right:
            if add:
                self.maximum[node] += add
                self.lazy[node] += add
            return self.maximum[node]
        middle = (low + high) // 2
        a = self._visit(left, right, add, node * 2 + 1, low, middle)
        b = self._visit(left, right, add, node * 2 + 2, middle, high)
        if add:
            self.maximum[node] = self.lazy[node] + max(self.maximum[node * 2 + 1], self.maximum[node * 2 + 2])
        return self.lazy[node] + max(a, b)

    def voices(self, note: MidiNote, *, add: bool = False) -> int:
        left, right = self.indices[note.start_ms], self.indices[note.end_ms]
        if left >= right:
            return 0
        return self._visit(left, right, int(add), 0, 0, self.size)


@dataclass(frozen=True, slots=True)
class ContextualArrangement:
    leads: tuple[MidiNote, ...]
    support: tuple[MidiNote, ...]
    capacity_rejected: int
    collision_rejected: int
    phrase_resets: int
    peak_voices: int


def _pitch_intervals(notes: list[MidiNote]) -> dict[int, tuple[list[float], list[float]]]:
    """Merge held lead spans once; support queries never scan the whole melody."""
    by_pitch: dict[int, list[MidiNote]] = defaultdict(list)
    for note in notes:
        by_pitch[note.pitch].append(note)
    result = {}
    for pitch, pitched in by_pitch.items():
        starts: list[float] = []
        ends: list[float] = []
        for note in sorted(pitched, key=lambda n: n.start_ms):
            if ends and note.start_ms <= ends[-1]:
                ends[-1] = max(ends[-1], note.end_ms)
            else:
                starts.append(note.start_ms)
                ends.append(note.end_ms)
        result[pitch] = starts, ends
    return result


def process_contextual_arrangement(
    groups: list[list[MidiNote]], traced: tuple[MidiNote, ...], primary: int,
    layers: int, texture: str, layer_roles: dict[int, str] | None = None,
) -> ContextualArrangement:
    """Reserve all lead spans before choosing exact, existing support attacks.

    Source lead overlaps are retained. Support cannot increase any interval
    beyond the requested ceiling, including intervals containing future leads.
    """
    leads: list[MidiNote] = []
    contexts: list[MidiNote] = []
    held: MidiNote | None = None
    is_cover = texture in {"cover", "cover_riff"}
    for group, candidate in zip(groups, traced, strict=True):
        owned = any(n.track_index == primary for n in group)
        onset = min(n.start_ms for n in group)
        continuing_fill = is_cover and held is not None and candidate.track_index == held.track_index
        if held is not None and onset < held.end_ms and not owned and not continuing_fill:
            contexts.append(held)
            continue
        leads.append(candidate)
        contexts.append(candidate)
        # Also protect instrumental fills and inferred/unnamed lead sustains.
        held = candidate

    if is_cover:
        return _combine_cover_layers(groups, contexts, leads, layers, layer_roles or {}, texture == "cover_riff")

    source_lead_set = set(leads)
    source = [note for group in groups for note in group]
    timeline = _VoiceTimeline(source + leads)
    for note in leads:
        timeline.voices(note, add=True)
    lead_intervals = _pitch_intervals(leads)
    support: list[MidiNote] = []
    active: list[MidiNote] = []
    previous: tuple[int, ...] = ()
    sounding_end = float("-inf")
    capacity_rejected = collision_rejected = phrase_resets = 0
    for group, lead in zip(groups, contexts, strict=True):
        onset = min(n.start_ms for n in group)
        active = [note for note in active if note.end_ms > onset]
        if sounding_end != float("-inf") and onset - sounding_end >= 750:
            previous = ()
            phrase_resets += 1
        sounding_end = max(sounding_end, lead.end_ms)
        chosen: list[MidiNote] = []
        candidates = [n for n in group if n not in source_lead_set and n.pitch <= lead.pitch - 3]

        def rank(
            note: MidiNote, lead: MidiNote = lead, previous: tuple[int, ...] = previous,
            active: list[MidiNote] = active, chosen: list[MidiNote] = chosen,
        ) -> tuple[float, int, int, int, float]:
            distance = lead.pitch - note.pitch
            continuity = min((abs(note.pitch - pitch) for pitch in previous), default=12)
            score = 0.4 * note.velocity / 127 - 0.025 * min(continuity, 24)
            score += 0.3 * ((distance % 12) in {0, 3, 4, 5, 7, 8, 9})
            occupied_pitch_classes = {lead.pitch % 12} | {
                existing.pitch % 12 for existing in active + chosen
            }
            if note.pitch % 12 in occupied_pitch_classes:
                score -= 0.65
            else:
                score += 0.30
            if texture == "pulse":
                score += 0.7 * (1 - min(note.duration_ms / 1200, 1))
            elif texture == "warm":
                score += 0.7 * min(note.duration_ms / 1200, 1)
            # Foundation first, then compact inner harmony. Existing held bass
            # counts too, so offbeat attacks cannot stack extra low foundations.
            has_bass = any(n.pitch <= lead.pitch - 12 for n in active + chosen)
            score += (min(distance, 36) / 24 if not has_bass else -distance / 48)
            return score, note.velocity, -note.track_index, -note.pitch, -note.end_ms

        candidates.sort(key=rank)
        while candidates:
            note = candidates.pop()
            starts, ends = lead_intervals.get(note.pitch, ([], []))
            index = bisect_left(starts, note.end_ms) - 1
            clashes_with_lead = index >= 0 and ends[index] > note.start_ms
            clashes_with_support = any(
                n.pitch == note.pitch and n.start_ms < note.end_ms and n.end_ms > note.start_ms
                for n in active + chosen
            )
            if clashes_with_lead or clashes_with_support:
                collision_rejected += 1
                continue
            if layers <= 1 or timeline.voices(note) >= layers:
                capacity_rejected += 1
                continue
            timeline.voices(note, add=True)
            support.append(note)
            chosen.append(note)
            sounding_end = max(sounding_end, note.end_ms)
            candidates.sort(key=rank)
        active.extend(chosen)
        if chosen:
            previous = tuple(n.pitch for n in chosen)
    return ContextualArrangement(
        tuple(leads), tuple(support), capacity_rejected, collision_rejected,
        phrase_resets, timeline.maximum[0],
    )


def _combine_cover_layers(
    groups: list[list[MidiNote]], contexts: list[MidiNote], leads: list[MidiNote],
    layers: int, roles: dict[int, str], riff_first: bool = False,
) -> ContextualArrangement:
    """Reserve complete bass/rhythm lines before filling remaining harmony space.

    Chronological greedy harmony selection can occupy the rhythm's later slots.
    Separate passes protect source rhythmic attacks without truncating releases.
    One sounding support voice per role prevents doubled bass or stacked riffs.
    """
    source = [n for group in groups for n in group]
    timeline = _VoiceTimeline(source)
    pitches = {pitch: _VoiceTimeline([n for n in source if n.pitch == pitch])
               for pitch in {n.pitch for n in source}}
    role_timelines = {role: _VoiceTimeline(source) for role in ("bass", "rhythm", "harmony", "fill", "lead")}
    for note in leads:
        timeline.voices(note, add=True)
        pitches[note.pitch].voices(note, add=True)
    lead_set = set(leads)
    candidates = []
    order = {"bass": 0, "rhythm": 1, "harmony": 2, "lead": 2, "fill": 3}
    if riff_first:
        order.update(rhythm=0, bass=1)
    for group, lead in zip(groups, contexts, strict=True):
        for note in group:
            if note in lead_set:
                continue
            role = roles.get(note.track_index, "harmony")
            if role == "bass" and note.pitch > lead.pitch - 3:
                continue
            if note.pitch > lead.pitch + 12:
                continue
            # Lower bass, compact accompaniment, then performed accent.
            distance = note.pitch if role == "bass" else abs(note.pitch - lead.pitch)
            candidates.append((order[role], note.start_ms, distance, -note.velocity,
                               note.track_index, note.channel, note.pitch, note.end_ms, note, role))
    support = []
    capacity = collisions = 0
    for *_, note, role in sorted(candidates, key=lambda item: item[:8]):
        if pitches[note.pitch].voices(note):
            collisions += 1
            continue
        if layers <= 1 or timeline.voices(note) >= layers or role_timelines[role].voices(note):
            capacity += 1
            continue
        support.append(note)
        timeline.voices(note, add=True)
        pitches[note.pitch].voices(note, add=True)
        role_timelines[role].voices(note, add=True)
    support.sort(key=lambda n: (n.start_ms, n.pitch, n.track_index, n.channel, n.end_ms, -n.velocity))
    return ContextualArrangement(tuple(leads), tuple(support), capacity, collisions, 0, timeline.maximum[0])
