from __future__ import annotations

import bisect
import math
import re
from dataclasses import dataclass, replace
from functools import cache
from statistics import median
from typing import Iterable

from .arrangement_options import ARRANGEMENT_RECIPES
from .arranger import _is_vocal_name, recognised_score_onsets
from .config import AppSettings
from .instrument_profiles import resolve_instrument_profile
from .gm import describe_program
from .model import MidiNote, MidiProject, MidiTrack

_LEAD_WORDS = ("lead", "melody", "vocal", "voice", "solo", "guitar", "flute", "sax", "violin")
_BASS_WORDS = ("bass", "cello", "contrabass", "low")
_SUPPORT_WORDS = ("support", "chord", "harmony", "piano", "keys", "organ", "pad", "rhythm", "accomp")
_NOISE_WORDS = ("drum", "percussion", "click", "metronome", "noise", "fx", "effect", "sfx")
_PREPARED_TRACK_NAMES = {"Lead Melody", "Light Support"}


@dataclass(frozen=True, slots=True)
class NoteAnalysis:
    note_count: int
    track_count: int
    onset_count: int
    chord_onset_ratio: float
    attack_polyphony_p95: int
    peak_starts_per_second: int
    median_onset_gap_ms: float
    median_note_duration_ms: float
    short_note_p10_ms: float
    pitch_span: int
    texture: str
    peak_onsets_per_second: int
    sounding_polyphony_p95: int
    overlap_ratio: float
    phrase_count: int
    rhythmic_variation: float

    @property
    def description(self) -> str:
        return {
            "melody": "single-line melody",
            "light_polyphony": "melody with light accompaniment",
            "chordal": "chord-led score",
            "dense": "dense polyphonic score",
            "empty": "empty score",
        }[self.texture]


@dataclass(frozen=True, slots=True)
class TrackAnalysis:
    track_index: int
    name: str
    note_count: int
    median_pitch: float
    chord_onset_ratio: float
    melody_score: float
    support_score: float
    bass_score: float
    rejected_as_noise: bool
    monophony: float
    activity: float
    coverage_ratio: float
    melodic_continuity: float
    program_family: str
    program_role_hint: str

    @property
    def role(self) -> str:
        if self.rejected_as_noise:
            return "Ignored noise/effect"
        best = max(self.melody_score, self.support_score, self.bass_score)
        if best == self.bass_score:
            return "Bass"
        if best == self.support_score:
            return "Chord/support"
        return "Lead candidate"


@dataclass(frozen=True, slots=True)
class ProjectAnalysis:
    tracks: tuple[TrackAnalysis, ...]
    recommended_track_indices: tuple[int, ...]
    selected_notes: NoteAnalysis
    rationale: str
    lead_track_index: int | None = None
    selection_reasons: tuple[tuple[int, str], ...] = ()


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * max(0.0, min(1.0, fraction))
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _onset_groups(notes: list[MidiNote], tolerance_ms: float = 12.0) -> list[list[MidiNote]]:
    groups: list[list[MidiNote]] = []
    for note in sorted(notes, key=lambda item: (item.start_ms, item.pitch, item.end_ms)):
        if not groups or note.start_ms - groups[-1][0].start_ms > tolerance_ms:
            groups.append([note])
        else:
            groups[-1].append(note)
    return groups


def _peak_starts_per_second(notes: list[MidiNote]) -> int:
    return _peak_times_per_second([note.start_ms for note in notes])


def _peak_times_per_second(times: Iterable[float]) -> int:
    starts = sorted(times)
    if not starts:
        return 0
    peak = left = 0
    for right, start in enumerate(starts):
        while start - starts[left] >= 1000.0:
            left += 1
        peak = max(peak, right - left + 1)
    return peak


