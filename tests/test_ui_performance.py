import os
import time
from types import SimpleNamespace

import mido
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import QApplication

from musical_scumme.config import create_default_settings
from musical_scumme.input_backend import DryRunBackend
from musical_scumme.live_midi import MidiInputDevice, MidiInputEvent
from musical_scumme.model import MidiProject, MidiTrack
from musical_scumme.ui import (
    STYLE,
    AudioConvertDialog,
    KeymapDialog,
    MainWindow,
    MappingComparisonDialog,
    SongTransposerDialog,
    _selection_is_prepared_song,
)


@pytest.fixture(autouse=True)
def isolate_live_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


def test_scum_safe_preset_is_visible_and_manual_edit_switches_to_custom(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        safe_index = window.performance_combo.findData("scum_safe")
        assert safe_index >= 0
        window.performance_combo.setCurrentIndex(safe_index)
        app.processEvents()

        assert window.polyphony_spin.value() == 2
        assert window.spread_spin.value() == 25
        assert window.min_hold_spin.value() == 110
        assert window.key_gap_spin.value() == 35
        assert window.modifier_release_spin.value() == 30
        assert window.modifier_settle_spin.value() == 45
        assert window.density_spin.value() == 12
        assert window.speed_spin.value() == 0.90

        window.spread_spin.setValue(26)
        app.processEvents()
        assert window.performance_combo.currentData() == "custom"
    finally:
        window.close()
        app.processEvents()


def test_audio_conversion_dialog_constructs_offscreen():
    app = QApplication.instance() or QApplication([])
    dialog = AudioConvertDialog()
    try:
        assert dialog.windowTitle() == "Audio to MIDI"
        assert dialog.process.parent() is dialog
        assert dialog.onset_spin.value() == 0.45
        assert dialog.frame_spin.value() == 0.30
        assert dialog.audio_min_note_spin.value() == 90
        assert dialog.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
        assert len(dialog._frameless_controller.handles) == 8
    finally:
        dialog.close()
        app.processEvents()


def test_contextual_recipe_preparation_shows_friendly_name_and_diagnostics(tmp_path):
    midi = mido.MidiFile(ticks_per_beat=480)
    midi.tracks.append(mido.MidiTrack([
        mido.MetaMessage("track_name", name="Main Lead Vocal"),
        mido.Message("note_on", note=72, velocity=90),
        mido.Message("note_off", note=72, time=960),
    ]))
    path = tmp_path / "director.mid"
    midi.save(path)
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.load_file(str(path))
        window.arrangement_combo.setCurrentIndex(window.arrangement_combo.findData("vocal_director"))
        app.processEvents()
        assert window.prepare_plan()
        assert "Next · Vocal director / 3" in window.summary_label.text()
        assert "duration-aware support" in window.warning_label.text()
        assert window.plan.diagnostics["contextual_peak_voices_before_density"] == 1
        assert window.performance_combo.currentData() == "custom"
    finally:
        window.close()
        app.processEvents()


def test_mapping_guidance_follows_selection_and_discloses_tradeoffs():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    try:
        assert {window.mapping_combo.itemData(i) for i in range(window.mapping_combo.count())} == {
            "fold_smart", "strict_auto", "smart3_harmonic", "melody3_contour", "match3_adaptive",
        }
        window.performance_combo.setCurrentIndex(window.performance_combo.findData("custom"))
        window.resize(1080, 720)
        window.show()
        for mode, expected in (
            ("melody3_contour", "Preserves playable pitches first"),
            ("strict_auto", "omitted"),
            ("smart3_harmonic", "real silence"),
            ("fold_smart", "Other octave doubles can still merge"),
        ):
            index = window.mapping_combo.findData(mode)
            window.mapping_combo.setCurrentIndex(index)
            app.processEvents()
            assert expected in window.mapping_help_label.text()
            assert window.mapping_combo.itemData(index, Qt.ItemDataRole.ToolTipRole)
        assert window.mapping_help_label.wordWrap()
        assert window.mapping_help_label.width() <= window.width() * 0.55
        assert window.mapping_help_label.accessibleName() == "Pitch mapping guidance"
    finally:
        window.close()
        app.processEvents()


def test_arrangement_guidance_and_chord_options_follow_selection():
    from musical_scumme.arrangement_options import ARRANGEMENT_OPTIONS, CHORD_RECOGNITION_MODES

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.performance_combo.setCurrentIndex(window.performance_combo.findData("custom"))
        for mode, (_, guidance) in ARRANGEMENT_OPTIONS.items():
            index = window.arrangement_combo.findData(mode)
            assert index >= 0
            window.arrangement_combo.setCurrentIndex(index)
            app.processEvents()
            assert window.arrangement_help_label.text() == guidance
            assert window.arrangement_combo.itemData(index, Qt.ItemDataRole.ToolTipRole) == guidance
            assert window.chord_recognition_combo.isEnabled() == (mode in CHORD_RECOGNITION_MODES)
            assert window.performance_combo.currentData() == "custom"
        assert window.arrangement_help_label.wordWrap()
    finally:
        window.close()
        app.processEvents()


def test_frameless_windows_cover_every_native_resize_zone():
    app = QApplication.instance() or QApplication([])
    dialog = KeymapDialog(create_default_settings())
    try:
        expected = {
            (Qt.Edge.TopEdge, Qt.CursorShape.SizeVerCursor),
            (Qt.Edge.BottomEdge, Qt.CursorShape.SizeVerCursor),
            (Qt.Edge.LeftEdge, Qt.CursorShape.SizeHorCursor),
            (Qt.Edge.RightEdge, Qt.CursorShape.SizeHorCursor),
            (Qt.Edge.TopEdge | Qt.Edge.LeftEdge, Qt.CursorShape.SizeFDiagCursor),
            (Qt.Edge.TopEdge | Qt.Edge.RightEdge, Qt.CursorShape.SizeBDiagCursor),
            (Qt.Edge.BottomEdge | Qt.Edge.LeftEdge, Qt.CursorShape.SizeBDiagCursor),
            (Qt.Edge.BottomEdge | Qt.Edge.RightEdge, Qt.CursorShape.SizeFDiagCursor),
        }
        actual = {
            (handle.edges, handle.cursor().shape())
            for handle in dialog._frameless_controller.handles
        }

        assert dialog.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
        assert actual == expected
    finally:
        dialog.close()
        app.processEvents()


def test_song_transposer_dialog_constructs_and_accepts_midi_input(tmp_path):
    app = QApplication.instance() or QApplication([])
    dialog = SongTransposerDialog()
    try:
        source = tmp_path / "rough.mid"
        midi = mido.MidiFile()
        midi.tracks.append(mido.MidiTrack())
        midi.save(source)
        dialog.set_input_path(source)
        assert dialog.windowTitle() == "Song Transposer"
        assert dialog.profile_combo.currentData() == "guitar_arpeggio"
        assert dialog.profile_combo.findData("guitar_arpeggio") >= 0
        assert dialog.onset_spin.value() == 0.45
        assert dialog.frame_spin.value() == 0.30
        assert dialog.audio_min_note_spin.value() == 90
        assert dialog.pitch_focus_combo.currentData() == "guitar"
        assert not dialog.pitch_focus_combo.isEnabled()
        assert not dialog.raw_edit.isEnabled()
        assert dialog.output_edit.text().endswith("rough.scum-ready.mid")
        assert dialog.process_button.isEnabled()
        assert dialog.form_status_label.objectName() == "inlineGood"
        assert "source file will not be modified" in dialog.form_status_label.text()
        dialog.set_input_path(tmp_path / "rough.wav")
        assert dialog.pitch_focus_combo.isEnabled()
        assert dialog.raw_edit.isEnabled()
        assert dialog.separate_checkbox.isChecked()
        assert dialog.stem_combo.currentData() == "instrumental"
        assert dialog.stem_folder_edit.text().endswith("rough.uvr-stems")
        dialog.profile_combo.setCurrentIndex(dialog.profile_combo.findData("melody_focus"))
        assert dialog.pitch_focus_combo.currentData() == "scum"
        assert dialog.stem_combo.currentData() == "vocals"
        dialog.pitch_focus_combo.setCurrentIndex(dialog.pitch_focus_combo.findData("full"))
        dialog._pitch_focus_selected()
        dialog.profile_combo.setCurrentIndex(dialog.profile_combo.findData("guitar_arpeggio"))
        assert dialog.pitch_focus_combo.currentData() == "full"
        assert dialog.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
        assert len(dialog._frameless_controller.handles) == 8
        dialog.resize(880, 720)
        dialog.show()
        app.processEvents()
        assert dialog.width() == 880
        assert dialog.height() == 720
        assert dialog.minimumSizeHint().height() <= 720
        assert not dialog.settings_scroll.horizontalScrollBar().isVisible()
        assert dialog.settings_scroll.verticalScrollBar().isVisible()
    finally:
        dialog.close()
        app.processEvents()


def test_main_window_exposes_song_transposer():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window.song_action.text() == "Song Transposer…"
        assert window.audio_action.text() == "Convert audio to MIDI…"
        assert window.performance_combo.currentData() == "optimal"
        assert window.instrument_combo.currentData() == "guitar"
        assert window.instrument_combo.count() == 3
        assert "2,000 ms" in window.instrument_hint.text()
        window.plan = object()
        window.instrument_combo.setCurrentIndex(window.instrument_combo.findData("banjo"))
        app.processEvents()
        assert window.plan is None
        assert window.settings.target_instrument == "banjo"
        assert "1,000 ms" in window.instrument_hint.text()
        assert window.mapping_box.isHidden()
        assert window.track_table.columnCount() == 6
        assert window.track_table.horizontalHeaderItem(3).text() == "Role"
        assert window.chord_recognition_combo.currentData() == "auto"
        assert window.export_button.text() == "Score CSV"
        assert window.export_events_button.text() == "Events CSV"
        assert window.open_action.shortcut().toString() == "Ctrl+O"
        assert window.reload_action.shortcut().toString() == "Ctrl+R"
        assert window.prepare_action.shortcut().toString() == "Ctrl+P"
        assert window.focus_source_action.shortcut().toString() == "Ctrl+L"
        assert window.quick_start_action.shortcut().toString() == "F1"
        assert window.live_button.text() == "Live"
        assert window.live_mapping_combo.currentData() == "fold"
        assert window.live_polyphony_spin.value() == 3
        window.performance_combo.setCurrentIndex(window.performance_combo.findData("custom"))
        app.processEvents()
        assert not window.mapping_box.isHidden()
        assert window.fidelity_priority_combo.currentData() == "balanced"
        assert window.mapping_stability_spin.value() == 50
        assert window.bank_switch_budget_spin.value() == 0
        assert window.c_boundary_combo.currentData() == "auto"
        assert not window.restore_base_bank_check.isChecked()
        assert window.polyphony_spin.maximum() == 26
        assert window.density_spin.maximum() == 240
        assert window.spread_spin.maximum() == 250
        assert "wider experimental limits" in window.performance_hint.text()
        window.arrangement_combo.setCurrentIndex(window.arrangement_combo.findData("melody"))
        app.processEvents()
        assert not window.chord_recognition_combo.isEnabled()
    finally:
        window.close()
        app.processEvents()


def test_guided_workflow_starts_with_prerequisite_aware_actions():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window.readiness_pill.text() == "LOAD MIDI"
        assert window.readiness_pill.objectName() == "pillIdle"
        assert window.workflow_steps[0].objectName() == "workflowActive"
        assert all(step.objectName() == "workflowIdle" for step in window.workflow_steps[1:])
        assert "Open or drop" in window.workflow_hint.text()
        assert not window.tracks_box.isEnabled()
        assert not window.section_box.isEnabled()
        assert not window.prepare_button.isEnabled()
        assert not window.play_button.isEnabled()
        assert not window.export_button.isEnabled()
        assert window.file_edit.accessibleName() == "MIDI source file"
        assert window.track_table.accessibleName() == "MIDI track selection table"
        assert window.progress.accessibleName() == "Playback progress"
    finally:
        window.close()
        app.processEvents()


def test_track_filter_selection_feedback_and_ready_plan_state(tmp_path):
    source = tmp_path / "workflow.mid"
    midi = mido.MidiFile(ticks_per_beat=480)
    lead = mido.MidiTrack()
    lead.append(mido.MetaMessage("track_name", name="Lead Guitar", time=0))
    lead.append(mido.Message("note_on", note=64, velocity=100, time=0))
    lead.append(mido.Message("note_off", note=64, velocity=0, time=480))
    solo = mido.MidiTrack()
    solo.append(mido.MetaMessage("track_name", name="Solo Guitar", time=0))
    solo.append(mido.Message("note_on", note=72, velocity=105, time=480))
    solo.append(mido.Message("note_off", note=72, velocity=0, time=480))
    empty = mido.MidiTrack()
    empty.append(mido.MetaMessage("track_name", name="Empty Guide", time=0))
    midi.tracks.extend((lead, solo, empty))
    midi.save(source)

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.load_file(str(source))
        assert window.tracks_box.isEnabled()
        assert window.section_box.isEnabled()
        assert "populated selected" in window.track_selection_label.text()
        assert window.readiness_pill.text() == "PREPARE"
        assert window.workflow_steps[0].objectName() == "workflowDone"
        assert window.workflow_steps[2].objectName() == "workflowActive"
        assert window.prepare_button.isEnabled()
        assert window.play_button.isEnabled()

        window.track_filter_edit.setText("solo")
        app.processEvents()
        visible_rows = [
            row
            for row in range(window.track_table.rowCount())
            if not window.track_table.isRowHidden(row)
        ]
        assert visible_rows == [1]
        assert "1 shown" in window.track_selection_label.text()
        window.track_filter_edit.clear()

        empty_use = window.track_table.item(2, 0)
        assert not (empty_use.flags() & Qt.ItemFlag.ItemIsUserCheckable)
        before = window.track_table.item(0, 0).checkState()
        window._toggle_track_row(0, 0)
        assert window.track_table.item(0, 0).checkState() != before
        window.auto_select_tracks()
        assert window.selected_tracks()

        assert window.prepare_plan()
        assert window.readiness_pill.text() == "READY"
        assert window.readiness_pill.objectName() == "pillGood"
        assert window.workflow_steps[3].objectName() == "workflowActive"
        assert "Ready to play" in window.summary_label.text()
        assert not window.warning_label.isHidden()
        assert window.warning_label.text().startswith("• ")
    finally:
        window.close()
        app.processEvents()


def test_audio_dialog_validates_paths_inline(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "musical_scumme.ui.audio_tools_status",
        lambda: SimpleNamespace(available=True, message="Audio runtime ready"),
    )
    source = tmp_path / "clean.wav"
    source.write_bytes(b"RIFF")
    app = QApplication.instance() or QApplication([])
    dialog = AudioConvertDialog()
    try:
        assert not dialog.convert_button.isEnabled()
        dialog.input_edit.setText(str(source))
        app.processEvents()
        assert dialog.output_edit.text().endswith("clean.transcribed.mid")
        assert dialog.convert_button.isEnabled()
        assert dialog.form_status_label.objectName() == "inlineGood"

        dialog.output_edit.setText(str(tmp_path / "bad.txt"))
        app.processEvents()
        assert not dialog.convert_button.isEnabled()
        assert dialog.form_status_label.objectName() == "inlineWarn"
        assert ".mid" in dialog.form_status_label.text()
    finally:
        dialog.close()
        app.processEvents()


def test_keymap_dialog_keeps_invalid_key_names_open():
    app = QApplication.instance() or QApplication([])
    dialog = KeymapDialog(create_default_settings())
    try:
        dialog.edits[0].setText("NOT_A_KEY")
        dialog._validate_and_accept()
        assert dialog.result() == 0
        assert dialog.validation_label.objectName() == "inlineWarn"
        assert "Check the key names" in dialog.validation_label.text()

        dialog.edits[0].setText("Y")
        dialog._validate_and_accept()
        assert dialog.result() == 1
    finally:
        dialog.close()
        app.processEvents()


def test_default_window_keeps_direct_midi_workflow_and_both_panels_usable():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    try:
        window.resize(1080, 720)
        window.show()
        app.processEvents()

        left_width, settings_width = window.main_splitter.sizes()
        settings_scroll = window.main_splitter.widget(1)

        assert window.width() == 1080
        assert window.height() == 720
        assert window.minimumSizeHint().width() <= 1080
        assert window.minimumSizeHint().height() <= 720
        assert left_width >= 500
        assert settings_width >= 340
        assert not settings_scroll.horizontalScrollBar().isVisible()
        assert window.browse_button.text() == "Open MIDI\nCtrl+O"
        assert "original" in window.file_edit.placeholderText().lower()
        assert window.song_action in window.file_menu.actions()
        assert window.audio_action in window.file_menu.actions()
        assert window.centralWidget().objectName() == "hudSurface"
        assert window.centralWidget().property("compact") == "false"
        assert not window.minimize_check.isChecked()
        assert window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
        assert window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
        assert len(window._frameless_controller.handles) == 8
        assert "#53d9ff" in STYLE.lower()

        editor_geometry = window.geometry()
        window._set_compact_playback_mode(True)
        app.processEvents()
        assert window._compact_playback
        assert window.centralWidget().property("compact") == "true"
        assert window.header.property("compact") == "true"
        assert window.command_deck.property("compact") == "true"
        assert window.source_deck.isHidden()
        assert window.main_splitter.isHidden()
        assert window.menuBar().isHidden()
        assert window.pause_button.isVisible()
        assert window.stop_button.isVisible()
        assert window.width() <= 580

        window._set_compact_playback_mode(False)
        app.processEvents()
        assert not window._compact_playback
        assert window.centralWidget().property("compact") == "false"
        assert window.source_deck.isVisible()
        assert window.main_splitter.isVisible()
        assert window.height() == editor_geometry.height()
        assert window.width() >= editor_geometry.width()
    finally:
        window.close()
        app.processEvents()


def test_play_pause_hotkey_starts_or_toggles_active_playback(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    calls = []
    try:
        monkeypatch.setattr(window, "play", lambda: calls.append("play"))
        window.play_pause_hotkey()
        assert calls == ["play"]

        window.scheduler = type("RunningScheduler", (), {"running": True})()
        monkeypatch.setattr(window, "pause_resume", lambda: calls.append("pause"))
        window.play_pause_hotkey()
        assert calls == ["play", "pause"]
    finally:
        window.scheduler = None
        window.close()
        app.processEvents()


def test_seek_hotkeys_invoke_scheduler_seek():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    seek_calls = []
    try:
        mock_scheduler = type(
            "MockScheduler",
            (),
            {
                "running": True,
                "seek_by": lambda _self, delta: seek_calls.append(delta),
            },
        )()
        window.scheduler = mock_scheduler

        window.seek_forward_hotkey()
        assert seek_calls == [5000.0]

        window.seek_backward_hotkey()
        assert seek_calls == [5000.0, -5000.0]
    finally:
        window.scheduler = None
        window.close()
        app.processEvents()


def test_toggle_hold_w_auto_walk():
    from musical_scumme.input_backend import DryRunBackend

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.backend = DryRunBackend()
    try:
        assert window._w_held is False
        assert ("down", "W") not in window.backend.history

        # Toggle ON
        window.toggle_hold_w()
        assert window._w_held is True
        assert window.backend.pressed == {"W"}
        assert ("down", "W") in window.backend.history

        # Toggle OFF
        window.toggle_hold_w()
        assert window._w_held is False
        assert window.backend.pressed == set()
        assert ("up", "W") in window.backend.history
    finally:
        window.close()
        app.processEvents()



def test_prepared_song_selection_is_identified_by_exported_track_names(tmp_path):
    project = MidiProject(
        path=tmp_path / "prepared.mid",
        ticks_per_beat=480,
        tracks=[
            MidiTrack(0, "MusicalScumme Song Transposer", 0, None, None, 0),
            MidiTrack(1, "Lead Melody", 10, 48, 72, 1000),
            MidiTrack(2, "Light Support", 4, 40, 60, 1000),
        ],
        notes=[],
        duration_ms=1000,
        first_bpm=120,
    )

    assert _selection_is_prepared_song(project, [1])
    assert _selection_is_prepared_song(project, [1, 2])
    assert not _selection_is_prepared_song(project, [0, 1])


def test_track_table_invert_and_space_toggle(tmp_path):
    from PySide6.QtGui import QKeyEvent

    path = tmp_path / "multi_track.mid"
    midi = mido.MidiFile(ticks_per_beat=480)
    for idx in range(3):
        track = mido.MidiTrack()
        track.append(mido.MetaMessage("track_name", name=f"Track {idx}", time=0))
        track.append(mido.Message("note_on", note=60 + idx, velocity=100, time=0))
        track.append(mido.Message("note_off", note=60 + idx, velocity=0, time=480))
        midi.tracks.append(track)
    midi.save(path)

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.load_file(str(path))
        initial_selected = window.selected_tracks()
        assert len(initial_selected) > 0

        window.invert_tracks()
        inverted = window.selected_tracks()
        assert set(inverted) == set(range(3)) - set(initial_selected)

        # Space key toggles current row
        window.track_table.setCurrentCell(0, 0)
        before_state = window.track_table.item(0, 0).checkState()
        key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
        window._track_table_key_press(key_event)
        after_state = window.track_table.item(0, 0).checkState()
        assert before_state != after_state
    finally:
        window.close()
        app.processEvents()


def test_compact_hud_telemetry_updates(tmp_path):
    path = tmp_path / "telemetry_test.mid"
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name="Solo Lead", time=0))
    track.append(mido.Message("note_on", note=60, velocity=100, time=0))
    track.append(mido.Message("note_off", note=60, velocity=0, time=960))
    midi.tracks.append(track)
    midi.save(path)

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.load_file(str(path))
        window.prepare_plan()
        window._set_compact_playback_mode(True)

        assert "telemetry_test" in window.compact_title_label.text().lower()
        window._set_timecode(500.0, 1000.0)
        assert "00:00 / 00:01" in window.compact_timecode_label.text()

        window._set_status("Playing · loop 1")
        assert "PLAYING" in window.compact_status_badge.text()
        assert window.compact_status_badge.objectName() == "pillGood"

        window._set_status("Paused — press Resume or F9")
        assert "PAUSED" in window.compact_status_badge.text()

        window._set_status("SCUM lost focus — playback paused safely")
        assert "UNPAIRED" in window.compact_status_badge.text()
    finally:
        window.close()
        app.processEvents()



