import pytest

from musical_scumme.config import CURRENT_SCUM_PROFILE, AppSettings
from musical_scumme.model import MidiNote
from musical_scumme.planner import _lead_fidelity_sequence, build_playback_plan


def note(pitch, start=0, track=0, velocity=100):
    return MidiNote(track, 0, pitch, velocity, start, start + 180)


def test_traced_lead_beats_louder_high_backing():
    lead = note(55, velocity=60)
    backing = [note(pitch, track=1, velocity=127) for pitch in (76, 79, 83)]
    assert _lead_fidelity_sequence([[lead, *backing]], AppSettings(), {lead}) == {0: -1}


@pytest.mark.parametrize("transpose", [-12, 0, 12])
def test_register_crossings_preserve_playable_lead(transpose):
    notes = [note(pitch - transpose, index * 500) for index, pitch in enumerate((55, 67, 79, 67))]
    sequence = _lead_fidelity_sequence([[n] for n in notes], AppSettings(transpose=transpose), set(notes))
    assert list(sequence.values()) == [-1, 0, 1, 0]


def test_empty_and_fallback_are_deterministic_and_source_is_unchanged():
    settings = AppSettings()
    assert _lead_fidelity_sequence([], settings, set()) == {}
    notes = [note(55, velocity=120), note(79, track=1, velocity=40)]
    original = tuple(notes)
    assert _lead_fidelity_sequence([notes], settings, set()) == {0: -1}
    assert _lead_fidelity_sequence([list(reversed(notes))], settings, set()) == {0: -1}
    assert tuple(notes) == original


def test_config_retains_opt_in_identity():
    settings = AppSettings(mapping_mode="lead_fidelity", performance_preset="custom")
    settings.normalize()
    assert settings.mapping_mode == "lead_fidelity"


def test_offbeat_backing_does_not_displace_a_held_lead():
    lead = MidiNote(0, 0, 55, 60, 0, 900)
    backing = note(79, start=400, track=1, velocity=127)
    assert _lead_fidelity_sequence([[lead], [backing]], AppSettings(), {lead}) == {0: -1, 1: -1}


def test_backing_can_change_bank_after_lead_release():
    lead = note(55)
    backing = note(79, start=700, track=1)
    assert _lead_fidelity_sequence([[lead], [backing]], AppSettings(), {lead}) == {0: -1, 1: 1}


def test_complete_plan_balances_keys_and_keeps_bank_taps_separate():
    settings = AppSettings(
        mapping_mode="lead_fidelity", performance_preset="custom", arrangement_mode="melody",
        chord_spread_ms=0, min_source_note_ms=0, min_retrigger_ms=0,
    )
    notes = [note(pitch, index * 500) for index, pitch in enumerate((55, 67, 79, 67))]
    plan = build_playback_plan(notes, settings, CURRENT_SCUM_PROFILE)
    assert plan == build_playback_plan(notes, settings, CURRENT_SCUM_PROFILE)
    assert plan.retained_notes == 4
    assert [n.mapped_pitch for n in plan.planned_notes] == [55, 67, 79, 67]
    held = set()
    for event in plan.events:
        if event.action == "down":
            if event.key in {"LCTRL", "LSHIFT"}:
                assert not held
            else:
                assert not held.intersection({"LCTRL", "LSHIFT"})
            assert event.key not in held
            held.add(event.key)
        else:
            assert event.key in held
            held.remove(event.key)
    assert not held


def test_switch_budget_remains_authoritative():
    settings = AppSettings(
        mapping_mode="lead_fidelity", performance_preset="custom", arrangement_mode="melody",
        bank_switch_budget_per_second=1, min_source_note_ms=0, min_retrigger_ms=0,
    )
    notes = [note(55 if i % 2 == 0 else 79, i * 150) for i in range(12)]
    plan = build_playback_plan(notes, settings, CURRENT_SCUM_PROFILE)
    assert any("budget" in warning for warning in plan.warnings)
    assert all(60 <= n.base_pitch <= 72 for n in plan.planned_notes)
