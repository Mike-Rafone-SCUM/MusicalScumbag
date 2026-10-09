from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def midi_note_name(pitch: int) -> str:
    pitch = max(0, min(127, int(pitch)))
    return f"{NOTE_NAMES[pitch % 12]}{pitch // 12 - 1}"


@dataclass(frozen=True, slots=True)
class MidiNote:
    track_index: int
    channel: int
    pitch: int
    velocity: int
    start_ms: float
    end_ms: float
    # General MIDI program active when this note began, when explicitly known.
    # None means the source file never declared a program for this channel.
    program: int | None = None

    @property
    def duration_ms(self) -> float:
        return max(0.0, self.end_ms - self.start_ms)


@dataclass(frozen=True, slots=True)
class MidiTrack:
    index: int
    name: str
    note_count: int
    min_pitch: int | None
    max_pitch: int | None
    duration_ms: float
    percussion_note_count: int = 0
    # Explicit General MIDI program changes observed on this track.  We do not
    # invent the default piano program when the file never declared one.
    programs: tuple[int, ...] = ()
    primary_program: int | None = None

    @property
    def playable_note_count(self) -> int:
        return max(0, self.note_count - self.percussion_note_count)

    @property
    def is_percussion_only(self) -> bool:
        return self.note_count > 0 and self.playable_note_count == 0

    @property
    def pitch_range_text(self) -> str:
        if self.min_pitch is None or self.max_pitch is None:
            return "—"
        return f"{midi_note_name(self.min_pitch)}–{midi_note_name(self.max_pitch)}"


@dataclass(frozen=True, slots=True)
class MidiLyric:
    time_ms: float
    text: str
    # Character offset and absolute source timestamp for timed words/syllables.
    word_times: tuple[tuple[int, float], ...] = ()


@dataclass(slots=True)
class MidiProject:
    path: Path
    ticks_per_beat: int
    tracks: list[MidiTrack]
    notes: list[MidiNote]
    duration_ms: float
    first_bpm: float
    warnings: tuple[str, ...] = ()
    lyrics: tuple[MidiLyric, ...] = ()

    def notes_for_tracks(self, selected_tracks: Iterable[int]) -> list[MidiNote]:
        selected = set(int(i) for i in selected_tracks)
        return [n for n in self.notes if n.track_index in selected]


@dataclass(frozen=True, slots=True)
class KeyBindingProfile:
    name: str
    description: str
    base_notes: tuple[str, ...]
    octave_down: str = "LCTRL"
    octave_up: str = "LSHIFT"

    def __post_init__(self) -> None:
        if len(self.base_notes) != 13:
            raise ValueError("A SCUM profile must define 13 base-note keys (C through high C).")

    def key_for_base_pitch(self, base_pitch: int) -> str:
        if not 60 <= base_pitch <= 72:
            raise ValueError(f"Base pitch must be C4..C5, got {base_pitch}")
        return self.base_notes[base_pitch - 60]


@dataclass(frozen=True, slots=True)
class PlannedNote:
    source_pitch: int
    mapped_pitch: int
    base_pitch: int
    modifier: int  # -1 = octave down, 0 = base, +1 = octave up
    key: str
    velocity: int
    start_ms: float
    end_ms: float
    score_group: int = 0
    voice_index: int = 0
    mapping_reason: str = ""


@dataclass(frozen=True, slots=True)
class KeyEvent:
    at_ms: float
    action: str  # down | up
    key: str
    reason: str = ""


@dataclass(slots=True)
class PlaybackPlan:
    events: list[KeyEvent]
    planned_notes: list[PlannedNote]
    source_notes: int
    retained_notes: int
    dropped_notes: int
    duration_ms: float
    warnings: list[str] = field(default_factory=list)
    diagnostics: dict[str, int | float | str] = field(default_factory=dict)

    @property
    def event_count(self) -> int:
        return len(self.events)
