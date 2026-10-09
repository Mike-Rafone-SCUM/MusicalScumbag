import os

import mido
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from musical_scumme.arrangement_options import ARRANGEMENT_RECIPES
from musical_scumme.ui import MainWindow


@pytest.fixture
def suite_window(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    yield window
    window.close()
    app.processEvents()


def _write_song(path):
    midi = mido.MidiFile()
    for name, pitch, channel in (("Vocals", 67, 0), ("Piano", 60, 1), ("Drums", 36, 9)):
        track = mido.MidiTrack()
        track.append(mido.MetaMessage("track_name", name=name))
        track.append(mido.Message("note_on", note=pitch, velocity=90, channel=channel))
        track.append(mido.Message("note_off", note=pitch, time=480, channel=channel))
        midi.tracks.append(track)
    midi.save(path)


def test_suite_lead_selection_persists_invalidates_and_locks(suite_window, tmp_path):
    window = suite_window
    path = tmp_path / "vocal.mid"
    _write_song(path)
    window.load_file(str(path))
    window._set_all_tracks(True)
    mode, recipe = next(iter(ARRANGEMENT_RECIPES.items()))
    window.arrangement_combo.setCurrentIndex(window.arrangement_combo.findData(mode))
    assert window.arrangement_lead_combo.isEnabled()
    assert str(recipe.layers) in window.arrangement_layers_label.text()
    assert window.arrangement_lead_combo.findData(2) == -1
    window.plan = object()
    window.arrangement_lead_combo.setCurrentIndex(window.arrangement_lead_combo.findData(0))
    assert window.plan is None
    assert window.settings.arrangement_lead_track == 0
    assert window.performance_combo.currentData() == "custom"
    window._save_ui_to_settings()
    assert window.settings.arrangement_lead_track == 0
    window._set_plan_controls_enabled(False)
    assert not window.arrangement_lead_combo.isEnabled()
    window._set_plan_controls_enabled(True)
    assert window.arrangement_lead_combo.isEnabled()
    window.load_file(str(path))
    assert window.arrangement_lead_combo.currentData() == 0
    window.arrangement_combo.setCurrentIndex(window.arrangement_combo.findData("intelligent"))
    assert not window.arrangement_lead_combo.isEnabled()


def test_suite_override_clears_on_deselection_and_different_source(suite_window, tmp_path):
    window = suite_window
    first, second = tmp_path / "first.mid", tmp_path / "second.mid"
    _write_song(first)
    _write_song(second)
    window.load_file(str(first))
    window._set_all_tracks(True)
    window.arrangement_lead_combo.setCurrentIndex(window.arrangement_lead_combo.findData(0))
    window.track_table.item(0, 0).setCheckState(Qt.Unchecked)
    assert window.arrangement_lead_combo.currentData() == -1
    assert window.settings.arrangement_lead_track == -1
    window._set_all_tracks(True)
    window.arrangement_lead_combo.setCurrentIndex(window.arrangement_lead_combo.findData(0))
    window.load_file(str(second))
    assert window.arrangement_lead_combo.currentData() == -1
    assert window.settings.arrangement_lead_track == -1


def test_cover_mode_is_available_and_prepares_with_layer_explanation(suite_window, tmp_path):
    window = suite_window
    path = tmp_path / "cover.mid"
    _write_song(path)
    window.load_file(str(path))
    window._set_all_tracks(True)
    index = window.arrangement_combo.findData("cover_song")
    assert index >= 0
    window.arrangement_combo.setCurrentIndex(index)
    assert window.performance_combo.currentData() == "custom"
    assert window.arrangement_lead_combo.isEnabled()
    window._save_ui_to_settings()
    assert window.settings.arrangement_mode == "cover_song"
    assert window.prepare_plan()
    assert any("Cover source layers" in warning for warning in window.plan.warnings)
