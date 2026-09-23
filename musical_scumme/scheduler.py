from __future__ import annotations

import ctypes
import gc
from ctypes import wintypes
import logging
import os
import threading
import time
from bisect import bisect_left
from dataclasses import dataclass
from operator import attrgetter
from typing import Callable

from .input_backend import InputBackend, emergency_stop_pressed, foreground_window_info
from .model import PlaybackPlan

logger = logging.getLogger("musical_scumme.scheduler")


StatusCallback = Callable[[str], None]
ProgressCallback = Callable[[float], None]
FinishedCallback = Callable[[str], None]
TimecodeCallback = Callable[[float, float], None]


@dataclass(slots=True)
class SchedulerCallbacks:
    status: StatusCallback = lambda _message: None
    progress: ProgressCallback = lambda _fraction: None
    finished: FinishedCallback = lambda _reason: None
    timecode: TimecodeCallback = lambda _elapsed_ms, _total_ms: None



@dataclass(slots=True)
class SchedulerMetrics:
    events_sent: int = 0
    batches_sent: int = 0
    late_events: int = 0
    late_batches: int = 0
    batches_over_5ms: int = 0
    batches_over_20ms: int = 0
    max_lateness_ms: float = 0.0
    total_lateness_ms: float = 0.0
    total_dispatch_ms: float = 0.0
    max_dispatch_ms: float = 0.0
    dispatches_over_2ms: int = 0
    loops_completed: int = 0
    stalls_recovered: int = 0
    stall_recovered_ms: float = 0.0
    focus_pauses: int = 0
    seek_reconstructed_notes: int = 0
    pause_reconstructed_notes: int = 0
    focus_reconstructed_notes: int = 0
    stop_bank_restores: int = 0
    stop_bank_restore_skipped: int = 0
    session_bank_resyncs: int = 0

    @property
    def average_lateness_ms(self) -> float:
        if not self.batches_sent:
            return 0.0
        return self.total_lateness_ms / self.batches_sent

    @property
    def average_dispatch_ms(self) -> float:
        if not self.batches_sent:
            return 0.0
        return self.total_dispatch_ms / self.batches_sent

    @property
    def timing_summary(self) -> str:
        if not self.batches_sent:
            return "No timing sample"
        pressure_ratio = self.batches_over_5ms / self.batches_sent
        if (
            self.batches_over_20ms
            or self.max_lateness_ms >= 35.0
            or pressure_ratio >= 0.04
            or self.max_dispatch_ms >= 12.0
        ):
            return "Timing interference detected"
        if self.batches_over_5ms or self.max_lateness_ms >= 8.0 or self.dispatches_over_2ms:
            return "Minor timing pressure"
        return "Timing clean"

    def record_batch(self, event_count: int, lateness_ms: float, dispatch_ms: float = 0.0) -> None:
        self.events_sent += event_count
        self.batches_sent += 1
        self.total_lateness_ms += max(0.0, lateness_ms)
        self.max_lateness_ms = max(self.max_lateness_ms, lateness_ms)
        dispatch_ms = max(0.0, dispatch_ms)
        self.total_dispatch_ms += dispatch_ms
        self.max_dispatch_ms = max(self.max_dispatch_ms, dispatch_ms)
        if dispatch_ms > 2.0:
            self.dispatches_over_2ms += 1
        if lateness_ms > 0.5:
            self.late_events += event_count
            self.late_batches += 1
        if lateness_ms > 5.0:
            self.batches_over_5ms += 1
        if lateness_ms > 20.0:
            self.batches_over_20ms += 1


@dataclass(frozen=True, slots=True)
class _ScheduledBatch:
    offset_ns: int
    events: tuple[tuple[str, str], ...]
    cumulative_events: int
    bank_after: int = 0



