"""Deterministic MIDI layer hints for cover arranging; no playback dependencies."""

import re
from collections import Counter, defaultdict
from statistics import median

from .model import MidiNote


def infer_cover_layers(notes: list[MidiNote], primary: int, names: dict[int, str]) -> dict[int, str]:
    """Use names and articulation, never claim to recover a missing vocal part.

    A track is a source pool, not necessarily a single voice. The arranger still
    selects individual source notes within each pool and budgets held voices.
    """
    tracks: dict[int, list[MidiNote]] = defaultdict(list)
    for note in notes:
        tracks[note.track_index].append(note)
    lead_pitch = median(n.pitch for n in tracks[primary])
    roles = {}
    for track, part in sorted(tracks.items()):
        tokens = set(re.findall(r"[a-z0-9]+", names.get(track, "").casefold()))
        onsets = sorted({n.start_ms for n in part})
        gaps = [b - a for a, b in zip(onsets, onsets[1:], strict=False)]
        articulated = len(gaps) >= 3 and median(n.duration_ms for n in part) <= 1.25 * median(gaps)
        programs = Counter(n.program for n in part if n.program is not None)
        program = max(programs, key=lambda p: (programs[p], -p)) if programs else None
        guitar = bool(tokens & {"guitar", "guitarra"}) or program in range(24, 32)
        if track == primary:
            role = "lead"
        elif tokens & {"bass", "contrabass", "baixo"} or program in range(32, 40):
            role = "bass"
        elif tokens & {"vocal", "vocals", "vox", "voice", "choir", "pad", "strings"}:
            role = "harmony"
        elif tokens & {"solo", "lead", "melody"}:
            role = "fill"
        elif guitar or tokens & {"rhythm", "riff", "arpeggio", "strum"}:
            role = "rhythm"
        elif program in range(48, 52):
            role = "harmony"
        elif median(n.pitch for n in part) <= min(55, lead_pitch - 12):
            role = "bass"
        elif articulated:
            role = "rhythm"
        else:
            role = "harmony"
        roles[track] = role
    return roles
