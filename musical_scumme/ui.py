from __future__ import annotations

import logging
import os
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTime, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QColor, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .arrangement_options import ARRANGEMENT_OPTIONS, ARRANGEMENT_RECIPES, CHORD_RECOGNITION_MODES
from .config import (
    BUILTIN_PROFILES,
    CUSTOM_MAX_CHORD_SPREAD_MS,
    CUSTOM_MAX_NOTES_PER_SECOND,
    CUSTOM_MAX_POLYPHONY,
    MAX_RECENT_MIDI_FILES,
    PERFORMANCE_PRESETS,
    AppSettings,
    apply_performance_preset,
    create_default_settings,
    load_settings,
    save_settings,
)
from .input_backend import (
    create_backend,
    emergency_stop_pressed,
    focus_scum_window,
    foreground_scum_window_rect,
    foreground_window_info,
    function_key_pressed,
    is_control_down,
    key_name_to_vk,
    numpad_divide_pressed,
    numpad_key_pressed,
)
from .instrument_profiles import INSTRUMENT_PROFILES, resolve_instrument_profile
from .live_midi import (
    LiveMidiCallbacks,
    LiveMidiConfig,
    LiveMidiSession,
    MidiInputDevice,
    MidiInputProvider,
    MidiInputUnavailable,
    RtMidiInputProvider,
)
from .midi_engine import load_midi
from .model import MidiNote, PlaybackPlan, midi_note_name
from .numeric_widgets import QDoubleSpinBox, QSpinBox
from .planner import build_playback_plan, export_plan_csv, export_score_csv, recommend_optimal_transpose
from .performance_health import assess_performance
from .playback_sections import (
    PlaybackSection,
    PlaybackSelectionResult,
    apply_playback_sections,
    format_timecode,
    section_to_dict,
    sections_from_dicts,
)
from .scheduler import PlaybackScheduler, SchedulerCallbacks
from .score_optimizer import ProjectAnalysis, analyse_notes, analyse_project

APP_TITLE = f"MusicalScumbag {__version__}"
logger = logging.getLogger("musical_scumme.ui")


def _selection_is_prepared_song(project, selected_tracks: list[int]) -> bool:
    selected = set(selected_tracks)
    names = {track.name for track in project.tracks if track.index in selected}
    return bool(names) and names.issubset({"Lead Melody", "Light Support"})


def _qtime_from_ms(milliseconds: float) -> QTime:
    return QTime(0, 0).addMSecs(max(0, min(86_399_999, round(milliseconds))))


def _format_timecode_min_sec(milliseconds: float) -> str:
    total_seconds = max(0, int(milliseconds / 1000.0))
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"



def _fit_combo_to_panel(combo: QComboBox, minimum_contents_length: int = 18) -> None:
    """Keep long descriptive choices from forcing a panel wider than the window."""

    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(minimum_contents_length)


def _set_visual_state(widget: QWidget, object_name: str) -> None:
    """Change a dynamic style state and immediately refresh its Qt polish."""

    if widget.objectName() == object_name:
        return
    widget.setObjectName(object_name)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _describe_control(widget: QWidget, name: str, description: str) -> None:
    widget.setAccessibleName(name)
    widget.setAccessibleDescription(description)
    if not widget.toolTip():
        widget.setToolTip(description)


def _apply_native_dark_titlebar(window: QWidget) -> None:
    """Ask Windows to draw its real caption controls in dark mode."""

    if os.name != "nt":
        return
    try:
        import ctypes

        enabled = ctypes.c_int(1)
        hwnd = int(window.winId())
        dwmapi = ctypes.windll.dwmapi
        for attribute in (20, 19):  # current and older Windows 10 attribute ids
            result = dwmapi.DwmSetWindowAttribute(
                hwnd,
                attribute,
                ctypes.byref(enabled),
                ctypes.sizeof(enabled),
            )
            if result == 0:
                break
    except Exception:
        logger.debug("Could not enable the native dark title bar", exc_info=True)


def _set_native_no_activate(window: QWidget, enabled: bool) -> None:
    """Make the compact player clickable without taking foreground focus from SCUM."""

    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        GWL_EXSTYLE = -20
        WS_EX_NOACTIVATE = 0x08000000
        hwnd = wintypes.HWND(int(window.winId()))
        get_style = user32.GetWindowLongPtrW
        set_style = user32.SetWindowLongPtrW
        get_style.argtypes = (wintypes.HWND, ctypes.c_int)
        get_style.restype = ctypes.c_ssize_t
        set_style.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
        set_style.restype = ctypes.c_ssize_t
        style = int(get_style(hwnd, GWL_EXSTYLE))
        new_style = style | WS_EX_NOACTIVATE if enabled else style & ~WS_EX_NOACTIVATE
        if new_style != style:
            set_style(hwnd, GWL_EXSTYLE, new_style)
    except Exception:
        logger.debug("Could not update compact-player activation style", exc_info=True)


def _pin_native_topmost_no_activate(
    window: QWidget,
    target_rect: tuple[int, int, int, int] | None = None,
) -> None:
    """Keep the compact player above the game without pulling focus away from it."""

    if os.name != "nt":
        window.raise_()
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SetWindowPos.argtypes = (
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        )
        user32.SetWindowPos.restype = wintypes.BOOL
        user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
        user32.GetWindowRect.restype = wintypes.BOOL
        HWND_TOPMOST = wintypes.HWND(-1)
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOACTIVATE = 0x0010
        SWP_SHOWWINDOW = 0x0040
        hwnd = wintypes.HWND(int(window.winId()))
        x = 0
        y = 0
        flags = SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
        if target_rect is None:
            flags |= SWP_NOMOVE
        else:
            own_rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(own_rect)):
                own_width = max(1, int(own_rect.right - own_rect.left))
                left, top, right, _bottom = target_rect
                margin = 14
                x = max(left + margin, right - own_width - margin)
                y = top + margin
            else:
                flags |= SWP_NOMOVE
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            x, y, 0, 0,
            flags,
        )
    except Exception:
        logger.debug("Could not pin compact player without activation", exc_info=True)