def _sustaining_keys_at(plan: PlaybackPlan, target_ms: float, target_bank: int) -> tuple[str, ...]:
    """Physical keys that should already be down immediately after a seek.

    Notes beginning exactly at the seek point are left to the normal event
    timeline.  A bank change cannot safely coexist with held musical keys, so
    only notes in the reconstructed bank are considered.
    """

    keys: list[str] = []
    seen: set[str] = set()
    epsilon_ms = 0.25
    for note in sorted(plan.planned_notes, key=lambda item: (item.start_ms, item.voice_index, item.key)):
        if note.modifier != target_bank:
            continue
        if note.start_ms >= target_ms - epsilon_ms or note.end_ms <= target_ms + epsilon_ms:
            continue
        if note.key in seen:
            continue
        seen.add(note.key)
        keys.append(note.key)
    return tuple(keys)

def _compile_event_batches(plan: PlaybackPlan) -> tuple[_ScheduledBatch, ...]:
    batches: list[_ScheduledBatch] = []
    index = 0
    current_bank = 0
    while index < len(plan.events):
        anchor = plan.events[index]
        end = index + 1
        while end < len(plan.events) and abs(plan.events[end].at_ms - anchor.at_ms) < 0.0005:
            end += 1
        for event in plan.events[index:end]:
            if event.action == "down":
                if "octave bank up" in event.reason or "restore base bank up" in event.reason:
                    current_bank += 1
                elif "octave bank down" in event.reason or "restore base bank down" in event.reason:
                    current_bank -= 1
        batches.append(
            _ScheduledBatch(
                offset_ns=int(anchor.at_ms * 1_000_000),
                events=tuple((event.action, event.key) for event in plan.events[index:end]),
                cumulative_events=end,
                bank_after=current_bank,
            )
        )
        index = end
    return tuple(batches)


class _WindowsPlaybackPriority:
    """Best-effort MMCSS priority for the worker thread during playback only."""

    def __init__(self) -> None:
        self._avrt = None
        self._handle = None
        self._kernel32 = None
        self._thread = None
        self._previous_priority: int | None = None
        self.mode = "normal"

    def enable(self) -> str:
        if os.name != "nt":
            return self.mode
        try:
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._kernel32.GetCurrentThread.restype = wintypes.HANDLE
            self._kernel32.GetThreadPriority.argtypes = (wintypes.HANDLE,)
            self._kernel32.GetThreadPriority.restype = ctypes.c_int
            self._kernel32.SetThreadPriority.argtypes = (wintypes.HANDLE, ctypes.c_int)
            self._kernel32.SetThreadPriority.restype = wintypes.BOOL
            self._thread = self._kernel32.GetCurrentThread()
            self._previous_priority = int(self._kernel32.GetThreadPriority(self._thread))
            # HIGHEST is intentionally below TIME_CRITICAL. The scheduler needs
            # low jitter, not permission to starve input/render/audio threads.
            if self._kernel32.SetThreadPriority(self._thread, 2):
                self.mode = "high"
        except (AttributeError, OSError, ValueError):
            self._kernel32 = None
            self._thread = None
            self._previous_priority = None

        try:
            self._avrt = ctypes.WinDLL("avrt", use_last_error=True)
            self._avrt.AvSetMmThreadCharacteristicsW.argtypes = (
                wintypes.LPCWSTR,
                ctypes.POINTER(wintypes.DWORD),
            )
            self._avrt.AvSetMmThreadCharacteristicsW.restype = wintypes.HANDLE
            self._avrt.AvSetMmThreadPriority.argtypes = (wintypes.HANDLE, ctypes.c_int)
            self._avrt.AvSetMmThreadPriority.restype = wintypes.BOOL
            self._avrt.AvRevertMmThreadCharacteristics.argtypes = (wintypes.HANDLE,)
            self._avrt.AvRevertMmThreadCharacteristics.restype = wintypes.BOOL
            for task_name in ("Pro Audio", "Games"):
                task_index = wintypes.DWORD(0)
                handle = self._avrt.AvSetMmThreadCharacteristicsW(
                    task_name, ctypes.byref(task_index)
                )
                if handle:
                    self._handle = handle
                    # AVRT_PRIORITY_HIGH = 1.
                    self._avrt.AvSetMmThreadPriority(handle, 1)
                    self.mode = f"MMCSS {task_name}"
                    break
        except (AttributeError, OSError, ValueError):
            self._avrt = None
            self._handle = None
        return self.mode

    def disable(self) -> None:
        if self._avrt is not None and self._handle:
            try:
                self._avrt.AvRevertMmThreadCharacteristics(self._handle)
            except (AttributeError, OSError, ValueError):
                pass
            self._handle = None
        if (
            self._kernel32 is not None
            and self._thread is not None
            and self._previous_priority is not None
        ):
            try:
                self._kernel32.SetThreadPriority(self._thread, self._previous_priority)
            except (AttributeError, OSError, ValueError):
                pass