def test_main_window_prepares_and_remembers_a_specific_playback_range(tmp_path):
    path = tmp_path / "range.mid"
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name="Lead Melody", time=0))
    track.append(mido.Message("note_on", note=60, velocity=100, time=0))
    track.append(mido.Message("note_off", note=60, velocity=0, time=1920))
    midi.tracks.append(track)
    midi.save(path)

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.load_file(str(path))
        window.section_start_time.setTime(QTime(0, 0, 0, 500))
        window.section_end_time.setTime(QTime(0, 0, 1, 500))
        window.add_playback_section("include")

        assert len(window.playback_sections) == 1
        assert window.settings.recent_files == [str(path.resolve())]
        assert len(window.recent_file_actions) == 1
        assert path.name in window.recent_file_actions[0].text()
        assert window.prepare_button.text() == "Prepare selection\nCtrl+P"
        assert window.play_button.text() == "Play selection(s)\nF9"
        window.section_table.clearSelection()
        app.processEvents()
        assert not window.update_section_button.isEnabled()
        window.section_table.selectRow(0)
        app.processEvents()
        assert window.section_start_time.time().msecsSinceStartOfDay() == 500
        assert window.section_end_time.time().msecsSinceStartOfDay() == 1500
        window.section_start_time.setTime(QTime(0, 0, 0, 750))
        window.section_end_time.setTime(QTime(0, 0, 1, 750))
        window.update_playback_section()
        assert window.playback_sections[0].start_ms == 750
        assert window.playback_sections[0].end_ms == 1750
        assert window.prepare_plan()
        assert window.plan is not None
        assert window.plan.diagnostics["playback_selection_intervals"] == 1
        assert window.plan.diagnostics["playback_selection_source_span_ms"] == 1000
        assert window.plan.retained_notes == 1
        assert "Guitar preparation" in window.warning_label.text()
        assert "hard ceiling" in window.warning_label.text()
    finally:
        window.close()
        app.processEvents()

    restored = MainWindow()
    try:
        restored.load_file(str(path))
        assert len(restored.playback_sections) == 1
        assert restored.playback_sections[0].start_ms == 750
        assert restored.playback_sections[0].end_ms == 1750
        assert restored.settings.recent_files == [str(path.resolve())]
    finally:
        restored.close()
        app.processEvents()


