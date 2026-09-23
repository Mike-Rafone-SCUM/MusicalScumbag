import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from musical_scumme.ui import MainWindow


@pytest.mark.parametrize("name,text,expected", [
    ("speed_spin", "1.25", 1.25),
    ("polyphony_spin", "12", 12),
    ("min_hold_spin", "125", 125),
    ("transpose_spin", "-12", -12),
])
def test_typing_full_number_keeps_focus_and_commits(name, text, expected, tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICALSCUMME_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window._set_ui_mode("advanced")
        window.settings_tabs.setCurrentIndex(2 if name in {"polyphony_spin", "min_hold_spin"} else 0)
        window.performance_combo.setCurrentIndex(window.performance_combo.findData("custom"))
        window.show()
        spin = getattr(window, name)
        spin.setFocus()
        spin.selectAll()
        app.processEvents()
        QTest.keyClicks(spin, text)
        QTest.keyClick(spin, Qt.Key.Key_Return)
        app.processEvents()
        assert spin.value() == pytest.approx(expected)
        assert spin.hasFocus()
    finally:
        window.close()
        app.processEvents()


def test_pending_number_is_committed_before_settings_are_read(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICALSCUMME_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.performance_combo.setCurrentIndex(window.performance_combo.findData("scum_safe"))
        window.show()
        spin = window.speed_spin
        spin.setFocus()
        spin.selectAll()
        before = spin.value()
        QTest.keyClicks(spin, "1.25")
        assert spin.value() == before
        window._save_ui_to_settings()
        assert window.settings.speed == 1.25
        assert window.settings.performance_preset == "custom"
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("kind,text,expected", [("integer", "125", 125), ("decimal", "1.25", 1.25)])
def test_first_click_selects_number_and_tab_commits(kind, text, expected):
    from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

    from musical_scumme.numeric_widgets import QDoubleSpinBox, QSpinBox

    app = QApplication.instance() or QApplication([])
    container = QWidget()
    layout = QVBoxLayout(container)
    other = QLineEdit()
    spin = QSpinBox() if kind == "integer" else QDoubleSpinBox()
    spin.setRange(-1000, 2000)
    spin.setValue(80)
    spin.setSuffix(" units")
    layout.addWidget(other)
    layout.addWidget(spin)
    container.show()
    other.setFocus()
    app.processEvents()
    try:
        QTest.mouseClick(spin.lineEdit(), Qt.MouseButton.LeftButton)
        assert spin.lineEdit().selectedText() == ("80" if kind == "integer" else "80.00")
        QTest.keyClicks(spin, text)
        assert spin.value() == 80
        QTest.keyClick(spin, Qt.Key.Key_Tab)
        app.processEvents()
        assert spin.value() == pytest.approx(expected)
    finally:
        container.close()
        app.processEvents()


@pytest.mark.parametrize("action", ["play", "export_plan", "export_score"])
def test_action_shortcut_reprepares_after_pending_number(action, tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICALSCUMME_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    calls = []
    try:
        window.performance_combo.setCurrentIndex(window.performance_combo.findData("custom"))
        window.speed_spin.setValue(1.0)
        window.plan = object()
        window.speed_spin.selectAll()
        QTest.keyClicks(window.speed_spin, "1.25")
        assert window.plan is not None

        def prepare():
            calls.append(window.speed_spin.value())
            return False

        monkeypatch.setattr(window, "prepare_plan", prepare)
        getattr(window, action)()
        assert calls == [1.25]
        assert window.plan is None
    finally:
        window.close()
        app.processEvents()
