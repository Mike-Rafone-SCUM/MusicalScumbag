from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import pytest

from musical_scumme.config import CURRENT_SCUM_PROFILE
from musical_scumme.input_backend import DryRunBackend
from musical_scumme.live_midi import (
    LiveMidiCallbacks,
    LiveMidiConfig,
    LiveMidiSession,
    MidiInputDevice,
    MidiInputEvent,
    MidiInputUnavailable,
    RtMidiInputProvider,
    decode_midi_message,
    map_live_pitch,
)

DEVICE = MidiInputDevice(0, "Test Keyboard", "Test Keyboard")


def wait_until(predicate, timeout_s: float = 1.5) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    assert predicate()


class FakeMidiPort:
    def __init__(self, on_event, on_error) -> None:
        self.on_event = on_event
        self.on_error = on_error
        self.closed = False

    def emit(self, event: MidiInputEvent) -> None:
        self.on_event(event)

    def emit_error(self, message: str) -> None:
        self.on_error(message)

    def close(self) -> None:
        self.closed = True


class FakeMidiProvider:
    def __init__(self) -> None:
        self.devices = (DEVICE,)
        self.port: FakeMidiPort | None = None
        self.open_error: Exception | None = None
        self.enumeration_error: Exception | None = None

    def input_devices(self) -> tuple[MidiInputDevice, ...]:
        if self.enumeration_error is not None:
            raise self.enumeration_error
        return self.devices

    def open_input(self, device, on_event, on_error) -> FakeMidiPort:
        if self.open_error is not None:
            raise self.open_error
        assert device == DEVICE
        self.port = FakeMidiPort(on_event, on_error)
        return self.port


class FastLiveMidiSession(LiveMidiSession):
    _POLL_SECONDS = 0.002
    _FOCUS_POLL_SECONDS = 0.005
    _DEVICE_POLL_SECONDS = 0.02


@dataclass
class MutableSafety:
    focused: bool = True
    emergency: bool = False

    @property
    def is_scum(self) -> bool:
        return self.focused


@dataclass
class SessionHarness:
    session: LiveMidiSession
    backend: DryRunBackend
    provider: FakeMidiProvider
    safety: MutableSafety
    statuses: list[str]
    activities: list[str]
    finished: list[str]

    @property
    def port(self) -> FakeMidiPort:
        assert self.provider.port is not None
        return self.provider.port

    def emit(self, event: MidiInputEvent) -> None:
        self.port.emit(event)


@pytest.fixture
def session_factory():
    sessions: list[LiveMidiSession] = []

    def factory(
        *,
        config: LiveMidiConfig | None = None,
        backend: DryRunBackend | None = None,
        provider: FakeMidiProvider | None = None,
        safety: MutableSafety | None = None,
    ) -> SessionHarness:
        actual_backend = backend or DryRunBackend()
        actual_provider = provider or FakeMidiProvider()
        actual_safety = safety or MutableSafety()
        statuses: list[str] = []
        activities: list[str] = []
        finished: list[str] = []
        session = FastLiveMidiSession(
            actual_backend,
            actual_provider,
            CURRENT_SCUM_PROFILE,
            config or LiveMidiConfig(require_scum_focus=False),
            LiveMidiCallbacks(statuses.append, activities.append, finished.append),
            focus_provider=lambda: actual_safety,
            emergency_stop=lambda: actual_safety.emergency,
        )
        sessions.append(session)
        session.start(DEVICE)
        wait_until(lambda: session.running)
        return SessionHarness(
            session,
            actual_backend,
            actual_provider,
            actual_safety,
            statuses,
            activities,
            finished,
        )

    yield factory

    for session in sessions:
        session.stop()
        assert session.wait(1.0)


def note_on(note: int, *, channel: int = 0, velocity: int = 100) -> MidiInputEvent:
    return MidiInputEvent("note_on", channel=channel, note=note, velocity=velocity)


def note_off(note: int, *, channel: int = 0, velocity: int = 64) -> MidiInputEvent:
    return MidiInputEvent("note_off", channel=channel, note=note, velocity=velocity)


def control_change(control: int, value: int, *, channel: int = 0) -> MidiInputEvent:
    return MidiInputEvent(
        "control_change",
        channel=channel,
        control=control,
        value=value,
    )


def test_short_midi_decoder_handles_notes_zero_velocity_and_controls():
    assert decode_midi_message([0x91, 60, 100]) == MidiInputEvent(
        "note_on", channel=1, note=60, velocity=100
    )
    assert decode_midi_message([0x91, 60, 0]) == MidiInputEvent(
        "note_off", channel=1, note=60, velocity=0
    )
    assert decode_midi_message([0x81, 60, 73]) == MidiInputEvent(
        "note_off", channel=1, note=60, velocity=73
    )
    assert decode_midi_message([0xBF, 64, 127]) == MidiInputEvent(
        "control_change", channel=15, control=64, value=127
    )