def test_active_playback_locks_every_plan_affecting_control(monkeypatch):
    class RunningScheduler:
        running = True

        def stop(self):
            self.running = False

    def unexpected_load(_path):
        raise AssertionError("load_midi must not run during active playback")

    monkeypatch.setattr("musical_scumme.ui.load_midi", unexpected_load)
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.scheduler = RunningScheduler()
        window._set_plan_controls_enabled(False)

        for control in (
            window.file_edit,
            window.browse_button,
            window.tracks_box,
            window.section_box,
            window.compatibility_box,
            window.live_midi_box,
            window.performance_box,
            window.mapping_box,
            window.timing_box,
        ):
            assert not control.isEnabled()
        for action in (
            window.open_action,
            window.reload_action,
            window.song_action,
            window.audio_action,
            window.reset_action,
        ):
            assert not action.isEnabled()

        window.start_live_midi()
        assert "Stop current output" in window.statusBar().currentMessage()
        window.load_file("must-not-load.mid")
        assert "Stop playback" in window.statusBar().currentMessage()

        window.scheduler.running = False
        window._set_plan_controls_enabled(True)
        assert window.file_edit.isEnabled()
        assert not window.tracks_box.isEnabled()
        assert window.performance_box.isEnabled()
        assert window.open_action.isEnabled()
    finally:
        window.scheduler = None
        window.close()
        app.processEvents()


