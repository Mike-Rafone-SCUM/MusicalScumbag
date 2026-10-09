"""Source-backed karaoke lines and display timing; never keyboard events."""
from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass

from .model import MidiLyric
from .playback_sections import PlaybackSelectionResult


def _midi_lines(events: tuple[MidiLyric, ...]) -> list[MidiLyric]:
    lines = []
    text = ""
    marks = []
    joining = False
    content = [event.text for event in events if not event.text.startswith("@")]
    # Score-exported MIDI uses one word per event, hyphens for syllable joins,
    # and underscores for melisma. Other MIDI spells spaces explicitly.
    notation = any(part.rstrip().endswith(("-", "_")) for part in content)
    word_events = notation or not any(any(c.isspace() for c in part.strip("/\\\r\n")) for part in content)

    def flush():
        nonlocal text, marks, joining
        if text.strip():
            leading = len(text) - len(text.lstrip())
            words = text.strip()
            points = tuple((max(0, index - leading), at) for index, at in marks)
            lines.append(MidiLyric(marks[0][1], words, points if len(points) > 1 else ()))
        text, marks, joining = "", [], False

    for event in events:
        if event.text.startswith("@"):
            continue
        fragments = event.text.replace("\\", "\n").replace("/", "\n").replace("\r", "\n").split("\n")
        for index, fragment in enumerate(fragments):
            if index:
                flush()
            if not fragment.strip():
                continue
            continuation = word_events and fragment.rstrip().endswith("-")
            if word_events:
                fragment = fragment.replace("_", "").strip()
                leading_join = fragment.startswith("-")
                fragment = fragment.strip("-")
                if not fragment:
                    continue
                new_word = not joining and not leading_join
                gap = event.time_ms - marks[-1][1] if marks else 0
                capital_start = len(fragment) > 1 and fragment[0].isupper() and len(text.split()) >= 3
                phrase_end = bool(re.search(r"[.!?][\"']?$", text))
                if text and new_word and (len(text) + len(fragment) > 64 or len(text.split()) >= 10
                                          or gap > 4000 or (gap >= 800 and len(text.split()) >= 3)
                                          or capital_start or phrase_end):
                    flush()
                if text and new_word and not text.endswith(" "):
                    text += " "
            else:
                if marks and (len(text) >= 100 or event.time_ms - marks[-1][1] > 4000):
                    flush()
                if " " in fragment.strip() and " " in text.strip() and not text.endswith(" "):
                    flush()
            marks.append((len(text), event.time_ms))
            text += fragment
            joining = continuation
    flush()
    return lines


def _move(cue: MidiLyric, delta: float = 0, speed: float = 1, pre_roll: float = 0) -> MidiLyric:
    return MidiLyric((cue.time_ms + delta) / speed + pre_roll, cue.text,
                     tuple((index, (at + delta) / speed + pre_roll) for index, at in cue.word_times))


def lyric_cues(events: tuple[MidiLyric, ...], *, speed: float = 1.0, timed_lines: bool = False,
               pre_roll_ms: float = 0.0, selection: PlaybackSelectionResult | None = None) -> tuple[MidiLyric, ...]:
    cues = list(events) if timed_lines else _midi_lines(events)
    if not cues:
        return ()
    if selection is not None:
        selected = []
        cursor = 0.0
        for interval in selection.intervals:
            selected.append(MidiLyric(cursor, ""))
            for index, cue in enumerate(cues):
                end = cues[index + 1].time_ms if index + 1 < len(cues) else interval.end_ms
                if cue.time_ms < interval.end_ms and end > interval.start_ms:
                    moved = _move(cue, cursor - interval.start_ms)
                    selected.append(MidiLyric(max(cursor, moved.time_ms), moved.text, moved.word_times))
            cursor += interval.duration_ms
            selected.append(MidiLyric(cursor, ""))
            cursor += selection.gap_ms
        cues = selected
    return tuple(_move(cue, speed=speed, pre_roll=pre_roll_ms) for cue in cues)


@dataclass(frozen=True)
class KaraokeFrame:
    previous: str = ""
    current: str = ""
    upcoming: str = ""
    following: str = ""
    highlight: float = 0
    progress: float = 0
    countdown_ms: float = 0
    timed_words: bool = False


class LyricTimeline:
    def __init__(self, cues: tuple[MidiLyric, ...] = (), end_ms: float | None = None) -> None:
        self.cues = cues
        self.times = tuple(cue.time_ms for cue in cues)
        self.end_ms = end_ms
        self.visible = tuple(index for index, cue in enumerate(cues) if cue.text)

    def text_at(self, elapsed_ms: float) -> str:
        index = bisect_right(self.times, elapsed_ms) - 1
        return self.cues[index].text if index >= 0 else ""

    def frame_at(self, elapsed_ms: float) -> KaraokeFrame:
        index = bisect_right(self.times, elapsed_ms) - 1
        slot = bisect_right(self.visible, index)
        upcoming = self.visible[slot:slot + 2]
        previous_slot = slot - 2 if index >= 0 and self.cues[index].text else slot - 1
        previous = self.cues[self.visible[previous_slot]].text if previous_slot >= 0 else ""
        current = self.cues[index] if index >= 0 else None
        text = current.text if current else ""
        end = self.times[index + 1] if index + 1 < len(self.times) else self.end_ms
        if end is None:
            end = (current.time_ms if current else 0) + 5000
        progress = 0.0
        highlight = 0.0
        if current and text:
            progress = max(0, min(1, (elapsed_ms - current.time_ms) / max(1, end - current.time_ms)))
            highlight = len(text) * progress
            if current.word_times:
                marks = current.word_times
                position = bisect_right(tuple(at for _, at in marks), elapsed_ms) - 1
                if position < 0:
                    highlight = 0
                else:
                    char, start = marks[position]
                    next_char, finish = marks[position + 1] if position + 1 < len(marks) else (len(text), end)
                    fraction = max(0, min(1, (elapsed_ms - start) / max(1, finish - start)))
                    highlight = min(len(text), char + (next_char - char) * fraction)
        return KaraokeFrame(previous, text,
                            self.cues[upcoming[0]].text if upcoming else "",
                            self.cues[upcoming[1]].text if len(upcoming) > 1 else "",
                            highlight, progress,
                            max(0, self.times[upcoming[0]] - elapsed_ms) if not text and upcoming else 0,
                            bool(current and len(current.word_times) > 1))
