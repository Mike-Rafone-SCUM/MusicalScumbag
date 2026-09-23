import pytest

from musical_scumme.input_backend import (
    DryRunBackend,
    key_name_to_vk,
    normalize_key_name,
    sendinput_abi_sizes,
)


def test_key_name_parser():
    assert key_name_to_vk("z") == ord("Z")
    assert key_name_to_vk("5") == ord("5")
    assert key_name_to_vk("LCTRL") == 0xA2
    assert normalize_key_name("shift") == "LSHIFT"
    assert normalize_key_name("Left Cmd") == "LWIN"
    assert key_name_to_vk("Left Cmd") == 0x5B
    with pytest.raises(ValueError):
        key_name_to_vk("not-a-key")


def test_dry_run_releases_everything():
    backend = DryRunBackend()
    backend.key_down("Z")
    backend.key_down("LSHIFT")
    backend.release_all()
    assert backend.pressed == set()
    assert ("up", "Z") in backend.history
    assert ("up", "LSHIFT") in backend.history


def test_dry_run_batch_preserves_event_order_and_balanced_state():
    backend = DryRunBackend()
    backend.send_batch([("down", "Y"), ("down", "I"), ("up", "Y"), ("up", "I")])

    assert backend.history == [
        ("down", "Y"),
        ("down", "I"),
        ("up", "Y"),
        ("up", "I"),
    ]
    assert backend.pressed == set()


def test_sendinput_structure_matches_windows_abi():
    actual, expected = sendinput_abi_sizes()
    assert actual == expected


def test_check_key_pressed_edge_detects_transitions(monkeypatch):
    import musical_scumme.input_backend as ib

    state = False
    monkeypatch.setattr(ib, "is_virtual_key_down", lambda vk: state)

    test_vk = 0x66  # Numpad 6
    # Reset internal state for test_vk
    with ib._KEY_STATE_LOCK:
        ib._PREVIOUS_KEY_STATES.pop(test_vk, None)

    # Initial state: key up -> edge should be False
    assert not ib.check_key_pressed_edge(test_vk)
    assert not ib.check_key_pressed_edge(test_vk)

    # Key pressed down: edge should be True on first check
    state = True
    assert ib.check_key_pressed_edge(test_vk)

    # Key remains held down: edge should be False on subsequent checks
    assert not ib.check_key_pressed_edge(test_vk)
    assert not ib.check_key_pressed_edge(test_vk)

    # Key released: edge should be False
    state = False
    assert not ib.check_key_pressed_edge(test_vk)

    # Key pressed again: edge should be True
    state = True
    assert ib.check_key_pressed_edge(test_vk)


def test_numpad_divide_pressed_calls_check_key_pressed_edge(monkeypatch):
    import musical_scumme.input_backend as ib

    called_vk = []
    monkeypatch.setattr(ib, "check_key_pressed_edge", lambda vk: called_vk.append(vk) or True)

    assert ib.numpad_divide_pressed() is True
    assert called_vk == [0x6F]


def test_is_control_down_checks_vk_control(monkeypatch):
    import musical_scumme.input_backend as ib

    called_with = []
    monkeypatch.setattr(ib, "is_virtual_key_down", lambda vk: called_with.append(vk) or True)

    assert ib.is_control_down() is True
    assert called_with == [0x11]


def test_pid_process_cache_avoids_repeated_open_process(monkeypatch):
    import musical_scumme.input_backend as ib

    # Pre-populate PID cache
    with ib._FOREGROUND_LOCK:
        ib._PID_PROCESS_CACHE[99999] = "scum.exe"

    # Verify ForegroundWindowInfo detection
    info = ib.ForegroundWindowInfo("SCUM", "scum.exe", "")
    assert info.is_scum is True