@pytest.mark.parametrize(
    "message",
    (
        [],
        [0x40, 60, 100],
        [0x90, 60],
        [0x90, 128, 100],
        [0x90, 60, 128],
        [0xF8],
        [256, 60, 100],
        ["not-a-byte"],
    ),
)
def test_short_midi_decoder_rejects_incomplete_or_unsupported_messages(message):
    assert decode_midi_message(message) is None


def test_live_pitch_mapping_transposes_then_folds_or_rejects_strict_notes():
    assert map_live_pitch(48, 0, "fold") == 60
    assert map_live_pitch(84, 0, "fold") == 72
    assert map_live_pitch(59, 1, "fold") == 60
    assert map_live_pitch(127, 36, "fold") == 67
    assert map_live_pitch(59, 0, "strict") is None
    assert map_live_pitch(60, 0, "strict") == 60
    assert map_live_pitch(72, 0, "strict") == 72
    assert map_live_pitch(73, 0, "strict") is None


def test_note_references_and_fold_collisions_release_only_after_final_note_off(
    session_factory,
):
    harness = session_factory()

    harness.emit(note_on(48))
    harness.emit(note_on(60))
    wait_until(lambda: harness.backend.history == [("down", "Y")])

    harness.emit(note_off(48))
    time.sleep(0.02)
    assert harness.backend.pressed == {"Y"}
    assert harness.backend.history == [("down", "Y")]

    harness.emit(note_off(60))
    wait_until(lambda: harness.backend.pressed == set())
    assert harness.backend.history == [("down", "Y"), ("up", "Y")]


def test_repeated_pitch_requires_balanced_note_off_count(session_factory):
    harness = session_factory()

    harness.emit(note_on(60))
    harness.emit(note_on(60))
    wait_until(lambda: harness.backend.pressed == {"Y"})
    assert harness.backend.history == [("down", "Y")]

    harness.emit(note_off(60))
    time.sleep(0.02)
    assert harness.backend.pressed == {"Y"}
    harness.emit(note_off(60))
    wait_until(lambda: harness.backend.pressed == set())
    assert harness.backend.history == [("down", "Y"), ("up", "Y")]


def test_sustain_cc64_defers_release_until_pedal_up(session_factory):
    harness = session_factory()

    harness.emit(note_on(60))
    harness.emit(control_change(64, 127))
    harness.emit(note_off(60))
    wait_until(lambda: harness.backend.pressed == {"Y"})
    assert harness.backend.history == [("down", "Y")]

    harness.emit(control_change(64, 0))
    wait_until(lambda: harness.backend.pressed == set())
    assert harness.backend.history[-1] == ("up", "Y")


def test_reset_controllers_cc121_releases_only_that_channels_sustain(
    session_factory,
):
    harness = session_factory()

    for channel, note in ((0, 60), (1, 62)):
        harness.emit(note_on(note, channel=channel))
        harness.emit(control_change(64, 127, channel=channel))
        harness.emit(note_off(note, channel=channel))
    wait_until(lambda: harness.backend.pressed == {"Y", "O"})

    harness.emit(control_change(121, 0, channel=0))
    wait_until(lambda: harness.backend.pressed == {"O"})
    harness.emit(control_change(64, 0, channel=1))
    wait_until(lambda: harness.backend.pressed == set())


@pytest.mark.parametrize("control", (120, 123))
def test_all_sound_and_all_notes_off_release_only_the_addressed_channel(
    session_factory,
    control,
):
    harness = session_factory()
    harness.emit(note_on(60, channel=0))
    harness.emit(note_on(62, channel=1))
    wait_until(lambda: harness.backend.pressed == {"Y", "O"})

    harness.emit(control_change(control, 0, channel=0))
    wait_until(lambda: harness.backend.pressed == {"O"})
    assert harness.session.running

    history_after_release = list(harness.backend.history)
    harness.emit(note_off(60, channel=0))
    time.sleep(0.02)
    assert harness.backend.history == history_after_release
    harness.emit(note_off(62, channel=1))
    wait_until(lambda: harness.backend.pressed == set())