class _FakeUiMidiPort:
    def __init__(self, on_event, on_error) -> None:
        self.on_event = on_event
        self.on_error = on_error
        self.closed = False

    def emit(self, event: MidiInputEvent) -> None:
        self.on_event(event)

    def close(self) -> None:
        self.closed = True


class _FakeUiMidiProvider:
    device = MidiInputDevice(0, "HUD Keyboard", "HUD Keyboard")

    def __init__(self) -> None:
        self.port: _FakeUiMidiPort | None = None

    def input_devices(self):
        return (self.device,)

    def open_input(self, device, on_event, on_error):
        assert device == self.device
        self.port = _FakeUiMidiPort(on_event, on_error)
        return self.port


def _process_events_until(app: QApplication, predicate, timeout_s: float = 1.5) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.005)
    app.processEvents()
    assert predicate()


def test_live_midi_hud_arms_locks_routes_and_panics_safely():
    app = QApplication.instance() or QApplication([])
    provider = _FakeUiMidiProvider()
    window = MainWindow(midi_provider=provider)
    try:
        dry_run_index = window.input_combo.findData("dry_run")
        window.input_combo.setCurrentIndex(dry_run_index)
        strict_index = window.live_mapping_combo.findData("strict")
        window.live_mapping_combo.setCurrentIndex(strict_index)

        assert window.midi_input_combo.currentText() == "HUD Keyboard"
        assert window.live_button.isEnabled()
        window.start_live_midi()

        assert window._live_midi_active()
        assert "strict C4-C5" in window.live_state_label.text()
        assert not window.play_button.isEnabled()
        assert not window.live_button.isEnabled()
        assert not window.live_midi_box.isEnabled()
        assert window.stop_button.isEnabled()
        assert isinstance(window.backend, DryRunBackend)
        assert provider.port is not None
        window.play()
        assert window.scheduler is None
        assert "Disarm live MIDI" in window.statusBar().currentMessage()

        provider.port.emit(MidiInputEvent("note_on", note=60, velocity=100))
        _process_events_until(
            app,
            lambda: window.backend.pressed == {"Y"}
            and "key Y" in window.live_state_label.text(),
        )
        assert "key Y" in window.live_state_label.text()

        window.stop()
        _process_events_until(app, lambda: not window._output_busy())
        assert window.backend.pressed == set()
        assert provider.port.closed
        assert not window.play_button.isEnabled()
        assert window.live_button.isEnabled()
        assert window.live_midi_box.isEnabled()
    finally:
        window.close()
        app.processEvents()


