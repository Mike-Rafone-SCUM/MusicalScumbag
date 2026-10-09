import os
from types import SimpleNamespace

import mido
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from musical_scumme import ui
from musical_scumme.input_backend import DryRunBackend
from musical_scumme.karaoke_view import KaraokeView
from musical_scumme.lyrics import LyricTimeline, lyric_cues


@pytest.fixture
def restored_window(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICALSCUMME_DATA_DIR", str(tmp_path / "settings"))
    monkeypatch.setattr(ui, "create_backend", lambda _mode: DryRunBackend())
    app = QApplication.instance() or QApplication([])
    window = ui.MainWindow(midi_provider=SimpleNamespace(input_devices=lambda: ()))
    window.hotkey_timer.stop()
    window.focus_timer.stop()
    window._last_file_timer.stop()
    yield window
    window.scheduler = None
    window.live_midi = None
    window.close()
    app.processEvents()


def _choose(combo, value):
    index = combo.findData(value)
    assert index >= 0
    combo.setCurrentIndex(index)


def _cover_midi(path):
    midi = mido.MidiFile()
    for channel, (name, program, pitches) in enumerate((
        ("Vocals", 53, (67, 69, 71, 67)),
        ("Bass", 33, (48, 50, 52, 48)),
        ("Rhythm guitar", 25, (60, 62, 64, 60)),
    )):
        track = mido.MidiTrack([
            mido.MetaMessage("track_name", name=name),
            mido.Message("program_change", program=program, channel=channel),
        ])
        if channel == 0:
            track.append(mido.MetaMessage("lyrics", text="Cover lyrics"))
        for pitch in pitches:
            track.append(mido.Message("note_on", note=pitch, velocity=90, channel=channel))
            track.append(mido.Message("note_off", note=pitch, time=320, channel=channel))
            track.append(mido.MetaMessage("marker", text="", time=160))
        midi.tracks.append(track)
    midi.save(path)


@pytest.mark.parametrize("mode", ["cover_song", "cover_riff"])
@pytest.mark.parametrize("strength", [0, 65], ids=["Fluid-off", "Flowing"])
def test_both_cover_modes_prepare_with_fluid_control_and_preserve_source(restored_window, tmp_path, mode, strength):
    window = restored_window
    path = tmp_path / "cover.mid"
    _cover_midi(path)
    source_bytes = path.read_bytes()
    window.load_file(str(path))
    window._set_all_tracks(True)
    window._set_ui_mode("advanced")
    _choose(window.arrangement_combo, mode)
    _choose(window.arrangement_lead_combo, 0)
    _choose(window.simple_fluid_phrasing_combo, strength)

    assert window.performance_combo.currentData() == "custom"
    assert window.fluid_phrasing_combo.currentData() == strength
    assert window.prepare_plan()

    assert window.settings.arrangement_mode == mode
    assert window.settings.arrangement_lead_track == 0
    assert window.settings.fluid_phrasing == strength
    assert window.plan.events
    assert all(event.key != "W" for event in window.plan.events)
    assert any("Cover source layers" in warning for warning in window.plan.warnings)
    assert ("Fluid phrasing · Flowing (65%)" in window.summary_label.text()) == bool(strength)
    assert path.read_bytes() == source_bytes


@pytest.mark.parametrize("ui_mode", ["simple", "advanced"])
def test_lyrics_karaoke_and_audio_tools_survive_fluid_ui_merge(restored_window, tmp_path, monkeypatch, ui_mode):
    window = restored_window
    path = tmp_path / "cover.mid"
    _cover_midi(path)
    window.load_file(str(path))
    window._set_ui_mode(ui_mode)

    assert not window.find_lyrics_button.isHidden()
    assert window.find_lyrics_button.isEnabled()
    assert not window.auto_lyrics_check.isHidden()
    assert isinstance(window.karaoke_view, KaraokeView)
    assert all(action in window.file_menu.actions() and action.isEnabled() for action in (
        window.song_action, window.audio_action, window.separate_action,
    ))

    dialogs = []

    class CancelledDialog:
        processed_path = None
        converted_path = None

        def __init__(self, _parent):
            dialogs.append(self)

        def set_input_path(self, source):
            self.source = source

        def exec(self):
            return ui.QDialog.DialogCode.Rejected

    monkeypatch.setattr(ui, "SongTransposerDialog", CancelledDialog)
    monkeypatch.setattr(ui, "AudioConvertDialog", CancelledDialog)
    window.song_action.trigger()
    window.audio_action.trigger()
    window.separate_action.trigger()
    assert len(dialogs) == 3
    assert dialogs[0].source == str(path)

    window._lyric_timeline = LyricTimeline(lyric_cues(window.project.lyrics))
    window._set_compact_playback_mode(True)
    window.lyrics_toggle.click()
    window._set_timecode(0, window.project.duration_ms)
    assert not window.lyrics_panel.isHidden()
    assert not window.karaoke_view.isHidden()
    assert window.lyrics_label.text() == "Cover lyrics"
    window._set_compact_playback_mode(False)