def _sounding_polyphony(notes: list[MidiNote]) -> tuple[int, float]:
    """Return time-weighted p95 polyphony and the share of sounding time overlapped."""

    events: dict[float, int] = {}
    for note in notes:
        if note.end_ms <= note.start_ms:
            continue
        events[note.start_ms] = events.get(note.start_ms, 0) + 1
        events[note.end_ms] = events.get(note.end_ms, 0) - 1
    if not events:
        return 0, 0.0

    durations_by_polyphony: dict[int, float] = {}
    active = 0
    previous_time: float | None = None
    for at_ms in sorted(events):
        if previous_time is not None and at_ms > previous_time and active > 0:
            durations_by_polyphony[active] = (
                durations_by_polyphony.get(active, 0.0) + at_ms - previous_time
            )
        active += events[at_ms]
        previous_time = at_ms

    total = sum(durations_by_polyphony.values())
    if total <= 0:
        return 0, 0.0
    threshold = total * 0.95
    cumulative = 0.0
    p95 = 1
    for polyphony in sorted(durations_by_polyphony):
        cumulative += durations_by_polyphony[polyphony]
        p95 = polyphony
        if cumulative >= threshold:
            break
    overlapped = sum(
        duration for polyphony, duration in durations_by_polyphony.items() if polyphony > 1
    )
    return p95, overlapped / total


def _rhythmic_variation(gaps: list[float]) -> float:
    if not gaps:
        return 0.0
    centre = median(gaps)
    if centre <= 0:
        return 0.0
    return median(abs(gap - centre) for gap in gaps) / centre


def analyse_notes(notes: Iterable[MidiNote]) -> NoteAnalysis:
    musical = sorted(
        (note for note in notes if note.channel != 9),
        key=lambda item: (item.start_ms, item.track_index, item.pitch, item.end_ms),
    )
    if not musical:
        return NoteAnalysis(
            0,
            0,
            0,
            0.0,
            0,
            0,
            0.0,
            0.0,
            0.0,
            0,
            "empty",
            0,
            0,
            0.0,
            0,
            0.0,
        )

    performed_groups, _window_ms = recognised_score_onsets(musical)
    performed_sizes = [len(group) for group in performed_groups]
    chord_groups = sum(len(group) > 1 for group in performed_groups)
    starts = [group[0].start_ms for group in performed_groups]
    gaps = [right - left for left, right in zip(starts, starts[1:], strict=False) if right > left]
    durations = [note.duration_ms for note in musical]
    p95_polyphony = max(1, round(_percentile([float(size) for size in performed_sizes], 0.95)))
    chord_ratio = chord_groups / len(performed_groups)
    peak_rate = _peak_starts_per_second(musical)
    peak_onset_rate = _peak_times_per_second(starts)
    sounding_p95, overlap_ratio = _sounding_polyphony(musical)
    typical_gap = median(gaps) if gaps else 0.0
    phrase_threshold = max(700.0, typical_gap * 4.0)
    phrase_count = 1 + sum(gap >= phrase_threshold for gap in gaps)

    if (
        p95_polyphony == 1
        and chord_ratio < 0.06
        and (
            len({note.track_index for note in musical}) == 1
            or sounding_p95 <= 2
            or overlap_ratio < 0.18
        )
    ):
        # Attack-monophonic single-track MIDI is very often legato melody or a
        # controller recording with overlapping note-offs. Treat the attacks as
        # authoritative instead of misclassifying pedal/legato overlap as harmony.
        texture = "melody"
    elif (
        peak_rate > 24
        or peak_onset_rate > 18
        or sounding_p95 >= 6
        or (p95_polyphony >= 5 and peak_rate > 18)
    ):
        texture = "dense"
    elif chord_ratio >= 0.16 or p95_polyphony >= 3 or sounding_p95 >= 3:
        texture = "chordal"
    else:
        texture = "light_polyphony"

    pitches = [note.pitch for note in musical]
    return NoteAnalysis(
        note_count=len(musical),
        track_count=len({note.track_index for note in musical}),
        onset_count=len(performed_groups),
        chord_onset_ratio=chord_ratio,
        attack_polyphony_p95=p95_polyphony,
        peak_starts_per_second=peak_rate,
        median_onset_gap_ms=typical_gap,
        median_note_duration_ms=median(durations),
        short_note_p10_ms=_percentile(durations, 0.10),
        pitch_span=max(pitches) - min(pitches),
        texture=texture,
        peak_onsets_per_second=peak_onset_rate,
        sounding_polyphony_p95=sounding_p95,
        overlap_ratio=overlap_ratio,
        phrase_count=phrase_count,
        rhythmic_variation=_rhythmic_variation(gaps),
    )


