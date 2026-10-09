import os
import threading
from pathlib import Path

import mido
import pytest

from musical_scumme import auto_lyrics
from musical_scumme.config import AppSettings, load_settings, save_settings
from musical_scumme.lyric_sources import LyricChoice, load_saved_lyrics
from musical_scumme.model import MidiLyric, MidiNote


def choice(title="Song", artist="Artist", duration=180):
    return LyricChoice(title, artist, "Album", duration, "[00:01]First\n[00:02]Second")


@pytest.mark.parametrize("filename,expected", [
    ("01 - Artist - Song (MIDI).mid", ("Song", "Artist")),
    ("Artist_-_Song.mid", ("Song", "Artist")),
    ("Song [karaoke].mid", ("Song", "")),
    ("Artist - Song - MIDI Find.mid", ("Song", "Artist")),
    ("MIDI Find - Artist - Song.mid", ("Song", "Artist")),
    ("Artist_-_Song_(midi_find.com).mid", ("Song", "Artist")),
    ("Song [www.midifind.com].mid", ("Song", "")),
    ("Artist - Song midifind.mid", ("Song", "Artist")),
    ("Artist - Song (Live).mid", ("Song (Live)", "Artist")),
    ("Artist - MIDI Finder.mid", ("MIDI Finder", "Artist")),
    ("Artist - MIDI.mid", ("MIDI", "Artist")),
])
def test_filename_metadata(filename, expected):
    assert auto_lyrics.filename_metadata(Path(filename)) == expected


def test_branded_filename_lookup_and_dialog(app, monkeypatch):
    from musical_scumme.lyrics_dialog import LyricsDialog
    calls = []
    def search(title, artist, **kwargs):
        calls.append((title, artist))
        return [choice()]
    monkeypatch.setattr(auto_lyrics, "search_lyrics", search)
    path = Path("01 - Artist - Song - MIDI Find.mid")
    assert auto_lyrics.lookup_automatic(path, 180) == (choice(), "")
    assert calls == [("Song", "Artist")]
    dialog = LyricsDialog(path)
    try:
        assert dialog.title_edit.text() == "Song"
        assert dialog.artist_edit.text() == "Artist"
    finally:
        dialog.close()


def test_matching_rejects_ambiguous_artists_and_prefers_duration():
    first, second = choice(duration=180), choice(duration=230)
    assert auto_lyrics.choose_match([first, second], "Song", "Artist", 228) is second
    assert auto_lyrics.choose_match([first, choice(artist="Other")], "Song", "", 180) is None
    assert auto_lyrics.choose_match([first], "Song live", "Artist", 180) is None
    assert auto_lyrics.choose_match([first], "Artist Song", "", 180) is first
    assert auto_lyrics.choose_match([first], "Song", "Wrong", 180) is None


def test_lookup_reversed_filename_and_broad_query(monkeypatch):
    calls = []
    def search(title, artist, **kwargs):
        calls.append((title, artist, kwargs))
        return [choice()] if (title, artist) in {("Song", "Artist"), ("Artist Song", "")} else []
    monkeypatch.setattr(auto_lyrics, "search_lyrics", search)
    result, message = auto_lyrics.lookup_automatic(Path("Song - Artist.mid"), 180)
    assert result == choice() and not message
    assert len(calls) == 2
    result, _ = auto_lyrics.lookup_automatic(Path("Artist_Song.mid"), 180)
    assert result == choice()
    assert calls[-1][2] == {"broad": True}


@pytest.fixture
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def wait_for(predicate):
    from PySide6.QtTest import QTest
    for _ in range(200):
        if predicate():
            return
        QTest.qWait(10)
    assert predicate()