def _set_high_resolution_timer(enabled: bool) -> bool:
    if os.name != "nt":
        return False
    try:
        winmm = ctypes.WinDLL("winmm", use_last_error=True)
        function = winmm.timeBeginPeriod if enabled else winmm.timeEndPeriod
        function.argtypes = (ctypes.c_uint,)
        function.restype = ctypes.c_uint
        return int(function(1)) == 0
    except (AttributeError, OSError):
        return False


class PlaybackScheduler:
    def __init__(
        self,
        backend: InputBackend,
        callbacks: SchedulerCallbacks | None = None,
        *,
        initial_bank: int = 0,
    ) -> None:
        self.backend = backend
        self.callbacks = callbacks or SchedulerCallbacks()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._running = threading.Event()
        self._lock = threading.RLock()
        self.last_metrics = SchedulerMetrics()
        self._seek_request_ms: float | None = None
        self._seek_delta_ms: float | None = None
        self._current_position_ms: float = 0.0
        self._current_bank: int = max(-1, min(1, int(initial_bank)))

    @property
    def running(self) -> bool:
        return self._running.is_set()

    @property
    def paused(self) -> bool:
        return self._pause.is_set()

    @property
    def current_bank(self) -> int:
        with self._lock:
            return self._current_bank

    @property
    def current_position_ms(self) -> float:
        with self._lock:
            return self._current_position_ms

    def seek_by(self, delta_ms: float) -> None:
        if not self.running:
            return
        with self._lock:
            if self._seek_delta_ms is not None:
                self._seek_delta_ms += delta_ms
            else:
                self._seek_delta_ms = delta_ms

    def seek_to(self, target_ms: float) -> None:
        if not self.running:
            return
        with self._lock:
            self._seek_request_ms = max(0.0, target_ms)
            self._seek_delta_ms = None

    def start(
        self,
        plan: PlaybackPlan,
        countdown_s: int,
        require_scum_focus: bool,
        pause_on_focus_loss: bool,
        repeat: bool = False,
        repeat_gap_ms: int = 500,
        octave_up_key: str = "LSHIFT",
        octave_down_key: str = "LCTRL",
        modifier_release_ms: float = 30.0,
        modifier_settle_ms: float = 45.0,
    ) -> None:
        if self.running:
            raise RuntimeError("Playback is already running.")
        if not plan.events:
            raise ValueError("Playback plan has no events.")
        self._stop.clear()
        self._pause.clear()
        self._running.set()
        with self._lock:
            # Preserve the last known physical SCUM bank across scheduler runs.
            # The worker safely synchronises it to base after SCUM focus is
            # confirmed; throwing it away here can make the next song start an
            # octave wrong after an emergency/aborted previous session.
            self._current_position_ms = 0.0
            self._seek_request_ms = None
            self._seek_delta_ms = None
        self.last_metrics = SchedulerMetrics()
        self._thread = threading.Thread(
            target=self._run,
            args=(
                plan,
                countdown_s,
                require_scum_focus,
                pause_on_focus_loss,
                bool(repeat),
                max(0, min(5000, int(repeat_gap_ms))),
                octave_up_key,
                octave_down_key,
                float(modifier_release_ms),
                float(modifier_settle_ms),
            ),
            daemon=True,
            name="MusicalScummePlayback",
        )
        self._thread.start()

    def _sync_octave_bank(
        self,
        target_bank: int,
        octave_up_key: str,
        octave_down_key: str,
        release_ms: float = 30.0,
        settle_ms: float = 45.0,
    ) -> bool:
        if self._stop.is_set() or self._pause.is_set() or emergency_stop_pressed():
            return False
        delta = target_bank - self._current_bank
        if delta == 0:
            return True
        tap_key = octave_up_key if delta > 0 else octave_down_key
        tap_count = abs(delta)
        self._release_all()
        if release_ms > 0:
            if not self._wait_interruptible(release_ms / 1000.0):
                return False
        for _ in range(tap_count):
            if self._stop.is_set() or self._pause.is_set() or emergency_stop_pressed():
                return False
            self.backend.send_batch((("down", tap_key),))
            if not self._wait_interruptible(0.018):
                return False
            self.backend.send_batch((("up", tap_key),))
            if settle_ms > 0:
                if not self._wait_interruptible(settle_ms / 1000.0):
                    return False
        with self._lock:
            self._current_bank = target_bank
        return True

    def _restore_base_bank_after_normal_stop(
        self,
        octave_up_key: str,
        octave_down_key: str,
        *,
        settle_ms: float,
    ) -> bool:
        """Best-effort base-bank return after the user presses ordinary Stop.

        This intentionally bypasses the scheduler's stop flag because the song
        has already been cancelled.  It is never called for F8/emergency stop,
        and the caller verifies that SCUM is still the foreground window before
        allowing any post-stop modifier input.
        """

        with self._lock:
            current_bank = self._current_bank
        if current_bank == 0:
            return True
        delta = -current_bank
        tap_key = octave_up_key if delta > 0 else octave_down_key
        try:
            for _ in range(abs(delta)):
                if emergency_stop_pressed():
                    return False
                self.backend.send_batch((("down", tap_key),))
                time.sleep(0.018)
                self.backend.send_batch((("up", tap_key),))
                if settle_ms > 0:
                    time.sleep(max(0.0, settle_ms) / 1000.0)
        except Exception:
            logger.exception("Could not return SCUM to the base octave after Stop")
            return False
        with self._lock:
            self._current_bank = 0
        self.last_metrics.stop_bank_restores += 1
        return True

    def _restore_sustains(
        self,
        plan: PlaybackPlan,
        target_ms: float,
        target_bank: int,
        *,
        source: str,
    ) -> int:
        keys = _sustaining_keys_at(plan, target_ms, target_bank)
        if not keys:
            return 0
        events = tuple(("down", key) for key in keys)
        if not self._send_batch_if_active(events):
            return 0
        if source == "seek":
            self.last_metrics.seek_reconstructed_notes += len(keys)
        elif source == "pause":
            self.last_metrics.pause_reconstructed_notes += len(keys)
        elif source == "focus":
            self.last_metrics.focus_reconstructed_notes += len(keys)
        return len(keys)

    def toggle_pause(self) -> bool:
        if not self.running:
            return False
        if self._pause.is_set():
            self._pause.clear()
            self.callbacks.status("Resuming…")
            return False
        self._pause.set()
        self._release_all()
        self.callbacks.status("Paused")
        return True

    def stop(self) -> None:
        self._stop.set()
        self._pause.clear()
        self._release_all()

    def wait(self, timeout: float | None = None) -> bool:
        """Wait briefly for the playback worker to finish its cleanup."""

        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        return not self.running

    def _release_all(self) -> None:
        with self._lock:
            self.backend.release_all()

    def _send_batch_if_active(self, events: tuple[tuple[str, str], ...]) -> bool:
        """Serialize backend access and reject dispatch after Pause or Stop wins the race."""

        with self._lock:
            if self._stop.is_set() or self._pause.is_set():
                return False
            self.backend.send_batch(events)
            return True

    def _wait_interruptible(self, seconds: float) -> bool:
        end = time.monotonic() + max(0.0, seconds)
        while time.monotonic() < end:
            if self._stop.is_set() or emergency_stop_pressed():
                self._stop.set()
                return False
            time.sleep(min(0.05, max(0.0, end - time.monotonic())))
        return True

    def _wait_for_scum(self) -> bool:
        warned = False
        while not self._stop.is_set():
            if emergency_stop_pressed():
                self._stop.set()
                return False
            try:
                focused = bool(foreground_window_info().is_scum)
            except Exception:
                logger.exception("Could not inspect foreground window while waiting for SCUM")
                focused = False
            if focused:
                return True
            if not warned:
                self.callbacks.status("Waiting for SCUM to be the foreground window… (F8 stops)")
                warned = True
            time.sleep(0.1)
        return False

    def _run(
        self,
        plan: PlaybackPlan,
        countdown_s: int,
        require_scum_focus: bool,
        pause_on_focus_loss: bool,
        repeat: bool,
        repeat_gap_ms: int,
        octave_up_key: str = "LSHIFT",
        octave_down_key: str = "LCTRL",
        modifier_release_ms: float = 30.0,
        modifier_settle_ms: float = 45.0,
    ) -> None:
        reason = "completed"
        timer_resolution_active = _set_high_resolution_timer(True)
        playback_priority = _WindowsPlaybackPriority()
        priority_mode = playback_priority.enable()
        gc_was_enabled = gc.isenabled()
        if gc_was_enabled:
            gc.collect()
            gc.disable()
        logger.debug("Playback timing mode: %s", priority_mode)
        try:
            # Infer octave keys from plan events if defined
            for event in plan.events:
                if "octave bank up" in event.reason or "restore base bank up" in event.reason:
                    octave_up_key = event.key
                elif "octave bank down" in event.reason or "restore base bank down" in event.reason:
                    octave_down_key = event.key

            for remaining in range(max(0, int(countdown_s)), 0, -1):
                self.callbacks.status(f"Starting in {remaining}…")
                if not self._wait_interruptible(1.0):
                    reason = "stopped"
                    return

            if require_scum_focus and not self._wait_for_scum():
                reason = "stopped"
                return

            # A previous session may have ended before its planned/base-bank
            # restore (F8, focus abort, exception). Carry the last known bank
            # forward and recover here, when it is safe to emit SCUM controls.
            if self.current_bank != 0:
                previous_bank = self.current_bank
                if not self._sync_octave_bank(
                    0,
                    octave_up_key,
                    octave_down_key,
                    modifier_release_ms,
                    modifier_settle_ms,
                ):
                    reason = "stopped"
                    return
                self.last_metrics.session_bank_resyncs += 1
                self.callbacks.status(
                    f"Recovered SCUM octave bank {previous_bank:+d} to base before playback"
                )

            schedule = _compile_event_batches(plan)
            total = len(plan.events)
            loop_number = 0
            while not self._stop.is_set():
                loop_number += 1
                if loop_number > 1 and self._current_bank != 0:
                    self._sync_octave_bank(
                        0,
                        octave_up_key,
                        octave_down_key,
                        modifier_release_ms,
                        modifier_settle_ms,
                    )
                loop_suffix = f" · loop {loop_number}" if repeat else ""
                self.callbacks.status(f"Playing{loop_suffix} — F8 is emergency stop")
                start_ns = time.perf_counter_ns()
                pause_accumulated_ns = 0
                batch_index = 0
                last_focus_check_ns = 0
                last_timecode_ns = 0
                scum_focused = True

                while batch_index < len(schedule) and not self._stop.is_set():
                    if emergency_stop_pressed():
                        reason = "emergency stop"
                        self._stop.set()
                        break

                    # Check for pending seek requests
                    seek_target: float | None = None
                    with self._lock:
                        if self._seek_request_ms is not None:
                            seek_target = self._seek_request_ms
                            self._seek_request_ms = None
                            self._seek_delta_ms = None
                        elif self._seek_delta_ms is not None:
                            current_ms = max(0.0, (time.perf_counter_ns() - start_ns - pause_accumulated_ns) / 1_000_000.0)
                            seek_target = max(0.0, current_ms + self._seek_delta_ms)
                            self._seek_delta_ms = None

                    if seek_target is not None:
                        seek_target_ms = min(plan.duration_ms, max(0.0, seek_target))
                        self._release_all()
                        target_offset_ns = int(seek_target_ms * 1_000_000)
                        batch_index = bisect_left(schedule, target_offset_ns, key=attrgetter("offset_ns"))
                        target_bank = schedule[batch_index - 1].bank_after if batch_index > 0 else 0
                        synced = self._sync_octave_bank(
                            target_bank,
                            octave_up_key,
                            octave_down_key,
                            modifier_release_ms,
                            modifier_settle_ms,
                        )
                        restored = (
                            self._restore_sustains(
                                plan, seek_target_ms, target_bank, source="seek"
                            )
                            if synced else 0
                        )
                        start_ns = time.perf_counter_ns() - pause_accumulated_ns - target_offset_ns
                        with self._lock:
                            self._current_position_ms = seek_target_ms
                        self.callbacks.timecode(seek_target_ms, plan.duration_ms)
                        cum_events = schedule[batch_index].cumulative_events if batch_index < len(schedule) else total
                        self.callbacks.progress(cum_events / total)
                        sustain_text = f" · restored {restored} held note(s)" if restored else ""
                        self.callbacks.status(
                            f"Seek to {seek_target_ms / 1000.0:.1f}s / {plan.duration_ms / 1000.0:.1f}s{sustain_text}"
                        )
                        continue

                    if self._pause.is_set():
                        pause_started = time.perf_counter_ns()
                        pause_position_ms = min(
                            plan.duration_ms,
                            max(
                                0.0,
                                (pause_started - start_ns - pause_accumulated_ns)
                                / 1_000_000.0,
                            ),
                        )
                        pending_sync_bank: int | None = self._current_bank
                        pending_seek_restore_ms: float | None = pause_position_ms
                        pending_restore_source = "pause"
                        with self._lock:
                            self._current_position_ms = pause_position_ms
                        while self._pause.is_set() and not self._stop.is_set():
                            if emergency_stop_pressed():
                                reason = "emergency stop"
                                self._stop.set()
                                break
                            pause_seek_target: float | None = None
                            with self._lock:
                                if self._seek_request_ms is not None:
                                    pause_seek_target = self._seek_request_ms
                                    self._seek_request_ms = None
                                    self._seek_delta_ms = None
                                elif self._seek_delta_ms is not None:
                                    pause_seek_target = max(0.0, self._current_position_ms + self._seek_delta_ms)
                                    self._seek_delta_ms = None
                            if pause_seek_target is not None:
                                seek_target_ms = min(plan.duration_ms, max(0.0, pause_seek_target))
                                target_offset_ns = int(seek_target_ms * 1_000_000)
                                batch_index = bisect_left(schedule, target_offset_ns, key=attrgetter("offset_ns"))
                                pending_sync_bank = schedule[batch_index - 1].bank_after if batch_index > 0 else 0
                                pending_seek_restore_ms = seek_target_ms
                                pending_restore_source = "seek"
                                start_ns = pause_started - pause_accumulated_ns - target_offset_ns
                                with self._lock:
                                    self._current_position_ms = seek_target_ms
                                self.callbacks.timecode(seek_target_ms, plan.duration_ms)
                                cum_events = schedule[batch_index].cumulative_events if batch_index < len(schedule) else total
                                self.callbacks.progress(cum_events / total)
                                self.callbacks.status(f"Paused at {seek_target_ms / 1000.0:.1f}s / {plan.duration_ms / 1000.0:.1f}s")
                            time.sleep(0.02)

                        if pending_sync_bank is not None and not self._stop.is_set():
                            if require_scum_focus and not foreground_window_info().is_scum:
                                self._wait_for_scum()
                            synced = self._sync_octave_bank(
                                pending_sync_bank,
                                octave_up_key,
                                octave_down_key,
                                modifier_release_ms,
                                modifier_settle_ms,
                            )
                            if synced and pending_seek_restore_ms is not None:
                                self._restore_sustains(
                                    plan,
                                    pending_seek_restore_ms,
                                    pending_sync_bank,
                                    source=pending_restore_source,
                                )
                        pause_accumulated_ns += time.perf_counter_ns() - pause_started
                        continue

                    now_focus_ns = time.perf_counter_ns()
                    if require_scum_focus and now_focus_ns - last_focus_check_ns >= 50_000_000:
                        try:
                            is_scum = bool(foreground_window_info().is_scum)
                        except Exception:
                            logger.exception("Could not inspect foreground window during playback")
                            is_scum = False
                        # Never deliberately emit game-control keys into a
                        # different foreground application.  The compact player
                        # is non-activating, so a genuine non-SCUM sample is a
                        # stronger safety signal than the old multi-sample
                        # debounce was worth.
                        scum_focused = bool(is_scum)
                        last_focus_check_ns = now_focus_ns
                    if require_scum_focus and not scum_focused:
                        lost_at = time.perf_counter_ns()
                        lost_position_ms = min(
                            plan.duration_ms,
                            max(
                                0.0,
                                (lost_at - start_ns - pause_accumulated_ns)
                                / 1_000_000.0,
                            ),
                        )
                        self._release_all()
                        if not pause_on_focus_loss:
                            reason = "SCUM lost focus"
                            self._stop.set()
                            break
                        self.last_metrics.focus_pauses += 1
                        self.callbacks.status("SCUM lost focus — playback safely paused")
                        if not self._wait_for_scum():
                            reason = "stopped"
                            break
                        restored = self._restore_sustains(
                            plan,
                            lost_position_ms,
                            self._current_bank,
                            source="focus",
                        )
                        pause_accumulated_ns += time.perf_counter_ns() - lost_at
                        last_focus_check_ns = time.perf_counter_ns()
                        scum_focused = True
                        sustain_text = (
                            f" · restored {restored} held note(s)" if restored else ""
                        )
                        self.callbacks.status(f"SCUM focused — resuming{sustain_text}")


                    batch = schedule[batch_index]
                    target_ns = start_ns + pause_accumulated_ns + batch.offset_ns
                    now_ns = time.perf_counter_ns()
                    remaining_ns = target_ns - now_ns
                    if remaining_ns > 2_000_000:
                        time.sleep(min(0.01, remaining_ns / 1_000_000_000 * 0.75))
                        continue
                    if remaining_ns > 0:
                        while time.perf_counter_ns() < target_ns:
                            if self._stop.is_set() or self._pause.is_set() or emergency_stop_pressed():
                                break

                    dispatch_ns = time.perf_counter_ns()
                    lateness_ms = max(0.0, (dispatch_ns - target_ns) / 1_000_000)

                    # If an unexpected system / OS stall occurred (> 400ms behind target),
                    # absorb the stall duration into pause_accumulated_ns so subsequent
                    # batches resume smoothly from the stall point rather than rushing
                    # forward and skipping seconds of music.
                    if lateness_ms > 400.0:
                        stall_absorbed_ns = int((lateness_ms - 10.0) * 1_000_000)
                        pause_accumulated_ns += stall_absorbed_ns
                        self.last_metrics.stalls_recovered += 1
                        self.last_metrics.stall_recovered_ms += stall_absorbed_ns / 1_000_000.0
                        target_ns += stall_absorbed_ns
                        lateness_ms = max(0.0, (dispatch_ns - target_ns) / 1_000_000)
                        logger.debug(
                            "Recovered from %.1f ms playback thread stall by sliding timeline",
                            stall_absorbed_ns / 1_000_000.0,
                        )

                    send_started_ns = time.perf_counter_ns()
                    if not self._send_batch_if_active(batch.events):
                        continue
                    dispatch_ms = (time.perf_counter_ns() - send_started_ns) / 1_000_000.0
                    self.last_metrics.record_batch(len(batch.events), lateness_ms, dispatch_ms)
                    with self._lock:
                        self._current_bank = batch.bank_after
                    batch_index += 1
                    elapsed_ms = batch.offset_ns / 1_000_000.0
                    with self._lock:
                        self._current_position_ms = elapsed_ms
                    now_perf_ns = time.perf_counter_ns()
                    if (
                        batch_index >= len(schedule)
                        or now_perf_ns - last_timecode_ns >= 33_000_000
                    ):
                        self.callbacks.timecode(elapsed_ms, plan.duration_ms)
                        last_timecode_ns = now_perf_ns
                    if batch.cumulative_events == total or batch.cumulative_events % 12 == 0:
                        self.callbacks.progress(batch.cumulative_events / total)

                if batch_index < len(schedule) or self._stop.is_set():
                    break
                self.last_metrics.loops_completed += 1
                self._release_all()
                if not repeat:
                    break
                self.callbacks.progress(0.0)
                self.callbacks.status(
                    f"Loop {loop_number} complete — restarting in {repeat_gap_ms / 1000.0:.1f}s"
                )
                if not self._wait_interruptible(repeat_gap_ms / 1000.0):
                    reason = "stopped"
                    break

            if self._stop.is_set() and reason == "completed":
                reason = "stopped"
            self.callbacks.progress(1.0 if reason == "completed" else 0.0)
        except Exception as exc:
            logger.exception("Playback failed")
            reason = f"error: {exc}"
            self.callbacks.status(f"Playback failed: {exc}")
        finally:
            self._release_all()
            should_restore_bank = (
                reason == "stopped"
                and bool(int(plan.diagnostics.get("restore_base_bank", 0)))
                and self.current_bank != 0
            )
            if should_restore_bank:
                # Even experts who disable continuous focus protection should
                # not receive an unexpected Ctrl/Shift tap in another app after
                # pressing Stop. Dry Run is intrinsically safe; real output
                # requires SCUM to be foreground at the moment of restoration.
                safe_to_send = self.backend.name == "Dry run"
                if not safe_to_send:
                    try:
                        safe_to_send = foreground_window_info(cache_ttl_s=0.0).is_scum
                    except Exception:
                        logger.exception("Could not verify SCUM focus for post-Stop bank restore")
                        safe_to_send = False
                if safe_to_send:
                    restored = self._restore_base_bank_after_normal_stop(
                        octave_up_key,
                        octave_down_key,
                        settle_ms=modifier_settle_ms,
                    )
                    if restored:
                        self.callbacks.status("Stopped · SCUM octave returned to base")
                else:
                    self.last_metrics.stop_bank_restore_skipped += 1
                    logger.warning(
                        "Normal Stop ended in SCUM octave bank %+d while SCUM was not focused; "
                        "post-stop bank restore was skipped for safety",
                        self.current_bank,
                    )
            playback_priority.disable()
            if gc_was_enabled:
                gc.enable()
            if timer_resolution_active:
                _set_high_resolution_timer(False)
            self._running.clear()
            self._pause.clear()
            logger.info(
                "Playback %s: %s; %d events/%d batches, avg/max lateness %.2f/%.2f ms, "
                "avg/max dispatch %.3f/%.3f ms, dispatches >2ms=%d, "
                ">5ms=%d, >20ms=%d, stalls=%d (%.1f ms), focus pauses=%d, "
                "restored seek/pause/focus=%d/%d/%d, stop bank restores=%d, "
                "stop bank restore skipped=%d, startup bank resyncs=%d, loops=%d",
                reason,
                self.last_metrics.timing_summary,
                self.last_metrics.events_sent,
                self.last_metrics.batches_sent,
                self.last_metrics.average_lateness_ms,
                self.last_metrics.max_lateness_ms,
                self.last_metrics.average_dispatch_ms,
                self.last_metrics.max_dispatch_ms,
                self.last_metrics.dispatches_over_2ms,
                self.last_metrics.batches_over_5ms,
                self.last_metrics.batches_over_20ms,
                self.last_metrics.stalls_recovered,
                self.last_metrics.stall_recovered_ms,
                self.last_metrics.focus_pauses,
                self.last_metrics.seek_reconstructed_notes,
                self.last_metrics.pause_reconstructed_notes,
                self.last_metrics.focus_reconstructed_notes,
                self.last_metrics.stop_bank_restores,
                self.last_metrics.stop_bank_restore_skipped,
                self.last_metrics.session_bank_resyncs,
                self.last_metrics.loops_completed,
            )
            if reason == "completed":
                self.callbacks.status(
                    f"Finished · {self.last_metrics.batches_sent:,} batches · "
                    f"max lateness {self.last_metrics.max_lateness_ms:.2f} ms"
                )
            elif reason not in {"error"}:
                self.callbacks.status(reason.capitalize())
            self.callbacks.finished(reason)
