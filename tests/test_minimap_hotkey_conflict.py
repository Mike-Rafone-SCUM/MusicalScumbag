from types import SimpleNamespace

from musical_scumme import input_backend, ui


def test_ui_ignores_minimap_copy_key_and_retired_f10_walking_shortcut(monkeypatch):
    down = set()
    toggles = []
    monkeypatch.setattr(input_backend, "is_virtual_key_down", lambda vk: vk in down)
    monkeypatch.setattr(input_backend, "_PREVIOUS_KEY_STATES", {})
    monkeypatch.setattr(ui, "function_key_pressed", lambda key: False)
    monkeypatch.setattr(ui, "is_control_down", lambda: False)
    window = SimpleNamespace(play_pause_hotkey=lambda: toggles.append("play"),
                             toggle_window_visibility=lambda: toggles.append("window"))
    for _ in range(20):
        down.add(0x6F)
        ui.MainWindow._poll_global_hotkeys(window)
        down.clear()
        ui.MainWindow._poll_global_hotkeys(window)
    assert toggles == []
    down.add(0x79)
    ui.MainWindow._poll_global_hotkeys(window)
    ui.MainWindow._poll_global_hotkeys(window)
    assert toggles == []
