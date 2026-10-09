import json
import os
import threading
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import mido
import pytest

from musical_scumme import lyric_sources as sources
from musical_scumme.lyrics import LyricTimeline, lyric_cues
from musical_scumme.model import MidiLyric


def test_lrc_timestamps_repeated_lines_offsets_and_enhanced_tags():
    cues = sources.parse_lrc("[ar:Artist]\n[offset:+100]\n[00:02.5][01:02.050]<00:02.50>Line / one\n"
                            "[00:03]\n[00:99]Invalid", offset_ms=200)
    assert cues == (MidiLyric(2600, "Line / one", ((0, 2600),)), MidiLyric(3100, ""),
                    MidiLyric(62150, "Line / one", ((0, 62150),)))
    timeline = LyricTimeline(lyric_cues(cues, timed_lines=True, speed=2))
    assert timeline.text_at(1300) == "Line / one"
    assert timeline.text_at(1550) == ""
    assert sources.parse_lrc("plain lyrics") == ()


def test_search_encodes_query_filters_untimed_and_uses_timeout(monkeypatch):
    def fake_open(request, timeout):
        assert timeout == 15
        query = parse_qs(urlparse(request.full_url).query)
        assert query == {"track_name": ["Song & more"], "artist_name": ["Artist"]}
        return BytesIO(json.dumps([
            {"trackName": "Song", "artistName": "Artist", "duration": 120,
             "syncedLyrics": "[00:01]Line"},
            {"plainLyrics": "Untimed words"}, {"syncedLyrics": "not timed"}, None,
        ]).encode())
    monkeypatch.setattr(sources, "urlopen", fake_open)
    results = sources.search_lyrics("Song & more", "Artist")
    assert len(results) == 1
    assert results[0].duration == 120
    with pytest.raises(ValueError, match="song title"):
        sources.search_lyrics(" ", "Artist")


@pytest.mark.parametrize("payload", [b"invalid", b"{}", b"x" * (sources.MAX_LYRIC_BYTES + 1)],
                         ids=["invalid-json", "wrong-schema", "oversized"])
def test_search_rejects_invalid_or_oversized_response(monkeypatch, payload):
    monkeypatch.setattr(sources, "urlopen", lambda *args, **kwargs: BytesIO(payload))
    with pytest.raises(ValueError):
        sources.search_lyrics("Song", "")


def test_saved_lyrics_are_per_midi_and_recover_from_corrupt_cache(tmp_path):
    song = tmp_path / "song.mid"
    sources.save_lyrics(tmp_path, song, "[00:02]Line", 500, "Local")
    assert sources.load_saved_lyrics(tmp_path, song) == ("[00:02]Line", 500, "Local")
    assert sources.load_saved_lyrics(tmp_path, tmp_path / "other.mid") is None
    sources.cache_path(tmp_path, song).write_text("broken", encoding="utf-8")
    assert sources.load_saved_lyrics(tmp_path, song) is None


@pytest.fixture
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_dialog_search_is_async_and_requires_result_selection(app, monkeypatch):
    from PySide6.QtTest import QTest

    from musical_scumme import lyrics_dialog
    gate = threading.Event()
    worker_threads = []

    def fake_search(title, artist):
        worker_threads.append(threading.get_ident())
        gate.wait(2)
        return [sources.LyricChoice(title, artist, "Album", 120, "[00:01]Line")]

    monkeypatch.setattr(lyrics_dialog, "search_lyrics", fake_search)
    dialog = lyrics_dialog.LyricsDialog(Path("Artist - Song.mid"))
    try:
        dialog._search()
        assert not dialog.search_button.isEnabled()
        assert not dialog.use_button.isEnabled()
        app.processEvents()  # GUI remains usable while the network worker waits.
        gate.set()
        for _ in range(100):
            QTest.qWait(10)
            if dialog.search_button.isEnabled():
                break
        assert dialog.search_button.isEnabled()
        assert worker_threads != [threading.get_ident()]
        assert dialog.results.count() == 1
        assert not dialog.use_button.isEnabled()
        dialog.results.setCurrentRow(0)
        assert dialog.use_button.isEnabled()
        assert dialog.selected_lrc == "[00:01]Line"
    finally:
        gate.set()
        dialog.close()


def test_dialog_network_failure_and_local_bom_file(app, tmp_path):
    from musical_scumme.lyrics_dialog import LyricsDialog
    dialog = LyricsDialog(Path("song.mid"))
    dialog._search_finished([], "Network unavailable")
    assert dialog.status.text() == "Network unavailable"
    assert dialog.search_button.isEnabled()
    path = tmp_path / "song.lrc"
    path.write_text("[00:01]Line", encoding="utf-8-sig")
    dialog.load_path(path)
    assert dialog.selected_lrc == "[00:01]Line"
    assert dialog.use_button.isEnabled()
    dialog.close()


def test_window_applies_persists_and_reloads_lyrics_without_changing_midi(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QDialog

    from musical_scumme import ui

    monkeypatch.setenv("MUSICALSCUMME_DATA_DIR", str(tmp_path / "settings"))
    path = tmp_path / "song.mid"
    midi = mido.MidiFile()
    midi.tracks.append(mido.MidiTrack([
        mido.Message("note_on", note=60), mido.Message("note_off", note=60, time=480),
    ]))
    midi.save(path)
    original = path.read_bytes()
    window = ui.MainWindow()
    try:
        window.load_file(str(path))
        assert window._external_lyrics is None

        def choose(dialog):
            assert window._plan_controls_locked
            dialog.selected_lrc = "[00:01]Line"
            dialog.selected_source = "Test result"
            dialog.offset.setValue(0.5)
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(ui.LyricsDialog, "exec", choose)
        window._find_lyrics()
        assert not window._plan_controls_locked
        assert window._external_lyrics == (MidiLyric(1500, "Line"),)
        window._external_lyrics = None
        window.load_file(str(path))
        assert window._external_lyrics == (MidiLyric(1500, "Line"),)
        assert path.read_bytes() == original
        other = tmp_path / "other.mid"
        midi.save(other)
        window.load_file(str(other))
        assert window._external_lyrics is None
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("retry_after", ["120", "Mon, 01 Jan 2035 00:00:00 GMT"])
def test_rate_limit_stops_followup_requests(monkeypatch, retry_after):
    from urllib.error import HTTPError

    calls = []
    def limited(*args, **kwargs):
        calls.append(1)
        raise HTTPError("https://lrclib.net/api/search", 429, "Too many requests",
                        {"Retry-After": retry_after}, None)
    monkeypatch.setattr(sources, "urlopen", limited)
    monkeypatch.setattr(sources, "_retry_after_until", 0)
    monkeypatch.setattr(sources, "_last_request_at", 0)
    with pytest.raises(HTTPError):
        sources.search_lyrics("Song", "Artist")
    with pytest.raises(ValueError, match="rate limit"):
        sources.search_lyrics("Another", "Artist")
    assert len(calls) == 1