def test_controller_serializes_latest_request_and_discards_stale(app, monkeypatch):
    gate = threading.Event()
    started = threading.Event()
    calls = []
    def lookup(path, duration):
        calls.append(path.name)
        if path.name == "one.mid":
            started.set()
            gate.wait(3)
        return choice(title=path.stem), ""
    monkeypatch.setattr(auto_lyrics, "lookup_automatic", lookup)
    controller = auto_lyrics.AutoLyrics()
    received = []
    controller.result.connect(lambda item, message: received.append(item.title))
    try:
        controller.request(Path("one.mid"), 180)
        controller.timer.stop()
        controller._start()
        wait_for(started.is_set)
        controller.request(Path("two.mid"), 180)
        controller.request(Path("three.mid"), 180)
        controller.timer.stop()
        controller._start()
        assert calls == ["one.mid"]
        gate.set()
        wait_for(lambda: len(received) == 1)
        assert received == ["three"]
        assert calls == ["one.mid", "three.mid"]
        controller.request(Path("cancelled.mid"), 180)
        controller.cancel()
        controller._start()
        assert calls == ["one.mid", "three.mid"]
    finally:
        gate.set()
        controller.shutdown()


def test_auto_preference_round_trip(tmp_path):
    assert AppSettings().auto_lyrics
    path = tmp_path / "settings.json"
    save_settings(AppSettings(auto_lyrics=False), path)
    assert load_settings(path).auto_lyrics is False


def test_loaded_midi_requests_lyrics_cache_and_embedded_skip_network(app, tmp_path, monkeypatch):
    from musical_scumme import ui
    monkeypatch.setenv("MUSICALSCUMME_DATA_DIR", str(tmp_path / "data"))
    path = tmp_path / "Artist - Song.mid"
    midi = mido.MidiFile()
    midi.tracks.append(mido.MidiTrack([
        mido.Message("note_on", note=60), mido.Message("note_off", note=60, time=480),
    ]))
    midi.save(path)
    window = ui.MainWindow()
    requests = []
    monkeypatch.setattr(window.auto_lyrics, "request", lambda *args: requests.append(args))
    try:
        window.load_file(str(path))
        assert len(requests) == 1
        assert "Finding" in window.lyric_source_status.text()
        from PySide6.QtWidgets import QDialog
        monkeypatch.setattr(ui.LyricsDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
        window._find_lyrics()
        assert len(requests) == 2  # cancelling manual lookup resumes the automatic request
        window._automatic_lyrics_ready(choice(), "")
        assert window._external_lyrics[0] == MidiLyric(1000, "First")
        assert load_saved_lyrics(tmp_path / "data", path) is not None
        window.load_file(str(path))
        assert len(requests) == 2
        window._external_lyrics = None
        window.project.lyrics = (MidiLyric(0, "Embedded"),)
        window._request_automatic_lyrics()
        assert len(requests) == 2
        window.project.lyrics = ()
        window.auto_lyrics_check.setChecked(False)
        assert window.settings.auto_lyrics is False
        window._automatic_lyrics_ready(choice(), "")
        assert window._external_lyrics is None
        assert len(requests) == 2
    finally:
        window.close()
        app.processEvents()


def test_late_lyrics_join_current_playback_position_without_restarting(app, tmp_path, monkeypatch):
    from musical_scumme import ui
    from musical_scumme.model import MidiProject
    from musical_scumme.planner import build_playback_plan
    monkeypatch.setenv("MUSICALSCUMME_DATA_DIR", str(tmp_path / "data"))
    window = ui.MainWindow()
    try:
        note = MidiNote(0, 0, 60, 100, 0, 3000)
        window.project = MidiProject(tmp_path / "song.mid", 480, [], [note], 3000, 120)
        window.plan = build_playback_plan([note], window.settings, window.settings.resolved_profile())
        window._active_playback_plan = window.plan
        window._set_compact_playback_mode(True)
        window._set_timecode(2500, 3000)
        plan_before = window.plan
        window._automatic_lyrics_ready(choice(), "")
        assert window.lyrics_label.text() == "Second"
        assert window.plan is plan_before
        assert window._lyric_elapsed_ms == 2500
    finally:
        window.close()
        app.processEvents()
