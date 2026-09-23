import threading
import time

from musical_scumme.input_backend import DryRunBackend
from musical_scumme.model import KeyEvent, PlaybackPlan
from musical_scumme.scheduler import PlaybackScheduler


def plan(events: list[KeyEvent]) -> PlaybackPlan:
    return PlaybackPlan(events, [], 0, 0, 0, max(event.at_ms for event in events))


def wait_until_stopped(scheduler: PlaybackScheduler, timeout_s: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_s
    while scheduler.running and time.monotonic() < deadline:
        time.sleep(0.005)
    assert not scheduler.running


def test_scheduler_batches_only_events_with_the_same_timestamp():
    backend = DryRunBackend()
    scheduler = PlaybackScheduler(backend)
    scheduler.start(
        plan(
            [
                KeyEvent(0, "down", "Y"),
                KeyEvent(0, "down", "I"),
                KeyEvent(20, "up", "Y"),
                KeyEvent(20, "up", "I"),
            ]
        ),
        countdown_s=0,
        require_scum_focus=False,
        pause_on_focus_loss=True,
    )

    wait_until_stopped(scheduler)

    assert backend.history == [
        ("down", "Y"),
        ("down", "I"),
        ("up", "Y"),
        ("up", "I"),
    ]
    assert scheduler.last_metrics.events_sent == 4
    assert scheduler.last_metrics.batches_sent == 2
    assert scheduler.last_metrics.loops_completed == 1
    assert scheduler.last_metrics.average_lateness_ms >= 0
    assert scheduler.last_metrics.max_lateness_ms >= 0
    assert scheduler.last_metrics.late_events >= 0
    assert backend.pressed == set()


def test_scheduler_can_repeat_until_the_user_stops_it():
    backend = DryRunBackend()
    scheduler = PlaybackScheduler(backend)
    scheduler.start(
        plan([KeyEvent(0, "down", "Y"), KeyEvent(2, "up", "Y")]),
        countdown_s=0,
        require_scum_focus=False,
        pause_on_focus_loss=True,
        repeat=True,
        repeat_gap_ms=1,
    )
    deadline = time.monotonic() + 2.0
    while scheduler.last_metrics.loops_completed < 2 and time.monotonic() < deadline:
        time.sleep(0.005)
    scheduler.stop()
    wait_until_stopped(scheduler)

    assert scheduler.last_metrics.loops_completed >= 2
    assert scheduler.last_metrics.events_sent >= 4
    assert backend.pressed == set()


def test_pause_cannot_leave_a_key_down_dispatched_after_cleanup():
    class BlockingBackend(DryRunBackend):
        def __init__(self) -> None:
            super().__init__()
            self.dispatch_entered = threading.Event()
            self.allow_dispatch = threading.Event()

        def send_batch(self, events):
            self.dispatch_entered.set()
            assert self.allow_dispatch.wait(2.0)
            super().send_batch(events)

    backend = BlockingBackend()
    scheduler = PlaybackScheduler(backend)
    scheduler.start(
        plan([KeyEvent(0, "down", "Y"), KeyEvent(1000, "up", "Y")]),
        countdown_s=0,
        require_scum_focus=False,
        pause_on_focus_loss=True,
    )
    assert backend.dispatch_entered.wait(2.0)

    pause_thread = threading.Thread(target=scheduler.toggle_pause)
    pause_thread.start()
    deadline = time.monotonic() + 2.0
    while not scheduler.paused and time.monotonic() < deadline:
        time.sleep(0.005)
    assert scheduler.paused

    backend.allow_dispatch.set()
    pause_thread.join(2.0)
    assert not pause_thread.is_alive()
    scheduler.stop()
    wait_until_stopped(scheduler)
    assert backend.pressed == set()


def test_scheduler_emits_timecode_callbacks():
    from musical_scumme.scheduler import SchedulerCallbacks

    recorded_timecodes = []
    callbacks = SchedulerCallbacks(
        timecode=lambda elapsed_ms, total_ms: recorded_timecodes.append((elapsed_ms, total_ms))
    )
    backend = DryRunBackend()
    scheduler = PlaybackScheduler(backend, callbacks)
    scheduler.start(
        plan([KeyEvent(0, "down", "Y"), KeyEvent(10, "up", "Y")]),
        countdown_s=0,
        require_scum_focus=False,
        pause_on_focus_loss=True,
    )
    wait_until_stopped(scheduler)
    assert len(recorded_timecodes) >= 2
    assert recorded_timecodes[0][1] == 10.0


def test_scheduler_seek_forward_skips_intermediate_events():
    backend = DryRunBackend()
    scheduler = PlaybackScheduler(backend)
    # Plan with events at 0ms, 100ms, 200ms, 300ms, 400ms, 500ms
    test_plan = plan(
        [
            KeyEvent(0, "down", "Y"),
            KeyEvent(50, "up", "Y"),
            KeyEvent(100, "down", "I"),
            KeyEvent(150, "up", "I"),
            KeyEvent(500, "down", "O"),
            KeyEvent(550, "up", "O"),
        ]
    )
    scheduler.start(
        test_plan,
        countdown_s=0,
        require_scum_focus=False,
        pause_on_focus_loss=True,
    )
    # Seek forward to 450ms immediately
    scheduler.seek_by(450.0)
    wait_until_stopped(scheduler)

    # Should have executed the event at 500ms
    dispatched_keys = [key for action, key in backend.history if action == "down"]
    assert "O" in dispatched_keys
    assert backend.pressed == set()


def test_scheduler_seek_while_paused():
    from musical_scumme.scheduler import SchedulerCallbacks

    recorded_timecodes = []
    callbacks = SchedulerCallbacks(
        timecode=lambda elapsed_ms, total_ms: recorded_timecodes.append((elapsed_ms, total_ms))
    )
    backend = DryRunBackend()
    scheduler = PlaybackScheduler(backend, callbacks)
    test_plan = plan(
        [
            KeyEvent(0, "down", "Y"),
            KeyEvent(50, "up", "Y"),
            KeyEvent(1000, "down", "I"),
            KeyEvent(1050, "up", "I"),
        ]
    )
    scheduler.start(
        test_plan,
        countdown_s=0,
        require_scum_focus=False,
        pause_on_focus_loss=True,
    )
    time.sleep(0.02)
    scheduler.toggle_pause()
    time.sleep(0.05)
    assert scheduler.paused

    scheduler.seek_to(600.0)
    time.sleep(0.05)
    assert scheduler.current_position_ms == 600.0

    scheduler.stop()
    wait_until_stopped(scheduler)


def test_scheduler_batches_track_bank_state():
    from musical_scumme.scheduler import _compile_event_batches

    test_plan = plan(
        [
            KeyEvent(0, "down", "Y", "note start"),
            KeyEvent(50, "up", "Y", "note end"),
            KeyEvent(100, "down", "LSHIFT", "octave bank up tap"),
            KeyEvent(118, "up", "LSHIFT", "octave bank up tap release"),
            KeyEvent(200, "down", "Y", "note start"),
            KeyEvent(250, "up", "Y", "note end"),
            KeyEvent(300, "down", "LCTRL", "octave bank down tap"),
            KeyEvent(318, "up", "LCTRL", "octave bank down tap release"),
        ]
    )
    batches = _compile_event_batches(test_plan)
    # Check bank_after values
    assert batches[0].bank_after == 0  # note down
    assert batches[1].bank_after == 0  # note up
    assert batches[2].bank_after == 1  # shift down
    assert batches[3].bank_after == 1  # shift up
    assert batches[4].bank_after == 1  # note down
    assert batches[5].bank_after == 1  # note up
    assert batches[6].bank_after == 0  # ctrl down
    assert batches[7].bank_after == 0  # ctrl up


def test_scheduler_seek_synchronizes_octave_bank():
    backend = DryRunBackend()
    scheduler = PlaybackScheduler(backend)
    test_plan = plan(
        [
            KeyEvent(0, "down", "Y", "note start"),
            KeyEvent(50, "up", "Y", "note end"),
            KeyEvent(100, "down", "LSHIFT", "octave bank up tap"),
            KeyEvent(118, "up", "LSHIFT", "octave bank up tap release"),
            KeyEvent(500, "down", "I", "note start"),
            KeyEvent(550, "up", "I", "note end"),
        ]
    )
    scheduler.start(
        test_plan,
        countdown_s=0,
        require_scum_focus=False,
        pause_on_focus_loss=True,
        modifier_release_ms=5.0,
        modifier_settle_ms=5.0,
    )
    # Seek directly past the bank tap to 300ms
    scheduler.seek_to(300.0)
    wait_until_stopped(scheduler)

    # Verify that LSHIFT was tapped to synchronize the bank to +1
    history_events = backend.history
    assert ("down", "LSHIFT") in history_events
    assert ("up", "LSHIFT") in history_events
    assert ("down", "I") in history_events
    assert scheduler.current_bank == 1


def test_scheduler_seek_while_paused_defers_octave_bank_sync():
    backend = DryRunBackend()
    scheduler = PlaybackScheduler(backend)
    test_plan = plan(
        [
            KeyEvent(0, "down", "Y", "note start"),
            KeyEvent(50, "up", "Y", "note end"),
            KeyEvent(200, "down", "LSHIFT", "octave bank up tap"),
            KeyEvent(218, "up", "LSHIFT", "octave bank up tap release"),
            KeyEvent(1000, "down", "I", "note start"),
            KeyEvent(1050, "up", "I", "note end"),
        ]
    )
    scheduler.start(
        test_plan,
        countdown_s=0,
        require_scum_focus=False,
        pause_on_focus_loss=True,
        modifier_release_ms=5.0,
        modifier_settle_ms=5.0,
    )
    time.sleep(0.02)
    scheduler.toggle_pause()
    time.sleep(0.05)
    assert scheduler.paused

    # Clear history while paused to isolate seek actions
    backend.history.clear()

    # Seek into bank +1 region
    scheduler.seek_to(500.0)
    time.sleep(0.05)
    # While paused, no sync keystrokes should be sent
    assert ("down", "LSHIFT") not in backend.history

    # Now unpause
    scheduler.toggle_pause()
    wait_until_stopped(scheduler)

    # Upon unpause, bank sync should have executed before note 'I'
    assert ("down", "LSHIFT") in backend.history
    assert ("down", "I") in backend.history


def test_scheduler_recovers_from_system_stall_without_skipping():
    """Verify that an OS/thread stall (>400ms) absorbs the lag into pause_accumulated_ns

    and plays subsequent notes normally instead of dumping/skipping them.
    """
    class StallingBackend(DryRunBackend):
        def __init__(self) -> None:
            super().__init__()
            self.first_batch_sent = False

        def send_batch(self, events):
            super().send_batch(events)
            if not self.first_batch_sent:
                self.first_batch_sent = True
                # Simulate a 450ms OS stall/latency freeze
                time.sleep(0.45)

    backend = StallingBackend()
    scheduler = PlaybackScheduler(backend)
    test_plan = plan(
        [
            KeyEvent(0, "down", "Y"),
            KeyEvent(20, "up", "Y"),
            KeyEvent(200, "down", "I"),
            KeyEvent(220, "up", "I"),
        ]
    )
    scheduler.start(
        test_plan,
        countdown_s=0,
        require_scum_focus=False,
        pause_on_focus_loss=True,
    )
    wait_until_stopped(scheduler, timeout_s=3.0)

    # Both notes must have been dispatched in order despite the 450ms thread stall
    assert backend.history == [
        ("down", "Y"),
        ("up", "Y"),
        ("down", "I"),
        ("up", "I"),
    ]
    assert scheduler.last_metrics.batches_sent == 4




