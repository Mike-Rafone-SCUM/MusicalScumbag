import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from musical_scumme import input_backend, ui
from musical_scumme.input_backend import DryRunBackend

VK_CONTROL = 0x11
VK_DIVIDE = 0x6F
VK_F10 = 0x79


@pytest.fixture
def hotkey_window(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICALSCUMME_DATA_DIR", str(tmp_path / "settings"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    # Exercise Windows global polling on every host without changing os.name
    # globally or allowing any real keyboard output or MIDI-device access.
    monkeypatch.setattr(ui, "os", SimpleNamespace(name="nt", path=os.path))
    monkeypatch.setattr(ui, "_apply_native_dark_titlebar", lambda *_args: None)
    monkeypatch.setattr(ui, "foreground_window_info", lambda **_kwargs: SimpleNamespace(is_scum=True))
    held = set()
    monkeypatch.setattr(input_backend, "is_virtual_key_down", lambda vk: vk in held)
    monkeypatch.setattr(input_backend, "_PREVIOUS_KEY_STATES", {})
    backends = []

    def record_backend(mode):
        backend = DryRunBackend()
        backends.append((mode, backend))
        return backend

    monkeypatch.setattr(ui, "create_backend", record_backend)
    app = QApplication.instance() or QApplication([])
    window = ui.MainWindow(midi_provider=SimpleNamespace(input_devices=lambda: ()))
    window.hotkey_timer.stop()
    window.focus_timer.stop()
    window._last_file_timer.stop()
    # Keep the production input-mode choice: selecting Dry run in the UI would
    # suppress the old auto-walk route and hide this regression.
    assert window.input_combo.currentData() == "scan_code"
    assert backends[0][0] == "scan_code"
    harness = SimpleNamespace(window=window, held=held, backends=backends)
    yield harness
    window.scheduler = None
    window.live_midi = None
    window.close()
    app.processEvents()


def _poll(harness, *keys):
    harness.held.clear()
    harness.held.update(keys)
    harness.window._poll_global_hotkeys()


def _assert_no_w(harness):
    for _mode, backend in harness.backends:
        assert ("down", "W") not in backend.history
        assert "W" not in backend.pressed


def _active_output(harness, kind):
    backend = harness.window.backend
    backend.key_down("Y")
    output = SimpleNamespace(running=True, paused=False)

    def stop(*_args):
        output.running = False
        backend.release_all()

    output.stop = Mock(side_effect=stop)
    output.wait = Mock(return_value=True)
    setattr(harness.window, kind, output)
    return output


@pytest.mark.parametrize("output_state", ["idle", "scheduler", "live_midi"])
@pytest.mark.parametrize("retired_key", [VK_DIVIDE, VK_F10], ids=["Numpad-divide", "F10"])
def test_retired_walking_keys_never_hold_w_while_scum_is_focused(hotkey_window, output_state, retired_key):
    harness = hotkey_window
    if output_state != "idle":
        _active_output(harness, output_state)
    initial_backend_count = len(harness.backends)

    # Include held polls, release/repress, and Ctrl. Both historical walking
    # shortcuts must stay retired, even while no song is playing.
    for keys in (
        (), (retired_key,), (retired_key,), (), (retired_key,),
        (retired_key,), (), (VK_CONTROL, retired_key),
        (VK_CONTROL, retired_key), (),
    ):
        _poll(harness, *keys)
        _assert_no_w(harness)

    assert len(harness.backends) == initial_backend_count


@pytest.mark.parametrize(
    "keys, action",
    [
        ((0x78,), "play_pause_hotkey"),
        ((0x7A,), "toggle_window_visibility"),
        ((VK_CONTROL, 0x66), "seek_forward_hotkey"),
        ((VK_CONTROL, 0x64), "seek_backward_hotkey"),
    ],
    ids=["F9", "F11", "Ctrl-Numpad6", "Ctrl-Numpad4"],
)
def test_supported_global_shortcuts_still_dispatch_once_per_press(hotkey_window, monkeypatch, keys, action):
    harness = hotkey_window
    actions = {}
    for name in (
        "play_pause_hotkey", "toggle_window_visibility",
        "seek_forward_hotkey", "seek_backward_hotkey",
    ):
        actions[name] = Mock()
        monkeypatch.setattr(harness.window, name, actions[name])

    _poll(harness)
    _poll(harness, *keys)
    _poll(harness, *keys)
    _poll(harness, *keys)
    actions[action].assert_called_once_with()
    # Control remains down while releasing the numpad key, so its edge state
    # continues to be sampled by the actual global-hotkey polling code.
    _poll(harness, *((VK_CONTROL,) if VK_CONTROL in keys else ()))
    _poll(harness, *keys)
    assert actions[action].call_count == 2
    for name, callback in actions.items():
        if name != action:
            callback.assert_not_called()
    _assert_no_w(harness)


@pytest.mark.parametrize("kind", ["scheduler", "live_midi"])
@pytest.mark.parametrize("retired_key", [VK_DIVIDE, VK_F10], ids=["Numpad-divide", "F10"])
def test_stop_still_stops_output_after_retired_shortcut_without_sending_w(hotkey_window, kind, retired_key):
    harness = hotkey_window
    output = _active_output(harness, kind)
    _poll(harness, retired_key)

    harness.window.stop()

    output.stop.assert_called_once_with(*(("stopped",) if kind == "live_midi" else ()))
    assert not output.running
    assert not harness.window.backend.pressed
    _assert_no_w(harness)


@pytest.mark.parametrize("kind", ["scheduler", "live_midi"])
@pytest.mark.parametrize("retired_key", [VK_DIVIDE, VK_F10], ids=["Numpad-divide", "F10"])
def test_close_still_stops_and_waits_for_output_without_sending_w(hotkey_window, kind, retired_key):
    harness = hotkey_window
    output = _active_output(harness, kind)
    _poll(harness, retired_key)
    event = QCloseEvent()

    harness.window.closeEvent(event)

    output.stop.assert_called_once_with(*(("application closed",) if kind == "live_midi" else ()))
    output.wait.assert_called_once_with(0.5 if kind == "live_midi" else 0.75)
    assert event.isAccepted()
    assert not output.running
    assert not harness.window.backend.pressed
    _assert_no_w(harness)


def test_shortcut_help_and_actions_have_no_retired_walking_shortcut(hotkey_window, monkeypatch):
    window = hotkey_window.window
    messages = []
    monkeypatch.setattr(ui.QMessageBox, "information", lambda *args: messages.append(args[2]))

    window.show_keyboard_shortcuts()

    assert messages and all("auto-walk" not in message and "F10" not in message for message in messages)
    assert not hasattr(window, "toggle_hold_w")
    assert not hasattr(window, "_walk_backend")
    assert not hasattr(window, "_w_held")
    assert all(action.shortcut().toString() not in {"F10", "Num+/"} for action in window.actions())
