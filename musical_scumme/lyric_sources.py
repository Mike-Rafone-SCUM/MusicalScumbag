"""LRC parsing, bounded public lyric search and per-MIDI local persistence."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .model import MidiLyric

_REQUEST_LOCK = threading.Lock()
_last_request_at = 0.0
_retry_after_until = 0.0

MAX_LYRIC_BYTES = 2_000_000
_STAMP = re.compile(r"\[(\d+):([0-5]\d)(?:[.:](\d{1,3}))?\]")


def parse_lrc(text: str, offset_ms: float = 0) -> tuple[MidiLyric, ...]:
    offsets = re.findall(r"\[offset:([+-]?\d+)\]", text, re.IGNORECASE)
    offset = float(offsets[-1]) if offsets else 0
    cues = []
    for line in text.splitlines():
        stamps = list(_STAMP.finditer(line))
        if not stamps:
            continue
        raw = line[stamps[-1].end():]
        word_tags = list(re.finditer(r"<(\d+):([0-5]\d)(?:[.:](\d{1,3}))?>", raw))
        words = ""
        word_times = []
        cursor = 0
        for tag in word_tags:
            words += raw[cursor:tag.start()]
            minutes, seconds, fraction = tag.groups()
            at = int(minutes) * 60000 + int(seconds) * 1000 + int((fraction or "0").ljust(3, "0"))
            word_times.append((len(words), at))
            cursor = tag.end()
        words += raw[cursor:]
        leading = len(words) - len(words.lstrip())
        words = words.strip()
        first = stamps[0]
        first_at = int(first[1]) * 60000 + int(first[2]) * 1000 + int((first[3] or "0").ljust(3, "0"))
        for stamp in stamps:
            minutes, seconds, fraction = stamp.groups()
            at = int(minutes) * 60000 + int(seconds) * 1000 + int((fraction or "0").ljust(3, "0"))
            shift = at - first_at - offset + offset_ms
            marks = tuple((max(0, index - leading), max(0, time_ms + shift)) for index, time_ms in word_times)
            cues.append(MidiLyric(max(0, at - offset + offset_ms), words, marks))
    return tuple(sorted(cues, key=lambda cue: cue.time_ms))


@dataclass(frozen=True)
class LyricChoice:
    title: str
    artist: str
    album: str
    duration: float
    lrc: str


def search_lyrics(title: str, artist: str, *, broad: bool = False) -> list[LyricChoice]:
    global _last_request_at, _retry_after_until
    if not title.strip():
        raise ValueError("Enter a song title.")
    params = {"q" if broad else "track_name": title.strip()}
    if artist.strip():
        params["artist_name"] = artist.strip()
    request = Request("https://lrclib.net/api/search?" + urlencode(params),
                      headers={"User-Agent": "MusicalScumbag/3.9.1 (https://github.com/Mike-Rafone-SCUM/MusicalScumbag)",
                               "Accept": "application/json"})
    with _REQUEST_LOCK:
        if time.monotonic() < _retry_after_until:
            raise ValueError("Lyric service rate limit; try again later")
        time.sleep(max(0, 0.25 - (time.monotonic() - _last_request_at)))
        try:
            with urlopen(request, timeout=15) as response:
                data = response.read(MAX_LYRIC_BYTES + 1)
        except HTTPError as exc:
            if exc.code == 429:
                try:
                    delay = max(1, int(exc.headers.get("Retry-After", "60")))
                except (TypeError, ValueError):
                    try:
                        delay = max(1, parsedate_to_datetime(exc.headers.get("Retry-After", "")).timestamp() - time.time())
                    except (TypeError, ValueError, AttributeError, OverflowError):
                        delay = 60
                _retry_after_until = time.monotonic() + delay
            raise
        finally:
            _last_request_at = time.monotonic()
    if len(data) > MAX_LYRIC_BYTES:
        raise ValueError("Lyrics response is too large; narrow the search.")
    rows = json.loads(data)
    if not isinstance(rows, list):
        raise ValueError("The lyric service returned an unexpected response.")
    choices = []
    for row in rows[:100]:
        if not isinstance(row, dict):
            continue
        lrc = row.get("syncedLyrics")
        if not isinstance(lrc, str) or not parse_lrc(lrc):
            continue
        try:
            duration = float(row.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0
        choices.append(LyricChoice(str(row.get("trackName", "")), str(row.get("artistName", "")),
                                   str(row.get("albumName", "")), duration, lrc))
    return choices


def cache_path(root: Path, midi: Path) -> Path:
    key = hashlib.sha256(str(midi.resolve()).encode("utf-8")).hexdigest()
    return root / "lyrics" / (key + ".json")


def load_saved_lyrics(root: Path, midi: Path) -> tuple[str, float, str] | None:
    try:
        path = cache_path(root, midi)
        if path.stat().st_size > MAX_LYRIC_BYTES:
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        lrc = record["lrc"]
        offset = float(record.get("offset_ms", 0))
        if not isinstance(lrc, str) or not -600000 <= offset <= 600000 or not parse_lrc(lrc, offset):
            return None
        return lrc, offset, str(record.get("source", "Saved lyrics"))
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        return None


def save_lyrics(root: Path, midi: Path, lrc: str, offset_ms: float, source: str) -> None:
    path = cache_path(root, midi)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"lrc": lrc, "offset_ms": offset_ms, "source": source}), encoding="utf-8")
    temporary.replace(path)
