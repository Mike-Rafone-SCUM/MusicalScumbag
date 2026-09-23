from __future__ import annotations

import logging
import queue
import threading
import time
from collections import Counter, defaultdict, deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

try:
    import rtmidi as _rtmidi
except ImportError:  # pragma: no cover - exercised through the provider error path
    _rtmidi = None

from .input_backend import (
    InputBackend,
    emergency_stop_pressed,
    foreground_window_info,
)
from .model import KeyBindingProfile, midi_note_name

logger = logging.getLogger("musical_scumme.live_midi")


class MidiInputUnavailable(RuntimeError):
    """Raised when the native MIDI input runtime or selected port is unavailable."""


@dataclass(frozen=True, slots=True)
class MidiInputDevice:
    index: int
    name: str
    display_name: str


@dataclass(frozen=True, slots=True)
class MidiInputEvent:
    kind: str
    channel: int = 0
    note: int = 0
    velocity: int = 0
    control: int = 0
    value: int = 0


@dataclass(frozen=True, slots=True)
class LiveMidiConfig:
    mapping_mode: str = "fold"
    transpose: int = 0
    channel: int = -1
    ignore_channel_10: bool = True
    max_polyphony: int = 3
    require_scum_focus: bool = True
    pause_on_focus_loss: bool = True


StatusCallback = Callable[[str], None]
ActivityCallback = Callable[[str], None]
FinishedCallback = Callable[[str], None]


@dataclass(slots=True)
class LiveMidiCallbacks:
    status: StatusCallback = lambda _message: None
    activity: ActivityCallback = lambda _message: None
    finished: FinishedCallback = lambda _reason: None


class MidiInputPort(Protocol):
    def close(self) -> None: ...


class MidiInputProvider(Protocol):
    def input_devices(self) -> tuple[MidiInputDevice, ...]: ...

    def open_input(
        self,
        device: MidiInputDevice,
        on_event: Callable[[MidiInputEvent], None],
        on_error: Callable[[str], None],
    ) -> MidiInputPort: ...


def decode_midi_message(message: Sequence[int]) -> MidiInputEvent | None:
    """Decode the short channel messages used by a live keyboard."""

    if not message:
        return None
    try:
        values = tuple(int(value) for value in message)
    except (TypeError, ValueError):
        return None
    if any(value < 0 or value > 255 for value in values):
        return None

    status = values[0]
    if status < 0x80 or status >= 0xF0:
        return None
    message_type = status & 0xF0
    channel = status & 0x0F

    if message_type in {0x80, 0x90}:
        if len(values) < 3 or values[1] > 127 or values[2] > 127:
            return None
        kind = "note_on" if message_type == 0x90 and values[2] > 0 else "note_off"
        return MidiInputEvent(
            kind=kind,
            channel=channel,
            note=values[1],
            velocity=values[2],
        )

    if message_type == 0xB0:
        if len(values) < 3 or values[1] > 127 or values[2] > 127:
            return None
        return MidiInputEvent(
            kind="control_change",
            channel=channel,
            control=values[1],
            value=values[2],
        )
    return None


def map_live_pitch(pitch: int, transpose: int, mapping_mode: str) -> int | None:
    """Map one live note to the fixed SCUM C4-C5 base bank."""

    mapped = max(0, min(127, int(pitch) + int(transpose)))
    if mapping_mode == "strict":
        return mapped if 60 <= mapped <= 72 else None
    while mapped < 60:
        mapped += 12
    while mapped > 72:
        mapped -= 12
    return mapped


class _RtMidiInputPort:
    def __init__(
        self,
        midi_in: Any,
        device: MidiInputDevice,
        on_event: Callable[[MidiInputEvent], None],
        on_error: Callable[[str], None],
    ) -> None:
        self._midi_in = midi_in
        self._on_event = on_event
        self._on_error = on_error
        self._closed = False
        self._close_lock = threading.Lock()
        try:
            self._midi_in.ignore_types(sysex=True, timing=True, active_sense=True)
            self._midi_in.set_callback(self._message_callback)
            self._midi_in.set_error_callback(self._error_callback)
            self._midi_in.open_port(device.index, "MusicalScumme live MIDI input")
        except Exception:
            self.close()
            raise

    def _message_callback(self, event_and_delta: Any, _data: Any = None) -> None:
        if self._closed:
            return
        try:
            message, _delta = event_and_delta
            event = decode_midi_message(message)
            if event is not None:
                self._on_event(event)
        except Exception:
            logger.exception("MIDI input callback failed")
            self._on_error("MIDI input callback failed")

    def _error_callback(self, _error_type: Any, message: Any, _data: Any = None) -> None:
        if not self._closed:
            self._on_error(str(message).strip() or "MIDI input device error")

    def close(self) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            midi_in = self._midi_in
            self._midi_in = None
        if midi_in is None:
            return
        for method_name in ("cancel_callback", "cancel_error_callback", "close_port", "delete"):
            try:
                getattr(midi_in, method_name)()
            except Exception:
                logger.debug("MIDI port cleanup method %s failed", method_name, exc_info=True)