STYLE = """
* {
  font-family: "Segoe UI", sans-serif;
  font-size: 12px;
  color: #d6d6d1;
}
QMainWindow, QDialog, QWidget#hudSurface {
  background: #181818;
}
QWidget, QLabel, QScrollArea, QScrollArea > QWidget > QWidget {
  background: transparent;
}
QToolTip {
  background: #252525;
  color: #eeeeea;
  border: 1px solid #484848;
  padding: 4px 6px;
}

QMenuBar {
  background: #181818;
  color: #b6b6b0;
  border-bottom: 1px solid #343434;
  padding: 1px 4px;
}
QMenuBar::item {
  background: transparent;
  padding: 4px 8px;
}
QMenuBar::item:selected {
  color: #f0f0eb;
  background: #2a2a2a;
}
QMenu {
  background: #202020;
  border: 1px solid #3c3c3c;
  padding: 3px;
}
QMenu::item { padding: 6px 24px 6px 9px; }
QMenu::item:selected { background: #35322a; color: #f1ead8; }
QMenu::separator { height: 1px; background: #383838; margin: 4px 7px; }

QFrame#topBar {
  background: #1b1b1b;
  border: none;
  border-bottom: 1px solid #353535;
  border-radius: 0;
}
QFrame#sourceDeck {
  background: #181818;
  border: none;
  border-bottom: 1px solid #303030;
  border-radius: 0;
}
QFrame#commandDeck {
  background: #1b1b1b;
  border: none;
  border-top: 1px solid #383838;
  border-radius: 0;
}
QFrame#panel { background: transparent; border: none; }
QFrame#topBar[compact="true"], QFrame#commandDeck[compact="true"] {
  background: #1d1c1a;
  border-color: #4c4536;
}
QLabel#projectTitle {
  color: #d2d2cc;
  font-size: 11px;
  font-weight: 600;
}
QLabel#sectionCode {
  color: #8b8b85;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
}
QLabel#selectionStatus, QLabel#subtitle, QLabel#muted {
  color: #91918b;
  font-size: 11px;
}
QLabel#compactTitle {
  color: #e8e7df;
  font-size: 12px;
  font-weight: 600;
}
QLabel#timecode, QLabel#compactTimecode {
  color: #deddd4;
  font-size: 11px;
  font-weight: 600;
  font-family: "Consolas", monospace;
  background: #151515;
  border: 1px solid #3a3a3a;
  border-radius: 1px;
  padding: 3px 6px;
}

QLabel#pillGood, QLabel#pillBad, QLabel#pillIdle {
  border-radius: 1px;
  padding: 3px 6px;
  font-size: 10px;
  font-weight: 600;
}
QLabel#pillGood { color: #b8d2a7; background: #242d21; border: 1px solid #44553d; }
QLabel#pillBad { color: #dfaaa4; background: #302120; border: 1px solid #5c3b38; }
QLabel#pillIdle { color: #b2aa95; background: #2b2924; border: 1px solid #4d483d; }
QLabel#advisory {
  color: #d2c29d;
  background: #28251e;
  border: 1px solid #4d4636;
  border-radius: 1px;
  padding: 7px 8px;
}
QLabel#inlineGood, QLabel#inlineWarn, QLabel#inlineIdle {
  border-radius: 1px;
  padding: 3px 6px;
  font-size: 10px;
  font-weight: 600;
}
QLabel#inlineGood { color: #b8d2a7; background: #242d21; }
QLabel#inlineWarn { color: #d6c18e; background: #302a1d; }
QLabel#inlineIdle { color: #aaa9a2; background: #292929; }

QGroupBox {
  background: transparent;
  border: none;
  border-top: 1px solid #383838;
  border-radius: 0;
  margin-top: 13px;
  padding: 12px 4px 4px 4px;
  font-weight: 600;
}
QGroupBox::title {
  subcontrol-origin: margin;
  left: 0;
  padding: 0 7px 0 0;
  color: #aaa79d;
  background: #181818;
  font-size: 11px;
  font-weight: 600;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTimeEdit {
  min-height: 25px;
  background: #202020;
  color: #e1e1dc;
  border: 1px solid #414141;
  border-radius: 1px;
  padding: 2px 6px;
  selection-background-color: #6f6448;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QTimeEdit:hover { border-color: #555555; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTimeEdit:focus {
  border-color: #9a895e;
  background: #232323;
}
QLineEdit#trackFilter { background: #1d1d1d; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
  background: #202020;
  color: #e1e1dc;
  border: 1px solid #484848;
  selection-background-color: #484233;
  outline: 0;
}
QSpinBox, QDoubleSpinBox, QTimeEdit { font-weight: 600; }

QFrame#modeStrip {
  background: #1d1d1d;
  border: 1px solid #393939;
  border-radius: 2px;
}
QPushButton#modeChoice {
  min-height: 30px;
  padding: 4px 13px;
  background: transparent;
  border: 1px solid transparent;
  color: #97978f;
  font-weight: 700;
}
QPushButton#modeChoice:checked {
  background: #343126;
  border-color: #655c43;
  color: #eee9da;
}
QLabel#simpleHero, QLabel#advancedHero {
  color: #ece9df;
  font-size: 15px;
  font-weight: 700;
}
QFrame#advancedHeader {
  background: transparent;
  border: none;
  border-bottom: 1px solid #343434;
}
QLabel#tabIntro {
  color: #aaa9a1;
  background: #1e1e1e;
  border-left: 2px solid #6d6247;
  padding: 7px 9px;
  font-size: 11px;
}
QLabel#simpleValue {
  min-width: 76px;
  color: #e3ddc8;
  background: #22211d;
  border: 1px solid #484333;
  border-radius: 2px;
  padding: 4px 7px;
  font-weight: 700;
}
QSlider::groove:horizontal {
  height: 4px;
  background: #353535;
  border: none;
}
QSlider::sub-page:horizontal { background: #887a55; }
QSlider::handle:horizontal {
  width: 16px;
  margin: -6px 0;
  background: #d2c59e;
  border: 1px solid #5b543f;
  border-radius: 8px;
}
QSlider::handle:horizontal:hover { background: #e4d8b0; }

QTabWidget::pane {
  border: none;
  border-top: 1px solid #383838;
  border-radius: 0;
  background: #191919;
  top: -1px;
}
QTabBar::tab {
  background: #1b1b1b;
  color: #8e8e88;
  border: 1px solid transparent;
  border-bottom: 1px solid #383838;
  padding: 6px 10px;
  margin-right: 0;
  font-size: 11px;
  font-weight: 600;
}
QTabBar::tab:selected {
  color: #deddd5;
  background: #222222;
  border-color: #3d3d3d;
  border-bottom-color: #222222;
}
QTabBar::tab:hover:!selected { color: #c7c6bf; background: #202020; }

QTableWidget {
  background: #1b1b1b;
  alternate-background-color: #202020;
  color: #d7d7d2;
  border: 1px solid #3a3a3a;
  border-radius: 0;
  gridline-color: #2c2c2c;
  selection-background-color: #4a4435;
  selection-color: #f0eee6;
}
QTableWidget::item { padding: 4px 6px; border: none; }
QHeaderView::section {
  background: #242424;
  color: #9b9b95;
  border: none;
  border-right: 1px solid #353535;
  border-bottom: 1px solid #3b3b3b;
  padding: 5px 6px;
  font-size: 10px;
  font-weight: 600;
}

QPushButton {
  min-height: 26px;
  background: #292929;
  color: #d4d4cf;
  border: 1px solid #454545;
  border-radius: 1px;
  padding: 3px 9px;
  font-size: 11px;
  font-weight: 600;
}
QPushButton:hover { background: #333333; color: #f0f0eb; border-color: #5b5b5b; }
QPushButton:pressed { background: #202020; }
QPushButton:disabled { background: #202020; color: #62625f; border-color: #303030; }
QPushButton#primary, QPushButton#transportButton {
  background: #4b4535;
  color: #eee9dc;
  border-color: #776a4c;
}
QPushButton#primary:hover, QPushButton#transportButton:hover { background: #5b533e; border-color: #9a895e; }
QPushButton#primary:pressed, QPushButton#transportButton:pressed { background: #3d392d; }
QPushButton#secondary { background: #292929; color: #cdcdc7; border-color: #424242; }
QPushButton#secondary:hover { background: #333333; color: #efefe9; border-color: #575757; }
QPushButton#transportPanicButton, QPushButton#danger {
  background: #352524;
  color: #dfaaa4;
  border-color: #68413e;
}
QPushButton#transportPanicButton:hover, QPushButton#danger:hover { background: #442c2a; color: #efc2bd; border-color: #81504c; }
QCheckBox { spacing: 6px; color: #c6c6c0; }
QCheckBox::indicator {
  width: 13px;
  height: 13px;
  background: #1c1c1c;
  border: 1px solid #4a4a4a;
  border-radius: 1px;
}
QCheckBox::indicator:hover { border-color: #817454; }
QCheckBox::indicator:checked { background: #776a4c; border-color: #9a895e; }

QProgressBar {
  min-height: 2px;
  max-height: 2px;
  background: #2a2a2a;
  border: none;
  border-radius: 0;
  color: transparent;
}
QProgressBar::chunk { background: #8b7c58; }
QStatusBar { background: #151515; color: #898983; border-top: 1px solid #303030; }
QSplitter::handle { background: #242424; width: 5px; }
QSplitter::handle:hover { background: #4a4538; }
QScrollBar:vertical { background: #191919; width: 9px; margin: 0; }
QScrollBar::handle:vertical { background: #444444; min-height: 28px; border-radius: 0; }
QScrollBar::handle:vertical:hover { background: #565656; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class UiSignals(QObject):
    status = Signal(str)
    progress = Signal(float)
    finished = Signal(str)
    live_activity = Signal(str)
    live_finished = Signal(str)
    timecode = Signal(float, float)





class KeymapDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Custom SCUM key profile")
        _apply_native_dark_titlebar(self)
        self.setMinimumWidth(430)
        profile = settings.resolved_profile()
        custom = settings.custom_profile or {
            "base_notes": list(profile.base_notes),
            "octave_down": profile.octave_down,
            "octave_up": profile.octave_up,
        }
        self.edits: list[QLineEdit] = []
        layout = QVBoxLayout(self)
        form = QFormLayout()
        for index in range(13):
            pitch = 60 + index
            edit = QLineEdit(str(custom["base_notes"][index]))
            edit.setMaxLength(12)
            self.edits.append(edit)
            form.addRow(midi_note_name(pitch), edit)
        self.octave_down = QLineEdit(str(custom.get("octave_down", "LCTRL")))
        self.octave_up = QLineEdit(str(custom.get("octave_up", "LSHIFT")))
        form.addRow("Octave down", self.octave_down)
        form.addRow("Octave up", self.octave_up)
        layout.addLayout(form)
        note = QLabel(
            "Key names use Windows names such as Y, I, Q, LCTRL, LSHIFT, LWIN or F8. "
            "Use the exact physical bindings configured in your copy of SCUM."
        )
        note.setWordWrap(True)
        note.setObjectName("subtitle")
        layout.addWidget(note)
        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)
        self.validation_label.setAccessibleName("Key profile validation")
        layout.addWidget(self.validation_label)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        for index, edit in enumerate(self.edits):
            _describe_control(
                edit,
                f"SCUM key for {midi_note_name(60 + index)}",
                "Enter the Windows key name bound to this note in SCUM.",
            )
        _describe_control(
            self.octave_down,
            "SCUM octave-down key",
            "Enter the standalone key that steps SCUM down one persistent octave bank.",
        )
        _describe_control(
            self.octave_up,
            "SCUM octave-up key",
            "Enter the standalone key that steps SCUM up one persistent octave bank.",
        )

    def _validate_and_accept(self) -> None:
        try:
            self.result_profile()
        except Exception as exc:
            self.validation_label.setText(f"Check the key names: {exc}")
            _set_visual_state(self.validation_label, "inlineWarn")
            return
        self.validation_label.setText("Key profile is valid.")
        _set_visual_state(self.validation_label, "inlineGood")
        self.accept()

    def result_profile(self) -> dict:
        result = {
            "base_notes": [edit.text().strip().upper() for edit in self.edits],
            "octave_down": self.octave_down.text().strip().upper(),
            "octave_up": self.octave_up.text().strip().upper(),
        }
        for key in result["base_notes"] + [result["octave_down"], result["octave_up"]]:
            key_name_to_vk(key)
        return result


class MappingComparisonDialog(QDialog):
    def __init__(
        self,
        notes: list[MidiNote],
        settings: AppSettings,
        parent: QWidget | None = None,
        prepared_source: bool = False,
        track_names: dict[int, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pitch Mapping Policy Comparison")
        _apply_native_dark_titlebar(self)
        self.setMinimumSize(920, 430)
        self.selected_mode: str | None = None
        self.notes = notes
        self.settings = settings
        self.prepared_source = prepared_source
        self.track_names = track_names or {}

        layout = QVBoxLayout(self)

        summary = QLabel(
            "Compare note retention, octave-bank switching, "
            "and musical voice preservation across all 5 SCUM mapping policies for the active score."
        )
        summary.setWordWrap(True)
        summary.setObjectName("subtitle")
        layout.addWidget(summary)

        modes = [
            ("fold_smart", "Fold", "Safe base-bank fold with unison C preservation"),
            ("match3_adaptive", "Pitch Match", "Adaptive song-register shift + 3-octave coverage"),
            ("strict_auto", "Strict Range", "Single whole-octave shift, omits out-of-range notes"),
            ("melody3_contour", "Melody Contour", "Minimizes pitch loss & interval distortion for lead"),
            ("smart3_harmonic", "Harmonic", "Harmonic-aware bank optimization with rest discounting"),
        ]

        table = QTableWidget(len(modes), 7)
        table.setHorizontalHeaderLabels(
            ["Policy", "Behaviour", "Retained", "Dropped", "Bank taps", "Delays", ""]
        )
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setMinimumHeight(300)
        table.setAccessibleName("Pitch mapping comparison")

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for column in range(2, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        profile = settings.resolved_profile()
        for row, (mode_key, mode_title, mode_desc) in enumerate(modes):
            test_settings = replace(settings, mapping_mode=mode_key)
            plan = build_playback_plan(
                notes,
                test_settings,
                profile,
                prepared_source=prepared_source,
                track_names=self.track_names,
            )

            total_source = plan.source_notes or len(notes)
            retained = plan.retained_notes
            retained_pct = (retained / total_source * 100.0) if total_source else 0.0
            bank_taps = int(plan.diagnostics.get("octave_bank_taps", 0))
            timing_corrections = (
                int(plan.diagnostics.get("contour_transition_groups_delayed", 0))
                + int(plan.diagnostics.get("physical_retriggers_delayed", 0))
            )
            timing_delay_ms = (
                float(plan.diagnostics.get("contour_transition_delay_ms", 0.0))
                + float(plan.diagnostics.get("physical_retrigger_delay_ms", 0.0))
            )

            table.setItem(row, 0, QTableWidgetItem(mode_title))
            table.setItem(row, 1, QTableWidgetItem(mode_desc))
            table.setItem(row, 2, QTableWidgetItem(f"{retained:,}/{total_source:,} ({retained_pct:.0f}%)"))
            table.setItem(row, 3, QTableWidgetItem(f"{plan.dropped_notes:,}"))
            table.setItem(row, 4, QTableWidgetItem(f"{bank_taps:,}"))
            table.setItem(
                row, 5, QTableWidgetItem(f"{timing_corrections:,} · {timing_delay_ms:.0f} ms")
            )

            apply_btn = QPushButton("Active" if mode_key == settings.mapping_mode else "Use")
            if mode_key == settings.mapping_mode:
                apply_btn.setEnabled(False)
            else:
                apply_btn.setObjectName("secondary")
                apply_btn.clicked.connect(lambda checked=False, m=mode_key: self._select_mode(m))
            table.setCellWidget(row, 6, apply_btn)
            table.setRowHeight(row, 42)

        layout.addWidget(table)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _select_mode(self, mode: str) -> None:
        self.selected_mode = mode
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, midi_provider: MidiInputProvider | None = None) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        _apply_native_dark_titlebar(self)
        self.setAcceptDrops(True)
        self.setMinimumSize(900, 600)
        self.settings = load_settings()
        self._loading_ui = False
        self._applying_preset = False
        self._syncing_simple_ui = False
        self.resize(self.settings.window_width, self.settings.window_height)
        self.project = None
        self.score_analysis: ProjectAnalysis | None = None
        self.playback_sections: list[PlaybackSection] = []
        self.active_selection: PlaybackSelectionResult | None = None
        self.plan: PlaybackPlan | None = None
        self._active_playback_plan: PlaybackPlan | None = None
        self.backend = create_backend(self.settings.input_mode)
        self.scheduler: PlaybackScheduler | None = None
        # Last bank we believe SCUM is physically using.  This survives a new
        # scheduler/backend instance so the next Play can recover after F8 or
        # another interrupted performance instead of assuming base octave.
        self._known_scum_bank = 0
        self.midi_provider = midi_provider or RtMidiInputProvider()
        self.midi_devices: dict[int, MidiInputDevice] = {}
        self.live_midi: LiveMidiSession | None = None
        self._plan_controls_locked = False
        self._compact_playback = False
        self._editor_geometry = None
        self._editor_was_maximized = False
        self._user_keep_on_top = bool(self.settings.window_on_top)
        self._w_held = False
        self._walk_backend = None

        self.signals = UiSignals()
        self.signals.status.connect(self._set_status)
        self.signals.progress.connect(self._set_progress)
        self.signals.finished.connect(self._playback_finished)
        self.signals.live_activity.connect(self._set_live_activity)
        self.signals.live_finished.connect(self._live_midi_finished)
        self.signals.timecode.connect(self._set_timecode)

        self._build_ui()
        self._load_settings_into_ui()
        self._refresh_midi_devices(show_status=False)
        self._refresh_section_table()
        self._connect_signals()

        self.focus_timer = QTimer(self)
        self.focus_timer.timeout.connect(self._refresh_game_status)
        self.focus_timer.start(700)
        self._refresh_game_status()

        self.hotkey_timer = QTimer(self)
        self.hotkey_timer.timeout.connect(self._poll_global_hotkeys)
        self.hotkey_timer.start(50)

        self._last_file_timer = QTimer(self)
        self._last_file_timer.setSingleShot(True)
        self._last_file_timer.timeout.connect(self._load_last_file_after_startup)
        if self.settings.last_file and Path(self.settings.last_file).exists():
            self._last_file_timer.start(150)

    def _build_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("hudSurface")
        central.setProperty("compact", "false")
        central.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 7, 8, 6)
        root.setSpacing(6)

        header = QFrame()
        self.header = header
        header.setObjectName("topBar")
        header.setProperty("compact", "false")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(9, 5, 9, 5)
        header_layout.setSpacing(10)

        full_header_widget = QWidget()
        full_header_layout = QHBoxLayout(full_header_widget)
        full_header_layout.setContentsMargins(0, 0, 0, 0)
        full_header_layout.setSpacing(9)

        project_caption = QLabel("Project")
        project_caption.setObjectName("sectionCode")
        self.header_project_label = QLabel("No MIDI loaded")
        self.header_project_label.setObjectName("projectTitle")
        self.header_project_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.header_project_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        full_header_layout.addWidget(project_caption)
        full_header_layout.addWidget(self.header_project_label, 1)

        self.game_pill = QLabel("Checking SCUM…")
        self.game_pill.setObjectName("pillIdle")
        self.game_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.game_pill.setAccessibleName("SCUM foreground status")
        full_header_layout.addWidget(self.game_pill)

        header_layout.addWidget(full_header_widget, 1)
        self.full_header_widget = full_header_widget
        self.header_detail_widgets = (full_header_widget,)

        compact_header_widget = QWidget()
        compact_header_layout = QHBoxLayout(compact_header_widget)
        compact_header_layout.setContentsMargins(0, 0, 0, 0)
        compact_header_layout.setSpacing(7)
        self.compact_title_label = QLabel("NO MIDI LOADED")
        self.compact_title_label.setObjectName("compactTitle")
        self.compact_title_label.setMaximumWidth(180)
        self.compact_status_badge = QLabel("READY")
        self.compact_status_badge.setObjectName("pillIdle")
        self.compact_timecode_label = QLabel("00:00 / 00:00")
        self.compact_timecode_label.setObjectName("compactTimecode")
        self.compact_expand_button = QPushButton("Expand")
        self.compact_expand_button.setObjectName("secondary")
        self.compact_expand_button.setToolTip(
            "Pause playback safely and return to the full editor. Resume returns to the compact player and refocuses SCUM."
        )
        self.compact_expand_button.clicked.connect(self._expand_from_compact_player)
        compact_header_layout.addWidget(self.compact_title_label, 1)
        compact_header_layout.addWidget(self.compact_status_badge)
        compact_header_layout.addWidget(self.compact_timecode_label)
        compact_header_layout.addWidget(self.compact_expand_button)
        compact_header_widget.setVisible(False)
        self.compact_header_widget = compact_header_widget
        header_layout.addWidget(compact_header_widget, 1)

        root.addWidget(header)

        source_deck = QFrame()
        self.source_deck = source_deck
        source_deck.setObjectName("sourceDeck")
        source_layout = QVBoxLayout(source_deck)
        source_layout.setContentsMargins(9, 5, 7, 5)
        source_layout.setSpacing(5)
        file_row = QHBoxLayout()
        source_label = QLabel("Source")
        source_label.setObjectName("sectionCode")
        file_row.addWidget(source_label)
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Drop the original .mid/.midi file here or browse…")
        self.file_edit.setToolTip("MusicalScumbag reads the original MIDI and never modifies it.")
        self.file_edit.setAccessibleName("MIDI source file")
        self.file_edit.setAccessibleDescription(
            "Enter or drop an original .mid or .midi file. MusicalScumbag only reads it."
        )
        self.browse_button = QPushButton("Open MIDI")
        self.browse_button.setObjectName("primary")
        self.browse_button.setAccessibleName("Open MIDI file")
        self.reload_button = QPushButton("Reload")
        self.reload_button.setObjectName("secondary")
        self.reload_button.setEnabled(False)
        file_row.addWidget(self.file_edit, 1)
        file_row.addWidget(self.browse_button)
        file_row.addWidget(self.reload_button)
        source_layout.addLayout(file_row)

        workflow_row = QHBoxLayout()
        workflow_row.setContentsMargins(0, 0, 0, 0)
        self.workflow_hint = QLabel("Open or drop a MIDI file to begin")
        self.workflow_hint.setObjectName("subtitle")
        self.workflow_hint.setAccessibleName("Recommended next action")
        self.workflow_hint.setMinimumWidth(0)
        self.workflow_hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        workflow_row.addWidget(self.workflow_hint, 1)
        source_layout.addLayout(workflow_row)
        root.addWidget(source_deck)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.main_splitter = splitter
        root.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(0)
        workspace_tabs = QTabWidget()
        workspace_tabs.setObjectName("workspaceTabs")
        self.workspace_tabs = workspace_tabs
        left_layout.addWidget(workspace_tabs)

        tracks_box = QFrame()
        tracks_box.setObjectName("panel")
        self.tracks_box = tracks_box
        tracks_layout = QVBoxLayout(tracks_box)
        track_overview = QHBoxLayout()
        self.track_filter_edit = QLineEdit()
        self.track_filter_edit.setObjectName("trackFilter")
        self.track_filter_edit.setPlaceholderText("Filter tracks by name, role, or number…")
        self.track_filter_edit.setClearButtonEnabled(True)
        self.track_filter_edit.setAccessibleName("Filter MIDI tracks")
        self.track_selection_label = QLabel("No MIDI loaded")
        self.track_selection_label.setObjectName("selectionStatus")
        self.track_selection_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.track_selection_label.setAccessibleName("MIDI track selection summary")
        track_overview.addWidget(self.track_filter_edit, 1)
        track_overview.addWidget(self.track_selection_label)
        tracks_layout.addLayout(track_overview)
        self.track_table = QTableWidget(0, 6)
        self.track_table.setHorizontalHeaderLabels(["Use", "Track", "Name", "Role", "Notes", "Range"])
        self.track_table.verticalHeader().setVisible(False)
        self.track_table.verticalHeader().setDefaultSectionSize(28)
        self.track_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.track_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.track_table.setAlternatingRowColors(True)
        self.track_table.setAccessibleName("MIDI track selection table")
        self.track_table.setAccessibleDescription(
            "Choose which MIDI tracks to use. Double-click or press Space on a populated row to toggle it."
        )
        self.track_table.keyPressEvent = self._track_table_key_press
        header_view = self.track_table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.Stretch)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        tracks_layout.addWidget(self.track_table)
        track_buttons = QHBoxLayout()
        self.select_all_button = QPushButton("All")
        self.select_all_button.setObjectName("secondary")
        self.select_none_button = QPushButton("None")
        self.select_none_button.setObjectName("secondary")
        self.invert_tracks_button = QPushButton("Invert")
        self.invert_tracks_button.setObjectName("secondary")
        self.auto_select_button = QPushButton("Smart auto-select")
        self.auto_select_button.setObjectName("secondary")
        self.select_all_button.setToolTip("Select every populated track, including percussion tracks.")
        self.select_none_button.setToolTip("Clear every source-track selection.")
        self.invert_tracks_button.setToolTip("Invert selection across all populated source tracks.")
        self.auto_select_button.setToolTip(
            "Choose source tracks for the current arrangement and layer count, favouring the main vocal. "
            "Respects your Lead track choice, retains useful instrumental handoffs, and avoids redundant doubles. "
            "Change the arrangement, then click again to update the selection."
        )
        track_buttons.addWidget(self.select_all_button)
        track_buttons.addWidget(self.select_none_button)
        track_buttons.addWidget(self.invert_tracks_button)
        track_buttons.addWidget(self.auto_select_button)
        track_buttons.addStretch(1)
        tracks_layout.addLayout(track_buttons)
        workspace_tabs.addTab(tracks_box, "Tracks")

        self.section_box = QFrame()
        self.section_box.setObjectName("panel")
        self.section_box.setToolTip(
            "Play ranges include only selected passages; Omit ranges remove passages from the prepared playback."
        )
        section_layout = QVBoxLayout(self.section_box)
        self.section_table = QTableWidget(0, 4)
        self.section_table.setHorizontalHeaderLabels(["Action", "From", "To", "Length"])
        self.section_table.verticalHeader().setVisible(False)
        self.section_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.section_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.section_table.setMinimumHeight(180)
        self.section_table.setAccessibleName("Playback section table")
        self.section_table.setAccessibleDescription(
            "Optional source-time Play and Omit ranges. Select a row to edit or remove it."
        )
        section_header = self.section_table.horizontalHeader()
        section_header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, 4):
            section_header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        section_layout.addWidget(self.section_table)

        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("From"))
        self.section_start_time = QTimeEdit()
        self.section_start_time.setDisplayFormat("HH:mm:ss.zzz")
        self.section_start_time.setKeyboardTracking(False)
        range_row.addWidget(self.section_start_time, 1)
        range_row.addWidget(QLabel("To"))
        self.section_end_time = QTimeEdit()
        self.section_end_time.setDisplayFormat("HH:mm:ss.zzz")
        self.section_end_time.setKeyboardTracking(False)
        range_row.addWidget(self.section_end_time, 1)
        section_layout.addLayout(range_row)

        self.add_play_section_button = QPushButton("Add Play")
        self.add_play_section_button.setObjectName("secondary")
        self.add_omit_section_button = QPushButton("Add Omit")
        self.add_omit_section_button.setObjectName("secondary")

        section_buttons = QHBoxLayout()
        self.remove_section_button = QPushButton("Remove")
        self.remove_section_button.setObjectName("secondary")
        self.update_section_button = QPushButton("Update")
        self.update_section_button.setObjectName("secondary")
        self.clear_sections_button = QPushButton("Clear")
        self.clear_sections_button.setObjectName("secondary")
        self.loop_playback_check = QCheckBox("Loop")
        self.section_gap_spin = QSpinBox()
        self.section_gap_spin.setRange(0, 5000)
        self.section_gap_spin.setSuffix(" ms gap")
        self.section_gap_spin.setToolTip("Pause inserted between non-contiguous selected source ranges and loops.")
        self.add_play_section_button.setToolTip("Include only this source-time range when one or more Play ranges exist.")
        self.add_omit_section_button.setToolTip("Remove this source-time range from the prepared song.")
        self.update_section_button.setToolTip("Replace the selected range boundaries without changing its Play/Omit role.")
        self.remove_section_button.setToolTip("Remove the selected playback range. Shortcut: Delete.")
        self.clear_sections_button.setToolTip("Remove every Play/Omit range and restore the complete selected timeline.")
        self.loop_playback_check.setToolTip("Repeat the immutable prepared plan until Stop or F8.")
        section_buttons.addWidget(self.add_play_section_button)
        section_buttons.addWidget(self.add_omit_section_button)
        section_buttons.addWidget(self.update_section_button)
        section_buttons.addWidget(self.remove_section_button)
        section_buttons.addWidget(self.clear_sections_button)
        section_buttons.addStretch(1)
        section_layout.addLayout(section_buttons)

        section_options = QHBoxLayout()
        section_options.addWidget(self.loop_playback_check)
        section_options.addStretch(1)
        section_options.addWidget(QLabel("Gap"))
        section_options.addWidget(self.section_gap_spin)
        section_layout.addLayout(section_options)
        self.remove_section_action = QAction("Remove selected playback section", self.section_table)
        self.remove_section_action.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        self.remove_section_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.remove_section_action.triggered.connect(self.remove_playback_section)
        self.section_table.addAction(self.remove_section_action)
        workspace_tabs.addTab(self.section_box, "Sections")

        summary_box = QFrame()
        summary_box.setObjectName("panel")
        summary_layout = QVBoxLayout(summary_box)
        self.summary_label = QLabel("Load a MIDI file to begin.")
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.summary_label.setAccessibleName("Prepared song summary")
        summary_layout.addWidget(self.summary_label)
        self.runtime_health_label = QLabel("Last playback · not run yet")
        self.runtime_health_label.setObjectName("inlineIdle")
        self.runtime_health_label.setWordWrap(True)
        self.runtime_health_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.runtime_health_label.setAccessibleName("Last playback timing health")
        summary_layout.addWidget(self.runtime_health_label)
        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        self.warning_label.setObjectName("advisory")
        self.warning_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.warning_label.setAccessibleName("Preparation notes and warnings")
        self.warning_label.setVisible(False)
        summary_layout.addWidget(self.warning_label)
        self.summary_box = summary_box
        workspace_tabs.addTab(summary_box, "Summary")
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setMinimumWidth(420)
        left_scroll.setWidget(left)
        self.main_left_scroll = left_scroll
        splitter.addWidget(left_scroll)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(380)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(10)
        scroll.setWidget(right)

        mode_strip = QFrame()
        mode_strip.setObjectName("modeStrip")
        mode_layout = QHBoxLayout(mode_strip)
        mode_layout.setContentsMargins(7, 5, 7, 5)
        mode_layout.setSpacing(4)
        mode_title = QLabel("Settings")
        mode_title.setObjectName("sectionCode")
        mode_layout.addWidget(mode_title)
        mode_layout.addStretch(1)
        self.simple_mode_button = QPushButton("Simple")
        self.simple_mode_button.setObjectName("modeChoice")
        self.simple_mode_button.setCheckable(True)
        self.simple_mode_button.setToolTip("Recommended: only the controls needed to load, tune, and play a song.")
        self.advanced_mode_button = QPushButton("Advanced")
        self.advanced_mode_button.setObjectName("modeChoice")
        self.advanced_mode_button.setCheckable(True)
        self.advanced_mode_button.setToolTip("Expert workspace organised into Song, Mapping, Timing, SCUM, and Live MIDI tasks.")
        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.setExclusive(True)
        self.mode_button_group.addButton(self.simple_mode_button)
        self.mode_button_group.addButton(self.advanced_mode_button)
        mode_layout.addWidget(self.simple_mode_button)
        mode_layout.addWidget(self.advanced_mode_button)
        right_layout.addWidget(mode_strip)

        self.simple_settings_panel = QWidget()
        simple_layout = QVBoxLayout(self.simple_settings_panel)
        simple_layout.setContentsMargins(2, 2, 2, 6)
        simple_layout.setSpacing(12)

        simple_heading = QLabel("Load it. Tune it. Play it.")
        simple_heading.setObjectName("simpleHero")
        simple_layout.addWidget(simple_heading)
        simple_intro = QLabel(
            "Simple mode keeps MusicalScumbag on the safe automatic path. Play prepares the song for you; "
            "the technical arrangement and keyboard controls stay out of the way."
        )
        simple_intro.setObjectName("subtitle")
        simple_intro.setWordWrap(True)
        simple_layout.addWidget(simple_intro)

        simple_playback_box = QGroupBox("Playback")
        simple_playback_form = QFormLayout(simple_playback_box)
        simple_playback_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        simple_playback_form.setVerticalSpacing(10)

        self.simple_instrument_combo = QComboBox()
        for instrument in INSTRUMENT_PROFILES.values():
            self.simple_instrument_combo.addItem(instrument.label, instrument.key)
        _fit_combo_to_panel(self.simple_instrument_combo, 14)
        self.simple_instrument_combo.setToolTip("Choose the instrument you are holding in SCUM.")
        simple_playback_form.addRow("Instrument", self.simple_instrument_combo)

        self.simple_performance_combo = QComboBox()
        for preset_name, preset in PERFORMANCE_PRESETS.items():
            self.simple_performance_combo.addItem(str(preset["label"]), preset_name)
        self.simple_performance_combo.addItem("Custom (from Advanced)", "custom")
        _fit_combo_to_panel(self.simple_performance_combo, 14)
        self.simple_performance_combo.setToolTip(
            "Automatic is recommended. SCUM Safe trades some detail for more reliable keyboard input."
        )
        simple_playback_form.addRow("Quality", self.simple_performance_combo)

        speed_widget = QWidget()
        speed_layout = QVBoxLayout(speed_widget)
        speed_layout.setContentsMargins(0, 0, 0, 0)
        speed_layout.setSpacing(4)
        speed_head = QHBoxLayout()
        speed_head.setContentsMargins(0, 0, 0, 0)
        speed_name = QLabel("Speed")
        self.simple_speed_value = QLabel("100%")
        self.simple_speed_value.setObjectName("simpleValue")
        self.simple_speed_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        speed_head.addWidget(speed_name)
        speed_head.addStretch(1)
        speed_head.addWidget(self.simple_speed_value)
        speed_layout.addLayout(speed_head)
        self.simple_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.simple_speed_slider.setRange(25, 300)
        self.simple_speed_slider.setSingleStep(5)
        self.simple_speed_slider.setPageStep(25)
        self.simple_speed_slider.setTickInterval(25)
        self.simple_speed_slider.setAccessibleName("Playback speed")
        self.simple_speed_slider.setToolTip("Mouse wheel or drag: 100% is the original MIDI tempo.")
        speed_layout.addWidget(self.simple_speed_slider)
        simple_playback_form.addRow(speed_widget)

        pitch_widget = QWidget()
        pitch_layout = QVBoxLayout(pitch_widget)
        pitch_layout.setContentsMargins(0, 0, 0, 0)
        pitch_layout.setSpacing(4)
        pitch_head = QHBoxLayout()
        pitch_head.setContentsMargins(0, 0, 0, 0)
        pitch_name = QLabel("Pitch")
        self.simple_pitch_value = QLabel("Original")
        self.simple_pitch_value.setObjectName("simpleValue")
        self.simple_pitch_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pitch_head.addWidget(pitch_name)
        pitch_head.addStretch(1)
        self.simple_pitch_value.setMinimumWidth(96)
        pitch_head.addWidget(self.simple_pitch_value)
        pitch_layout.addLayout(pitch_head)
        pitch_control_row = QHBoxLayout()
        pitch_control_row.setContentsMargins(0, 0, 0, 0)
        self.simple_transpose_slider = QSlider(Qt.Orientation.Horizontal)
        self.simple_transpose_slider.setRange(-36, 36)
        self.simple_transpose_slider.setSingleStep(1)
        self.simple_transpose_slider.setPageStep(12)
        self.simple_transpose_slider.setTickInterval(12)
        self.simple_transpose_slider.setAccessibleName("Song pitch")
        self.simple_transpose_slider.setToolTip("Move the song up or down in semitones. The centre is the original pitch.")
        self.simple_auto_transpose_button = QPushButton("Auto")
        self.simple_auto_transpose_button.setObjectName("secondary")
        self.simple_auto_transpose_button.setToolTip("Choose the transposition that best fits SCUM's playable notes.")
        pitch_control_row.addWidget(self.simple_transpose_slider, 1)
        pitch_control_row.addWidget(self.simple_auto_transpose_button)
        pitch_layout.addLayout(pitch_control_row)
        simple_playback_form.addRow(pitch_widget)

        delay_widget = QWidget()
        delay_layout = QVBoxLayout(delay_widget)
        delay_layout.setContentsMargins(0, 0, 0, 0)
        delay_layout.setSpacing(4)
        delay_head = QHBoxLayout()
        delay_head.setContentsMargins(0, 0, 0, 0)
        delay_name = QLabel("Start delay")
        self.simple_countdown_value = QLabel("4 sec")
        self.simple_countdown_value.setObjectName("simpleValue")
        self.simple_countdown_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        delay_head.addWidget(delay_name)
        delay_head.addStretch(1)
        delay_head.addWidget(self.simple_countdown_value)
        delay_layout.addLayout(delay_head)
        self.simple_countdown_slider = QSlider(Qt.Orientation.Horizontal)
        self.simple_countdown_slider.setRange(0, 30)
        self.simple_countdown_slider.setSingleStep(1)
        self.simple_countdown_slider.setPageStep(5)
        self.simple_countdown_slider.setTickInterval(5)
        self.simple_countdown_slider.setAccessibleName("Playback countdown")
        self.simple_countdown_slider.setToolTip("Time after Play is pressed before the first note is sent to SCUM.")
        delay_layout.addWidget(self.simple_countdown_slider)
        simple_playback_form.addRow(delay_widget)

        self.simple_focus_safety_check = QCheckBox("Protect playback if SCUM loses focus")
        self.simple_focus_safety_check.setToolTip(
            "Recommended. Keys are only sent to SCUM and playback pauses if another window takes focus."
        )
        simple_playback_form.addRow(self.simple_focus_safety_check)

        self.simple_test_button = QPushButton("Test one C note in SCUM")
        self.simple_test_button.setObjectName("secondary")
        self.simple_test_button.setToolTip("Send one short C note using the current SCUM keyboard setup.")
        simple_playback_form.addRow(self.simple_test_button)
        simple_layout.addWidget(simple_playback_box)

        self.simple_advisory_label = QLabel("")
        self.simple_advisory_label.setObjectName("advisory")
        self.simple_advisory_label.setWordWrap(True)
        self.simple_advisory_label.setVisible(False)
        simple_layout.addWidget(self.simple_advisory_label)

        simple_note = QLabel(
            "Need track shaping, song sections, key bindings, mapping policies, timing limits, exports or Live MIDI? "
            "Switch to Advanced — nothing is deleted or reset. Saved Advanced sections and looping are preserved but ignored in Simple mode."
        )
        simple_note.setObjectName("muted")
        simple_note.setWordWrap(True)
        simple_layout.addWidget(simple_note)
        self.simple_show_advanced_button = QPushButton("Show advanced controls")
        self.simple_show_advanced_button.setObjectName("secondary")
        simple_layout.addWidget(self.simple_show_advanced_button)
        simple_layout.addStretch(1)
        right_layout.addWidget(self.simple_settings_panel)

        self.advanced_settings_header = QFrame()
        self.advanced_settings_header.setObjectName("advancedHeader")
        advanced_header_layout = QVBoxLayout(self.advanced_settings_header)
        advanced_header_layout.setContentsMargins(3, 3, 3, 7)
        advanced_header_layout.setSpacing(4)
        advanced_title_row = QHBoxLayout()
        advanced_title_row.setContentsMargins(0, 0, 0, 0)
        advanced_title = QLabel("Advanced controls")
        advanced_title.setObjectName("advancedHero")
        advanced_title_row.addWidget(advanced_title)
        advanced_title_row.addStretch(1)
        self.advanced_preset_state = QLabel("Preset")
        self.advanced_preset_state.setObjectName("inlineIdle")
        advanced_title_row.addWidget(self.advanced_preset_state)
        advanced_header_layout.addLayout(advanced_title_row)
        advanced_intro = QLabel(
            "Start with a preset, then change only what you need. Advanced controls are grouped by job; "
            "editing a preset-controlled value switches the song to Custom without hiding anything."
        )
        advanced_intro.setObjectName("subtitle")
        advanced_intro.setWordWrap(True)
        advanced_header_layout.addWidget(advanced_intro)
        right_layout.addWidget(self.advanced_settings_header)

        settings_tabs = QTabWidget()
        settings_tabs.setObjectName("settingsTabs")
        self.settings_tabs = settings_tabs
        right_layout.addWidget(settings_tabs)

        tab_song = QWidget()
        tab_song_layout = QVBoxLayout(tab_song)
        tab_song_layout.setContentsMargins(2, 6, 2, 6)
        tab_song_layout.setSpacing(10)

        tab_mapping = QWidget()
        tab_mapping_layout = QVBoxLayout(tab_mapping)
        tab_mapping_layout.setContentsMargins(2, 6, 2, 6)
        tab_mapping_layout.setSpacing(10)

        tab_timing = QWidget()
        tab_timing_layout = QVBoxLayout(tab_timing)
        tab_timing_layout.setContentsMargins(2, 6, 2, 6)
        tab_timing_layout.setSpacing(10)

        tab_system = QWidget()
        tab_system_layout = QVBoxLayout(tab_system)
        tab_system_layout.setContentsMargins(2, 6, 2, 6)
        tab_system_layout.setSpacing(10)

        tab_live = QWidget()
        tab_live_layout = QVBoxLayout(tab_live)
        tab_live_layout.setContentsMargins(2, 6, 2, 6)
        tab_live_layout.setSpacing(10)

        settings_tabs.addTab(tab_song, "Song")
        settings_tabs.addTab(tab_mapping, "Mapping")
        settings_tabs.addTab(tab_timing, "Timing")
        settings_tabs.addTab(tab_system, "SCUM")
        settings_tabs.addTab(tab_live, "Live MIDI")
        settings_tabs.setTabToolTip(0, "Instrument, preset, tempo, pitch and arrangement style.")
        settings_tabs.setTabToolTip(1, "How MIDI notes are fitted into SCUM's playable pitch range.")
        settings_tabs.setTabToolTip(2, "Chord density, note lengths and keyboard reliability delays.")
        settings_tabs.setTabToolTip(3, "SCUM key bindings, keyboard output, focus safety and start behaviour.")
        settings_tabs.setTabToolTip(4, "Physical MIDI controller input for live playing.")

        song_intro = QLabel(
            "Musical choices first: choose the SCUM instrument, a known-good starting preset, tempo/pitch, "
            "then decide how the selected MIDI tracks should be arranged."
        )
        song_intro.setObjectName("tabIntro")
        song_intro.setWordWrap(True)
        tab_song_layout.addWidget(song_intro)

        performance_box = QGroupBox("Sound and tempo")
        self.performance_box = performance_box
        self.performance_form = QFormLayout(performance_box)
        self.performance_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.instrument_combo = QComboBox()
        for instrument in INSTRUMENT_PROFILES.values():
            self.instrument_combo.addItem(
                f"{instrument.label} · {instrument.max_sustain_ms:,} ms max sustain",
                instrument.key,
            )
        _fit_combo_to_panel(self.instrument_combo)
        self.instrument_combo.setToolTip(
            "Choose the instrument you are holding in SCUM. Its sustain limit is used when preparing notes."
        )
        self.performance_form.addRow("SCUM instrument", self.instrument_combo)
        self.instrument_hint = QLabel()
        self.instrument_hint.setWordWrap(True)
        self.instrument_hint.setObjectName("subtitle")
        self.performance_form.addRow("", self.instrument_hint)

        self.performance_combo = QComboBox()
        for preset_name, preset in PERFORMANCE_PRESETS.items():
            self.performance_combo.addItem(str(preset["label"]), preset_name)
        self.performance_combo.addItem("Custom", "custom")
        _fit_combo_to_panel(self.performance_combo)
        self.performance_combo.setToolTip(
            "Loads a complete arrangement/mapping/timing baseline. Song-specific choices such as instrument, lead track and transpose stay yours."
        )
        self.performance_form.addRow("Starting preset", self.performance_combo)
        self.performance_hint = QLabel()
        self.performance_hint.setWordWrap(True)
        self.performance_hint.setObjectName("subtitle")
        self.performance_form.addRow("", self.performance_hint)

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.25, 3.0)
        self.speed_spin.setSingleStep(0.05)
        self.speed_spin.setDecimals(2)
        self.speed_spin.setSuffix("×")
        self.speed_spin.setToolTip("1.00× is the MIDI's original tempo. This affects the entire prepared song.")
        self.performance_form.addRow("Tempo", self.speed_spin)

        self.transpose_spin = QSpinBox()
        self.transpose_spin.setRange(-36, 36)
        self.transpose_spin.setSuffix(" semitones")
        self.transpose_spin.setToolTip("Move the entire song up or down before it is mapped to SCUM keys.")
        self.auto_transpose_button = QPushButton("Recommend")
        self.auto_transpose_button.setObjectName("secondary")
        self.auto_transpose_button.setToolTip(
            "Analyze the selected notes and choose the transposition that gives the mapping stage the best coverage."
        )
        self.auto_transpose_button.clicked.connect(self._recommend_transpose_clicked)
        transpose_layout = QHBoxLayout()
        transpose_layout.setContentsMargins(0, 0, 0, 0)
        transpose_layout.addWidget(self.transpose_spin, 1)
        transpose_layout.addWidget(self.auto_transpose_button)
        self.performance_form.addRow("Song pitch", transpose_layout)
        tab_song_layout.addWidget(performance_box)

        self.arrangement_box = QGroupBox("Arrangement and musical interpretation")
        arrangement_form = QFormLayout(self.arrangement_box)
        arrangement_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.arrangement_combo = QComboBox()
        for mode, (label, guidance) in ARRANGEMENT_OPTIONS.items():
            self.arrangement_combo.addItem(label, mode)
            self.arrangement_combo.setItemData(
                self.arrangement_combo.count() - 1, guidance, Qt.ItemDataRole.ToolTipRole,
            )
        _fit_combo_to_panel(self.arrangement_combo)
        self.arrangement_combo.setMaxVisibleItems(18)
        self.arrangement_combo.view().setMinimumWidth(460)
        self.arrangement_combo.setAccessibleName("Arrangement selection")
        arrangement_form.addRow("Arrangement style", self.arrangement_combo)
        self.arrangement_help_label = QLabel()
        self.arrangement_help_label.setWordWrap(True)
        self.arrangement_help_label.setObjectName("muted")
        self.arrangement_help_label.setAccessibleName("Arrangement guidance")
        self.arrangement_help_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.arrangement_combo.currentIndexChanged.connect(
            lambda: self.arrangement_help_label.setText(
                ARRANGEMENT_OPTIONS[self.arrangement_combo.currentData()][1]
            )
        )
        self.arrangement_help_label.setText(ARRANGEMENT_OPTIONS["intelligent"][1])
        arrangement_form.addRow(self.arrangement_help_label)

        self.arrangement_lead_combo = QComboBox()
        self.arrangement_lead_combo.addItem("Auto - detect vocal / melody", -1)
        self.arrangement_lead_combo.setAccessibleName("Suite lead track")
        self.arrangement_lead_combo.setToolTip(
            "For suite-style arrangements, choose the selected MIDI track carrying the main tune. Auto uses names and musical activity."
        )
        _fit_combo_to_panel(self.arrangement_lead_combo)
        arrangement_form.addRow("Lead / melody track", self.arrangement_lead_combo)
        self.arrangement_layers_label = QLabel(
            "Select the musical tracks you want available to the arrangement. The chosen style decides their roles; "
            "Timing limits on the Timing tab still cap the final keyboard output."
        )
        self.arrangement_layers_label.setWordWrap(True)
        self.arrangement_layers_label.setObjectName("muted")
        arrangement_form.addRow(self.arrangement_layers_label)

        self.chord_recognition_combo = QComboBox()
        self.chord_recognition_combo.addItem("Group performed chords automatically", "auto")
        self.chord_recognition_combo.addItem("Only notes with identical MIDI attack time", "exact")
        _fit_combo_to_panel(self.chord_recognition_combo)
        self.chord_recognition_combo.setToolTip(
            "Automatic grouping aligns sustained source notes that land within a small adaptive rhythmic window. It never invents chord tones."
        )
        arrangement_form.addRow("Chord grouping", self.chord_recognition_combo)
        self.ignore_percussion_check = QCheckBox("Ignore MIDI channel 10 percussion")
        arrangement_form.addRow(self.ignore_percussion_check)

        self.expression_spin = QSpinBox()
        self.expression_spin.setRange(0, 100)
        self.expression_spin.setSuffix("%")
        self.expression_spin.setToolTip(
            "Use MIDI velocity to vary played note length. SCUM volume is unchanged; zero disables velocity-based length variation."
        )
        arrangement_form.addRow("Velocity expression", self.expression_spin)
        tab_song_layout.addWidget(self.arrangement_box)
        tab_song_layout.addStretch(1)

        mapping_intro = QLabel(
            "Mapping decides what happens when MIDI pitches do not fit SCUM's small playable keyboard range. "
            "If a song sounds in the wrong register or changes octave too often, this is the tab to adjust."
        )
        mapping_intro.setObjectName("tabIntro")
        mapping_intro.setWordWrap(True)
        tab_mapping_layout.addWidget(mapping_intro)

        self.mapping_box = QGroupBox("Pitch range strategy")
        mapping_form = QFormLayout(self.mapping_box)
        mapping_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.mapping_combo = QComboBox()
        self.mapping_combo.addItem("Fold · keep everything in one bank", "fold_smart")
        self.mapping_combo.addItem("Pitch Match · fit the song register", "match3_adaptive")
        self.mapping_combo.addItem("Strict Range · omit notes outside one octave", "strict_auto")
        self.mapping_combo.addItem("Melody Contour · protect the lead line", "melody3_contour")
        self.mapping_combo.addItem("Harmonic · balance bass, melody and chords", "smart3_harmonic")
        _fit_combo_to_panel(self.mapping_combo)
        self.compare_mappings_button = QPushButton("Compare")
        self.compare_mappings_button.setObjectName("secondary")
        self.compare_mappings_button.setToolTip(
            "Build each mapping strategy against the current song and compare retained notes, octave switches and timing."
        )
        self.compare_mappings_button.clicked.connect(self._open_mapping_comparison)
        mapping_row = QHBoxLayout()
        mapping_row.setContentsMargins(0, 0, 0, 0)
        mapping_row.addWidget(self.mapping_combo, 1)
        mapping_row.addWidget(self.compare_mappings_button)
        mapping_form.addRow("Range strategy", mapping_row)
        mapping_guides = {
            "fold_smart": "No octave-switch taps during the song. Notes are folded into SCUM's base bank; octave doubles can merge.",
            "strict_auto": "Centres the song around one octave and omits anything still outside C4-C5. Predictable, but can lose notes.",
            "match3_adaptive": "Fits the overall register, then uses octave switches when useful. A good general-purpose mapping for wider songs.",
            "melody3_contour": "Prioritises the shape of exposed melodies and arpeggios, then reduces unnecessary octave switching.",
            "smart3_harmonic": "Balances bass and melody when choosing banks and prefers to switch during real silence. Experimental.",
        }
        self.mapping_help_label = QLabel()
        self.mapping_help_label.setWordWrap(True)
        self.mapping_help_label.setObjectName("muted")
        self.mapping_help_label.setAccessibleName("Pitch mapping guidance")
        self.mapping_help_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        for index in range(self.mapping_combo.count()):
            self.mapping_combo.setItemData(
                index, mapping_guides[self.mapping_combo.itemData(index)], Qt.ItemDataRole.ToolTipRole,
            )

        def update_mapping_guide():
            self.mapping_help_label.setText(mapping_guides.get(self.mapping_combo.currentData(), ""))

        self.mapping_combo.currentIndexChanged.connect(update_mapping_guide)
        update_mapping_guide()
        mapping_form.addRow(self.mapping_help_label)

        self.fidelity_priority_combo = QComboBox()
        self.fidelity_priority_combo.addItem("Balanced", "balanced")
        self.fidelity_priority_combo.addItem("Keep original register", "register")
        self.fidelity_priority_combo.addItem("Keep rhythm exact", "rhythm")
        self.fidelity_priority_combo.addItem("Avoid octave-bank changes", "stability")
        _fit_combo_to_panel(self.fidelity_priority_combo, 14)
        self.fidelity_priority_combo.setToolTip("Choose what the planner should protect first when SCUM cannot reproduce everything exactly.")
        mapping_form.addRow("When compromises are needed", self.fidelity_priority_combo)

        self.mapping_stability_spin = QSpinBox()
        self.mapping_stability_spin.setRange(0, 100)
        self.mapping_stability_spin.setSuffix("%")
        self.mapping_stability_spin.setToolTip(
            "Higher values keep recurring passages in the same SCUM octave bank when musically reasonable."
        )
        mapping_form.addRow("Prefer a stable octave bank", self.mapping_stability_spin)

        self.bank_switch_budget_spin = QSpinBox()
        self.bank_switch_budget_spin.setRange(0, 20)
        self.bank_switch_budget_spin.setSpecialValueText("Unlimited")
        self.bank_switch_budget_spin.setSuffix(" taps/s")
        self.bank_switch_budget_spin.setToolTip(
            "Maximum Ctrl/Shift octave-bank taps per second. Zero leaves this unlimited. Lower values trade register accuracy for keyboard reliability."
        )
        mapping_form.addRow("Maximum octave switches", self.bank_switch_budget_spin)

        self.c_boundary_combo = QComboBox()
        self.c_boundary_combo.addItem("Automatic", "auto")
        self.c_boundary_combo.addItem("Prefer lower bank", "lower")
        self.c_boundary_combo.addItem("Prefer upper bank", "upper")
        _fit_combo_to_panel(self.c_boundary_combo, 14)
        self.c_boundary_combo.setToolTip("Resolve ambiguous C notes that can be represented at the edge of two SCUM banks.")
        mapping_form.addRow("Boundary C notes", self.c_boundary_combo)

        self.restore_base_bank_check = QCheckBox("Return SCUM to the base octave after playback")
        self.restore_base_bank_check.setToolTip(
            "After musical keys are released, send the required standalone Ctrl/Shift tap to restore the base octave bank."
        )
        mapping_form.addRow(self.restore_base_bank_check)
        tab_mapping_layout.addWidget(self.mapping_box)

        self.source_cleanup_box = QGroupBox("Source cleanup")
        source_cleanup_form = QFormLayout(self.source_cleanup_box)
        source_cleanup_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        source_cleanup_hint = QLabel(
            "These filters run before SCUM mapping. Leave them low unless a MIDI contains accidental micro-notes or extremely dense repeated attacks."
        )
        source_cleanup_hint.setWordWrap(True)
        source_cleanup_hint.setObjectName("muted")
        source_cleanup_form.addRow(source_cleanup_hint)
        self.source_min_note_spin = QSpinBox()
        self.source_min_note_spin.setRange(0, 1000)
        self.source_min_note_spin.setSuffix(" ms")
        self.source_min_note_spin.setToolTip("Remove source notes shorter than this before arrangement. Zero keeps every source-note duration.")
        source_cleanup_form.addRow("Ignore notes shorter than", self.source_min_note_spin)
        self.retrigger_spin = QSpinBox()
        self.retrigger_spin.setRange(0, 500)
        self.retrigger_spin.setSuffix(" ms")
        self.retrigger_spin.setToolTip("Drop low-priority repeated source notes that start closer together than this. Zero disables the filter.")
        source_cleanup_form.addRow("Ignore repeats closer than", self.retrigger_spin)
        tab_mapping_layout.addWidget(self.source_cleanup_box)
        tab_mapping_layout.addStretch(1)

        timing_intro = QLabel(
            "Timing is about keyboard reliability and articulation, not musical pitch. If SCUM misses notes, chords arrive messy, "
            "or rapid repeats fail, adjust these values before changing the mapping strategy."
        )
        timing_intro.setObjectName("tabIntro")
        timing_intro.setWordWrap(True)
        tab_timing_layout.addWidget(timing_intro)

        self.timing_box = QGroupBox("Density and chords")
        timing_form = QFormLayout(self.timing_box)
        timing_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.polyphony_spin = QSpinBox()
        self.polyphony_spin.setRange(1, CUSTOM_MAX_POLYPHONY)
        self.polyphony_spin.setToolTip(
            "Maximum original notes retained at one musical onset. Higher values can sound fuller but increase simultaneous keyboard pressure."
        )
        timing_form.addRow("Maximum chord notes", self.polyphony_spin)
        self.spread_spin = QSpinBox()
        self.spread_spin.setRange(0, CUSTOM_MAX_CHORD_SPREAD_MS)
        self.spread_spin.setSuffix(" ms / note")
        self.spread_spin.setToolTip("Roll chord notes apart instead of pressing them all at once. Zero keeps simultaneous attacks.")
        timing_form.addRow("Roll chord notes apart", self.spread_spin)
        self.density_spin = QSpinBox()
        self.density_spin.setRange(4, CUSTOM_MAX_NOTES_PER_SECOND)
        self.density_spin.setSuffix(" note-ons/s")
        self.density_spin.setToolTip("Cap arranged note starts per second so SCUM is less likely to miss bursts of keyboard input.")
        timing_form.addRow("Maximum note starts", self.density_spin)
        tab_timing_layout.addWidget(self.timing_box)

        self.note_length_box = QGroupBox("Played note lengths")
        note_length_form = QFormLayout(self.note_length_box)
        note_length_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.hold_spin = QSpinBox()
        self.hold_spin.setRange(5, 100)
        self.hold_spin.setSuffix("%")
        self.hold_spin.setToolTip("Scale each source MIDI note's duration before minimum/maximum key-hold limits are applied.")
        note_length_form.addRow("Keep source note length", self.hold_spin)
        self.min_hold_spin = QSpinBox()
        self.min_hold_spin.setRange(10, 2000)
        self.min_hold_spin.setSuffix(" ms")
        self.min_hold_spin.setToolTip("Shortest keyboard hold emitted after arrangement and velocity expression.")
        note_length_form.addRow("Minimum key hold", self.min_hold_spin)
        self.max_hold_spin = QSpinBox()
        self.max_hold_spin.setRange(20, 5000)
        self.max_hold_spin.setSuffix(" ms")
        self.max_hold_spin.setToolTip("Longest played key hold before the instrument's own hard sustain ceiling is applied.")
        note_length_form.addRow("Maximum key hold", self.max_hold_spin)
        tab_timing_layout.addWidget(self.note_length_box)

        self.keyboard_timing_box = QGroupBox("Keyboard timing")
        keyboard_timing_form = QFormLayout(self.keyboard_timing_box)
        keyboard_timing_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        keyboard_timing_hint = QLabel(
            "These are tiny safety gaps around repeated physical keys and Ctrl/Shift octave changes. Increase them only if SCUM drops or merges input."
        )
        keyboard_timing_hint.setObjectName("muted")
        keyboard_timing_hint.setWordWrap(True)
        keyboard_timing_form.addRow(keyboard_timing_hint)
        self.key_gap_spin = QSpinBox()
        self.key_gap_spin.setRange(0, 250)
        self.key_gap_spin.setSuffix(" ms")
        self.key_gap_spin.setToolTip("Guarantee a real key-up window before the same physical SCUM note key is pressed again.")
        keyboard_timing_form.addRow("Gap before the same key repeats", self.key_gap_spin)
        self.modifier_release_spin = QSpinBox()
        self.modifier_release_spin.setRange(0, 250)
        self.modifier_release_spin.setSuffix(" ms")
        self.modifier_release_spin.setToolTip("Wait after releasing note keys before changing the Ctrl/Shift octave state.")
        keyboard_timing_form.addRow("Wait before octave switch", self.modifier_release_spin)
        self.modifier_settle_spin = QSpinBox()
        self.modifier_settle_spin.setRange(0, 250)
        self.modifier_settle_spin.setSuffix(" ms")
        self.modifier_settle_spin.setToolTip("Wait after changing Ctrl/Shift before pressing the first note in the new octave.")
        keyboard_timing_form.addRow("Wait after octave switch", self.modifier_settle_spin)
        tab_timing_layout.addWidget(self.keyboard_timing_box)

        self.unlimited_inputs_check = QCheckBox("Remove normal numeric safety limits (experimental)")
        self.unlimited_inputs_check.setToolTip(
            "Allows extreme values outside the normal validated ranges. This is intended for testing only and can cause missed notes, stalls or input flooding."
        )
        unlimited_hint = QLabel(
            "Normal limits are deliberately conservative. Only remove them when testing a specific engine behaviour."
        )
        unlimited_hint.setObjectName("advisory")
        unlimited_hint.setWordWrap(True)
        unlimited_row = QVBoxLayout()
        unlimited_row.setContentsMargins(4, 4, 4, 4)
        unlimited_row.addWidget(self.unlimited_inputs_check)
        unlimited_row.addWidget(unlimited_hint)
        unlimited_widget = QWidget()
        unlimited_widget.setLayout(unlimited_row)
        tab_timing_layout.addWidget(unlimited_widget)
        tab_timing_layout.addStretch(1)

        self.performance_advanced_widgets = (
            self.polyphony_spin,
            self.spread_spin,
            self.min_hold_spin,
            self.key_gap_spin,
            self.density_spin,
            self.modifier_release_spin,
            self.modifier_settle_spin,
        )
        self.timing_form = note_length_form
        self.timing_advanced_widgets = (self.hold_spin, self.max_hold_spin)

        scum_intro = QLabel(
            "SCUM controls how MusicalScumbag talks to the game. The defaults are safest; change the key profile only when your in-game bindings differ."
        )
        scum_intro.setObjectName("tabIntro")
        scum_intro.setWordWrap(True)
        tab_system_layout.addWidget(scum_intro)

        compatibility_box = QGroupBox("Keyboard output")
        self.compatibility_box = compatibility_box
        compatibility_form = QFormLayout(compatibility_box)
        compatibility_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(list(BUILTIN_PROFILES) + ["Custom"])
        _fit_combo_to_panel(self.profile_combo, 14)
        self.custom_keys_button = QPushButton("Edit bindings")
        self.custom_keys_button.setObjectName("secondary")
        self.custom_keys_button.setToolTip("Copy the selected profile and edit its 13 musical keys plus octave controls.")
        profile_row = QHBoxLayout()
        profile_row.addWidget(self.profile_combo, 1)
        profile_row.addWidget(self.custom_keys_button)
        compatibility_form.addRow("SCUM key bindings", profile_row)
        self.profile_hint = QLabel()
        self.profile_hint.setWordWrap(True)
        self.profile_hint.setObjectName("subtitle")
        compatibility_form.addRow("", self.profile_hint)
        self.input_combo = QComboBox()
        self.input_combo.addItem("Scan-code SendInput (recommended)", "scan_code")
        self.input_combo.addItem("Virtual-key SendInput (fallback)", "virtual_key")
        self.input_combo.addItem("Dry run / no keyboard output", "dry_run")
        _fit_combo_to_panel(self.input_combo, 14)
        compatibility_form.addRow("Keyboard output", self.input_combo)
        tab_system_layout.addWidget(compatibility_box)

        self.focus_safety_box = QGroupBox("Focus and start behaviour")
        focus_safety_form = QFormLayout(self.focus_safety_box)
        focus_safety_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.require_focus = QCheckBox("Only send keys while SCUM is focused")
        self.require_focus.setToolTip("Prevents musical keystrokes from being sent to another foreground application.")
        focus_safety_form.addRow(self.require_focus)
        self.pause_focus = QCheckBox("Pause playback if SCUM loses focus")
        self.pause_focus.setToolTip("If you Alt-Tab or SCUM loses foreground focus, release held keys and pause instead of continuing blindly.")
        focus_safety_form.addRow(self.pause_focus)
        self.countdown_spin = QSpinBox()
        self.countdown_spin.setRange(0, 30)
        self.countdown_spin.setSuffix(" s")
        self.countdown_spin.setToolTip("Delay between pressing Play and the first musical note. SCUM is focused before the countdown begins.")
        focus_safety_form.addRow("Start delay", self.countdown_spin)
        playback_overlay_hint = QLabel(
            "Play brings SCUM to the foreground and leaves the compact MusicalScumbag controller visible above the game."
        )
        playback_overlay_hint.setObjectName("muted")
        playback_overlay_hint.setWordWrap(True)
        focus_safety_form.addRow("Player overlay", playback_overlay_hint)
        self.test_button = QPushButton("Send one test C")
        self.test_button.setObjectName("secondary")
        self.test_button.setToolTip("Focus SCUM and play a single C using the current keyboard-output settings.")
        focus_safety_form.addRow(self.test_button)
        tab_system_layout.addWidget(self.focus_safety_box)
        tab_system_layout.addStretch(1)

        live_intro = QLabel(
            "Live MIDI bypasses song preparation and turns a physical MIDI keyboard into SCUM note-key presses in real time. "
            "It deliberately stays in the base octave bank for predictable input."
        )
        live_intro.setObjectName("tabIntro")
        live_intro.setWordWrap(True)
        tab_live_layout.addWidget(live_intro)

        live_midi_box = QGroupBox("Live MIDI controller")
        self.live_midi_box = live_midi_box
        live_midi_form = QFormLayout(live_midi_box)
        live_midi_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.midi_input_combo = QComboBox()
        _fit_combo_to_panel(self.midi_input_combo, 14)
        self.refresh_midi_button = QPushButton("Refresh")
        self.refresh_midi_button.setObjectName("secondary")
        self.refresh_midi_button.setToolTip("Rescan connected physical and virtual MIDI input ports.")
        midi_device_row = QHBoxLayout()
        midi_device_row.addWidget(self.midi_input_combo, 1)
        midi_device_row.addWidget(self.refresh_midi_button)
        live_midi_form.addRow("MIDI controller", midi_device_row)

        self.live_mapping_combo = QComboBox()
        self.live_mapping_combo.addItem("Fold into SCUM base octave", "fold")
        self.live_mapping_combo.addItem("Only accept C4-C5", "strict")
        _fit_combo_to_panel(self.live_mapping_combo, 14)
        self.live_mapping_combo.setToolTip("Live input never sends Ctrl/Shift octave-bank changes.")
        live_midi_form.addRow("Pitch handling", self.live_mapping_combo)

        self.live_transpose_spin = QSpinBox()
        self.live_transpose_spin.setRange(-36, 36)
        self.live_transpose_spin.setSuffix(" semitones")
        live_midi_form.addRow("Transpose", self.live_transpose_spin)

        self.live_channel_combo = QComboBox()
        self.live_channel_combo.addItem("Omni (all channels)", -1)
        for channel in range(16):
            self.live_channel_combo.addItem(f"Channel {channel + 1}", channel)
        _fit_combo_to_panel(self.live_channel_combo, 14)
        live_midi_form.addRow("Listen to", self.live_channel_combo)

        self.live_polyphony_spin = QSpinBox()
        self.live_polyphony_spin.setRange(1, 8)
        self.live_polyphony_spin.setToolTip("Maximum different SCUM note keys held from the MIDI controller at once. Three is the safe default.")
        live_midi_form.addRow("Maximum held keys", self.live_polyphony_spin)

        self.live_ignore_channel_10 = QCheckBox("Ignore MIDI channel 10 percussion")
        live_midi_form.addRow(self.live_ignore_channel_10)
        self.live_state_label = QLabel(
            "Set SCUM to its base octave before arming Live MIDI. Live mode never sends Ctrl or Shift octave changes."
        )
        self.live_state_label.setObjectName("subtitle")
        self.live_state_label.setWordWrap(True)
        self.live_state_label.setAccessibleName("Live MIDI status and safety guidance")
        live_midi_form.addRow("", self.live_state_label)
        tab_live_layout.addWidget(live_midi_box)
        tab_live_layout.addStretch(1)

        self.unlimited_inputs_check.toggled.connect(self._on_unlimited_inputs_toggled)
        self._default_spin_ranges = {
            self.speed_spin: (0.25, 3.0),
            self.transpose_spin: (-36, 36),
            self.polyphony_spin: (1, CUSTOM_MAX_POLYPHONY),
            self.spread_spin: (0, CUSTOM_MAX_CHORD_SPREAD_MS),
            self.min_hold_spin: (10, 2000),
            self.key_gap_spin: (0, 250),
            self.density_spin: (4, CUSTOM_MAX_NOTES_PER_SECOND),
            self.modifier_release_spin: (0, 250),
            self.modifier_settle_spin: (0, 250),
            self.source_min_note_spin: (0, 1000),
            self.retrigger_spin: (0, 500),
            self.expression_spin: (0, 100),
            self.mapping_stability_spin: (0, 100),
            self.bank_switch_budget_spin: (0, 20),
            self.hold_spin: (5, 100),
            self.max_hold_spin: (20, 5000),
            self.countdown_spin: (0, 30),
            self.section_gap_spin: (0, 5000),
            self.live_transpose_spin: (-36, 36),
            self.live_polyphony_spin: (1, 8),
        }
        right_layout.addStretch(1)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 11)
        splitter.setStretchFactor(1, 9)
        splitter.setSizes([580, 480])

        command_deck = QFrame()
        self.command_deck = command_deck
        command_deck.setObjectName("commandDeck")
        command_deck.setProperty("compact", "false")
        controls = QHBoxLayout(command_deck)
        controls.setContentsMargins(10, 8, 10, 8)
        controls.setSpacing(7)
        command_label = QLabel("Transport")
        self.command_label = command_label
        command_label.setObjectName("sectionCode")
        controls.addWidget(command_label)
        self.readiness_pill = QLabel("Load MIDI")
        self.readiness_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.readiness_pill.setObjectName("pillIdle")
        self.readiness_pill.setAccessibleName("Output readiness")
        controls.addWidget(self.readiness_pill)
        self.full_timecode_label = QLabel("00:00 / 00:00")
        self.full_timecode_label.setObjectName("timecode")
        self.full_timecode_label.setAccessibleName("Playback timecode")
        controls.addWidget(self.full_timecode_label)
        self.prepare_button = QPushButton("Prepare")
        self.prepare_button.setObjectName("secondary")
        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("transportButton")
        self.live_button = QPushButton("Live")
        self.live_button.setEnabled(False)
        self.live_button.setAccessibleName("Arm live MIDI keyboard")
        self.live_button.setToolTip(
            "Route the selected MIDI controller to SCUM until Stop or F8."
        )
        self.pause_button = QPushButton("Pause")
        self.pause_button.setObjectName("secondary")
        self.pause_button.setEnabled(False)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("transportPanicButton")
        self.stop_button.setEnabled(False)
        self.stop_button.setAccessibleName("Stop and panic release")
        self.stop_button.setToolTip(
            "Immediately stop scheduled or live input and release every held key."
        )
        self.export_button = QPushButton("Score CSV")
        self.export_button.setObjectName("secondary")
        self.export_events_button = QPushButton("Events CSV")
        self.export_events_button.setObjectName("secondary")
        _describe_control(
            self.prepare_button,
            "Prepare SCUM score",
            "Build the playable SCUM score from the current tracks, ranges, instrument, and timing settings. Shortcut: Ctrl+P.",
        )
        _describe_control(
            self.play_button,
            "Play prepared song",
            "Prepare when needed, focus SCUM automatically, and open the compact always-visible player. Global shortcut: F9.",
        )
        _describe_control(
            self.pause_button,
            "Pause or resume playback",
            "Pause safely and release held keys, or resume the active plan. Global shortcut: F9.",
        )
        _describe_control(
            self.export_button,
            "Export musical SCUM score",
            "Save the readable planned-note score as CSV."
        )
        _describe_control(
            self.export_events_button,
            "Export physical key events",
            "Save the low-level keyboard event timeline as CSV."
        )
        controls.addStretch(1)
        controls.addWidget(self.prepare_button)
        controls.addWidget(self.play_button)
        controls.addWidget(self.live_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.stop_button)
        self.compact_hint = QLabel("F8 STOP · F9 · Ctrl+4/6 · F11")
        self.compact_hint.setObjectName("selectionStatus")
        self.compact_hint.setToolTip("Global shortcuts: F8 Panic Stop · F9 Play/Pause · Ctrl+Numpad 4/6 Seek · F11 Show/Hide window")
        self.compact_hint.setVisible(False)
        controls.addWidget(self.compact_hint)
        controls.addSpacing(6)
        controls.addWidget(self.export_button)
        controls.addWidget(self.export_events_button)
        root.addWidget(command_deck)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setAccessibleName("Playback progress")
        root.addWidget(self.progress)
        self.setStatusBar(QStatusBar())
        self.statusBar().setAccessibleName("Application status")
        self.statusBar().showMessage("Ready. Play focuses SCUM automatically; F8 is emergency stop.")

        self.play_pause_action = QAction("Play / Pause", self)
        if os.name != "nt":
            self.play_pause_action.setShortcut(QKeySequence("F9"))
        self.play_pause_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.play_pause_action.triggered.connect(self.play_pause_hotkey)
        self.addAction(self.play_pause_action)
        self.show_hide_action = QAction("Show / Hide window", self)
        if os.name != "nt":
            self.show_hide_action.setShortcut(QKeySequence("F11"))
        self.show_hide_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.show_hide_action.triggered.connect(self.toggle_window_visibility)
        self.addAction(self.show_hide_action)
        self.seek_forward_action = QAction("Seek forward", self)
        if os.name != "nt":
            self.seek_forward_action.setShortcut(QKeySequence("Ctrl+Num+6"))
        self.seek_forward_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.seek_forward_action.triggered.connect(self.seek_forward_hotkey)
        self.addAction(self.seek_forward_action)
        self.seek_backward_action = QAction("Seek backward", self)
        if os.name != "nt":
            self.seek_backward_action.setShortcut(QKeySequence("Ctrl+Num+4"))
        self.seek_backward_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.seek_backward_action.triggered.connect(self.seek_backward_hotkey)
        self.addAction(self.seek_backward_action)


        menu = self.menuBar()
        self.file_menu = menu.addMenu("File")
        self.open_action = QAction("Open MIDI…", self)
        self.open_action.setShortcut(QKeySequence("Ctrl+O"))
        self.open_action.setStatusTip("Open an original MIDI file without modifying it.")
        self.open_action.triggered.connect(self.browse_file)
        self.file_menu.addAction(self.open_action)
        self.recent_menu = self.file_menu.addMenu("Open Recent")
        self.reload_action = QAction("Reload current MIDI", self)
        self.reload_action.setShortcut(QKeySequence("Ctrl+R"))
        self.reload_action.setStatusTip("Reload and reanalyse the current source MIDI.")
        self.reload_action.setEnabled(False)
        self.reload_action.triggered.connect(self.reload_current_file)
        self.file_menu.addAction(self.reload_action)
        self.focus_source_action = QAction("Focus MIDI path", self)
        self.focus_source_action.setShortcut(QKeySequence("Ctrl+L"))
        self.focus_source_action.setStatusTip("Move keyboard focus to the MIDI source path.")
        self.focus_source_action.triggered.connect(self._focus_midi_path)
        self.file_menu.addAction(self.focus_source_action)
        self.file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        self.file_menu.addAction(exit_action)
        tools_menu = menu.addMenu("Tools")
        self.prepare_action = QAction("Prepare SCUM score", self)
        self.prepare_action.setShortcut(QKeySequence("Ctrl+P"))
        self.prepare_action.setStatusTip("Build the SCUM score without sending keyboard input.")
        self.prepare_action.triggered.connect(self.prepare_plan)
        tools_menu.addAction(self.prepare_action)
        tools_menu.addSeparator()
        self.reset_action = QAction("Reset settings", self)
        self.reset_action.triggered.connect(self.reset_settings)
        tools_menu.addAction(self.reset_action)

        view_menu = menu.addMenu("View")
        self.keep_on_top_action = QAction("Keep window on top", self)
        self.keep_on_top_action.setCheckable(True)
        self.keep_on_top_action.setStatusTip("Keep the full editor above other windows. Compact playback is pinned automatically.")
        self.keep_on_top_action.toggled.connect(self._set_user_keep_on_top)
        view_menu.addAction(self.keep_on_top_action)

        help_menu = menu.addMenu("Help")
        self.quick_start_action = QAction("Quick start", self)
        self.quick_start_action.setShortcut(QKeySequence("F1"))
        self.quick_start_action.triggered.connect(self.show_quick_start)
        help_menu.addAction(self.quick_start_action)
        self.shortcuts_action = QAction("Keyboard shortcuts", self)
        self.shortcuts_action.triggered.connect(self.show_keyboard_shortcuts)
        help_menu.addAction(self.shortcuts_action)
        help_menu.addSeparator()
        self.about_action = QAction(f"About MusicalScumbag {__version__}", self)
        self.about_action.triggered.connect(self.show_about)
        help_menu.addAction(self.about_action)
        self._refresh_recent_menu()
        self._plan_widgets = (
            self.file_edit,
            self.browse_button,
            self.reload_button,
            self.tracks_box,
            self.section_box,
            self.simple_settings_panel,
            self.settings_tabs,
        )
        self._plan_actions = (
            self.open_action,
            self.reload_action,
            self.focus_source_action,
            self.prepare_action,
            self.reset_action,
        )
        self.tracks_box.setEnabled(False)
        self.section_box.setEnabled(False)
        self._refresh_workflow_state()

    def _playback_active(self) -> bool:
        return bool(self.scheduler and self.scheduler.running)

    def _live_midi_active(self) -> bool:
        return bool(self.live_midi and self.live_midi.running)

    def _output_active(self) -> bool:
        return self._playback_active() or self._live_midi_active()

    def _output_busy(self) -> bool:
        return self._plan_controls_locked or self._output_active()

    def _set_user_keep_on_top(self, enabled: bool) -> None:
        self._user_keep_on_top = bool(enabled)
        self._apply_topmost_state()

    def _apply_topmost_state(self) -> None:
        should_pin = self._compact_playback or self._user_keep_on_top
        is_pinned = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        if should_pin == is_pinned:
            return
        was_visible = self.isVisible()
        was_maximized = self.isMaximized()
        geometry = self.geometry()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, should_pin)
        if was_visible:
            if was_maximized and not self._compact_playback:
                self.showMaximized()
            else:
                self.show()
                if not self._compact_playback:
                    self.setGeometry(geometry)
        _apply_native_dark_titlebar(self)

    def _set_ui_mode(self, mode: str, *, save: bool = False) -> None:
        mode = "advanced" if mode == "advanced" else "simple"
        simple = mode == "simple"
        self.settings.ui_mode = mode

        self.simple_mode_button.setChecked(simple)
        self.advanced_mode_button.setChecked(not simple)
        self.simple_settings_panel.setVisible(simple)
        self.advanced_settings_header.setVisible(not simple)
        self.settings_tabs.setVisible(not simple)

        section_index = self.workspace_tabs.indexOf(self.section_box)
        if section_index >= 0:
            self.workspace_tabs.setTabVisible(section_index, not simple)
            if simple and self.workspace_tabs.currentWidget() is self.section_box:
                self.workspace_tabs.setCurrentWidget(self.tracks_box)

        for button in (self.select_all_button, self.select_none_button, self.invert_tracks_button):
            button.setVisible(not simple)
        for column in (1, 3, 5):
            self.track_table.setColumnHidden(column, simple)

        self.prepare_button.setVisible(not simple)
        self.live_button.setVisible(not simple)
        self.export_button.setVisible(not simple)
        self.export_events_button.setVisible(not simple)
        self.prepare_action.setVisible(not simple)
        self.command_label.setText("Playback" if simple else "Transport")
        self.play_button.setText("Play in SCUM" if simple else "Play")

        if simple:
            self._sync_simple_from_advanced()
            self._refresh_simple_advisory()
            self.statusBar().showMessage(
                "Simple mode: load a MIDI and press Play. MusicalScumbag handles preparation automatically."
            )
        else:
            self.statusBar().showMessage(
                "Advanced mode: Song sets musical intent; Mapping handles pitch range; Timing handles keyboard reliability."
            )
        if save and not self._loading_ui:
            self._save_ui_to_settings()

    def _format_simple_pitch(self, semitones: int) -> str:
        if semitones == 0:
            return "Original"
        direction = "Higher" if semitones > 0 else "Lower"
        return f"{direction} {abs(semitones)}"

    def _sync_simple_from_advanced(self, *_args) -> None:
        if self._syncing_simple_ui or not hasattr(self, "simple_speed_slider"):
            return
        self._syncing_simple_ui = True
        try:
            index = self.simple_instrument_combo.findData(self.instrument_combo.currentData())
            if index >= 0:
                self.simple_instrument_combo.setCurrentIndex(index)
            index = self.simple_performance_combo.findData(self.performance_combo.currentData())
            if index >= 0:
                self.simple_performance_combo.setCurrentIndex(index)

            speed_percent = round(float(self.speed_spin.value()) * 100)
            self.simple_speed_slider.setValue(max(25, min(300, speed_percent)))
            self.simple_speed_value.setText(f"{speed_percent}%")

            transpose = int(self.transpose_spin.value())
            self.simple_transpose_slider.setValue(max(-36, min(36, transpose)))
            self.simple_pitch_value.setText(self._format_simple_pitch(transpose))

            countdown = int(self.countdown_spin.value())
            self.simple_countdown_slider.setValue(max(0, min(30, countdown)))
            self.simple_countdown_value.setText("None" if countdown == 0 else f"{countdown} sec")

            self.simple_focus_safety_check.setChecked(
                self.require_focus.isChecked() and self.pause_focus.isChecked()
            )
        finally:
            self._syncing_simple_ui = False

    def _simple_instrument_changed(self, _index: int) -> None:
        if self._syncing_simple_ui:
            return
        index = self.instrument_combo.findData(self.simple_instrument_combo.currentData())
        if index >= 0:
            self.instrument_combo.setCurrentIndex(index)

    def _simple_performance_changed(self, _index: int) -> None:
        if self._syncing_simple_ui:
            return
        index = self.performance_combo.findData(self.simple_performance_combo.currentData())
        if index >= 0:
            self.performance_combo.setCurrentIndex(index)

    def _simple_speed_changed(self, value: int) -> None:
        self.simple_speed_value.setText(f"{value}%")
        if not self._syncing_simple_ui:
            self.speed_spin.setValue(value / 100.0)

    def _simple_transpose_changed(self, value: int) -> None:
        self.simple_pitch_value.setText(self._format_simple_pitch(value))
        if not self._syncing_simple_ui:
            self.transpose_spin.setValue(value)

    def _simple_countdown_changed(self, value: int) -> None:
        self.simple_countdown_value.setText("None" if value == 0 else f"{value} sec")
        if not self._syncing_simple_ui:
            self.countdown_spin.setValue(value)

    def _simple_focus_safety_changed(self, checked: bool) -> None:
        if self._syncing_simple_ui:
            return
        self.require_focus.setChecked(checked)
        self.pause_focus.setChecked(checked)

    def _refresh_simple_advisory(self) -> None:
        if not hasattr(self, "simple_advisory_label"):
            return
        messages: list[str] = []
        if self.input_combo.currentData() == "dry_run":
            messages.append("Dry run is active: Play will not send keyboard input. Change Input method in Advanced → SCUM.")
        if self.playback_sections or self.loop_playback_check.isChecked():
            messages.append("Advanced song sections or looping are saved, but Simple mode plays the complete song once.")
        self.simple_advisory_label.setText("\n".join(messages))
        self.simple_advisory_label.setVisible(bool(messages))

    def _focus_midi_path(self) -> None:
        if self._output_busy():
            self._set_status("Stop current output before changing the MIDI source.")
            return
        self.showNormal()
        self.raise_()
        self.file_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.file_edit.selectAll()

    def show_quick_start(self) -> None:
        QMessageBox.information(
            self,
            "MusicalScumbag quick start",
            "<b>Simple mode:</b> load a MIDI, choose the SCUM instrument, then press <b>Play in SCUM</b>. "
            "Preparation is automatic.<br><br>"
            "<b>Advanced mode:</b> is organised by task: <b>Song</b> for musical intent, <b>Mapping</b> for SCUM pitch range, "
            "<b>Timing</b> for keyboard reliability, <b>SCUM</b> for bindings/focus, and <b>Live MIDI</b> for a physical controller.<br><br>"
            "Put SCUM's instrument into Play mode before starting. MusicalScumbag focuses SCUM and keeps the compact controller above it.<br><br>"
            "F8 always stops output and releases held keys. F9 plays, pauses, or resumes. "
            "F11 shows or hides the window.",
        )

    def show_keyboard_shortcuts(self) -> None:
        QMessageBox.information(
            self,
            "MusicalScumbag keyboard shortcuts",
            "<b>Ctrl+O</b> — Open MIDI<br>"
            "<b>Ctrl+R</b> — Reload current MIDI<br>"
            "<b>Ctrl+L</b> — Focus the MIDI path<br>"
            "<b>Ctrl+P</b> — Prepare SCUM score<br>"
            "<b>Delete</b> — Remove the selected playback section<br>"
            "<b>F8</b> — Emergency stop and panic release<br>"
            "<b>F9</b> — Play, pause, or resume<br>"
            "<b>F11</b> — Show or hide the window<br>"
            "<b>Numpad /</b> — Toggle auto-walk while SCUM is focused<br>"
            "<b>Ctrl+Numpad 4/6</b> — Seek backward/forward 5s<br>"
            "<b>F1</b> — Quick start",
        )

    def show_about(self) -> None:
        QMessageBox.information(
            self,
            f"About {APP_TITLE}",
            "A MIDI preparation and playback tool for SCUM instruments.<br><br>"
            "MusicalScumbag never injects into SCUM, edits game files, or runs unattended gameplay. "
            "Keyboard output remains user-initiated and protected by focus checks and F8 cleanup.",
        )

    def _set_advisories(self, messages: list[str] | tuple[str, ...]) -> None:
        cleaned = [str(message).strip() for message in messages if str(message).strip()]
        self.warning_label.setText("\n".join(f"• {message}" for message in cleaned))
        self.warning_label.setVisible(bool(cleaned))

    def _refresh_workflow_state(self, *_args) -> None:
        if not hasattr(self, "readiness_pill"):
            return
        selected = self.selected_tracks() if self.project else []
        playback_active = self._playback_active()
        live_active = self._live_midi_active()
        dry_run = self.input_combo.currentData() == "dry_run"
        if hasattr(self, "header_project_label"):
            project_name = self.project.path.name if self.project else "No MIDI loaded"
            self.header_project_label.setText(project_name)
            self.header_project_label.setToolTip(str(self.project.path) if self.project else "")

        if live_active:
            pill = "Live armed"
            pill_style = "pillGood"
            hint = "Controller input active · F8 or Stop releases every key"
        elif playback_active:
            paused = bool(getattr(self.scheduler, "paused", False))
            pill = "Paused" if paused else "Playing"
            pill_style = "pillGood"
            hint = "F9 resumes" if paused else "F9 pauses · F8 stops"
        elif not self.project:
            pill = "Load MIDI"
            pill_style = "pillIdle"
            hint = "Open or drop an original MIDI file to begin"
        elif not selected:
            pill = "Select tracks"
            pill_style = "pillIdle"
            hint = "Choose at least one populated source track"
        elif not self.plan:
            if self.settings.ui_mode == "simple":
                pill = "Ready"
                pill_style = "pillGood"
                hint = "Press Play in SCUM — preparation is automatic"
            else:
                pill = "Prepare"
                pill_style = "pillIdle"
                hint = "Review the instrument and playback preset, then prepare"
        else:
            pill = "Ready"
            pill_style = "pillGood"
            hint = "Dry run ready · no keyboard output" if dry_run else "Focus SCUM, put the instrument in Play mode, then start"

        self.readiness_pill.setText(pill)
        _set_visual_state(self.readiness_pill, pill_style)
        self.workflow_hint.setText(hint)
        self._refresh_simple_advisory()

        unlocked = not self._plan_controls_locked and not self._output_active()
        can_plan = unlocked and self.project is not None and bool(selected)
        self.prepare_button.setEnabled(can_plan)
        self.play_button.setEnabled(can_plan)
        self.export_button.setEnabled(can_plan)
        self.export_events_button.setEnabled(can_plan)
        self.prepare_action.setEnabled(can_plan)
        self.live_button.setEnabled(
            unlocked
            and bool(self.midi_devices)
            and self._selected_midi_device() is not None
        )
        self.pause_button.setEnabled(playback_active)
        self.stop_button.setEnabled(playback_active or live_active)

    def _refresh_track_selection_state(self) -> None:
        self._refresh_arrangement_lead_tracks()
        if not self.project:
            self.track_selection_label.setText("No MIDI loaded")
            self._refresh_workflow_state()
            return
        selected = len(self.selected_tracks())
        populated = sum(track.playable_note_count > 0 for track in self.project.tracks)
        shown = sum(not self.track_table.isRowHidden(row) for row in range(self.track_table.rowCount()))
        suffix = f" · {shown} shown" if shown != self.track_table.rowCount() else ""
        self.track_selection_label.setText(f"{selected} of {populated} populated selected{suffix}")
        self._refresh_workflow_state()

    def _refresh_arrangement_lead_tracks(self) -> None:
        preferred = self.arrangement_lead_combo.currentData()
        available = set(self.selected_tracks())
        self.arrangement_lead_combo.blockSignals(True)
        try:
            self.arrangement_lead_combo.clear()
            self.arrangement_lead_combo.addItem("Auto - detect vocal / melody", -1)
            if self.project:
                for track in self.project.tracks:
                    if track.index in available and track.playable_note_count > 0 and not track.is_percussion_only:
                        self.arrangement_lead_combo.addItem(f"{track.index}: {track.name}", track.index)
            self.arrangement_lead_combo.setCurrentIndex(
                max(0, self.arrangement_lead_combo.findData(preferred)),
            )
        finally:
            self.arrangement_lead_combo.blockSignals(False)
        self.settings.arrangement_lead_track = int(self.arrangement_lead_combo.currentData())
        self._update_chord_recognition_state()

    def _filter_tracks(self, text: str) -> None:
        terms = text.casefold().split()
        for row in range(self.track_table.rowCount()):
            haystack = " ".join(
                self.track_table.item(row, column).text()
                for column in range(1, self.track_table.columnCount())
                if self.track_table.item(row, column) is not None
            ).casefold()
            self.track_table.setRowHidden(row, not all(term in haystack for term in terms))
        self._refresh_track_selection_state()

    def _track_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        self.invalidate_plan()
        self._refresh_track_selection_state()

    def _toggle_track_row(self, row: int, _column: int) -> None:
        item = self.track_table.item(row, 0)
        if item is None or not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return
        item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)

    def _track_table_key_press(self, event) -> None:
        if event.key() == Qt.Key.Key_Space:
            row = self.track_table.currentRow()
            if 0 <= row < self.track_table.rowCount():
                self._toggle_track_row(row, 0)
                event.accept()
                return
        QTableWidget.keyPressEvent(self.track_table, event)

    def invert_tracks(self) -> None:
        self.track_table.blockSignals(True)
        for row in range(self.track_table.rowCount()):
            item = self.track_table.item(row, 0)
            if item and (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)
        self.track_table.blockSignals(False)
        self.invalidate_plan()
        self._refresh_track_selection_state()


    def _refresh_recent_menu(self) -> None:
        self.recent_menu.clear()
        self.recent_file_actions: list[QAction] = []
        controls_enabled = not self._plan_controls_locked and not self._output_active()
        for index, path_text in enumerate(self.settings.recent_files, start=1):
            path = Path(path_text)
            missing = not path.is_file()
            label = f"{index}. {path.name} — {path.parent}"
            if missing:
                label += " (missing)"
            action = QAction(label, self.recent_menu)
            action.setToolTip(str(path))
            action.setEnabled(controls_enabled and not missing)
            action.triggered.connect(lambda _checked=False, recent_path=str(path): self.load_file(recent_path))
            self.recent_menu.addAction(action)
            self.recent_file_actions.append(action)
        if not self.recent_file_actions:
            empty_action = QAction("No recent MIDI files", self.recent_menu)
            empty_action.setEnabled(False)
            self.recent_menu.addAction(empty_action)
        self.recent_menu.addSeparator()
        self.clear_recent_action = QAction("Clear recent files", self.recent_menu)
        self.clear_recent_action.setEnabled(controls_enabled and bool(self.settings.recent_files))
        self.clear_recent_action.triggered.connect(self._clear_recent_files)
        self.recent_menu.addAction(self.clear_recent_action)

    def _remember_recent_file(self, path: str | Path) -> None:
        resolved = str(Path(path).expanduser().resolve())
        identity = os.path.normcase(resolved)
        remaining = [
            recent
            for recent in self.settings.recent_files
            if os.path.normcase(str(Path(recent).expanduser().resolve())) != identity
        ]
        self.settings.recent_files = [resolved, *remaining][:MAX_RECENT_MIDI_FILES]
        self._refresh_recent_menu()

    def _clear_recent_files(self) -> None:
        self.settings.recent_files = []
        self._refresh_recent_menu()
        self._save_ui_to_settings()
        self._set_status("Recent MIDI history cleared.")

    def reload_current_file(self) -> None:
        path = str(self.project.path) if self.project else self.file_edit.text().strip()
        if path:
            self.load_file(path)

    def _load_last_file_after_startup(self) -> None:
        path = self.settings.last_file
        if path and Path(path).exists() and not self._output_busy():
            self.load_file(path)

    def _set_plan_controls_enabled(self, enabled: bool) -> None:
        self._plan_controls_locked = not enabled
        for widget in self._plan_widgets:
            widget.setEnabled(enabled)
        self.tracks_box.setEnabled(enabled and self.project is not None)
        self.section_box.setEnabled(enabled and self.project is not None)
        self.reload_button.setEnabled(enabled and self.project is not None)
        for action in self._plan_actions:
            action.setEnabled(enabled)
        self.reload_action.setEnabled(enabled and self.project is not None)
        self.midi_input_combo.setEnabled(enabled and bool(self.midi_devices))
        self._update_chord_recognition_state()
        self._refresh_recent_menu()
        self._refresh_workflow_state()

    def _selected_midi_device(self) -> MidiInputDevice | None:
        try:
            index = int(self.midi_input_combo.currentData())
        except (TypeError, ValueError):
            return None
        return self.midi_devices.get(index)

    def _refresh_midi_devices(
        self,
        _checked: bool = False,
        *,
        show_status: bool = True,
    ) -> None:
        if self._output_busy():
            if show_status:
                self._set_status("Stop current output before refreshing MIDI inputs.")
            return
        selected = self._selected_midi_device()
        preferred_name = selected.name if selected else self.settings.midi_input_name
        try:
            devices = self.midi_provider.input_devices()
            error_message = ""
        except MidiInputUnavailable as exc:
            devices = ()
            error_message = str(exc)
        except Exception as exc:
            logger.exception("Could not enumerate MIDI inputs")
            devices = ()
            error_message = f"Could not enumerate MIDI inputs: {exc}"

        self.midi_devices = {device.index: device for device in devices}
        self.midi_input_combo.blockSignals(True)
        try:
            self.midi_input_combo.clear()
            preferred_index = -1
            if preferred_name and not any(
                device.name == preferred_name for device in devices
            ):
                self.midi_input_combo.addItem(
                    f"{preferred_name} · not connected",
                    None,
                )
                preferred_index = 0
            for device in devices:
                self.midi_input_combo.addItem(device.display_name, device.index)
                if preferred_index < 0 and device.name == preferred_name:
                    preferred_index = self.midi_input_combo.count() - 1
            if not devices and self.midi_input_combo.count() == 0:
                self.midi_input_combo.addItem(
                    "MIDI runtime unavailable" if error_message else "No MIDI inputs detected",
                    None,
                )
            self.midi_input_combo.setCurrentIndex(max(0, preferred_index))
        finally:
            self.midi_input_combo.blockSignals(False)

        has_selection = self._selected_midi_device() is not None
        controls_enabled = not self._plan_controls_locked
        self.midi_input_combo.setEnabled(controls_enabled and bool(devices))
        self.live_button.setEnabled(controls_enabled and has_selection)
        if error_message:
            self.live_state_label.setText(error_message)
        elif not devices:
            self.live_state_label.setText(
                "No MIDI keyboard detected. Connect one, then choose Refresh."
            )
        elif not has_selection:
            self.live_state_label.setText(
                "The saved MIDI keyboard is disconnected. Select another input or reconnect it."
            )
        else:
            self.live_state_label.setText(
                "Set SCUM to its base octave before arming. Live input never taps Ctrl or Shift."
            )
        if show_status:
            if error_message:
                self._set_status(error_message)
            else:
                self._set_status(
                    f"Found {len(devices)} MIDI input port(s)."
                    if devices
                    else "No MIDI input ports detected."
                )
        self._refresh_workflow_state()

    def _midi_device_changed(self, _index: int) -> None:
        if self._loading_ui or self._output_busy():
            return
        device = self._selected_midi_device()
        self.live_button.setEnabled(device is not None)
        if device is not None:
            self.settings.midi_input_name = device.name
            self.live_state_label.setText(
                "Set SCUM to its base octave before arming. Live input never taps Ctrl or Shift."
            )
        self._refresh_workflow_state()

    def _connect_signals(self) -> None:
        self.simple_mode_button.clicked.connect(lambda _checked=False: self._set_ui_mode("simple", save=True))
        self.advanced_mode_button.clicked.connect(lambda _checked=False: self._set_ui_mode("advanced", save=True))
        self.simple_show_advanced_button.clicked.connect(lambda _checked=False: self._set_ui_mode("advanced", save=True))
        self.simple_instrument_combo.currentIndexChanged.connect(self._simple_instrument_changed)
        self.simple_performance_combo.currentIndexChanged.connect(self._simple_performance_changed)
        self.simple_speed_slider.valueChanged.connect(self._simple_speed_changed)
        self.simple_transpose_slider.valueChanged.connect(self._simple_transpose_changed)
        self.simple_countdown_slider.valueChanged.connect(self._simple_countdown_changed)
        self.simple_focus_safety_check.toggled.connect(self._simple_focus_safety_changed)
        self.simple_auto_transpose_button.clicked.connect(self._recommend_transpose_clicked)
        self.simple_test_button.clicked.connect(self.test_note)

        self.browse_button.clicked.connect(self.browse_file)
        self.reload_button.clicked.connect(self.reload_current_file)
        self.file_edit.returnPressed.connect(lambda: self.load_file(self.file_edit.text().strip()))
        self.track_filter_edit.textChanged.connect(self._filter_tracks)
        self.track_table.cellDoubleClicked.connect(self._toggle_track_row)
        self.select_all_button.clicked.connect(lambda: self._set_all_tracks(True))
        self.select_none_button.clicked.connect(lambda: self._set_all_tracks(False))
        self.invert_tracks_button.clicked.connect(self.invert_tracks)
        self.auto_select_button.clicked.connect(self.auto_select_tracks)
        self.add_play_section_button.clicked.connect(lambda: self.add_playback_section("include"))
        self.add_omit_section_button.clicked.connect(lambda: self.add_playback_section("omit"))
        self.update_section_button.clicked.connect(self.update_playback_section)
        self.remove_section_button.clicked.connect(self.remove_playback_section)
        self.clear_sections_button.clicked.connect(self.clear_playback_sections)
        self.section_table.itemSelectionChanged.connect(self._section_selection_changed)
        self.section_gap_spin.valueChanged.connect(self._section_gap_changed)
        self.loop_playback_check.toggled.connect(self._loop_playback_changed)
        self.prepare_button.clicked.connect(self.prepare_plan)
        self.play_button.clicked.connect(self.play)
        self.live_button.clicked.connect(self.start_live_midi)
        self.pause_button.clicked.connect(self.pause_resume)
        self.stop_button.clicked.connect(self.stop)
        self.export_button.clicked.connect(self.export_score)
        self.export_events_button.clicked.connect(self.export_plan)
        self.custom_keys_button.clicked.connect(self.edit_custom_keys)
        self.test_button.clicked.connect(self.test_note)
        self.refresh_midi_button.clicked.connect(self._refresh_midi_devices)
        self.midi_input_combo.currentIndexChanged.connect(self._midi_device_changed)
        self.profile_combo.currentTextChanged.connect(self._profile_changed)
        self.performance_combo.currentIndexChanged.connect(self._performance_preset_changed)
        self.instrument_combo.currentIndexChanged.connect(self._instrument_changed)
        self.arrangement_combo.currentIndexChanged.connect(self._update_chord_recognition_state)
        self.arrangement_lead_combo.currentIndexChanged.connect(self._arrangement_lead_changed)
        self.input_combo.currentIndexChanged.connect(self._refresh_workflow_state)

        preset_controlled = [
            self.arrangement_combo,
            self.chord_recognition_combo,
            self.ignore_percussion_check,
            self.mapping_combo,
            self.expression_spin,
            self.polyphony_spin,
            self.density_spin,
            self.source_min_note_spin,
            self.retrigger_spin,
            self.speed_spin,
            self.hold_spin,
            self.min_hold_spin,
            self.max_hold_spin,
            self.spread_spin,
            self.key_gap_spin,
            self.modifier_release_spin,
            self.modifier_settle_spin,
            self.fidelity_priority_combo,
            self.mapping_stability_spin,
            self.bank_switch_budget_spin,
            self.c_boundary_combo,
        ]
        for widget in preset_controlled:
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._mark_performance_custom)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.valueChanged.connect(self._mark_performance_custom)
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(self._mark_performance_custom)
        self.restore_base_bank_check.toggled.connect(self._mark_performance_custom)

        invalidate_widgets = [
            self.profile_combo,
            self.input_combo,
            self.instrument_combo,
            self.performance_combo,
            self.arrangement_combo,
            self.chord_recognition_combo,
            self.ignore_percussion_check,
            self.mapping_combo,
            self.transpose_spin,
            self.polyphony_spin,
            self.density_spin,
            self.source_min_note_spin,
            self.retrigger_spin,
            self.expression_spin,
            self.speed_spin,
            self.hold_spin,
            self.min_hold_spin,
            self.max_hold_spin,
            self.spread_spin,
            self.key_gap_spin,
            self.modifier_release_spin,
            self.modifier_settle_spin,
            self.fidelity_priority_combo,
            self.mapping_stability_spin,
            self.bank_switch_budget_spin,
            self.c_boundary_combo,
            self.restore_base_bank_check,
            self.countdown_spin,
            self.require_focus,
            self.pause_focus,
        ]
        for widget in invalidate_widgets:
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self.invalidate_plan)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.valueChanged.connect(self.invalidate_plan)
            elif isinstance(widget, QCheckBox):
                widget.toggled.connect(self.invalidate_plan)
        self.instrument_combo.currentIndexChanged.connect(self._sync_simple_from_advanced)
        self.performance_combo.currentIndexChanged.connect(self._sync_simple_from_advanced)
        self.speed_spin.valueChanged.connect(self._sync_simple_from_advanced)
        self.transpose_spin.valueChanged.connect(self._sync_simple_from_advanced)
        self.countdown_spin.valueChanged.connect(self._sync_simple_from_advanced)
        self.require_focus.toggled.connect(self._sync_simple_from_advanced)
        self.pause_focus.toggled.connect(self._sync_simple_from_advanced)
        self.track_table.itemChanged.connect(self._track_item_changed)

    def _load_performance_values_from_settings(self) -> None:
        arrangement_index = self.arrangement_combo.findData(self.settings.arrangement_mode)
        self.arrangement_combo.setCurrentIndex(max(0, arrangement_index))
        recognition_index = self.chord_recognition_combo.findData(self.settings.chord_recognition_mode)
        self.chord_recognition_combo.setCurrentIndex(max(0, recognition_index))
        mapping_index = self.mapping_combo.findData(self.settings.mapping_mode)
        self.mapping_combo.setCurrentIndex(max(0, mapping_index))
        self.ignore_percussion_check.setChecked(self.settings.ignore_percussion)
        self.polyphony_spin.setValue(self.settings.max_polyphony)
        self.density_spin.setValue(self.settings.max_notes_per_second)
        self.source_min_note_spin.setValue(self.settings.min_source_note_ms)
        self.retrigger_spin.setValue(self.settings.min_retrigger_ms)
        self.expression_spin.setValue(round(self.settings.velocity_expression * 100))
        self.speed_spin.setValue(self.settings.speed)
        self.hold_spin.setValue(round(self.settings.hold_ratio * 100))
        self.min_hold_spin.setValue(self.settings.min_hold_ms)
        self.max_hold_spin.setValue(self.settings.max_hold_ms)
        self.spread_spin.setValue(self.settings.chord_spread_ms)
        self.key_gap_spin.setValue(self.settings.key_retrigger_gap_ms)
        self.modifier_release_spin.setValue(self.settings.modifier_release_ms)
        self.modifier_settle_spin.setValue(self.settings.modifier_settle_ms)
        priority_index = self.fidelity_priority_combo.findData(self.settings.fidelity_priority)
        self.fidelity_priority_combo.setCurrentIndex(max(0, priority_index))
        self.mapping_stability_spin.setValue(self.settings.mapping_stability)
        self.bank_switch_budget_spin.setValue(self.settings.bank_switch_budget_per_second)
        boundary_index = self.c_boundary_combo.findData(self.settings.c_boundary_preference)
        self.c_boundary_combo.setCurrentIndex(max(0, boundary_index))
        self.restore_base_bank_check.setChecked(self.settings.restore_base_bank)
        self._update_chord_recognition_state()

    def _instrument_changed(self, _index: int) -> None:
        instrument = resolve_instrument_profile(self.instrument_combo.currentData())
        self.instrument_hint.setText(
            f"{instrument.preparation_note} Hard maximum: {instrument.max_sustain_ms:,} ms per played note."
        )
        if not self._loading_ui:
            self.settings.target_instrument = instrument.key

    def _update_chord_recognition_state(self, *_args) -> None:
        self.chord_recognition_combo.setEnabled(self.arrangement_combo.currentData() in CHORD_RECOGNITION_MODES)
        recipe = ARRANGEMENT_RECIPES.get(self.arrangement_combo.currentData())
        self.arrangement_lead_combo.setEnabled(recipe is not None and not self._plan_controls_locked)
        if recipe is not None:
            self.arrangement_layers_label.setText(
                f"This style can use up to {recipe.layers} musical layer(s). Select all relevant tracks; "
                "use Lead / melody track only when you want to override automatic lead detection. "
                "The Timing tab still caps the final keyboard output."
            )
        else:
            self.arrangement_layers_label.setText(
                "This style uses the selected MIDI tracks directly, so Lead / melody track is not used. "
                "The Timing tab still caps the final keyboard output."
            )

    def _arrangement_lead_changed(self, *_args) -> None:
        if not self._loading_ui:
            self.settings.arrangement_lead_track = int(self.arrangement_lead_combo.currentData())

    def _performance_preset_changed(self, _index: int) -> None:
        if self._loading_ui or self._applying_preset:
            return
        preset_name = str(self.performance_combo.currentData())
        if preset_name == "custom":
            self.settings.performance_preset = "custom"
            self._update_performance_hint("custom")
            self._set_advanced_controls_visible()
            return
        self._applying_preset = True
        try:
            apply_performance_preset(self.settings, preset_name)
            self._load_performance_values_from_settings()
            self._update_performance_hint(preset_name)
            self._set_advanced_controls_visible()
        finally:
            self._applying_preset = False
        self.invalidate_plan()
        self._set_status(f"Applied {self.performance_combo.currentText()} performance preset.")

    def _mark_performance_custom(self, *_args) -> None:
        if self._loading_ui or self._applying_preset:
            return
        if self.performance_combo.currentData() != "custom":
            self._applying_preset = True
            try:
                index = self.performance_combo.findData("custom")
                self.performance_combo.setCurrentIndex(index)
            finally:
                self._applying_preset = False
        self.settings.performance_preset = "custom"
        self._update_performance_hint("custom")
        self._set_advanced_controls_visible()

    def _set_advanced_controls_visible(self) -> None:
        # Advanced mode is intentionally transparent: presets are starting points,
        # never gates that hide the controls they changed.
        self.mapping_box.setVisible(True)
        preset_name = str(self.performance_combo.currentData())
        if preset_name == "custom":
            label = "Custom tuning"
        else:
            preset = PERFORMANCE_PRESETS.get(preset_name, {})
            label = f"Preset: {preset.get('label', self.performance_combo.currentText())}"
        if hasattr(self, "advanced_preset_state"):
            self.advanced_preset_state.setText(label)
            _set_visual_state(
                self.advanced_preset_state,
                "inlineWarn" if preset_name == "custom" else "inlineIdle",
            )

    def _on_unlimited_inputs_toggled(self, checked: bool) -> None:
        self.settings.unlimited_number_inputs = checked
        self._apply_unlimited_input_bounds(checked)
        self.invalidate_plan()

    def _apply_unlimited_input_bounds(self, enabled: bool) -> None:
        if not hasattr(self, "_default_spin_ranges"):
            return
        for spin, (default_min, default_max) in self._default_spin_ranges.items():
            if enabled:
                if isinstance(spin, QDoubleSpinBox):
                    spin.setRange(0.0, 999999.0)
                else:
                    min_val = -999999 if default_min < 0 else 0
                    spin.setRange(min_val, 999999)
            else:
                spin.setRange(default_min, default_max)

    def _update_performance_hint(self, preset_name: str) -> None:
        if preset_name == "custom":
            text = (
                "Custom means at least one preset-controlled value has been edited manually. Nothing extra is unlocked or hidden; "
                "use the Mapping and Timing tabs to tune only the behaviour you actually need to change."
            )
        else:
            preset = PERFORMANCE_PRESETS.get(preset_name, {})
            text = str(preset.get("description", "Unknown performance preset."))
        self.performance_hint.setText(text)

    def _load_settings_into_ui(self) -> None:
        self._loading_ui = True
        try:
            self.profile_combo.setCurrentText(self.settings.profile_name)
            instrument_index = self.instrument_combo.findData(self.settings.target_instrument)
            self.instrument_combo.setCurrentIndex(max(0, instrument_index))
            index = self.input_combo.findData(self.settings.input_mode)
            self.input_combo.setCurrentIndex(max(0, index))
            live_mapping_index = self.live_mapping_combo.findData(
                self.settings.live_midi_mapping_mode
            )
            self.live_mapping_combo.setCurrentIndex(max(0, live_mapping_index))
            self.live_transpose_spin.setValue(self.settings.live_midi_transpose)
            live_channel_index = self.live_channel_combo.findData(
                self.settings.live_midi_channel
            )
            self.live_channel_combo.setCurrentIndex(max(0, live_channel_index))
            self.live_ignore_channel_10.setChecked(
                self.settings.live_midi_ignore_channel_10
            )
            self.live_polyphony_spin.setValue(
                self.settings.live_midi_max_polyphony
            )
            preset_index = self.performance_combo.findData(self.settings.performance_preset)
            self.performance_combo.setCurrentIndex(max(0, preset_index))
            self._load_performance_values_from_settings()
            self.transpose_spin.setValue(self.settings.transpose)
            self.countdown_spin.setValue(self.settings.countdown_s)
            self.section_gap_spin.setValue(self.settings.section_gap_ms)
            self.loop_playback_check.setChecked(self.settings.loop_playback)
            self.require_focus.setChecked(self.settings.require_scum_focus)
            self.pause_focus.setChecked(self.settings.pause_on_focus_loss)
            self.unlimited_inputs_check.setChecked(self.settings.unlimited_number_inputs)
            self._apply_unlimited_input_bounds(self.settings.unlimited_number_inputs)
            self.keep_on_top_action.blockSignals(True)
            self.keep_on_top_action.setChecked(self.settings.window_on_top)
            self.keep_on_top_action.blockSignals(False)
            self._user_keep_on_top = bool(self.settings.window_on_top)
            self._apply_topmost_state()
            self._update_profile_hint(self.settings.profile_name)
            self._instrument_changed(self.instrument_combo.currentIndex())
            self._update_performance_hint(self.settings.performance_preset)
            self._set_advanced_controls_visible()
            self._set_ui_mode(self.settings.ui_mode)
        finally:
            self._loading_ui = False

    def _commit_numeric_edits(self) -> None:
        # Shortcuts can prepare/save while an editor still has focus.
        # Commit complete pending text before reading preset identity or values.
        for spin in self.findChildren(QSpinBox) + self.findChildren(QDoubleSpinBox):
            spin.interpretText()

    def _save_ui_to_settings(self) -> None:
        self._commit_numeric_edits()
        self.settings.profile_name = self.profile_combo.currentText()
        self.settings.target_instrument = str(self.instrument_combo.currentData())
        self.settings.input_mode = str(self.input_combo.currentData())
        selected_midi_device = self._selected_midi_device()
        if selected_midi_device is not None:
            self.settings.midi_input_name = selected_midi_device.name
        self.settings.live_midi_mapping_mode = str(
            self.live_mapping_combo.currentData()
        )
        self.settings.live_midi_transpose = self.live_transpose_spin.value()
        self.settings.live_midi_channel = int(self.live_channel_combo.currentData())
        self.settings.live_midi_ignore_channel_10 = (
            self.live_ignore_channel_10.isChecked()
        )
        self.settings.live_midi_max_polyphony = self.live_polyphony_spin.value()
        self.settings.performance_preset = str(self.performance_combo.currentData())
        self.settings.arrangement_mode = str(self.arrangement_combo.currentData())
        self.settings.arrangement_lead_track = int(self.arrangement_lead_combo.currentData())
        self.settings.chord_recognition_mode = str(self.chord_recognition_combo.currentData())
        self.settings.ignore_percussion = self.ignore_percussion_check.isChecked()
        self.settings.mapping_mode = str(self.mapping_combo.currentData())
        self.settings.transpose = self.transpose_spin.value()
        self.settings.max_polyphony = self.polyphony_spin.value()
        self.settings.max_notes_per_second = self.density_spin.value()
        self.settings.min_source_note_ms = self.source_min_note_spin.value()
        self.settings.min_retrigger_ms = self.retrigger_spin.value()
        self.settings.velocity_expression = self.expression_spin.value() / 100.0
        self.settings.fidelity_priority = str(self.fidelity_priority_combo.currentData())
        self.settings.mapping_stability = self.mapping_stability_spin.value()
        self.settings.bank_switch_budget_per_second = self.bank_switch_budget_spin.value()
        self.settings.c_boundary_preference = str(self.c_boundary_combo.currentData())
        self.settings.restore_base_bank = self.restore_base_bank_check.isChecked()
        self.settings.speed = self.speed_spin.value()
        self.settings.hold_ratio = self.hold_spin.value() / 100.0
        self.settings.min_hold_ms = self.min_hold_spin.value()
        self.settings.max_hold_ms = max(self.settings.min_hold_ms, self.max_hold_spin.value())
        self.settings.chord_spread_ms = self.spread_spin.value()
        self.settings.key_retrigger_gap_ms = self.key_gap_spin.value()
        self.settings.modifier_release_ms = self.modifier_release_spin.value()
        self.settings.modifier_settle_ms = self.modifier_settle_spin.value()
        self.settings.countdown_s = self.countdown_spin.value()
        self.settings.section_gap_ms = self.section_gap_spin.value()
        self.settings.loop_playback = self.loop_playback_check.isChecked()
        self.settings.require_scum_focus = self.require_focus.isChecked()
        self.settings.pause_on_focus_loss = self.pause_focus.isChecked()
        self.settings.unlimited_number_inputs = self.unlimited_inputs_check.isChecked()
        self.settings.window_on_top = self._user_keep_on_top
        self.settings.last_file = self.file_edit.text().strip()
        if self.project:
            self.settings.selected_tracks_by_file[str(self.project.path)] = self.selected_tracks()
            self.settings.playback_sections_by_file[str(self.project.path)] = [
                section_to_dict(section) for section in self.playback_sections
            ]
        if self._compact_playback and self._editor_geometry is not None:
            self.settings.window_width = self._editor_geometry.width()
            self.settings.window_height = self._editor_geometry.height()
        else:
            geometry = self.normalGeometry() if self.isMaximized() else self.geometry()
            self.settings.window_width = geometry.width()
            self.settings.window_height = geometry.height()
        save_settings(self.settings)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._output_busy():
            return
        urls = event.mimeData().urls()
        if urls and Path(urls[0].toLocalFile()).suffix.lower() in {".mid", ".midi"}:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        if self._output_busy():
            event.ignore()
            self._set_status("Stop current output before loading another MIDI file.")
            return
        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return
        path = urls[0].toLocalFile()
        if Path(path).suffix.lower() not in {".mid", ".midi"}:
            event.ignore()
            return
        self.load_file(path)
        event.acceptProposedAction()

    def _track_analysis_settings(self) -> AppSettings:
        """Read the current selection settings without saving or applying a performance preset."""

        return replace(
            self.settings,
            performance_preset=str(self.performance_combo.currentData()),
            arrangement_mode=str(self.arrangement_combo.currentData()),
            arrangement_lead_track=int(self.arrangement_lead_combo.currentData()),
            max_polyphony=self.polyphony_spin.value(),
            ignore_percussion=self.ignore_percussion_check.isChecked(),
            min_source_note_ms=self.source_min_note_spin.value(),
            min_retrigger_ms=self.retrigger_spin.value(),
        )

    def _refresh_track_analysis_tooltips(self) -> None:
        if not self.project or not self.score_analysis:
            return
        reasons = dict(self.score_analysis.selection_reasons)
        recommended = set(self.score_analysis.recommended_track_indices)
        for row, track in enumerate(self.project.tracks):
            reason = reasons.get(track.index)
            if reason is None:
                reason = (
                    "Recommended source track."
                    if track.index in recommended
                    else "Not needed by the current recommendation."
                )
            role_item = self.track_table.item(row, 3)
            role = role_item.text() if role_item is not None else "Musical"
            row_help = (
                f"Track {track.index}: {track.name}. {role}. {track.note_count:,} notes, "
                f"range {track.pitch_range_text}. Smart auto-select: {reason}"
            )
            for column in range(self.track_table.columnCount()):
                item = self.track_table.item(row, column)
                if item is not None:
                    item.setToolTip(row_help)

    def auto_select_tracks(self) -> None:
        if self._output_busy():
            self._set_status("Stop playback or live MIDI before changing the track selection.")
            return
        if not self.project:
            return
        self.score_analysis = analyse_project(self.project, settings=self._track_analysis_settings())
        preferred = set(self.score_analysis.recommended_track_indices)
        self.track_table.blockSignals(True)
        try:
            for row in range(self.track_table.rowCount()):
                item = self.track_table.item(row, 0)
                if item and (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                    item.setCheckState(Qt.Checked if int(item.data(Qt.UserRole)) in preferred else Qt.Unchecked)
            self._refresh_track_analysis_tooltips()
        finally:
            self.track_table.blockSignals(False)
        self.invalidate_plan()
        self._refresh_track_selection_state()
        self._set_advisories([self.score_analysis.rationale, *self.project.warnings])
        self._set_status(self.score_analysis.rationale)

    def _set_section_time_bounds(self, duration_ms: float) -> None:
        maximum = _qtime_from_ms(duration_ms)
        for editor in (self.section_start_time, self.section_end_time):
            editor.setMinimumTime(QTime(0, 0))
            editor.setMaximumTime(maximum)
        self.section_start_time.setTime(QTime(0, 0))
        self.section_end_time.setTime(maximum)

    def _refresh_section_table(self) -> None:
        self.section_table.blockSignals(True)
        self.section_table.setRowCount(len(self.playback_sections))
        for row, section in enumerate(self.playback_sections):
            action = section.label or ("Play" if section.mode == "include" else "Omit")
            self.section_table.setItem(row, 0, QTableWidgetItem(action))
            self.section_table.setItem(row, 1, QTableWidgetItem(format_timecode(section.start_ms)))
            self.section_table.setItem(row, 2, QTableWidgetItem(format_timecode(section.end_ms)))
            self.section_table.setItem(
                row,
                3,
                QTableWidgetItem(format_timecode(section.end_ms - section.start_ms)),
            )
        self.section_table.blockSignals(False)
        active = bool(self.playback_sections)
        self.update_section_button.setEnabled(False)
        self.remove_section_button.setEnabled(False)
        self.clear_sections_button.setEnabled(active)
        self.prepare_button.setText("Prepare selection" if active else "Prepare")
        self.play_button.setText("Play selection" if active else "Play")

    def _section_selection_changed(self) -> None:
        row = self.section_table.currentRow()
        selected = bool(self.section_table.selectedItems()) and 0 <= row < len(self.playback_sections)
        self.update_section_button.setEnabled(selected)
        self.remove_section_button.setEnabled(selected)
        if not selected:
            return
        section = self.playback_sections[row]
        self.section_start_time.setTime(_qtime_from_ms(section.start_ms))
        self.section_end_time.setTime(_qtime_from_ms(section.end_ms))

    def add_playback_section(self, mode: str) -> None:
        if not self.project:
            QMessageBox.information(self, APP_TITLE, "Load a MIDI file before defining playback sections.")
            return
        start_ms = float(self.section_start_time.time().msecsSinceStartOfDay())
        end_ms = float(self.section_end_time.time().msecsSinceStartOfDay())
        if end_ms <= start_ms:
            QMessageBox.warning(self, APP_TITLE, "The section end must be later than its start.")
            return
        count = 1 + sum(section.mode == mode for section in self.playback_sections)
        label = f"{'Play' if mode == 'include' else 'Omit'} range {count}"
        added = PlaybackSection(mode, start_ms, end_ms, label)
        self.playback_sections.append(added)
        self.playback_sections.sort(key=lambda section: (section.start_ms, section.end_ms, section.mode))
        self._refresh_section_table()
        added_row = next(index for index, section in enumerate(self.playback_sections) if section is added)
        self.section_table.selectRow(added_row)
        self.invalidate_plan()
        self._save_ui_to_settings()
        self._set_status(f"Added {label.lower()}: {format_timecode(start_ms)}–{format_timecode(end_ms)}.")

    def update_playback_section(self) -> None:
        row = self.section_table.currentRow()
        if not self.section_table.selectedItems() or not 0 <= row < len(self.playback_sections):
            return
        start_ms = float(self.section_start_time.time().msecsSinceStartOfDay())
        end_ms = float(self.section_end_time.time().msecsSinceStartOfDay())
        if end_ms <= start_ms:
            QMessageBox.warning(self, APP_TITLE, "The section end must be later than its start.")
            return
        previous = self.playback_sections[row]
        updated = PlaybackSection(previous.mode, start_ms, end_ms, previous.label)
        self.playback_sections[row] = updated
        self.playback_sections.sort(key=lambda section: (section.start_ms, section.end_ms, section.mode))
        self._refresh_section_table()
        updated_row = next(index for index, section in enumerate(self.playback_sections) if section is updated)
        self.section_table.selectRow(updated_row)
        self.invalidate_plan()
        self._save_ui_to_settings()
        self._set_status(
            f"Updated {previous.label.lower() or 'playback range'}: "
            f"{format_timecode(start_ms)}–{format_timecode(end_ms)}."
        )

    def remove_playback_section(self) -> None:
        row = self.section_table.currentRow()
        if not self.section_table.selectedItems() or not 0 <= row < len(self.playback_sections):
            return
        removed = self.playback_sections.pop(row)
        self._refresh_section_table()
        self.invalidate_plan()
        self._save_ui_to_settings()
        self._set_status(f"Removed {removed.label.lower() or 'playback range'}.")

    def clear_playback_sections(self) -> None:
        if not self.playback_sections:
            return
        self.playback_sections.clear()
        self._refresh_section_table()
        self.invalidate_plan()
        self._save_ui_to_settings()
        self._set_status("Playback ranges cleared; the complete selected tracks will play.")

    def _section_gap_changed(self, value: int) -> None:
        if self._loading_ui:
            return
        self.settings.section_gap_ms = value
        if self.playback_sections:
            self.invalidate_plan()
        self._save_ui_to_settings()

    def _loop_playback_changed(self, checked: bool) -> None:
        if self._loading_ui:
            return
        self.settings.loop_playback = checked
        self._save_ui_to_settings()

    def browse_file(self) -> None:
        start = self.file_edit.text().strip() or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Open MIDI", start, "MIDI files (*.mid *.midi)")
        if path:
            self.load_file(path)

    def load_file(self, path: str) -> None:
        path = str(path).strip()
        if len(path) >= 2 and path[0] == path[-1] and path[0] in {'"', "'"}:
            path = path[1:-1].strip()
        if not path:
            return
        if self._output_busy():
            self._set_status("Stop playback or live MIDI before loading another MIDI file.")
            return
        source = Path(path).expanduser()
        if source.suffix.lower() not in {".mid", ".midi"}:
            QMessageBox.warning(self, APP_TITLE, "Choose a .mid or .midi file.")
            self._set_status("Unsupported MIDI file type")
            return
        if not source.is_file():
            QMessageBox.warning(self, APP_TITLE, f"MIDI file not found:\n\n{source}")
            self._set_status("MIDI file not found")
            return
        try:
            source = source.resolve()
        except (OSError, RuntimeError):
            pass
        try:
            self._set_status("Reading MIDI…")
            QApplication.processEvents()
            project = load_midi(source)
        except Exception as exc:
            logger.exception("Could not read MIDI file: %s", source)
            QMessageBox.critical(self, APP_TITLE, f"Could not read the MIDI file:\n\n{exc}")
            self._set_status("MIDI load failed")
            return
        if self.project:
            self.settings.playback_sections_by_file[str(self.project.path)] = [
                section_to_dict(section) for section in self.playback_sections
            ]
        previous_path = str(self.project.path) if self.project else self.settings.last_file
        if previous_path != str(project.path):
            self.arrangement_lead_combo.blockSignals(True)
            self.arrangement_lead_combo.setCurrentIndex(0)
            self.arrangement_lead_combo.blockSignals(False)
            self.settings.arrangement_lead_track = -1
        remembered_lead = self.settings.arrangement_lead_track
        self.project = project
        self.score_analysis = analyse_project(
            project,
            settings=replace(self._track_analysis_settings(), arrangement_lead_track=remembered_lead),
        )
        self.active_selection = None
        self.playback_sections = sections_from_dicts(
            self.settings.playback_sections_by_file.get(str(project.path), []),
            project.duration_ms,
        )
        self._set_section_time_bounds(project.duration_ms)
        self._refresh_section_table()
        self.file_edit.setText(str(project.path))
        self.track_filter_edit.clear()
        self.settings.last_file = str(project.path)
        self._remember_recent_file(project.path)
        self.reload_button.setEnabled(True)
        self.reload_action.setEnabled(True)
        self.track_table.blockSignals(True)
        self.track_table.setRowCount(len(project.tracks))
        saved_tracks = self.settings.selected_tracks_by_file.get(str(project.path))
        remembered = set(saved_tracks or [])
        playable = {track.index for track in project.tracks if track.playable_note_count > 0}
        remembered_available = sorted(remembered.intersection(playable))
        restored_selection = saved_tracks is not None and (not remembered or bool(remembered_available))
        available = remembered_available if restored_selection else list(self.score_analysis.recommended_track_indices)
        selected_analysis = analyse_notes(project.notes_for_tracks(available))
        analysed_tracks = {track.track_index: track for track in self.score_analysis.tracks}
        for row, track in enumerate(project.tracks):
            use = QTableWidgetItem()
            if track.playable_note_count > 0:
                use.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            else:
                use.setFlags(Qt.ItemFlag.NoItemFlags)
            use.setCheckState(Qt.Checked if track.index in available else Qt.Unchecked)
            use.setData(Qt.UserRole, track.index)
            self.track_table.setItem(row, 0, use)
            self.track_table.setItem(row, 1, QTableWidgetItem(str(track.index)))
            display_name = f"{track.name} [percussion]" if track.is_percussion_only else track.name
            self.track_table.setItem(row, 2, QTableWidgetItem(display_name))
            if track.is_percussion_only:
                role = "Ignored percussion"
            elif track.note_count == 0:
                role = "No notes"
            else:
                analysis = analysed_tracks.get(track.index)
                role = analysis.role if analysis else "Musical"
                if analysis and analysis.program_family:
                    role = f"{role} · {analysis.program_family}"
            role_item = QTableWidgetItem(role)
            if "percussion" in role.lower() or "no notes" in role.lower():
                role_item.setForeground(QColor("#6f6f69"))
            elif "lead" in role.lower() or "melody" in role.lower():
                role_item.setForeground(QColor("#c1b58f"))
            else:
                role_item.setForeground(QColor("#aaa9a1"))
            self.track_table.setItem(row, 3, role_item)
            self.track_table.setItem(row, 4, QTableWidgetItem(str(track.note_count)))
            self.track_table.setItem(row, 5, QTableWidgetItem(track.pitch_range_text))
        self._refresh_track_analysis_tooltips()
        self.track_table.blockSignals(False)
        self.plan = None
        self.tracks_box.setEnabled(True)
        self.section_box.setEnabled(True)
        minutes, seconds = divmod(int(project.duration_ms / 1000), 60)
        self.summary_label.setText(
            f"{len(project.notes):,} notes across {sum(t.note_count > 0 for t in project.tracks)} populated tracks · "
            f"{minutes}:{seconds:02d} · first tempo {project.first_bpm:.1f} BPM · "
            f"{selected_analysis.description}"
        )
        self.runtime_health_label.setText("Last playback · not run for this file")
        _set_visual_state(self.runtime_health_label, "inlineIdle")
        selection_note = (
            f"Restored {len(remembered_available)} saved track choice(s)."
            if restored_selection
            else self.score_analysis.rationale
        )
        import_notes = [selection_note, *project.warnings]
        self._set_advisories(import_notes)
        self._refresh_track_selection_state()
        self.arrangement_lead_combo.blockSignals(True)
        self.arrangement_lead_combo.setCurrentIndex(
            max(0, self.arrangement_lead_combo.findData(remembered_lead)),
        )
        self.arrangement_lead_combo.blockSignals(False)
        self.workspace_tabs.setCurrentWidget(self.tracks_box)
        self._refresh_workflow_state()
        if self.settings.ui_mode == "simple":
            self._set_status("MIDI analysed and musical tracks selected. Press Play in SCUM when ready.")
        else:
            self._set_status("MIDI analysed and musical tracks selected. Press Prepare to build the SCUM score.")
        self._save_ui_to_settings()

    def selected_tracks(self) -> list[int]:
        result: list[int] = []
        for row in range(self.track_table.rowCount()):
            item = self.track_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                result.append(int(item.data(Qt.UserRole)))
        return result

    def _set_all_tracks(self, checked: bool) -> None:
        self.track_table.blockSignals(True)
        for row in range(self.track_table.rowCount()):
            item = self.track_table.item(row, 0)
            if item and (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.track_table.blockSignals(False)
        self.invalidate_plan()
        self._refresh_track_selection_state()

    def prepare_plan(self) -> bool:
        if not self.project:
            QMessageBox.information(self, APP_TITLE, "Load a MIDI file first.")
            return False
        tracks = self.selected_tracks()
        if not tracks:
            QMessageBox.information(self, APP_TITLE, "Select at least one populated MIDI track.")
            return False
        self._save_ui_to_settings()
        # Never leave a stale playable plan behind if rebuilding fails.
        self.plan = None
        self.active_selection = None
        self._set_status("Preparing the SCUM score…")
        self.readiness_pill.setText("ANALYSING")
        _set_visual_state(self.readiness_pill, "pillIdle")
        self.workflow_hint.setText("Applying arrangement, instrument, mapping, and timing settings")
        self.progress.setRange(0, 0)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            notes = self.project.notes_for_tracks(tracks)
            if self.settings.ui_mode == "advanced" and self.playback_sections:
                self.active_selection = apply_playback_sections(
                    notes,
                    self.playback_sections,
                    source_duration_ms=self.project.duration_ms,
                    gap_ms=self.settings.section_gap_ms,
                )
                notes = list(self.active_selection.notes)
            self.plan = build_playback_plan(
                notes,
                self.settings,
                self.settings.resolved_profile(),
                prepared_source=_selection_is_prepared_song(self.project, tracks),
                track_names={track.index: track.name for track in self.project.tracks},
            )
            if self.active_selection:
                selection = self.active_selection
                self.plan.diagnostics.update(
                    {
                        "playback_selection_intervals": len(selection.intervals),
                        "playback_selection_include_ranges": selection.include_sections,
                        "playback_selection_omit_ranges": selection.omit_sections,
                        "playback_selection_original_notes": selection.original_notes,
                        "playback_selection_dropped_notes": selection.dropped_source_notes,
                        "playback_selection_clipped_notes": selection.clipped_source_notes,
                        "playback_selection_source_span_ms": round(selection.source_span_ms, 3),
                        "playback_selection_output_duration_ms": round(
                            selection.output_duration_ms, 3
                        ),
                        "playback_selection_gap_ms": selection.gap_ms,
                    }
                )
                self.plan.warnings.insert(
                    0,
                    f"Playback selection resolved to {len(selection.intervals)} source segment(s) "
                    f"covering {format_timecode(selection.source_span_ms)}; non-contiguous segments "
                    f"are joined with a {selection.gap_ms} ms pause.",
                )
        except Exception as exc:
            logger.exception("Could not prepare playback plan")
            self._set_status("Preparation failed")
            QMessageBox.critical(self, APP_TITLE, f"Could not prepare the song:\n\n{exc}")
            return False
        finally:
            QApplication.restoreOverrideCursor()
            self.progress.setRange(0, 1000)
            self.progress.setValue(0)
            self._refresh_workflow_state()
        minutes, seconds = divmod(int(self.plan.duration_ms / 1000), 60)
        effective_arrangement = str(
            self.plan.diagnostics.get("arrangement_mode", self.settings.arrangement_mode)
        )
        arrangement_name = {
            "intelligent": "automatic",
            "melody": "melody only",
            "vocal": "vocal lead focus",
            "adaptive_lead": "adaptive lead only",
            "melody_bass": "melody + bass",
            "faithful": "faithful",
        }.get(effective_arrangement, ARRANGEMENT_OPTIONS.get(effective_arrangement, (effective_arrangement, ""))[0])
        preset = PERFORMANCE_PRESETS.get(self.settings.performance_preset, {})
        preset_name = str(preset.get("label", "Custom"))
        effective_speed = float(self.plan.diagnostics.get("effective_speed", self.settings.speed))
        score_description = str(self.plan.diagnostics.get("score_description", arrangement_name))
        section_summary = ""
        if self.active_selection:
            section_summary = (
                f" · {len(self.active_selection.intervals)} selected segment(s)"
            )
        health = assess_performance(self.plan)
        self.summary_label.setText(
            f"Ready to play · {minutes}:{seconds:02d} at {effective_speed:.2f}×{section_summary}\n"
            f"{self.plan.retained_notes:,}/{self.plan.source_notes:,} notes retained · "
            f"{self.plan.event_count:,} key events · "
            f"{int(self.plan.diagnostics.get('score_chord_groups', 0)):,} chord groups\n"
            f"{preset_name} · {score_description} · {arrangement_name}\n"
            f"Performance health · {health.summary}"
        )
        self.runtime_health_label.setText("Last playback · not run for this preparation")
        _set_visual_state(self.runtime_health_label, "inlineIdle")
        details = []
        details.append(f"Performance health: {health.summary}.")
        details.extend(health.recommendations)
        instrument_label = str(self.plan.diagnostics.get("target_instrument_label", "Instrument"))
        instrument_sustain_ms = int(self.plan.diagnostics.get("instrument_max_sustain_ms", 0))
        effective_sustain_ms = float(
            self.plan.diagnostics.get("effective_max_hold_ms", instrument_sustain_ms)
        )
        capped_sustains = int(self.plan.diagnostics.get("instrument_sustain_capped_notes", 0))
        removed_sustain_ms = float(
            self.plan.diagnostics.get("instrument_sustain_reduction_ms", 0.0)
        )
        if abs(effective_sustain_ms - instrument_sustain_ms) > 0.5:
            preparation_detail = (
                f"{instrument_label} preparation: {effective_sustain_ms:,.0f} ms plan maximum "
                f"within the {instrument_sustain_ms:,} ms hard ceiling."
            )
        else:
            preparation_detail = (
                f"{instrument_label} preparation: {instrument_sustain_ms:,} ms hard maximum sustain."
            )
        if capped_sustains:
            preparation_detail += (
                f" {capped_sustains:,} long note(s) shortened by "
                f"{removed_sustain_ms / 1000.0:,.2f} s total."
            )
        details.append(preparation_detail)
        director_groups = int(self.plan.diagnostics.get("performance_director_groups", 0))
        if director_groups:
            protected_leads = int(
                self.plan.diagnostics.get("performance_lead_attacks_protected", 0)
            )
            simplified_groups = int(
                self.plan.diagnostics.get("performance_dense_groups_simplified", 0)
            )
            voice_motion = float(
                self.plan.diagnostics.get("performance_average_voice_leading_semitones", 0.0)
            )
            director_detail = (
                f"Performance Director: {director_groups:,} attack group(s) planned as one continuous "
                f"performance; {protected_leads:,} traced lead attack(s) protected"
            )
            if simplified_groups:
                director_detail += f", {simplified_groups:,} over-dense group(s) simplified"
            if voice_motion:
                director_detail += f", {voice_motion:.1f} semitone average physical voice movement"
            details.append(director_detail + ".")
        lead_articulation = int(self.plan.diagnostics.get("lead_articulation_notes", 0))
        if lead_articulation:
            lead_trim_ms = float(self.plan.diagnostics.get("lead_articulation_ms", 0.0))
            details.append(
                f"Lead articulation: released {lead_articulation:,} overlapping melody note(s) "
                f"{lead_trim_ms / 1000.0:.2f} s earlier in total to keep the lead line clear."
            )
        chord_groups = int(self.plan.diagnostics.get("score_chord_groups", 0))
        if chord_groups:
            roll_style = str(self.plan.diagnostics.get("chord_roll_style", "lead-first"))
            stagger_ms = float(self.plan.diagnostics.get("chord_stagger_ms", 0.0))
            details.append(
                f"Chord articulation: {roll_style.replace('-', ' ')} ordering with up to "
                f"{stagger_ms:.0f} ms between physical chord keys."
            )
        rhythm_shortened = int(self.plan.diagnostics.get("rhythm_shortened_notes", 0))
        rhythm_delay_ms = float(self.plan.diagnostics.get("physical_retrigger_delay_ms", 0.0))
        if rhythm_shortened:
            rhythm_trim_ms = float(self.plan.diagnostics.get("rhythm_shortening_ms", 0.0))
            details.append(
                f"Rhythm protection: shortened {rhythm_shortened:,} sustain(s) by "
                f"{rhythm_trim_ms / 1000.0:.2f} s total instead of moving their following attacks; "
                f"unavoidable retrigger delay {rhythm_delay_ms:.0f} ms."
            )
        if self.active_selection and self.active_selection.dropped_source_notes:
            details.append(
                f"{self.active_selection.dropped_source_notes:,} source notes were outside the selected playback sections."
            )
        if self.active_selection and self.active_selection.clipped_source_notes:
            details.append(
                f"{self.active_selection.clipped_source_notes:,} sustained source notes were clipped at a section boundary."
            )
        if self.plan.dropped_notes:
            details.append(f"{self.plan.dropped_notes:,} notes simplified by arrangement, density, range, or polyphony limits.")
        solo_sections = int(self.plan.diagnostics.get("solo_segments", 0))
        if solo_sections:
            solo_notes = int(self.plan.diagnostics.get("solo_notes", 0))
            ducked_notes = int(self.plan.diagnostics.get("solo_accompaniment_dropped", 0))
            solo_mapping = str(self.plan.diagnostics.get("effective_mapping_mode", "fold"))
            details.append(
                f"Solo handling: {solo_sections} protected section(s), "
                f"{solo_notes} lead note(s), {ducked_notes} competing accompaniment note(s) "
                f"ducked, {solo_mapping.replace('_', ' ')} mapping."
            )
        early_banks = int(self.plan.diagnostics.get("octave_early_preparations", 0))
        if early_banks:
            extra_settle_ms = float(self.plan.diagnostics.get("octave_extra_settle_ms", 0.0))
            details.append(
                f"Octave preparation: used natural rests to prepare {early_banks:,} bank change(s) early, "
                f"adding {extra_settle_ms:.0f} ms of free SCUM settle time without moving note attacks."
            )
        initial_taps = int(self.plan.diagnostics.get("initial_bank_taps", 0))
        if initial_taps:
            bank = int(self.plan.diagnostics.get("initial_octave_bank", 0))
            direction = "Shift/up" if bank > 0 else "Ctrl/down"
            details.append(
                f"Initial bank preparation: {initial_taps} standalone {direction} tap(s) before the first musical key."
            )
        if int(self.plan.diagnostics.get("base_bank_restored", 0)):
            details.append("The plan returns SCUM to the base octave bank after releasing every musical key.")
        if self.plan.planned_notes:
            details.append(f"First-note mapping: {self.plan.planned_notes[0].mapping_reason}.")
        details.extend(self.plan.warnings)
        self._set_advisories(details)
        self.full_timecode_label.setText(f"00:00 / {_format_timecode_min_sec(self.plan.duration_ms)}")
        self.workspace_tabs.setCurrentWidget(self.summary_box)
        self._refresh_workflow_state()
        self._set_status("Prepared. Put an instrument into Play mode before starting.")
        return bool(self.plan.events)

    def start_live_midi(self) -> None:
        if self._output_busy():
            self._set_status("Stop current output before arming live MIDI.")
            return
        device = self._selected_midi_device()
        if device is None:
            QMessageBox.information(
                self,
                APP_TITLE,
                "Connect and select a MIDI keyboard, then choose Refresh.",
            )
            return

        self._save_ui_to_settings()
        self.backend = create_backend(self.settings.input_mode)
        if self.settings.input_mode != "dry_run" and not self.backend.available:
            QMessageBox.critical(
                self,
                APP_TITLE,
                "Keyboard output is only available on Windows. Use Dry run for testing.",
            )
            return

        require_focus = (
            self.settings.require_scum_focus
            and self.settings.input_mode != "dry_run"
            and os.name == "nt"
        )
        callbacks = LiveMidiCallbacks(
            status=self.signals.status.emit,
            activity=self.signals.live_activity.emit,
            finished=self.signals.live_finished.emit,
        )
        session = LiveMidiSession(
            self.backend,
            self.midi_provider,
            self.settings.resolved_profile(),
            LiveMidiConfig(
                mapping_mode=self.settings.live_midi_mapping_mode,
                transpose=self.settings.live_midi_transpose,
                channel=self.settings.live_midi_channel,
                ignore_channel_10=self.settings.live_midi_ignore_channel_10,
                max_polyphony=self.settings.live_midi_max_polyphony,
                require_scum_focus=require_focus,
                pause_on_focus_loss=self.settings.pause_on_focus_loss,
            ),
            callbacks,
        )
        try:
            session.start(device)
        except Exception as exc:
            logger.exception("Could not start live MIDI")
            QMessageBox.critical(
                self,
                APP_TITLE,
                f"Could not arm the MIDI keyboard:\n\n{exc}",
            )
            self._set_status("Live MIDI could not start.")
            return

        self.live_midi = session
        self.prepare_button.setEnabled(False)
        self.play_button.setEnabled(False)
        self.live_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.export_button.setEnabled(False)
        self.export_events_button.setEnabled(False)
        self._set_plan_controls_enabled(False)
        self.progress.setValue(0)
        mapping_label = (
            "strict C4-C5"
            if self.settings.live_midi_mapping_mode == "strict"
            else "safe base-bank fold"
        )
        self.live_state_label.setText(
            f"Armed · {device.name} · {mapping_label} · F8 or Stop disarms"
        )
        self._refresh_workflow_state()


    def _current_source_notes(self) -> list[MidiNote]:
        if not self.project:
            return []
        tracks = self.selected_tracks()
        if not tracks:
            return []
        notes = self.project.notes_for_tracks(tracks)
        if self.playback_sections:
            selection = apply_playback_sections(
                notes,
                self.playback_sections,
                source_duration_ms=self.project.duration_ms,
                gap_ms=self.settings.section_gap_ms,
            )
            return list(selection.notes)
        return notes

    def _recommend_transpose_clicked(self) -> None:
        notes = self._current_source_notes()
        if not notes:
            QMessageBox.information(self, APP_TITLE, "Load a MIDI file and select at least one populated track first.")
            return
        self._save_ui_to_settings()
        best_shift, metrics = recommend_optimal_transpose(notes, self.settings)
        self.transpose_spin.setValue(best_shift)
        self.settings.transpose = best_shift
        if not self.prepare_plan():
            return
        self._set_status(
            f"Recommended transpose: {best_shift:+d} semitones · "
            f"{metrics['in_bank_pct']:.0f}% in base bank, {metrics['in_range_pct']:.0f}% in SCUM range · "
            f"estimated bank-change rate {metrics['bank_switch_rate']:.0f}%"
        )

    def _open_mapping_comparison(self) -> None:
        notes = self._current_source_notes()
        if not notes:
            QMessageBox.information(
                self, APP_TITLE, "Load a MIDI file and select at least one populated track first."
            )
            return
        self._save_ui_to_settings()
        tracks = self.selected_tracks()
        dialog = MappingComparisonDialog(
            notes,
            self.settings,
            parent=self,
            prepared_source=_selection_is_prepared_song(self.project, tracks) if self.project else False,
            track_names={t.index: t.name for t in self.project.tracks} if self.project else {},
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_mode:
            self.settings.mapping_mode = dialog.selected_mode
            index = self.mapping_combo.findData(dialog.selected_mode)
            if index >= 0:
                self.mapping_combo.setCurrentIndex(index)
            self._mark_performance_custom()
            if self.prepare_plan():
                self._set_status(f"Applied {self.mapping_combo.currentText()} and rebuilt the SCUM score")

    def _start_playback(
        self,
        plan: PlaybackPlan,
        countdown_s: int,
        *,
        repeat: bool = False,
    ) -> None:
        if self._live_midi_active() or self._plan_controls_locked:
            self._set_status("Disarm live MIDI before starting scheduled playback.")
            return
        self._save_ui_to_settings()
        self.backend = create_backend(self.settings.input_mode)
        if self.settings.input_mode != "dry_run" and not self.backend.available:
            QMessageBox.critical(self, APP_TITLE, "Keyboard output is only available on Windows. Use Dry run for testing.")
            return
        callbacks = SchedulerCallbacks(
            status=self.signals.status.emit,
            progress=self.signals.progress.emit,
            finished=self.signals.finished.emit,
            timecode=self.signals.timecode.emit,
        )
        self.scheduler = PlaybackScheduler(
            self.backend, callbacks, initial_bank=self._known_scum_bank
        )
        self._active_playback_plan = plan
        require_focus = self.settings.require_scum_focus and self.settings.input_mode != "dry_run" and os.name == "nt"
        self.play_button.setEnabled(False)
        self.prepare_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.export_button.setEnabled(False)
        self.export_events_button.setEnabled(False)
        self._set_plan_controls_enabled(False)
        self.pause_button.setText("Pause")
        profile = self.settings.resolved_profile()

        # Build the overlay first, then transfer foreground focus to SCUM. Nothing
        # after the transfer is allowed to activate MusicalScumbag again.
        self._set_compact_playback_mode(True)
        if self.settings.input_mode != "dry_run" and os.name == "nt":
            if not focus_scum_window():
                self._active_playback_plan = None
                self._set_compact_playback_mode(False)
                self.play_button.setEnabled(True)
                self.prepare_button.setEnabled(True)
                self.pause_button.setEnabled(False)
                self.stop_button.setEnabled(False)
                self.export_button.setEnabled(True)
                self.export_events_button.setEnabled(True)
                self._set_plan_controls_enabled(True)
                QMessageBox.warning(
                    self,
                    APP_TITLE,
                    "SCUM's game window could not be found or brought to the foreground.\n\n"
                    "Open SCUM's instrument Play screen, then press Play again. If SCUM is running as "
                    "administrator, run MusicalScumbag at the same privilege level.",
                )
                return
            _pin_native_topmost_no_activate(self, foreground_scum_window_rect())

        try:
            self.scheduler.start(
                plan,
                countdown_s=countdown_s,
                require_scum_focus=require_focus,
                pause_on_focus_loss=self.settings.pause_on_focus_loss,
                repeat=repeat,
                repeat_gap_ms=self.settings.section_gap_ms,
                octave_up_key=profile.octave_up,
                octave_down_key=profile.octave_down,
                modifier_release_ms=self.settings.modifier_release_ms,
                modifier_settle_ms=self.settings.modifier_settle_ms,
            )
        except Exception as exc:
            logger.exception("Could not start playback")
            self._playback_finished("failed")
            QMessageBox.critical(self, APP_TITLE, f"Could not start playback:\n\n{exc}")
            return
        self._refresh_workflow_state()
        if self.settings.input_mode != "dry_run" and os.name == "nt":
            QTimer.singleShot(80, lambda: _pin_native_topmost_no_activate(self, foreground_scum_window_rect()))

    def play(self) -> None:
        if self._live_midi_active() or self._plan_controls_locked:
            self._set_status("Disarm live MIDI before starting scheduled playback.")
            return
        if self.scheduler and self.scheduler.running:
            return
        self._commit_numeric_edits()
        if not self.plan and not self.prepare_plan():
            return
        if not self.plan or not self.plan.events:
            QMessageBox.information(self, APP_TITLE, "The prepared song contains no playable key events.")
            return
        self._start_playback(
            self.plan,
            self.settings.countdown_s,
            repeat=self.settings.loop_playback if self.settings.ui_mode == "advanced" else False,
        )

    def pause_resume(self) -> None:
        if not self.scheduler or not self.scheduler.running:
            return
        if self.scheduler.paused and self.settings.input_mode != "dry_run" and os.name == "nt":
            was_compact = self._compact_playback
            self._set_compact_playback_mode(True)
            if not focus_scum_window():
                if not was_compact:
                    self._set_compact_playback_mode(False)
                    self.raise_()
                    self.activateWindow()
                self._set_status("Still paused — SCUM could not be focused.")
                return
            _pin_native_topmost_no_activate(self, foreground_scum_window_rect())
        paused = self.scheduler.toggle_pause()
        self.pause_button.setText("Resume" if paused else "Pause")
        self._refresh_workflow_state()

    def play_pause_hotkey(self) -> None:
        if self.scheduler and self.scheduler.running:
            self.pause_resume()
        elif not self._live_midi_active():
            self.play()

    def seek_forward_hotkey(self, delta_s: float = 5.0) -> None:
        if self.scheduler and self.scheduler.running:
            self.scheduler.seek_by(delta_s * 1000.0)

    def seek_backward_hotkey(self, delta_s: float = 5.0) -> None:
        if self.scheduler and self.scheduler.running:
            self.scheduler.seek_by(-delta_s * 1000.0)

    def toggle_window_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
            return
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        if self._compact_playback:
            _set_native_no_activate(self, True)
            _pin_native_topmost_no_activate(self, foreground_scum_window_rect())
        else:
            self.raise_()

    def _expand_from_compact_player(self) -> None:
        """Pause before opening the editor so focus-loss handling is predictable."""

        if self.scheduler and self.scheduler.running and not self.scheduler.paused:
            self.scheduler.toggle_pause()
            self.pause_button.setText("Resume")
        self._set_compact_playback_mode(False)
        self.raise_()
        self.activateWindow()
        self._refresh_workflow_state()

    def toggle_hold_w(self) -> None:
        if self._w_held:
            try:
                if self._walk_backend is not None:
                    self._walk_backend.key_up("W")
                    self._walk_backend.release_all()
            except Exception as exc:
                logger.warning("Failed to release W: %s", exc)
            self._w_held = False
            self._walk_backend = None
            self._set_status("Auto-walk toggled OFF (W released).")
        else:
            if os.name == "nt" and not foreground_window_info(cache_ttl_s=0.0).is_scum:
                self._set_status("Auto-walk was not enabled because SCUM is not focused.")
                return
            mode = str(self.input_combo.currentData())
            if mode == "dry_run":
                self._set_status("Auto-walk is disabled in Dry run mode.")
                return
            walk_backend = create_backend(mode)
            if not walk_backend.available:
                self._set_status("Auto-walk keyboard output is unavailable on this system.")
                return
            try:
                walk_backend.key_down("W")
            except Exception as exc:
                logger.warning("Failed to hold W: %s", exc)
                try:
                    walk_backend.release_all()
                except Exception:
                    pass
                self._set_status(f"Auto-walk could not start: {exc}")
                return
            self._walk_backend = walk_backend
            self._w_held = True
            self._set_status("Auto-walk ON. Numpad /, F8, or leaving SCUM releases W.")

    def _poll_global_hotkeys(self) -> None:
        if os.name != "nt":
            return
        if self._w_held and not foreground_window_info().is_scum:
            self.toggle_hold_w()
        if emergency_stop_pressed() and self._w_held:
            self.toggle_hold_w()
        if numpad_divide_pressed():
            self.toggle_hold_w()
        if function_key_pressed(9):
            self.play_pause_hotkey()
        if function_key_pressed(11):
            self.toggle_window_visibility()
        if is_control_down():
            if numpad_key_pressed(6):
                self.seek_forward_hotkey()
            if numpad_key_pressed(4):
                self.seek_backward_hotkey()


    def _set_compact_playback_mode(self, compact: bool) -> None:
        if compact == self._compact_playback:
            return
        if compact:
            self._editor_was_maximized = self.isMaximized()
            self._editor_geometry = self.normalGeometry() if self._editor_was_maximized else self.geometry()
        self._compact_playback = compact
        if compact:
            self.setMinimumSize(500, 108)
        else:
            self.setMinimumSize(900, 600)
        self._apply_topmost_state()
        if not compact:
            _set_native_no_activate(self, False)
        compact_prop = "true" if compact else "false"
        self.centralWidget().setProperty("compact", compact_prop)
        self.header.setProperty("compact", compact_prop)
        self.command_deck.setProperty("compact", compact_prop)
        for widget in (self.centralWidget(), self.header, self.command_deck):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self.source_deck.setVisible(not compact)
        self.main_splitter.setVisible(not compact)
        self.menuBar().setVisible(not compact)
        advanced = self.settings.ui_mode == "advanced"
        self.prepare_button.setVisible(not compact and advanced)
        self.play_button.setVisible(not compact)
        self.live_button.setVisible(not compact and advanced)
        self.export_button.setVisible(not compact and advanced)
        self.export_events_button.setVisible(not compact and advanced)
        self.command_label.setVisible(not compact)
        self.readiness_pill.setVisible(not compact)
        self.full_timecode_label.setVisible(not compact)
        for widget in self.header_detail_widgets:
            widget.setVisible(not compact)
        self.compact_hint.setVisible(compact)
        self.compact_header_widget.setVisible(compact)
        self.statusBar().setVisible(not compact)
        if compact:
            title_text = self.project.path.name if self.project else "Playback"
            if len(title_text) > 24:
                title_text = title_text[:21] + "…"
            self.compact_title_label.setText(title_text)
            self.compact_status_badge.setText("STARTING" if self.settings.countdown_s > 0 else "PLAYING")
            _set_visual_state(self.compact_status_badge, "pillIdle" if self.settings.countdown_s > 0 else "pillGood")
            active_plan = self._active_playback_plan or self.plan
            duration = active_plan.duration_ms if active_plan else 0.0
            self.compact_timecode_label.setText(f"00:00 / {_format_timecode_min_sec(duration)}")
            self.setWindowTitle(f"{APP_TITLE} — Player")
            self.showNormal()
            self.resize(620, 136)
            screen = self.screen() or QApplication.primaryScreen()
            available = screen.availableGeometry()
            self.move(available.right() - self.width() - 14, available.top() + 14)
            _set_native_no_activate(self, True)
            _pin_native_topmost_no_activate(self)
        else:
            self.setWindowTitle(APP_TITLE)
        if not compact and self._editor_was_maximized:
            self.showMaximized()
        elif not compact and self._editor_geometry is not None:
            geometry = self._editor_geometry
            QTimer.singleShot(0, lambda: self.setGeometry(geometry))

    def stop(self) -> None:
        if self._w_held:
            self.toggle_hold_w()
        if self.live_midi and self.live_midi.running:
            self.live_midi.stop("stopped")
            self._set_status("Disarming live MIDI and releasing every key…")
            return
        if self.scheduler:
            self.scheduler.stop()
        self._set_status("Stopping…")

    def test_note(self) -> None:
        if self._output_busy():
            self._set_status("Stop current output before testing a note.")
            return
        self._save_ui_to_settings()
        test = MidiNote(0, 0, 60, 100, 0.0, 260.0)
        test_plan = build_playback_plan([test], self.settings, self.settings.resolved_profile())
        self._start_playback(test_plan, min(3, self.settings.countdown_s))

    def export_plan(self) -> None:
        self._commit_numeric_edits()
        if not self.plan and not self.prepare_plan():
            return
        default_name = "musical_scumme_key_plan.csv"
        if self.project:
            default_name = f"{self.project.path.stem}_key_plan.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export key plan", default_name, "CSV files (*.csv)")
        if path and self.plan:
            export_plan_csv(self.plan, path)
            self._set_status(f"Exported key events to {Path(path).name}")

    def export_score(self) -> None:
        self._commit_numeric_edits()
        if not self.plan and not self.prepare_plan():
            return
        default_name = "musical_scumme_scum_score.csv"
        if self.project:
            default_name = f"{self.project.path.stem}_scum_score.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export SCUM score", default_name, "CSV files (*.csv)")
        if path and self.plan:
            export_score_csv(self.plan, path)
            self._set_status(f"Exported SCUM score to {Path(path).name}")

    def edit_custom_keys(self) -> None:
        # Seed the editor from the profile currently selected in the UI. Existing
        # custom values are preserved only when Custom itself is selected.
        self.settings.profile_name = self.profile_combo.currentText()
        if self.settings.profile_name != "Custom":
            profile = self.settings.resolved_profile()
            self.settings.custom_profile = {
                "base_notes": list(profile.base_notes),
                "octave_down": profile.octave_down,
                "octave_up": profile.octave_up,
            }
        dialog = KeymapDialog(self.settings, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.settings.custom_profile = dialog.result_profile()
        except Exception as exc:
            QMessageBox.warning(self, APP_TITLE, f"Invalid key profile:\n\n{exc}")
            return
        self.profile_combo.setCurrentText("Custom")
        self._save_ui_to_settings()
        self.invalidate_plan()

    def _profile_changed(self, name: str) -> None:
        self.settings.profile_name = name
        self._update_profile_hint(name)

    def _update_profile_hint(self, name: str) -> None:
        if name == "Custom":
            profile = self.settings.resolved_profile()
            text = (
                "Custom mapping: "
                + ", ".join(profile.base_notes)
                + f" · octave down {profile.octave_down} · octave up {profile.octave_up}"
            )
        else:
            profile = BUILTIN_PROFILES.get(name)
            text = profile.description if profile else "Unknown key profile."
        self.profile_hint.setText(text)

    def invalidate_plan(self, *_args) -> None:
        self.plan = None
        self.active_selection = None
        if self.project:
            self.summary_label.setText(
                "Preparation needed. Tracks, sections, instrument, or sound settings changed."
            )
            self.runtime_health_label.setText("Last playback · preparation changed")
            _set_visual_state(self.runtime_health_label, "inlineIdle")
            self._set_advisories([])
        self._refresh_workflow_state()

    def _refresh_game_status(self) -> None:
        info = foreground_window_info()
        if info.is_scum:
            self.game_pill.setText("SCUM focused")
            self.game_pill.setObjectName("pillGood")
        elif os.name != "nt":
            self.game_pill.setText("Windows required for output")
            self.game_pill.setObjectName("pillBad")
        else:
            label = info.process_name or info.title or "No foreground app"
            self.game_pill.setText(f"SCUM not focused · {label[:28]}")
            self.game_pill.setObjectName("pillIdle")
        self.game_pill.style().unpolish(self.game_pill)
        self.game_pill.style().polish(self.game_pill)

    def _set_status(self, message: str) -> None:
        self.statusBar().showMessage(message)
        if self._compact_playback:
            msg_upper = message.upper()
            if "STARTING IN" in msg_upper:
                self.compact_status_badge.setText(message.strip()[:20].upper())
                _set_visual_state(self.compact_status_badge, "pillIdle")
            elif "WAITING FOR SCUM" in msg_upper:
                self.compact_status_badge.setText("WAITING FOR SCUM")
                _set_visual_state(self.compact_status_badge, "pillIdle")
            elif "LOST FOCUS" in msg_upper or "NOT FOCUSED" in msg_upper:
                self.compact_status_badge.setText("FOCUS LOST")
                _set_visual_state(self.compact_status_badge, "pillBad")
            elif "PAUSED" in msg_upper:
                self.compact_status_badge.setText("PAUSED")
                _set_visual_state(self.compact_status_badge, "pillIdle")
            elif "PLAYING" in msg_upper or "RESUMING" in msg_upper:
                self.compact_status_badge.setText("PLAYING")
                _set_visual_state(self.compact_status_badge, "pillGood")
            elif "FINISHED" in msg_upper:
                self.compact_status_badge.setText("FINISHED")
                _set_visual_state(self.compact_status_badge, "pillGood")
            elif "STOPPED" in msg_upper or "STOPPING" in msg_upper:
                self.compact_status_badge.setText("STOPPED")
                _set_visual_state(self.compact_status_badge, "pillIdle")

    def _set_progress(self, fraction: float) -> None:
        self.progress.setValue(max(0, min(1000, round(fraction * 1000))))

    def _set_timecode(self, elapsed_ms: float, total_ms: float) -> None:
        elapsed_str = _format_timecode_min_sec(elapsed_ms)
        total_str = _format_timecode_min_sec(total_ms)
        remaining_ms = max(0.0, total_ms - elapsed_ms)
        remaining_str = _format_timecode_min_sec(remaining_ms)
        timecode = f"{elapsed_str} / {total_str}  (-{remaining_str})"
        self.compact_timecode_label.setText(timecode)
        self.full_timecode_label.setText(timecode)

    def _set_live_activity(self, message: str) -> None:
        if self._live_midi_active():
            self.live_state_label.setText(message)
            self._set_status(f"Live MIDI: {message}")


    def _live_midi_finished(self, reason: str) -> None:
        self.live_midi = None
        self.prepare_button.setEnabled(True)
        self.play_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.export_button.setEnabled(True)
        self.export_events_button.setEnabled(True)
        self._set_plan_controls_enabled(True)
        self._refresh_midi_devices(show_status=False)
        self.progress.setValue(0)
        if reason == "stopped":
            self.live_state_label.setText(
                "Set SCUM to its base octave before arming. Live input never taps Ctrl or Shift."
            )
        else:
            self.live_state_label.setText(f"Live MIDI stopped · {reason}")
        self._refresh_workflow_state()

    def _playback_finished(self, reason: str) -> None:
        if self.scheduler:
            self._known_scum_bank = self.scheduler.current_bank
        was_compact = self._compact_playback
        keep_game_focus = (
            was_compact
            and self.settings.input_mode != "dry_run"
            and os.name == "nt"
            and reason in {"completed", "stopped", "emergency stop"}
        )
        self._set_compact_playback_mode(False)
        self.play_button.setEnabled(True)
        self.prepare_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.export_button.setEnabled(True)
        self.export_events_button.setEnabled(True)
        self._set_plan_controls_enabled(True)
        self.pause_button.setText("Pause")
        finished_plan = self._active_playback_plan or self.plan
        duration = finished_plan.duration_ms if finished_plan else 0.0
        self.full_timecode_label.setText(f"00:00 / {_format_timecode_min_sec(duration)}")
        if reason == "completed":
            self.progress.setValue(1000)
        if self.scheduler and self.scheduler.last_metrics.events_sent:
            metrics = self.scheduler.last_metrics
            outcome = "Finished" if reason == "completed" else reason.capitalize()
            runtime_detail = (
                f"Last playback · {metrics.timing_summary} · "
                f"avg/max lateness {metrics.average_lateness_ms:.2f}/{metrics.max_lateness_ms:.2f} ms · "
                f"dispatch max {metrics.max_dispatch_ms:.2f} ms · "
                f">5 ms {metrics.batches_over_5ms:,} · stalls {metrics.stalls_recovered:,} · "
                f"focus pauses {metrics.focus_pauses:,}"
            )
            self.runtime_health_label.setText(runtime_detail)
            _set_visual_state(
                self.runtime_health_label,
                "inlineWarn"
                if metrics.timing_summary != "Timing clean"
                else "inlineGood",
            )
            self._set_status(
                f"{outcome} · {metrics.timing_summary} · "
                f"{metrics.events_sent:,} events in {metrics.batches_sent:,} batches · "
                f"average/max lateness {metrics.average_lateness_ms:.2f}/{metrics.max_lateness_ms:.2f} ms · "
                f"input dispatch avg/max {metrics.average_dispatch_ms:.3f}/{metrics.max_dispatch_ms:.3f} ms · "
                f"{metrics.batches_over_5ms:,} batch(es) >5 ms · "
                f"{metrics.stalls_recovered:,} recovered stall(s) · "
                f"{metrics.seek_reconstructed_notes:,} seek / "
                f"{metrics.pause_reconstructed_notes:,} pause / "
                f"{metrics.focus_reconstructed_notes:,} focus sustain(s) restored · "
                f"{metrics.stop_bank_restores:,} stop bank reset(s) · "
                f"{metrics.session_bank_resyncs:,} startup bank recovery(s) · "
                + (
                    "bank reset skipped (SCUM not focused) · "
                    if metrics.stop_bank_restore_skipped
                    else ""
                )
                + f"{metrics.loops_completed:,} completed loop(s)"
            )
        self._refresh_workflow_state()
        if keep_game_focus:
            # Restoring the editor can momentarily activate its native window.
            # Hand focus straight back so completing/stopping a song never
            # drags the user out of SCUM.
            QTimer.singleShot(0, focus_scum_window)
            QTimer.singleShot(100, focus_scum_window)
        else:
            self.raise_()
        self._active_playback_plan = None

    def reset_settings(self) -> None:
        if self._output_busy():
            self._set_status("Stop current output before resetting settings.")
            return
        answer = QMessageBox.question(self, APP_TITLE, "Reset all MusicalScumbag settings to defaults?")
        if answer != QMessageBox.Yes:
            return
        self.settings = create_default_settings()
        self.playback_sections = []
        save_settings(self.settings)
        self._load_settings_into_ui()
        self.midi_input_combo.setCurrentIndex(-1)
        self._refresh_midi_devices(show_status=False)
        self._refresh_section_table()
        self._refresh_recent_menu()
        self.invalidate_plan()
        self._refresh_track_selection_state()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._last_file_timer.stop()
        self.hotkey_timer.stop()
        self.focus_timer.stop()
        if self._w_held:
            self.toggle_hold_w()
        if self.live_midi:
            self.live_midi.stop("application closed")
            self.live_midi.wait(0.5)
        if self.scheduler:
            self.scheduler.stop()
            self.scheduler.wait(0.75)
        self._save_ui_to_settings()
        event.accept()


def run() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("MusicalScumbag")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    return app.exec()