def _name_tokens(name: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", name.casefold()))


def _contains_any(name: str, words: tuple[str, ...]) -> bool:
    """Match semantic name tokens without false positives such as ``low`` in ``slow``."""

    tokens = _name_tokens(name)
    return any(
        token == word or (len(word) >= 4 and token.startswith(word))
        for token in tokens
        for word in words
    )


def _coverage_ratio(notes: list[MidiNote]) -> float:
    if not notes:
        return 0.0
    ordered = sorted(notes, key=lambda note: (note.start_ms, note.end_ms))
    start = ordered[0].start_ms
    end = max(note.end_ms for note in ordered)
    span = end - start
    if span <= 0:
        return 0.0
    covered = 0.0
    interval_start = ordered[0].start_ms
    interval_end = ordered[0].end_ms
    for note in ordered[1:]:
        if note.start_ms > interval_end:
            covered += max(0.0, interval_end - interval_start)
            interval_start = note.start_ms
            interval_end = note.end_ms
        else:
            interval_end = max(interval_end, note.end_ms)
    covered += max(0.0, interval_end - interval_start)
    return max(0.0, min(1.0, covered / span))


def _melodic_continuity(notes: list[MidiNote]) -> float:
    groups = _onset_groups(notes)
    if len(groups) < 2:
        return 0.5
    representatives = [
        max(group, key=lambda note: (note.velocity, note.duration_ms, note.pitch)).pitch
        for group in groups
    ]
    intervals = [abs(right - left) for left, right in zip(representatives, representatives[1:], strict=False)]
    return math.exp(-median(intervals) / 8.0) if intervals else 0.5


def _analyse_track(track: MidiTrack, track_notes: list[MidiNote]) -> TrackAnalysis:
    notes = [note for note in track_notes if note.channel != 9]
    analysis = analyse_notes(notes)
    pitches = [note.pitch for note in notes]
    centre = median(pitches) if pitches else 60.0
    onset_count = max(1, analysis.onset_count)
    duration_s = max(1.0, track.duration_ms / 1000.0)
    activity = min(2.0, onset_count / duration_s / 4.0)
    coverage = _coverage_ratio(notes)
    continuity = _melodic_continuity(notes)
    lead_name = _contains_any(track.name, _LEAD_WORDS)
    bass_name = _contains_any(track.name, _BASS_WORDS)
    support_name = _contains_any(track.name, _SUPPORT_WORDS)
    program = describe_program(track.primary_program)
    explicit_musical_name = lead_name or bass_name or support_name
    rejected = (
        track.is_percussion_only
        or _contains_any(track.name, _NOISE_WORDS)
        or bool(program and program.noise_bias >= 4.0 and not explicit_musical_name)
    )
    # GM programs are soft evidence.  Names and the actual performed note shape
    # stay stronger, because many exported MIDIs have stale/incorrect patches.
    gm_lead = program.lead_bias if program else 0.0
    gm_support = program.support_bias if program else 0.0
    gm_bass = program.bass_bias if program else 0.0
    gm_noise = program.noise_bias if program else 0.0

    attack_monophony = 1.0 - analysis.chord_onset_ratio
    overlap_monophony = 1.0 - min(1.0, analysis.overlap_ratio)
    monophony = 0.75 * attack_monophony + 0.25 * overlap_monophony
    register_fit = max(0.0, 1.5 - abs(centre - 67.0) / 16.0)
    melody_score = (
        (4.0 if lead_name else 0.0)
        - (3.0 if bass_name else 0.0)
        - (1.5 if support_name else 0.0)
        + 2.4 * monophony
        + 1.4 * continuity
        + register_fit
        + activity * 0.8
        + coverage * 0.4
        + gm_lead
        - gm_noise
        - (8.0 if rejected else 0.0)
    )
    support_score = (
        (4.0 if support_name else 0.0)
        + 4.0 * analysis.chord_onset_ratio
        + max(0.0, analysis.sounding_polyphony_p95 - 1) * 0.35
        + activity * 0.7
        + coverage * 0.8
        + gm_support
        - gm_noise * 0.8
        - (2.0 if lead_name else 0.0)
        - (8.0 if rejected else 0.0)
    )
    bass_score = (
        (5.0 if bass_name else 0.0)
        + max(0.0, (55.0 - centre) / 5.0)
        + activity * 0.5
        + coverage * 0.35
        + gm_bass
        - gm_noise * 0.6
        - (8.0 if rejected else 0.0)
    )
    return TrackAnalysis(
        track_index=track.index,
        name=track.name,
        note_count=len(notes),
        median_pitch=float(centre),
        chord_onset_ratio=analysis.chord_onset_ratio,
        melody_score=melody_score,
        support_score=support_score,
        bass_score=bass_score,
        rejected_as_noise=rejected,
        monophony=monophony,
        activity=activity,
        coverage_ratio=coverage,
        melodic_continuity=continuity,
        program_family=program.family if program else "",
        program_role_hint=program.role_hint if program else "",
    )


def _onset_affinity(left: list[MidiNote], right: list[MidiNote], tolerance_ms: float = 45.0) -> float:
    """Measure how often two tracks participate in the same musical attacks."""

    left_starts = sorted({note.start_ms for note in left})
    right_starts = sorted({note.start_ms for note in right})
    if not left_starts or not right_starts:
        return 0.0

    def matched_fraction(source: list[float], targets: list[float]) -> float:
        matches = 0
        index = 0
        for start in source:
            # Both timelines are sorted: retain the nearest preceding target
            # and inspect its successor instead of allocating slices and doing
            # a fresh binary search for every attack.
            while index + 1 < len(targets) and targets[index + 1] <= start:
                index += 1
            if abs(targets[index] - start) <= tolerance_ms or (
                index + 1 < len(targets) and abs(targets[index + 1] - start) <= tolerance_ms
            ):
                matches += 1
        return matches / len(source)

    return math.sqrt(
        matched_fraction(left_starts, right_starts)
        * matched_fraction(right_starts, left_starts)
    )


def _temporal_overlap(left: list[MidiNote], right: list[MidiNote]) -> float:
    """Compare actually sounding time rather than the envelope around silent bars."""
    def intervals(notes: list[MidiNote]) -> list[tuple[float, float]]:
        merged: list[tuple[float, float]] = []
        for note in sorted(notes, key=lambda n: (n.start_ms, n.end_ms)):
            if note.end_ms <= note.start_ms:
                continue
            if merged and note.start_ms <= merged[-1][1]:
                merged[-1] = merged[-1][0], max(merged[-1][1], note.end_ms)
            else:
                merged.append((note.start_ms, note.end_ms))
        return merged
    a, b = intervals(left), intervals(right)
    shorter = min(sum(end - start for start, end in a), sum(end - start for start, end in b))
    if shorter <= 0:
        return 0.0
    i = j = 0
    shared = 0.0
    while i < len(a) and j < len(b):
        shared += max(0.0, min(a[i][1], b[j][1]) - max(a[i][0], b[j][0]))
        if a[i][1] <= b[j][1]:
            i += 1
        else:
            j += 1
    return shared / shorter


def _duplicate_ratio(
    left: list[MidiNote], right: list[MidiNote],
    *, left_signature: set[tuple[int, int]] | None = None,
) -> float:
    """Detect exact doubled parts without rejecting complementary harmony."""

    if not left or not right:
        return 0.0
    if left_signature is None:
        left_signature = {(round(note.start_ms / 12.0), note.pitch) for note in left}
    right_signature = {(round(note.start_ms / 12.0), note.pitch) for note in right}
    shared = len(left_signature.intersection(right_signature))
    return shared / max(1, min(len(left_signature), len(right_signature)))


def _handoff_utility(
    lead: TrackAnalysis,
    candidate: TrackAnalysis,
    lead_notes: list[MidiNote],
    candidate_notes: list[MidiNote],
) -> tuple[float, int, float]:
    """Score a track's ability to own a sustained alternate lead section."""

    starts = sorted({note.start_ms for note in candidate_notes})
    if len(starts) < 3:
        return (-1.0, len(starts), 0.0)
    gaps = [right - left for left, right in zip(starts, starts[1:], strict=False) if right > left]
    typical_gap = median(gaps) if gaps else 250.0
    split_gap = max(650.0, min(1400.0, typical_gap * 4.0))
    runs: list[list[float]] = []
    for start in starts:
        if not runs or start - runs[-1][-1] > split_gap:
            runs.append([start])
        else:
            runs[-1].append(start)
    longest = max(runs, key=lambda run: (len(run), run[-1] - run[0]))
    if len(longest) < 3:
        return (-1.0, len(longest), 0.0)

    ordered_lead = sorted(lead_notes, key=lambda note: note.start_ms)
    lead_starts = [note.start_ms for note in ordered_lead]
    lead_ends: list[float] = []
    for note in ordered_lead:
        lead_ends.append(max(note.end_ms, lead_ends[-1] if lead_ends else note.end_ms))
    shared = 0
    for start in longest:
        index = bisect.bisect_right(lead_starts, start + 60.0) - 1
        shared += int(index >= 0 and lead_ends[index] > start - 60.0)
    exclusive_ratio = 1.0 - shared / len(longest)
    span = longest[-1] - longest[0]
    sectional_strength = min(1.0, len(longest) / 6.0) * min(1.0, span / 1000.0)
    semantic_solo = _contains_any(candidate.name, ("solo",)) or (
        _contains_any(candidate.name, ("lead",))
        and _contains_any(candidate.name, ("guitar", "violin", "sax", "flute", "synth"))
    )
    register_separation = min(1.0, abs(candidate.median_pitch - lead.median_pitch) / 12.0)
    score = (
        2.2 * exclusive_ratio
        + 1.1 * sectional_strength
        + 0.8 * candidate.monophony
        + 0.6 * candidate.melodic_continuity
        + 0.25 * register_separation
        + (0.8 if semantic_solo else 0.0)
    )
    return score, len(longest), exclusive_ratio


def _recommended_tracks(
    project: MidiProject,
    tracks: list[TrackAnalysis],
    notes_by_track: dict[int, list[MidiNote]],
    settings: AppSettings | None = None,
) -> tuple[tuple[int, ...], str, int | None, tuple[tuple[int, str], ...]]:
    candidates = [track for track in tracks if track.note_count and not track.rejected_as_noise]
    rejected = {track.track_index: "Excluded: noise/effect track" for track in tracks if track.rejected_as_noise}
    if not candidates:
        return (), "No eligible non-percussion musical tracks found.", None, tuple(sorted(rejected.items()))
    recipe = ARRANGEMENT_RECIPES.get(settings.arrangement_mode) if settings else None
    manual_lead = settings.arrangement_lead_track if settings and recipe else -1
    base_layers = {"melody": 1, "adaptive_lead": 1, "melody_bass": 2}
    layers = recipe.layers if recipe else base_layers.get(settings.arrangement_mode if settings else "intelligent", 3)
    # A familiar name in an ordinary full score is not a prepared export.
    prepared = [track for track in candidates if track.name in _PREPARED_TRACK_NAMES]
    if len(prepared) == len(candidates) and manual_lead < 0 and recipe is None:
        indices = tuple(sorted(track.track_index for track in prepared))
        lead = next((track for track in prepared if track.name == "Lead Melody"), prepared[0])
        return indices, f"Recognised prepared {' + '.join(track.name for track in prepared)} tracks.", lead.track_index, tuple(
            (track.track_index, "Selected: prepared source voice") for track in prepared
        )

    def vocal_rank(track: TrackAnalysis) -> int:
        tokens = set(_name_tokens(track.name))
        if not _is_vocal_name(track.name):
            return 0
        if tokens.intersection({"backing", "background", "choir", "harmony"}):
            return 1
        return 3 if tokens.intersection({"main", "lead", "solo"}) else 2

    # A one-note cue must not outrank a whole melody just because of its label.
    # Two-note phrases are normally still too sparse, but an explicit General
    # MIDI lead-family program is useful evidence in badly labelled exports.
    # Let that evidence rescue a short phrase without making a single cue note
    # eligible to displace a real melody.
    def eligible_lead(track: TrackAnalysis) -> bool:
        onset_count = len({n.start_ms for n in notes_by_track[track.track_index]})
        strong_gm_lead = track.program_role_hint in {"lead", "lead / texture"}
        return onset_count >= 3 or (strong_gm_lead and onset_count >= 2)

    substantial = [track for track in candidates if eligible_lead(track)]
    lead_pool = substantial or candidates
    lead = next((track for track in candidates if track.track_index == manual_lead), None)
    lead = lead or max(lead_pool, key=lambda track: (
        vocal_rank(track), track.melody_score, track.melodic_continuity, track.note_count, -track.track_index,
    ))
    selected = [lead]
    reasons = dict(rejected)
    lead_reason = "explicit lead track" if lead.track_index == manual_lead else (
        "main vocal priority" if vocal_rank(lead) >= 2 else
        f"inferred melodic lead ({lead.program_family} program hint)" if lead.program_family else
        "inferred melodic lead"
    )
    reasons[lead.track_index] = "Selected: " + lead_reason
    lead_notes = notes_by_track[lead.track_index]

    @cache
    def signature(index: int) -> frozenset[tuple[int, int]]:
        return frozenset((round(n.start_ms / 12.0), n.pitch) for n in notes_by_track[index])

    @cache
    def doubled(left: int, right: int) -> bool:
        a, b = signature(left), signature(right)
        # Compare both full parts: overlapping verses alone are not duplicates.
        if not a or not b:
            return False
        for shift in (0, -12, 12, -24, 24):
            shared = len(a.intersection((at, pitch + shift) for at, pitch in b))
            if shared / max(len(a), len(b)) >= 0.9:
                return True
        return False

    def useful(track: TrackAnalysis) -> bool:
        if track in selected:
            return False
        double = next((other for other in selected if doubled(other.track_index, track.track_index)), None)
        if double:
            reasons[track.track_index] = f"Excluded: doubles {double.name}"
            return False
        return True

    @cache
    def relationship(index: int) -> tuple[float, float]:
        other = notes_by_track[index]
        return _onset_affinity(lead_notes, other), _temporal_overlap(lead_notes, other)

    def add(track: TrackAnalysis, role: str) -> None:
        selected.append(track)
        reasons[track.track_index] = "Selected: " + role

    # A source handoff is independent from simultaneous support layers.
    handoff: TrackAnalysis | None = None
    if not settings or settings.arrangement_mode != "melody":
        handoffs = []
        for track in candidates:
            if not useful(track) or track.monophony < 0.62:
                continue
            if (
                _contains_any(track.name, _BASS_WORDS + _SUPPORT_WORDS)
                or track.program_role_hint in {"bass", "keys / support", "pad / support"}
            ) and not _is_vocal_name(track.name):
                continue
            if track.median_pitch < lead.median_pitch - 6 and not _contains_any(track.name, ("solo",)):
                continue
            utility, onsets, exclusive = _handoff_utility(lead, track, lead_notes, notes_by_track[track.track_index])
            if utility >= 3.6 and onsets >= 3 and exclusive >= 0.35:
                handoffs.append((utility, -track.track_index, track))
        if handoffs:
            handoff = max(handoffs, key=lambda item: item[:2])[2]
            add(handoff, "solo handoff in lead rests")

    bass: TrackAnalysis | None = None
    texture = recipe.texture if recipe else "balanced"
    if layers > 1 and texture != "choir" and not (layers == 2 and texture in {"arpeggio", "tight", "jazz"}):
        basses = [track for track in candidates if useful(track) and track.bass_score >= 3.0 and (
            _contains_any(track.name, _BASS_WORDS)
            or track.program_role_hint == "bass"
            or track.median_pitch <= lead.median_pitch - 7.0
        )]
        def bass_utility(track: TrackAnalysis) -> tuple[float, int]:
            affinity, overlap = relationship(track.track_index)
            return track.bass_score + 1.4 * affinity + 0.6 * overlap, -track.track_index
        if basses:
            best = max(basses, key=bass_utility)
            if bass_utility(best)[0] >= 3.4:
                bass = best
                add(bass, "bass foundation")

    support_slots = max(0, layers - 1 - int(bass is not None))
    for _ in range(support_slots):
        supports = [track for track in candidates if useful(track) and (
            track.support_score >= 1.6 or (texture == "choir" and _is_vocal_name(track.name))
        ) and (
            texture not in {"bass", "arpeggio", "tight", "power", "pulse", "warm", "jazz"}
            or track.median_pitch <= lead.median_pitch - 3.0
        )]
        def support_utility(track: TrackAnalysis) -> tuple[float, int]:
            affinity, overlap = relationship(track.track_index)
            role = track.support_score
            if texture == "choir" and _is_vocal_name(track.name):
                role += 5.0
            elif texture in {"pulse", "arpeggio"}:
                role += 0.8 * track.activity
            elif texture in {"warm", "wide"}:
                role += track.coverage_ratio
            elif texture in {"tight", "jazz"}:
                role += max(0.0, 1.0 - abs(track.median_pitch - lead.median_pitch) / 24.0)
            return role + 1.5 * affinity + 0.7 * overlap, -track.track_index
        best = max(supports, key=support_utility, default=None)
        if best is None:
            break
        choir = texture == "choir" and _is_vocal_name(best.name)
        if (best.support_score < 1.6 and not choir) or support_utility(best)[0] < 2.75:
            break
        add(best, "backing vocal blend" if choir else "complementary support")

    for track in candidates:
        if track.track_index not in reasons:
            useful(track)
        reasons.setdefault(track.track_index, "Excluded: lower priority for this arrangement")
    roles = [f"lead={lead.name} ({lead_reason})"]
    roles.extend(f"{('solo handoff' if track is handoff else 'bass' if track is bass else 'support')}={track.name}" for track in selected[1:])
    rationale = "Selected a relationship-aware playable set: " + ", ".join(roles) + "."
    rationale += f" {len(selected)} source tracks; {layers} arrangement layer ceiling plus eligible lead handoff."
    if vocal_rank(lead) == 0 and manual_lead < 0:
        rationale += " No named main vocal found; review the inferred lead or choose Lead track."
    return tuple(sorted(track.track_index for track in selected)), rationale, lead.track_index, tuple(sorted(reasons.items()))


def analyse_project(project: MidiProject, *, settings: AppSettings | None = None) -> ProjectAnalysis:
    notes_by_track: dict[int, list[MidiNote]] = {}
    for note in project.notes:
        if note.channel != 9:
            notes_by_track.setdefault(note.track_index, []).append(note)
    tracks = [
        _analyse_track(track, notes_by_track.get(track.index, []))
        for track in project.tracks
        if track.playable_note_count > 0
    ]
    recommended, rationale, lead, reasons = _recommended_tracks(project, tracks, notes_by_track, settings)
    selected = set(recommended)
    note_analysis = analyse_notes(note for note in project.notes if note.track_index in selected)
    return ProjectAnalysis(tuple(tracks), recommended, note_analysis, rationale, lead, reasons)


def _clamp(value: float, low: int, high: int) -> int:
    return max(low, min(high, round(value)))


def optimal_settings_for_notes(
    notes: Iterable[MidiNote],
    settings: AppSettings,
    *,
    prepared_source: bool = False,
    track_names: dict[int, str] | None = None,
) -> tuple[AppSettings, NoteAnalysis]:
    """Return a source-aware settings copy; never mutate the caller's settings."""

    source = list(notes)
    analysis = analyse_notes(source)
    optimal = replace(settings)
    optimal.normalize()
    if analysis.note_count == 0:
        return optimal, analysis

    melodic = analysis.texture == "melody"
    dense = analysis.texture == "dense"
    chordal = analysis.texture in {"chordal", "dense"}
    selected_tracks = {note.track_index for note in source if note.channel != 9}
    named_vocal = any(
        index in selected_tracks and _is_vocal_name(name)
        for index, name in (track_names or {}).items()
    )
    gm_vocal = any(
        note.channel != 9 and note.program in {52, 53, 54}
        for note in source
    )
    if melodic and analysis.track_count == 1:
        optimal.arrangement_mode = "melody"
    elif named_vocal or gm_vocal:
        optimal.arrangement_mode = "vocal_director"
    else:
        # Duration-aware lead/support budgeting is materially better than the
        # legacy onset-only intelligent arranger for game playback.
        optimal.arrangement_mode = "chamber_director"
    optimal.chord_recognition_mode = "auto"
    optimal.ignore_percussion = True
    if melodic:
        optimal.mapping_mode = "match3_adaptive"
    elif dense:
        optimal.mapping_mode = "fold_smart"
    else:
        optimal.mapping_mode = "smart3_harmonic"
    optimal.max_polyphony = 1 if melodic else (2 if dense else 3 if chordal else 2)
    if melodic:
        optimal.chord_spread_ms = 0
    else:
        stagger_from_pulse = _clamp(analysis.median_onset_gap_ms * 0.04, 6, 12)
        optimal.chord_spread_ms = min(9, stagger_from_pulse) if dense else stagger_from_pulse
    optimal.max_notes_per_second = 16 if dense else 18

    # Separate source cleanup from physical playback timing. The 10th
    # percentile prevents a handful of outliers from weakening the filter.
    if prepared_source:
        optimal.min_source_note_ms = 0
    else:
        optimal.min_source_note_ms = _clamp(analysis.short_note_p10_ms * 0.45, 25, 50)
    gap = analysis.median_onset_gap_ms or analysis.median_note_duration_ms
    optimal.min_retrigger_ms = _clamp(gap * 0.16, 25, 55)

    if analysis.median_note_duration_ms < 150:
        optimal.hold_ratio = 0.80
    elif analysis.median_note_duration_ms > 650:
        optimal.hold_ratio = 0.62
    else:
        optimal.hold_ratio = 0.72
    if chordal and analysis.overlap_ratio > 0.55:
        optimal.hold_ratio = min(optimal.hold_ratio, 0.68)
    optimal.min_hold_ms = _clamp(gap * (0.42 if melodic else 0.32), 60, 105)
    instrument = resolve_instrument_profile(optimal.target_instrument)
    optimal.max_hold_ms = _clamp(
        analysis.median_note_duration_ms * 1.8,
        min(500, instrument.max_sustain_ms),
        instrument.max_sustain_ms,
    )
    optimal.velocity_expression = 0.25 if melodic else 0.35
    optimal.key_retrigger_gap_ms = 18 if melodic else 24 if dense else 22
    optimal.modifier_release_ms = 10 if melodic else 20
    optimal.modifier_settle_ms = 20 if melodic else 30
    if melodic:
        optimal.fidelity_priority = "register"
        optimal.mapping_stability = 40
        optimal.bank_switch_budget_per_second = 8
    elif dense:
        optimal.fidelity_priority = "rhythm"
        optimal.mapping_stability = 75
        optimal.bank_switch_budget_per_second = 0
    else:
        optimal.fidelity_priority = "balanced"
        optimal.mapping_stability = 68
        optimal.bank_switch_budget_per_second = 6
    optimal.performance_preset = "optimal"
    optimal.normalize()
    return optimal, analysis