@pytest.mark.parametrize("control", (120, 123))
def test_channel_release_preserves_a_shared_folded_key(session_factory, control):
    harness = session_factory()
    harness.emit(note_on(60, channel=0))
    harness.emit(note_on(48, channel=1))
    harness.emit(control_change(control, 0, channel=0))
    # Queue another key to confirm the worker passed the channel release.
    harness.emit(note_on(62, channel=1))
    wait_until(lambda: harness.backend.pressed == {"Y", "O"})
    harness.emit(control_change(control, 0, channel=1))
    wait_until(lambda: harness.backend.pressed == set())


def test_channel_selection_and_channel_10_filter_are_enforced(session_factory):
    selected = session_factory(
        config=LiveMidiConfig(
            channel=1,
            ignore_channel_10=True,
            require_scum_focus=False,
        )
    )
    selected.emit(note_on(60, channel=0))
    selected.emit(note_on(61, channel=1))
    selected.emit(note_on(62, channel=9))
    wait_until(lambda: selected.backend.pressed == {"I"})
    selected.emit(note_off(61, channel=1))
    wait_until(lambda: selected.backend.pressed == set())

    percussion = session_factory(
        config=LiveMidiConfig(
            channel=-1,
            ignore_channel_10=False,
            require_scum_focus=False,
        )
    )
    percussion.emit(note_on(62, channel=9))
    wait_until(lambda: percussion.backend.pressed == {"O"})


def test_live_polyphony_limit_ignores_extra_keys_but_balances_note_offs(
    session_factory,
):
    harness = session_factory(
        config=LiveMidiConfig(max_polyphony=2, require_scum_focus=False)
    )

    harness.emit(note_on(60))
    harness.emit(note_on(62))
    harness.emit(note_on(64))
    wait_until(lambda: harness.backend.pressed == {"Y", "O"})
    assert any("2-key live limit" in message for message in harness.activities)

    harness.emit(note_off(64))
    harness.emit(note_off(60))
    harness.emit(note_off(62))
    wait_until(lambda: harness.backend.pressed == set())


def test_explicit_stop_releases_keys_closes_port_and_finishes(session_factory):
    harness = session_factory()
    harness.emit(note_on(60))
    wait_until(lambda: harness.backend.pressed == {"Y"})

    harness.session.stop("user stop")
    assert harness.session.wait(1.0)

    assert harness.backend.pressed == set()
    assert harness.port.closed
    assert harness.finished == ["user stop"]


def test_f8_emergency_stop_releases_keys(session_factory):
    harness = session_factory()
    harness.emit(note_on(60))
    wait_until(lambda: harness.backend.pressed == {"Y"})

    harness.safety.emergency = True
    wait_until(lambda: not harness.session.running)

    assert harness.backend.pressed == set()
    assert harness.finished == ["emergency stop"]


def test_focus_loss_mutes_and_releases_then_accepts_fresh_note_ons(
    session_factory,
):
    safety = MutableSafety(focused=True)
    harness = session_factory(
        config=LiveMidiConfig(
            require_scum_focus=True,
            pause_on_focus_loss=True,
        ),
        safety=safety,
    )
    wait_until(lambda: any("active:" in status for status in harness.statuses))
    harness.emit(note_on(60))
    wait_until(lambda: harness.backend.pressed == {"Y"})

    safety.focused = False
    wait_until(lambda: harness.backend.pressed == set())
    assert harness.session.running
    assert any("safely muted" in status for status in harness.statuses)

    safety.focused = True
    wait_until(lambda: harness.statuses[-1].startswith("Live MIDI active"))
    harness.emit(note_on(62))
    wait_until(lambda: harness.backend.pressed == {"O"})


def test_focus_loss_disarms_when_pause_is_disabled(session_factory):
    safety = MutableSafety(focused=True)
    harness = session_factory(
        config=LiveMidiConfig(
            require_scum_focus=True,
            pause_on_focus_loss=False,
        ),
        safety=safety,
    )
    wait_until(lambda: any("active:" in status for status in harness.statuses))
    harness.emit(note_on(60))
    wait_until(lambda: harness.backend.pressed == {"Y"})

    safety.focused = False
    wait_until(lambda: not harness.session.running)

    assert harness.backend.pressed == set()
    assert harness.finished == ["SCUM lost focus"]


def test_device_disconnect_stops_and_releases(session_factory):
    harness = session_factory()
    harness.emit(note_on(60))
    wait_until(lambda: harness.backend.pressed == {"Y"})

    harness.provider.devices = ()
    wait_until(lambda: not harness.session.running)

    assert harness.backend.pressed == set()
    assert harness.port.closed
    assert harness.finished == ["MIDI input disconnected: Test Keyboard"]


