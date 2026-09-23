from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from typing import Any, Iterable

from .model import MidiNote

SECTION_MODES = {"include", "omit"}


@dataclass(frozen=True, slots=True)
class PlaybackSection:
    mode: str
    start_ms: float
    end_ms: float
    label: str = ""

    def __post_init__(self) -> None:
        if self.mode not in SECTION_MODES:
            raise ValueError(f"Unsupported playback section mode: {self.mode}")
        if not math.isfinite(self.start_ms) or not math.isfinite(self.end_ms):
            raise ValueError("Playback section times must be finite.")
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("Playback section end must be later than its non-negative start.")


@dataclass(frozen=True, slots=True)
class PlaybackInterval:
    start_ms: float
    end_ms: float

    @property
    def duration_ms(self) -> float:
        return max(0.0, self.end_ms - self.start_ms)


@dataclass(frozen=True, slots=True)
class PlaybackSelectionResult:
    notes: tuple[MidiNote, ...]
    intervals: tuple[PlaybackInterval, ...]
    original_notes: int
    dropped_source_notes: int
    clipped_source_notes: int
    source_span_ms: float
    output_duration_ms: float
    include_sections: int
    omit_sections: int
    gap_ms: int


def format_timecode(milliseconds: float) -> str:
    total_ms = max(0, round(milliseconds))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}.{millis:03d}"
    return f"{minutes}:{seconds:02d}.{millis:03d}"


def section_to_dict(section: PlaybackSection) -> dict[str, Any]:
    return {
        "mode": section.mode,
        "start_ms": round(section.start_ms, 3),
        "end_ms": round(section.end_ms, 3),
        "label": section.label,
    }


def sections_from_dicts(values: object, duration_ms: float) -> list[PlaybackSection]:
    if not isinstance(values, list):
        return []
    sections: list[PlaybackSection] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        try:
            start = max(0.0, min(float(duration_ms), float(value["start_ms"])))
            end = max(0.0, min(float(duration_ms), float(value["end_ms"])))
            section = PlaybackSection(
                mode=str(value["mode"]),
                start_ms=start,
                end_ms=end,
                label=str(value.get("label", "")).strip(),
            )
        except (KeyError, TypeError, ValueError):
            continue
        sections.append(section)
    return sections


def _merge_intervals(intervals: Iterable[PlaybackInterval]) -> list[PlaybackInterval]:
    ordered = sorted(intervals, key=lambda interval: (interval.start_ms, interval.end_ms))
    if not ordered:
        return []
    merged = [ordered[0]]
    for interval in ordered[1:]:
        previous = merged[-1]
        if interval.start_ms <= previous.end_ms:
            merged[-1] = PlaybackInterval(previous.start_ms, max(previous.end_ms, interval.end_ms))
        else:
            merged.append(interval)
    return merged


def resolve_playback_intervals(
    duration_ms: float,
    sections: Iterable[PlaybackSection],
) -> tuple[PlaybackInterval, ...]:
    duration = max(0.0, float(duration_ms))
    if duration <= 0:
        return ()
    valid: list[PlaybackSection] = []
    for section in sections:
        start = max(0.0, min(duration, section.start_ms))
        end = max(0.0, min(duration, section.end_ms))
        if end > start:
            valid.append(PlaybackSection(section.mode, start, end, section.label))

    includes = _merge_intervals(
        PlaybackInterval(section.start_ms, section.end_ms)
        for section in valid
        if section.mode == "include"
    )
    omits = _merge_intervals(
        PlaybackInterval(section.start_ms, section.end_ms)
        for section in valid
        if section.mode == "omit"
    )
    base = includes or [PlaybackInterval(0.0, duration)]
    if not omits:
        return tuple(base)

    result: list[PlaybackInterval] = []
    for interval in base:
        cursor = interval.start_ms
        for omission in omits:
            if omission.end_ms <= cursor:
                continue
            if omission.start_ms >= interval.end_ms:
                break
            if omission.start_ms > cursor:
                result.append(PlaybackInterval(cursor, min(omission.start_ms, interval.end_ms)))
            cursor = max(cursor, omission.end_ms)
            if cursor >= interval.end_ms:
                break
        if cursor < interval.end_ms:
            result.append(PlaybackInterval(cursor, interval.end_ms))
    return tuple(interval for interval in result if interval.duration_ms > 0)


def apply_playback_sections(
    notes: Iterable[MidiNote],
    sections: Iterable[PlaybackSection],
    *,
    source_duration_ms: float,
    gap_ms: int = 500,
) -> PlaybackSelectionResult:
    source = sorted(notes, key=lambda note: (note.start_ms, note.track_index, note.pitch, note.end_ms))
    section_list = list(sections)
    intervals = resolve_playback_intervals(source_duration_ms, section_list)
    gap = max(0, min(5000, int(gap_ms)))
    if not intervals:
        return PlaybackSelectionResult(
            notes=(),
            intervals=(),
            original_notes=len(source),
            dropped_source_notes=len(source),
            clipped_source_notes=0,
            source_span_ms=0.0,
            output_duration_ms=0.0,
            include_sections=sum(section.mode == "include" for section in section_list),
            omit_sections=sum(section.mode == "omit" for section in section_list),
            gap_ms=gap,
        )

    offsets: list[float] = []
    output_cursor = 0.0
    for index, interval in enumerate(intervals):
        offsets.append(output_cursor)
        output_cursor += interval.duration_ms
        if index + 1 < len(intervals):
            output_cursor += gap

    interval_ends = [interval.end_ms for interval in intervals]
    selected: list[MidiNote] = []
    dropped = 0
    clipped = 0
    for note in source:
        interval_index = bisect.bisect_right(interval_ends, note.start_ms)
        fragments = 0
        note_was_clipped = False
        while interval_index < len(intervals):
            interval = intervals[interval_index]
            if interval.start_ms >= note.end_ms:
                break
            if note.end_ms > interval.start_ms and note.start_ms < interval.end_ms:
                clipped_start = max(note.start_ms, interval.start_ms)
                clipped_end = min(note.end_ms, interval.end_ms)
                if clipped_end > clipped_start:
                    output_start = offsets[interval_index] + clipped_start - interval.start_ms
                    output_end = offsets[interval_index] + clipped_end - interval.start_ms
                    selected.append(
                        MidiNote(
                            track_index=note.track_index,
                            channel=note.channel,
                            pitch=note.pitch,
                            velocity=note.velocity,
                            start_ms=output_start,
                            end_ms=output_end,
                            program=note.program,
                        )
                    )
                    fragments += 1
                    note_was_clipped |= clipped_start != note.start_ms or clipped_end != note.end_ms
            interval_index += 1
        if not fragments:
            dropped += 1
        elif note_was_clipped or fragments > 1:
            clipped += 1

    selected.sort(key=lambda note: (note.start_ms, note.track_index, note.pitch, note.end_ms))
    return PlaybackSelectionResult(
        notes=tuple(selected),
        intervals=intervals,
        original_notes=len(source),
        dropped_source_notes=dropped,
        clipped_source_notes=clipped,
        source_span_ms=sum(interval.duration_ms for interval in intervals),
        output_duration_ms=output_cursor,
        include_sections=sum(section.mode == "include" for section in section_list),
        omit_sections=sum(section.mode == "omit" for section in section_list),
        gap_ms=gap,
    )
