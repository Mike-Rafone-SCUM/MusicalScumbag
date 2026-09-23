"""Complete-output regression snapshots captured before resource optimisation."""
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


def test_optimised_plans_preserve_complete_musical_and_timing_output():
    snapshots = json.loads((Path(__file__).parent / "fixtures/resource_plan_digests.json").read_text())
    notes = resource_fixture()
    for key, expected in snapshots.items():
        arrangement, mode, transpose = key.split("/")
        plan = build_playback_plan(
            notes, AppSettings(mapping_mode=mode, arrangement_mode=arrangement, transpose=int(transpose)),
            CURRENT_SCUM_PROFILE,
        )
        payload = asdict(plan)
        # Newly exposed enhanced-match audit fields are additive metadata;
        # every prior diagnostic, note, event, warning and timestamp must match.
        for added in ("automatic_pitch_shift_semitones", "pitch_match_exact_notes", "pitch_match_octave_folded_notes"):
            payload["diagnostics"].pop(added, None)
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        assert digest == expected, key