class RtMidiInputProvider:
    """Enumerate and open MIDI inputs through python-rtmidi."""

    def __init__(self, midi_module: Any | None = None) -> None:
        self._midi_module = midi_module if midi_module is not None else _rtmidi

    def _new_input(self) -> Any:
        if self._midi_module is None:
            raise MidiInputUnavailable(
                "The live MIDI runtime is unavailable. Install requirements.txt to add python-rtmidi."
            )
        try:
            return self._midi_module.MidiIn()
        except Exception as exc:
            raise MidiInputUnavailable(f"Could not initialise MIDI input: {exc}") from exc

    def input_devices(self) -> tuple[MidiInputDevice, ...]:
        midi_in = self._new_input()
        try:
            names = tuple(str(name) for name in midi_in.get_ports())
        except Exception as exc:
            raise MidiInputUnavailable(f"Could not enumerate MIDI inputs: {exc}") from exc
        finally:
            for method_name in ("close_port", "delete"):
                try:
                    getattr(midi_in, method_name)()
                except Exception:
                    logger.debug("MIDI enumeration cleanup failed", exc_info=True)

        name_counts = Counter(names)
        return tuple(
            MidiInputDevice(
                index=index,
                name=name,
                display_name=(
                    f"{name} · input {index + 1}" if name_counts[name] > 1 else name
                ),
            )
            for index, name in enumerate(names)
        )

    def open_input(
        self,
        device: MidiInputDevice,
        on_event: Callable[[MidiInputEvent], None],
        on_error: Callable[[str], None],
    ) -> MidiInputPort:
        midi_in = self._new_input()
        try:
            names = tuple(str(name) for name in midi_in.get_ports())
            if device.index >= len(names) or names[device.index] != device.name:
                raise MidiInputUnavailable(
                    f"MIDI input '{device.name}' changed or disconnected. Refresh the device list."
                )
            return _RtMidiInputPort(midi_in, device, on_event, on_error)
        except Exception:
            for method_name in ("close_port", "delete"):
                try:
                    getattr(midi_in, method_name)()
                except Exception:
                    logger.debug("MIDI open cleanup failed", exc_info=True)
            raise