def test_backend_partial_failure_still_releases_and_stops(session_factory):
    class FailingBackend(DryRunBackend):
        def send_batch(self, events) -> None:
            super().send_batch(events)
            raise RuntimeError("synthetic backend failure")

    backend = FailingBackend()
    harness = session_factory(backend=backend)

    harness.emit(note_on(60))
    wait_until(lambda: not harness.session.running)

    assert backend.pressed == set()
    assert ("down", "Y") in backend.history
    assert ("up", "Y") in backend.history
    assert harness.finished == ["error: synthetic backend failure"]


def test_stop_cannot_leave_a_late_live_key_down_after_cleanup(session_factory):
    class BlockingBackend(DryRunBackend):
        def __init__(self) -> None:
            super().__init__()
            self.dispatch_entered = threading.Event()
            self.allow_dispatch = threading.Event()

        def send_batch(self, events) -> None:
            self.dispatch_entered.set()
            assert self.allow_dispatch.wait(1.0)
            super().send_batch(events)

    backend = BlockingBackend()
    harness = session_factory(backend=backend)
    harness.emit(note_on(60))
    assert backend.dispatch_entered.wait(1.0)

    stop_thread = threading.Thread(target=harness.session.stop)
    stop_thread.start()
    wait_until(lambda: harness.session._stop.is_set())
    backend.allow_dispatch.set()
    stop_thread.join(1.0)

    assert not stop_thread.is_alive()
    assert harness.session.wait(1.0)
    assert backend.pressed == set()
    assert backend.history[-1] == ("up", "Y")


def test_device_open_failure_never_marks_session_running():
    provider = FakeMidiProvider()
    provider.open_error = RuntimeError("port busy")
    session = FastLiveMidiSession(
        DryRunBackend(),
        provider,
        CURRENT_SCUM_PROFILE,
        LiveMidiConfig(require_scum_focus=False),
    )

    with pytest.raises(MidiInputUnavailable, match="port busy"):
        session.start(DEVICE)

    assert not session.running


def test_late_callback_from_closed_port_cannot_press_a_key(session_factory):
    harness = session_factory()
    port = harness.port

    harness.session.stop()
    assert harness.session.wait(1.0)
    history_after_stop = list(harness.backend.history)

    port.emit(note_on(60))
    time.sleep(0.03)

    assert harness.backend.history == history_after_stop
    assert harness.backend.pressed == set()


class _FakeNativeMidiIn:
    def __init__(self, module) -> None:
        self.module = module
        self.callback = None
        self.error_callback = None
        self.opened_index = None
        self.closed = False
        self.deleted = False
        self.ignored_types = None

    def get_ports(self):
        return list(self.module.port_names)

    def ignore_types(self, **kwargs) -> None:
        self.ignored_types = kwargs

    def set_callback(self, callback) -> None:
        self.callback = callback

    def set_error_callback(self, callback) -> None:
        self.error_callback = callback

    def open_port(self, index, _name) -> None:
        self.opened_index = index

    def cancel_callback(self) -> None:
        self.callback = None

    def cancel_error_callback(self) -> None:
        self.error_callback = None

    def close_port(self) -> None:
        self.closed = True

    def delete(self) -> None:
        self.deleted = True


class _FakeRtMidiModule:
    def __init__(self, port_names) -> None:
        self.port_names = list(port_names)
        self.instances: list[_FakeNativeMidiIn] = []

    def MidiIn(self):
        instance = _FakeNativeMidiIn(self)
        self.instances.append(instance)
        return instance


def test_rtmidi_provider_labels_duplicate_ports_and_closes_enumerator():
    module = _FakeRtMidiModule(["Controller", "Controller"])
    provider = RtMidiInputProvider(module)

    devices = provider.input_devices()

    assert [device.display_name for device in devices] == [
        "Controller · input 1",
        "Controller · input 2",
    ]
    assert module.instances[0].closed
    assert module.instances[0].deleted


def test_rtmidi_provider_decodes_callback_and_cancels_it_before_close():
    module = _FakeRtMidiModule(["Controller"])
    provider = RtMidiInputProvider(module)
    device = provider.input_devices()[0]
    events: list[MidiInputEvent] = []
    errors: list[str] = []

    port = provider.open_input(device, events.append, errors.append)
    native = module.instances[-1]
    assert native.opened_index == 0
    assert native.ignored_types == {
        "sysex": True,
        "timing": True,
        "active_sense": True,
    }
    assert native.callback is not None
    native.callback(([0x90, 60, 100], 0.0))
    assert events == [MidiInputEvent("note_on", note=60, velocity=100)]

    port.close()

    assert native.callback is None
    assert native.error_callback is None
    assert native.closed
    assert native.deleted
    assert errors == []
