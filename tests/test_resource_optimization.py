"""Complete-output baseline audited on 2026-09-23; see docs/TEST_AUDIT.md."""
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from musical_scumme.config import CURRENT_SCUM_PROFILE, AppSettings
from musical_scumme.model import MidiNote
from musical_scumme.planner import build_playback_plan


def test_constant_time_octave_fold_matches_repeated_octaves_at_every_boundary():
    from musical_scumme.planner import _fold_to_window

    for low, high in ((48, 60), (60, 72), (72, 84), (48, 84)):
        for source_pitch in range(-120, 248):
            expected = source_pitch
            while expected < low:
                expected += 12
            while expected > high:
                expected -= 12
            assert _fold_to_window(source_pitch, low, high) == expected


def resource_fixture():
    return [
        MidiNote(j, j, 42 + i % 12 + j * 12, 70 + j * 10,
                 i * 240. + (j * 15 if i % 7 else 0), i * 240. + 400.)
        for i in range(130) for j in range(3)
    ]


def capture_plan(key):
    arrangement, mode, transpose = key.split("/")
    return build_playback_plan(
        resource_fixture(),
        AppSettings(mapping_mode=mode, arrangement_mode=arrangement, transpose=int(transpose)),
        CURRENT_SCUM_PROFILE,
    )


def plan_digest(plan):
    return hashlib.sha256(json.dumps(asdict(plan), sort_keys=True).encode()).hexdigest()


def assert_plan_invariants(plan):
    assert plan.retained_notes == len(plan.planned_notes) > 0
    assert [event.at_ms for event in plan.events] == sorted(event.at_ms for event in plan.events)
    source_pitches = {note.pitch for note in resource_fixture()}
    for note in plan.planned_notes:
        assert note.source_pitch in source_pitches
        assert note.start_ms < note.end_ms
        assert note.end_ms - note.start_ms <= 2000.001
        assert note.mapped_pitch == note.base_pitch + 12 * note.modifier
    held = set()
    bank_keys = {CURRENT_SCUM_PROFILE.octave_up, CURRENT_SCUM_PROFILE.octave_down}
    for event in plan.events:
        if event.action == "down":
            if event.key in bank_keys:
                assert not held
            else:
                assert not held & bank_keys
            held.add(event.key)
        else:
            held.discard(event.key)
    assert not held


def test_optimised_plans_preserve_complete_musical_and_timing_output():
    snapshots = json.loads((Path(__file__).parent / "fixtures/resource_plan_digests.json").read_text())
    for key, expected in snapshots.items():
        plan = capture_plan(key)
        assert_plan_invariants(plan)
        digest = plan_digest(plan)
        assert digest == expected, key