class LiveMidiSession:
    """Route a supervised MIDI keyboard to the existing SCUM key backend."""

    _QUEUE_LIMIT = 2048
    _POLL_SECONDS = 0.01
    _FOCUS_POLL_SECONDS = 0.05
    _DEVICE_POLL_SECONDS = 0.5

    def __init__(
        self,
        backend: InputBackend,
        provider: MidiInputProvider,
        profile: KeyBindingProfile,
        config: LiveMidiConfig,
        callbacks: LiveMidiCallbacks | None = None,
        *,
        focus_provider: Callable[[], Any] = foreground_window_info,
        emergency_stop: Callable[[], bool] = emergency_stop_pressed,
    ) -> None:
        self.backend = backend
        self.provider = provider
        self.profile = profile
        self.config = config
        self.callbacks = callbacks or LiveMidiCallbacks()
        self._focus_provider = focus_provider
        self._emergency_stop = emergency_stop

        self._queue: queue.Queue[MidiInputEvent] = queue.Queue(self._QUEUE_LIMIT)
        self._state_lock = threading.RLock()
        self._dispatch_lock = threading.RLock()
        self._stop = threading.Event()
        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._port: MidiInputPort | None = None
        self._device: MidiInputDevice | None = None
        self._generation = 0
        self._requested_reason = "stopped"

        self._presses: dict[tuple[int, int], deque[str | None]] = defaultdict(deque)
        self._sustained: dict[int, list[str]] = defaultdict(list)
        self._sustain_channels: set[int] = set()
        self._key_counts: Counter[str] = Counter()

    @property
    def running(self) -> bool:
        return self._running.is_set()

    def start(self, device: MidiInputDevice) -> None:
        with self._state_lock:
            if self.running:
                raise RuntimeError("Live MIDI input is already running.")
            self._stop.clear()
            self._requested_reason = "stopped"
            self._queue = queue.Queue(self._QUEUE_LIMIT)
            self._clear_logical_state()
            self._generation += 1
            generation = self._generation

        def on_event(event: MidiInputEvent) -> None:
            self._enqueue(generation, event)

        def on_error(message: str) -> None:
            self._fail_from_callback(generation, message)

        try:
            port = self.provider.open_input(device, on_event, on_error)
        except Exception as exc:
            raise MidiInputUnavailable(f"Could not open MIDI input '{device.name}': {exc}") from exc

        with self._state_lock:
            self._port = port
            self._device = device
            self._running.set()
            self._thread = threading.Thread(
                target=self._run,
                daemon=True,
                name="MusicalScummeLiveMIDI",
            )
            try:
                self._thread.start()
            except Exception:
                self._running.clear()
                self._port = None
                self._device = None
                port.close()
                raise

    def stop(self, reason: str = "stopped") -> None:
        self._request_stop(reason, close_port=True)

    def panic(self, reason: str = "panic stop") -> None:
        self._request_stop(reason, close_port=True)

    def wait(self, timeout: float | None = None) -> bool:
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        return not self.running

    def _enqueue(self, generation: int, event: MidiInputEvent) -> None:
        with self._state_lock:
            if (
                generation != self._generation
                or not self.running
                or self._stop.is_set()
            ):
                return
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            self._fail_from_callback(generation, "MIDI input overflow")

    def _fail_from_callback(self, generation: int, message: str) -> None:
        with self._state_lock:
            if generation != self._generation or not self.running:
                return
            self._requested_reason = f"error: {message}"
            self._generation += 1
            self._stop.set()

    def _request_stop(self, reason: str, *, close_port: bool) -> None:
        with self._state_lock:
            if not self.running and self._port is None:
                self._safe_release_all()
                return
            self._requested_reason = reason
            self._generation += 1
            self._stop.set()
            port = self._port if close_port else None
            if close_port:
                self._port = None
        if port is not None:
            port.close()
        self._safe_release_all()

    def _close_port(self) -> None:
        with self._state_lock:
            port = self._port
            self._port = None
        if port is not None:
            port.close()

    def _emit_status(self, message: str) -> None:
        try:
            self.callbacks.status(message)
        except Exception:
            logger.exception("Live MIDI status callback failed")

    def _emit_activity(self, message: str) -> None:
        try:
            self.callbacks.activity(message)
        except Exception:
            logger.exception("Live MIDI activity callback failed")

    def _run(self) -> None:
        reason = "stopped"
        device = self._device
        if device is None:
            self._running.clear()
            return
        muted = bool(self.config.require_scum_focus)
        focused_once = False
        next_focus_poll = 0.0
        next_device_poll = time.monotonic() + self._DEVICE_POLL_SECONDS
        if muted:
            self._emit_status(
                f"Live MIDI armed: {device.name}. Switch to SCUM; F8 or Stop disarms."
            )
        else:
            self._emit_status(f"Live MIDI active: {device.name}. F8 or Stop disarms.")

        try:
            while not self._stop.is_set():
                if self._emergency_stop():
                    reason = "emergency stop"
                    self._request_stop(reason, close_port=False)
                    break

                now = time.monotonic()
                if self.config.require_scum_focus and now >= next_focus_poll:
                    next_focus_poll = now + self._FOCUS_POLL_SECONDS
                    try:
                        focused = bool(self._focus_provider().is_scum)
                    except Exception:
                        logger.exception("Could not inspect foreground window during live MIDI")
                        focused = False
                    if focused:
                        if muted:
                            muted = False
                            focused_once = True
                            self._emit_status(
                                f"Live MIDI active: {device.name}. F8 or Stop disarms."
                            )
                    elif not muted:
                        muted = True
                        self._safe_release_all()
                        if focused_once and not self.config.pause_on_focus_loss:
                            reason = "SCUM lost focus"
                            self._request_stop(reason, close_port=False)
                            break
                        self._emit_status(
                            "SCUM is not focused — live MIDI safely muted; fresh note-ons resume."
                        )

                if now >= next_device_poll:
                    next_device_poll = now + self._DEVICE_POLL_SECONDS
                    try:
                        available = self.provider.input_devices()
                    except Exception as exc:
                        reason = f"error: MIDI device check failed: {exc}"
                        self._request_stop(reason, close_port=False)
                        break
                    if not any(
                        candidate.index == device.index and candidate.name == device.name
                        for candidate in available
                    ):
                        reason = f"MIDI input disconnected: {device.name}"
                        self._request_stop(reason, close_port=False)
                        break

                try:
                    event = self._queue.get(timeout=self._POLL_SECONDS)
                except queue.Empty:
                    continue
                if muted:
                    continue
                try:
                    self._process_event(event)
                except Exception as exc:
                    logger.exception("Live MIDI dispatch failed")
                    reason = f"error: {exc}"
                    self._request_stop(reason, close_port=False)
                    break

            with self._state_lock:
                reason = self._requested_reason if self._requested_reason != "stopped" else reason
        finally:
            self._stop.set()
            with self._state_lock:
                self._generation += 1
            self._close_port()
            self._safe_release_all()
            with self._state_lock:
                self._device = None
                self._running.clear()
            if reason.startswith("error:"):
                self._emit_status(f"Live MIDI stopped — {reason[7:]}")
            else:
                self._emit_status(reason.capitalize())
            try:
                self.callbacks.finished(reason)
            except Exception:
                logger.exception("Live MIDI finished callback failed")

    def _channel_allowed(self, channel: int) -> bool:
        selected = max(-1, min(15, int(self.config.channel)))
        if selected >= 0 and channel != selected:
            return False
        return not (self.config.ignore_channel_10 and channel == 9)

    def _process_event(self, event: MidiInputEvent) -> None:
        if not self._channel_allowed(event.channel):
            return
        if event.kind == "control_change" and event.control in {120, 123}:
            self._release_channel(event.channel)
            self._emit_activity(f"Channel {event.channel + 1} all notes off")
            return
        if event.kind == "note_on":
            self._note_on(event)
        elif event.kind == "note_off":
            self._note_off(event)
        elif event.kind == "control_change":
            self._control_change(event)

    def _note_on(self, event: MidiInputEvent) -> None:
        mapped_pitch = map_live_pitch(
            event.note,
            self.config.transpose,
            self.config.mapping_mode,
        )
        source = (event.channel, event.note)
        with self._dispatch_lock:
            if self._stop.is_set():
                return
            if mapped_pitch is None:
                self._presses[source].append(None)
                self._emit_activity(f"{midi_note_name(event.note)} outside strict live range")
                return
            key = self.profile.key_for_base_pitch(mapped_pitch)
            active_key_count = sum(count > 0 for count in self._key_counts.values())
            max_polyphony = max(1, min(8, int(self.config.max_polyphony)))
            if self._key_counts[key] <= 0 and active_key_count >= max_polyphony:
                self._presses[source].append(None)
                self._emit_activity(
                    f"{midi_note_name(event.note)} ignored · {max_polyphony}-key live limit"
                )
                return

            self._presses[source].append(key)
            first_reference = self._key_counts[key] <= 0
            self._key_counts[key] += 1
            if first_reference:
                self.backend.send_batch((("down", key),))
            self._emit_activity(
                f"{midi_note_name(event.note)} → {midi_note_name(mapped_pitch)} · "
                f"key {key} · velocity {event.velocity}"
            )

    def _note_off(self, event: MidiInputEvent) -> None:
        source = (event.channel, event.note)
        with self._dispatch_lock:
            presses = self._presses.get(source)
            if not presses:
                return
            key = presses.popleft()
            if not presses:
                self._presses.pop(source, None)
            if key is None:
                return
            if event.channel in self._sustain_channels:
                self._sustained[event.channel].append(key)
                return
            self._release_key_reference(key)

    def _control_change(self, event: MidiInputEvent) -> None:
        if event.control == 64:
            if event.value >= 64:
                self._sustain_channels.add(event.channel)
            else:
                self._sustain_channels.discard(event.channel)
                self._release_sustained(event.channel)
        elif event.control == 121:
            self._sustain_channels.discard(event.channel)
            self._release_sustained(event.channel)

    def _release_sustained(self, channel: int) -> None:
        with self._dispatch_lock:
            keys = self._sustained.pop(channel, [])
            for key in keys:
                self._release_key_reference(key)

    def _release_channel(self, channel: int) -> None:
        """Release only one MIDI channel without disturbing shared SCUM keys.

        A controller can legitimately send CC120/123 on one channel while notes
        from another selected channel are still sounding.  Reference counting
        preserves any physical key that is still owned elsewhere.
        """

        with self._dispatch_lock:
            sources = [source for source in self._presses if source[0] == channel]
            for source in sources:
                presses = self._presses.pop(source, ())
                for key in presses:
                    if key is not None:
                        self._release_key_reference(key)
            for key in self._sustained.pop(channel, []):
                self._release_key_reference(key)
            self._sustain_channels.discard(channel)

    def _release_key_reference(self, key: str) -> None:
        count = self._key_counts.get(key, 0)
        if count <= 1:
            self._key_counts.pop(key, None)
            self.backend.send_batch((("up", key),))
        else:
            self._key_counts[key] = count - 1

    def _clear_logical_state(self) -> None:
        self._presses.clear()
        self._sustained.clear()
        self._sustain_channels.clear()
        self._key_counts.clear()

    def _safe_release_all(self) -> None:
        with self._dispatch_lock:
            self._clear_logical_state()
            try:
                self.backend.release_all()
            except Exception:
                logger.exception("Could not release every live MIDI key")
