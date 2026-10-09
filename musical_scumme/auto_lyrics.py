"""Automatic lyric matching and serialized asynchronous lookup."""
from __future__ import annotations

import math
import re
import threading
import unicodedata
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from .lyric_sources import LyricChoice, search_lyrics


def _normal(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text).casefold() if c.isalnum())


def filename_metadata(path: Path) -> tuple[str, str]:
    stem = path.stem.replace("_", " ")
    # Download-site branding is not part of the song or artist name.
    source = r"(?:www\.)?midi[\s.-]*find(?:\.com)?"
    stem = re.sub(rf"(?i)[(\[]\s*{source}\s*[)\]]", " ", stem)
    stem = re.sub(rf"(?i)(?<!\w){source}(?!\w)", " ", stem)
    stem = re.sub(r"(?i)\s*(?:\((?:midi|karaoke|instrumental)\)|\[(?:midi|karaoke|instrumental)\])\s*", " ", stem)
    stem = re.sub(r"^\d{1,3}[ ._-]+", "", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" .-–—|")
    parts = re.split(r"\s+[-–—]\s+", stem, maxsplit=1)
    return (parts[1].strip(), parts[0].strip()) if len(parts) == 2 else (stem, "")


def choose_match(choices: list[LyricChoice], title: str, artist: str, duration_s: float) -> LyricChoice | None:
    title_key, artist_key = _normal(title), _normal(artist)
    matches = []
    for choice in choices:
        exact = _normal(choice.title) == title_key and (not artist_key or _normal(choice.artist) == artist_key)
        # Handles filenames like Artist_Title with no explicit separator.
        combined = not artist_key and title_key in {
            _normal(choice.artist + choice.title), _normal(choice.title + choice.artist),
        }
        if (exact or combined) and choice.lrc:
            matches.append(choice)
    if not matches or len({_normal(choice.artist) for choice in matches}) != 1:
        return None
    # Recording lengths help rank album/single versions; MIDI timing can differ.
    return min(matches, key=lambda choice: (
        abs(choice.duration - duration_s) if math.isfinite(choice.duration) and choice.duration > 0 else math.inf,
        choice.album.casefold(), choice.lrc,
    ))


def lookup_automatic(path: Path, duration_s: float) -> tuple[LyricChoice | None, str]:
    title, artist = filename_metadata(path)
    if not title:
        return None, "Could not identify the title. Use Find lyrics."
    choices = search_lyrics(title, artist, broad=not artist)
    match = choose_match(choices, title, artist, duration_s)
    if match is None and artist:
        # Some libraries use Title - Artist instead of Artist - Title.
        choices = search_lyrics(artist, title)
        match = choose_match(choices, artist, title, duration_s)
    if match is None:
        return None, "No clear timed-lyric match. Use Find lyrics to choose one."
    return match, ""


class _WorkerSignals(QObject):
    done = Signal(int, object, str)


def _lookup_worker(signals: _WorkerSignals, token: int, path: Path, duration_s: float) -> None:
    try:
        choice, message = lookup_automatic(path, duration_s)
    except Exception:
        choice, message = None, "Online lyrics unavailable. Use Find lyrics to retry or load an LRC."
    signals.done.emit(token, choice, message)


class AutoLyrics(QObject):
    result = Signal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.generation = 0
        self.pending = None
        self.running = False
        self.closed = False
        self.worker_signals = _WorkerSignals()
        self.worker_signals.done.connect(self._finished)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self._start)

    def cancel(self) -> None:
        self.generation += 1
        self.pending = None
        self.timer.stop()

    def request(self, path: Path, duration_s: float) -> None:
        self.cancel()
        if self.closed:
            return
        self.pending = (self.generation, path, duration_s)
        self.timer.start()

    def _start(self) -> None:
        if self.closed or self.running or self.pending is None:
            return
        token, path, duration_s = self.pending
        self.pending = None
        self.running = True
        threading.Thread(target=_lookup_worker, args=(self.worker_signals, token, path, duration_s),
                         daemon=True).start()

    def _finished(self, token: int, choice: LyricChoice | None, message: str) -> None:
        self.running = False
        if self.closed:
            return
        if token == self.generation:
            self.result.emit(choice, message)
        if self.pending is not None and not self.timer.isActive():
            self._start()

    def shutdown(self) -> None:
        self.closed = True
        self.cancel()
