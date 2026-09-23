import os
from dataclasses import asdict, replace
from types import SimpleNamespace

import mido
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from musical_scumme import ui


@pytest.fixture
def auto_window(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICALSCUMME_DATA_DIR", str(tmp_path / "settings"))
    app = QApplication.instance() or QApplication([])
    window = ui.MainWindow()
    yield window
    window.scheduler = None
    window.live_midi = None
    window.close()
    app.processEvents()


def _write_ensemble(path):
    midi = mido.MidiFile()
    parts = (
        ("Lead Vocals", (67, 69, 71, 69, 67, 64, 67, 69), 0),
        ("Backing Vocals", (60, 62, 64, 62, 60, 57, 60, 62), 1),
        ("Bass", (40, 40, 43, 43, 45, 45, 43, 43), 2),
        ("Piano Chords", (55, 59, 62, 59, 55, 60, 64, 60), 3),
        ("Guitar Melody", (72, 74, 76, 74, 72, 69, 72, 74), 4),
        ("Drums", (36,) * 8, 9),
    )
    for name, pitches, channel in parts:
        track = mido.MidiTrack()
        track.append(mido.MetaMessage("track_name", name=name))
        for pitch in pitches:
            track.append(mido.Message("note_on", note=pitch, velocity=90, channel=channel))
            track.append(mido.Message("note_off", note=pitch, time=420, channel=channel))
            track.append(mido.MetaMessage("marker", text="", time=60))
        midi.tracks.append(track)
    midi.tracks.append(mido.MidiTrack([mido.MetaMessage("track_name", name="Empty")]))
    midi.save(path)


def _set_arrangement(window, mode):
    window.performance_combo.setCurrentIndex(window.performance_combo.findData("custom"))
    window.arrangement_combo.setCurrentIndex(window.arrangement_combo.findData(mode))


def test_smart_auto_selection_reanalyses_current_arrangement_only_on_click(auto_window, tmp_path, monkeypatch):
    window = auto_window
    path = tmp_path / "ensemble.mid"
    _write_ensemble(path)
    window.settings.selected_tracks_by_file[str(path.resolve())] = [1, 3, 4]
    calls = []
    analyse = ui.analyse_project

    def capture_analysis(project, *, settings=None):
        calls.append(replace(settings))
        return analyse(project, settings=settings)

    monkeypatch.setattr(ui, "analyse_project", capture_analysis)
    window.load_file(str(path))
    assert window.selected_tracks() == [1, 3, 4]
    assert len(calls) == 1

    _set_arrangement(window, "vocal_spotlight")
    assert window.selected_tracks() == [1, 3, 4]
    assert len(calls) == 1
    window.auto_select_button.click()
    assert calls[-1].arrangement_mode == "vocal_spotlight"
    assert len(calls) == 2
    assert window.selected_tracks() == [0]

    _set_arrangement(window, "vocal_foundation")
    assert window.selected_tracks() == [0]
    assert len(calls) == 2
    window.auto_select_button.click()
    assert calls[-1].arrangement_mode == "vocal_foundation"
    assert len(calls) == 3
    assert window.selected_tracks() == [0, 2]
    assert window.score_analysis.rationale in window.warning_label.text()
    assert window.statusBar().currentMessage() == window.score_analysis.rationale
    for index, reason in window.score_analysis.selection_reasons:
        assert reason in window.track_table.item(index, 0).toolTip()
        assert reason in window.track_table.item(index, 3).toolTip()
    assert "Smart auto-select" in window.auto_select_button.text()


def test_smart_auto_selection_preserves_explicit_lead_and_custom_timing(auto_window, tmp_path):
    window = auto_window
    path = tmp_path / "manual-lead.mid"
    _write_ensemble(path)
    window.load_file(str(path))
    window._set_all_tracks(True)
    _set_arrangement(window, "vocal_spotlight")
    window.arrangement_lead_combo.setCurrentIndex(window.arrangement_lead_combo.findData(4))
    assert window.selected_tracks() == [0, 1, 2, 3, 4]
    window.speed_spin.setValue(1.23)
    window.spread_spin.setValue(47)
    window.key_gap_spin.setValue(31)
    window.modifier_release_spin.setValue(29)
    window._save_ui_to_settings()
    before = asdict(window.settings)
    window.plan = object()

    window.auto_select_tracks()

    assert window.selected_tracks() == [4]
    assert window.arrangement_lead_combo.currentData() == 4
    assert window.settings.arrangement_lead_track == 4
    assert window.score_analysis.lead_track_index == 4
    assert window.plan is None
    assert asdict(window.settings) == before
    assert window.speed_spin.value() == 1.23
    assert window.spread_spin.value() == 47
    assert window.key_gap_spin.value() == 31
    assert window.modifier_release_spin.value() == 29


def test_smart_auto_selection_keeps_named_performance_preset(auto_window, tmp_path):
    window = auto_window
    path = tmp_path / "safe.mid"
    _write_ensemble(path)
    window.load_file(str(path))
    window.performance_combo.setCurrentIndex(window.performance_combo.findData("scum_safe"))
    before = asdict(window.settings)
    window.auto_select_tracks()
    assert window.performance_combo.currentData() == "scum_safe"
    assert asdict(window.settings) == before


def test_saved_empty_selection_stays_empty_until_smart_auto_click(auto_window, tmp_path):
    window = auto_window
    path = tmp_path / "deliberately-empty.mid"
    _write_ensemble(path)
    window.settings.selected_tracks_by_file[str(path.resolve())] = []
    window.load_file(str(path))
    assert window.selected_tracks() == []
    assert "Restored 0 saved track choice(s)." in window.warning_label.text()
    _set_arrangement(window, "vocal_spotlight")
    assert window.selected_tracks() == []
    window.auto_select_tracks()
    assert window.selected_tracks() == [0]


def test_startup_analysis_respects_remembered_lead_before_track_combo_exists(auto_window, tmp_path):
    path = tmp_path / "remembered-lead.mid"
    _write_ensemble(path)
    ui.save_settings(replace(
        auto_window.settings,
        performance_preset="custom",
        arrangement_mode="vocal_spotlight",
        arrangement_lead_track=4,
        last_file=str(path.resolve()),
    ))
    restarted = ui.MainWindow()
    try:
        restarted._last_file_timer.stop()
        assert restarted.arrangement_lead_combo.findData(4) == -1
        restarted._load_last_file_after_startup()
        assert restarted.score_analysis.lead_track_index == 4
        assert restarted.selected_tracks() == [4]
        assert restarted.arrangement_lead_combo.currentData() == 4
        assert restarted.settings.arrangement_lead_track == 4
    finally:
        restarted.close()


@pytest.mark.parametrize("active", ["scheduler", "live_midi", "controls"])
def test_smart_auto_selection_cannot_mutate_during_output(auto_window, tmp_path, monkeypatch, active):
    window = auto_window
    path = tmp_path / "locked.mid"
    _write_ensemble(path)
    window.load_file(str(path))
    selected = window.selected_tracks()
    analysis = window.score_analysis
    plan = window.plan = object()

    def forbidden_analysis(*_args, **_kwargs):
        raise AssertionError("Track analysis must not run while output is active")

    monkeypatch.setattr(ui, "analyse_project", forbidden_analysis)
    if active == "controls":
        window._set_plan_controls_enabled(False)
        assert not window.auto_select_button.isEnabled()
    else:
        setattr(window, active, SimpleNamespace(running=True))

    window.auto_select_tracks()

    assert window.selected_tracks() == selected
    assert window.score_analysis is analysis
    assert window.plan is plan
    assert "Stop playback or live MIDI" in window.statusBar().currentMessage()


def test_smart_auto_selection_does_not_check_empty_or_percussion_tracks(auto_window, tmp_path):
    window = auto_window
    path = tmp_path / "clean.mid"
    _write_ensemble(path)
    window.load_file(str(path))
    _set_arrangement(window, "ensemble_max")
    window.polyphony_spin.setValue(6)
    window.auto_select_tracks()
    assert 5 not in window.selected_tracks()
    assert 6 not in window.selected_tracks()
    assert not (window.track_table.item(5, 0).flags() & Qt.ItemFlag.ItemIsUserCheckable)
    assert not (window.track_table.item(6, 0).flags() & Qt.ItemFlag.ItemIsUserCheckable)
