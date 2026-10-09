import os

import mido
import pytest

from musical_scumme.lyrics import LyricTimeline, lyric_cues
from musical_scumme.midi_engine import load_midi
from musical_scumme.model import MidiLyric
from musical_scumme.playback_sections import PlaybackInterval, PlaybackSelectionResult


def test_import_lyrics_uses_global_tempo_and_preserves_source(tmp_path):
    path = tmp_path / "lyrics.mid"
    midi = mido.MidiFile(ticks_per_beat=480)
    midi.tracks.append(mido.MidiTrack([
        mido.MetaMessage("set_tempo", tempo=500000),
        mido.MetaMessage("set_tempo", tempo=1000000, time=480),
    ]))
    midi.tracks.append(mido.MidiTrack([
        mido.MetaMessage("lyrics", text="Hello ", time=480),
        mido.MetaMessage("lyrics", text="world", time=480),
    ]))
    midi.save(path)
    before = path.read_bytes()
    project = load_midi(path)
    assert project.lyrics == (MidiLyric(500, "Hello "), MidiLyric(1500, "world"))
    assert path.read_bytes() == before


@pytest.mark.parametrize("karaoke", [False, True])
def test_text_metadata_is_only_used_for_identified_karaoke(tmp_path, karaoke):
    midi = mido.MidiFile()
    track = mido.MidiTrack()
    if karaoke:
        track.append(mido.MetaMessage("text", text="@KMIDI KARAOKE FILE"))
    track.append(mido.MetaMessage("text", text="/Hello"))
    midi.tracks.append(track)
    path = tmp_path / "text.mid"
    midi.save(path)
    assert bool(load_midi(path).lyrics) is karaoke


def test_syllables_lines_speed_preroll_and_seek():
    timeline = LyricTimeline(lyric_cues((
        MidiLyric(0, "@TTitle"), MidiLyric(100, "Hel"),
        MidiLyric(200, "lo "), MidiLyric(300, "world"),
        MidiLyric(400, "/Next line"),
    ), speed=2, pre_roll_ms=20))
    assert timeline.text_at(69) == ""
    assert timeline.text_at(70) == "Hello world"
    assert timeline.frame_at(70).highlight == 0
    assert timeline.frame_at(120).highlight == 3
    assert timeline.text_at(170) == "Hello world"
    assert timeline.text_at(220) == "Next line"
    assert timeline.text_at(120) == "Hello world"
    assert timeline.text_at(0) == ""  # loop/restart


def test_sections_remove_omitted_lyrics_and_clear_gaps():
    selection = PlaybackSelectionResult(
        (), (PlaybackInterval(100, 300), PlaybackInterval(500, 700)),
        0, 0, 0, 700, 500, 2, 0, 100,
    )
    timeline = LyricTimeline(lyric_cues((
        MidiLyric(100, "/First"), MidiLyric(300, "/Omitted"),
        MidiLyric(500, "/Second"),
    ), selection=selection, speed=2))
    assert timeline.text_at(0) == "First"
    assert timeline.text_at(100) == ""
    assert timeline.text_at(150) == "Second"
    assert timeline.text_at(250) == ""


def test_empty_lyrics_stay_empty_with_sections():
    selection = PlaybackSelectionResult((), (PlaybackInterval(0, 100),), 0, 0, 0, 100, 100, 1, 0, 0)
    assert lyric_cues((), selection=selection) == ()


def test_collapsible_player_lyrics_follow_timecode(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from musical_scumme import ui

    monkeypatch.setenv("MUSICALSCUMME_DATA_DIR", str(tmp_path / "settings"))
    app = QApplication.instance() or QApplication([])
    window = ui.MainWindow()
    try:
        assert window.lyrics_panel.isHidden()
        window._lyric_timeline = LyricTimeline(lyric_cues((
            MidiLyric(100, "<Hello>"), MidiLyric(200, "/Goodbye"),
        )))
        window._set_compact_playback_mode(True)
        app.processEvents()
        assert not window.lyrics_panel.isHidden()
        assert window.lyrics_label.isHidden()
        window.lyrics_toggle.click()
        assert not window.lyrics_label.isHidden()
        assert window.lyrics_label.textFormat() == Qt.TextFormat.PlainText
        window._set_timecode(100, 1000)
        assert window.lyrics_label.text() == "<Hello>"
        window._set_timecode(200, 1000)
        assert window.lyrics_label.text() == "Goodbye"
        window.lyrics_toggle.click()
        window._set_timecode(100, 1000)
        window.lyrics_toggle.click()
        assert window.lyrics_label.text() == "<Hello>"
        window._set_timecode(0, 1000)
        assert window.lyrics_label.text() == "Get ready"
        window._set_compact_playback_mode(False)
        assert window.lyrics_panel.isHidden()
        window._lyric_timeline = LyricTimeline()
        window._update_lyrics(0)
        assert window.lyrics_label.text() == "No lyrics loaded. Stop playback and choose Find lyrics."
    finally:
        window.scheduler = None
        window.close()
        app.processEvents()


def test_start_playback_builds_fresh_lyrics_from_active_plan(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from musical_scumme import ui
    from musical_scumme.model import MidiNote, MidiProject
    from musical_scumme.planner import build_playback_plan

    class Scheduler:
        running = False

        def __init__(self, *args, **kwargs):
            pass

        def start(self, *args, **kwargs):
            pass

    monkeypatch.setenv("MUSICALSCUMME_DATA_DIR", str(tmp_path / "settings"))
    monkeypatch.setattr(ui, "PlaybackScheduler", Scheduler)
    app = QApplication.instance() or QApplication([])
    window = ui.MainWindow()
    try:
        monkeypatch.setattr(window, "_save_ui_to_settings", lambda: None)
        window.settings.input_mode = "dry_run"
        window.settings.speed = 2
        note = MidiNote(0, 0, 48, 100, 1000, 1500)
        window.project = MidiProject(tmp_path / "song.mid", 480, [], [note], 1500, 120,
                                     lyrics=(MidiLyric(1000, "Hello"),))
        plan = build_playback_plan([note], window.settings, window.settings.resolved_profile())
        window.plan = plan
        window._start_playback(plan, 0)
        taps = plan.diagnostics["initial_bank_taps"]
        preroll = (window.settings.modifier_release_ms + taps * (
            plan.diagnostics["octave_tap_hold_ms"] + window.settings.modifier_settle_ms
        )) if taps else 0
        assert window._lyric_timeline.cues == (MidiLyric(500 + preroll, "Hello"),)
        window._set_timecode(500 + preroll, plan.duration_ms)
        assert window.lyrics_label.text() == "Hello"
        window._set_plan_controls_enabled(True)
        test_plan = build_playback_plan([note], window.settings, window.settings.resolved_profile())
        window._start_playback(test_plan, 0)
        assert not window._lyric_timeline.cues  # test-note playback cannot reuse song lyrics
    finally:
        window.scheduler = None
        window.close()
        app.processEvents()