def test_mapping_comparison_dialog_and_auto_transpose_offscreen():
    from musical_scumme.model import MidiNote

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window.auto_transpose_button is not None
        assert window.compare_mappings_button is not None

        notes = [
            MidiNote(0, 0, 60, 90, 0.0, 300.0),
            MidiNote(0, 0, 64, 90, 0.0, 300.0),
            MidiNote(0, 0, 67, 90, 0.0, 300.0),
            MidiNote(0, 0, 72, 90, 350.0, 650.0),
        ]
        dialog = MappingComparisonDialog(notes, window.settings, parent=window)
        assert dialog.windowTitle() == "Pitch Mapping Policy Comparison"
        dialog._select_mode("melody3_contour")
        assert dialog.selected_mode == "melody3_contour"
        dialog.close()
    finally:
        window.close()
        app.processEvents()


def test_start_playback_with_dry_run_backend():
    from musical_scumme.model import KeyEvent, PlaybackPlan

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        dry_run_index = window.input_combo.findData("dry_run")
        window.input_combo.setCurrentIndex(dry_run_index)
        plan = PlaybackPlan(
            events=[KeyEvent(0.0, "down", "Y"), KeyEvent(100.0, "up", "Y")],
            planned_notes=[],
            source_notes=1,
            retained_notes=1,
            dropped_notes=0,
            duration_ms=100.0,
        )
        window.plan = plan
        window._start_playback(plan, countdown_s=0, repeat=False, minimize=False)
        assert window.scheduler is not None
        assert window.scheduler.running
        window.stop()
        app.processEvents()
    finally:
        window.close()
        app.processEvents()


