import os
from types import SimpleNamespace

import mido
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from musical_scumme.config import load_settings
from musical_scumme.ui import MainWindow


@pytest.fixture
def fluid_window(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICALSCUMME_DATA_DIR", str(tmp_path / "settings"))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    yield window
    window.scheduler = None
    window.live_midi = None
    window.close()
    app.processEvents()


def _choose(combo, value):
    index = combo.findData(value)
    assert index >= 0
    combo.setCurrentIndex(index)


def test_fluid_controls_sync_and_invalidate_without_changing_quality(fluid_window):
    window = fluid_window
    assert window.performance_combo.currentData() == "optimal"
    assert window.fluid_phrasing_combo.currentData() == 0
    assert window.simple_fluid_phrasing_combo.currentData() == 0

    window.plan = object()
    _choose(window.simple_fluid_phrasing_combo, 65)

    assert window.plan is None
    assert window.fluid_phrasing_combo.currentData() == 65
    assert window.settings.fluid_phrasing == 65
    assert window.performance_combo.currentData() == "optimal"
    assert window.settings.performance_preset == "optimal"

    window.plan = object()
    _choose(window.fluid_phrasing_combo, 35)

    assert window.plan is None
    assert window.simple_fluid_phrasing_combo.currentData() == 35
    assert window.settings.fluid_phrasing == 35
    assert window.simple_performance_combo.currentData() == "optimal"


def test_fluid_preference_remains_visible_and_selected_across_modes_and_presets(fluid_window):
    window = fluid_window
    _choose(window.simple_fluid_phrasing_combo, 100)

    window._set_ui_mode("advanced")
    _choose(window.performance_combo, "scum_safe")

    assert not window.fluid_phrasing_combo.isHidden()
    assert window.fluid_phrasing_combo.currentData() == 100
    assert window.simple_fluid_phrasing_combo.currentData() == 100
    assert window.settings.fluid_phrasing == 100
    assert window.settings.performance_preset == "scum_safe"

    window._set_ui_mode("simple")
    _choose(window.simple_performance_combo, "optimal")

    assert not window.simple_fluid_phrasing_combo.isHidden()
    assert window.fluid_phrasing_combo.currentData() == 100
    assert window.simple_fluid_phrasing_combo.currentData() == 100
    assert window.settings.performance_preset == "optimal"


def test_saved_custom_fluid_strength_round_trips_without_rounding(fluid_window):
    window = fluid_window
    window.settings.fluid_phrasing = 42

    window._load_settings_into_ui()
    window._save_ui_to_settings()

    assert window.fluid_phrasing_combo.currentData() == 42
    assert window.simple_fluid_phrasing_combo.currentData() == 42
    assert "42%" in window.fluid_phrasing_combo.currentText()
    assert load_settings().fluid_phrasing == 42
    assert load_settings().performance_preset == "optimal"
    _choose(window.performance_combo, "scum_safe")
    assert window.fluid_phrasing_combo.currentData() == 42


@pytest.mark.parametrize("active_output", ["scheduler", "live_midi"])
def test_fluid_controls_lock_with_playback_and_live_midi(fluid_window, active_output):
    window = fluid_window
    _choose(window.simple_fluid_phrasing_combo, 65)
    setattr(window, active_output, SimpleNamespace(running=True))

    window._set_plan_controls_enabled(False)

    assert not window.fluid_phrasing_combo.isEnabled()
    assert not window.simple_fluid_phrasing_combo.isEnabled()
    assert window.fluid_phrasing_combo.currentData() == 65
    assert window.simple_fluid_phrasing_combo.currentData() == 65

    setattr(window, active_output, None)
    window._set_plan_controls_enabled(True)

    assert window.fluid_phrasing_combo.isEnabled()
    assert window.simple_fluid_phrasing_combo.isEnabled()


def test_prepared_summary_reports_fluid_strength_and_diagnostics(fluid_window, tmp_path):
    window = fluid_window
    path = tmp_path / "melody.mid"
    midi = mido.MidiFile()
    track = mido.MidiTrack([mido.MetaMessage("track_name", name="Lead Melody")])
    for pitch in (60, 62, 64, 67, 65, 64):
        track.append(mido.Message("note_on", note=pitch, velocity=90))
        track.append(mido.Message("note_off", note=pitch, time=360))
        track.append(mido.MetaMessage("marker", text="", time=120))
    midi.tracks.append(track)
    midi.save(path)
    original_bytes = path.read_bytes()
    window.load_file(str(path))
    _choose(window.simple_fluid_phrasing_combo, 65)

    assert window.prepare_plan()

    assert "Fluid phrasing · Flowing (65%)" in window.summary_label.text()
    phrase_count = int(window.plan.diagnostics.get("fluid_phrase_count", 0))
    assert f"{phrase_count:,} phrase(s)" in window.summary_label.text()
    assert "Fluid phrasing:" in window.warning_label.text()
    assert "Rests and the original MIDI are preserved." in window.warning_label.text()
    assert path.read_bytes() == original_bytes