def test_unlimited_number_inputs_ui_toggle():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert hasattr(window, "unlimited_inputs_check")
        assert not window.unlimited_inputs_check.isChecked()
        assert window.polyphony_spin.maximum() == 26
        assert window.density_spin.maximum() == 240
        assert window.speed_spin.maximum() == 3.0
        assert window.min_hold_spin.maximum() == 2000
        assert window.max_hold_spin.maximum() == 5000
        assert window.transpose_spin.maximum() == 36
        assert window.transpose_spin.minimum() == -36

        # Enable unlimited number input setting
        window.unlimited_inputs_check.setChecked(True)
        app.processEvents()
        assert window.settings.unlimited_number_inputs is True
        assert window.polyphony_spin.maximum() == 999999
        assert window.density_spin.maximum() == 999999
        assert window.speed_spin.maximum() == 999999.0
        assert window.min_hold_spin.maximum() == 999999
        assert window.max_hold_spin.maximum() == 999999
        assert window.transpose_spin.maximum() == 999999
        assert window.transpose_spin.minimum() == -999999

        # Uncheck to restore default safety bounds
        window.unlimited_inputs_check.setChecked(False)
        app.processEvents()
        assert window.settings.unlimited_number_inputs is False
        assert window.polyphony_spin.maximum() == 26
        assert window.density_spin.maximum() == 240
        assert window.speed_spin.maximum() == 3.0
        assert window.min_hold_spin.maximum() == 2000
        assert window.max_hold_spin.maximum() == 5000
        assert window.transpose_spin.maximum() == 36
        assert window.transpose_spin.minimum() == -36
    finally:
        window.close()
        app.processEvents()

