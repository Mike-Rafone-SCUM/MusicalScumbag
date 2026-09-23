import csv

import pytest

from musical_scumme.config import CURRENT_SCUM_PROFILE, AppSettings
from musical_scumme.model import MidiNote
from musical_scumme.planner import build_playback_plan, export_score_csv, recommend_optimal_transpose


def note(pitch: int, start: float = 0, end: float = 300, velocity: int = 100):
    return MidiNote(0, 0, pitch, velocity, start, end)


def test_current_scum_default_mapping():
    settings = AppSettings(mapping_mode="strict_auto", hold_ratio=1.0, chord_spread_ms=0)
    plan = build_playback_plan([note(60), note(61), note(72)], settings, CURRENT_SCUM_PROFILE)
    downs = [(event.key, event.action) for event in plan.events if event.action == "down"]
    assert ("Y", "down") in downs
    assert ("I", "down") in downs
    assert ("E", "down") in downs


def test_fold_mode_keeps_out_of_range_notes():
    settings = AppSettings(mapping_mode="fold_smart", max_polyphony=3, chord_spread_ms=0)
    plan = build_playback_plan([note(36), note(67), note(89)], settings, CURRENT_SCUM_PROFILE)
    assert plan.retained_notes == 3
    assert all(60 <= item.base_pitch <= 72 for item in plan.planned_notes)
    assert all(item.modifier == 0 for item in plan.planned_notes)


def test_fold_mode_unison_c4_not_spread_to_c5():
    settings = AppSettings(mapping_mode="fold_smart", chord_spread_ms=0, arrangement_mode="faithful")
    n1 = MidiNote(0, 0, 60, 100, 0, 300)
    n2 = MidiNote(1, 0, 60, 100, 0, 300)
    plan = build_playback_plan([n1, n2], settings, CURRENT_SCUM_PROFILE)
    assert all(item.mapped_pitch == 60 for item in plan.planned_notes)


def test_fold_mode_distinct_c_octaves_spread_to_boundary():
    settings = AppSettings(mapping_mode="fold_smart", chord_spread_ms=0, arrangement_mode="faithful")
    n1 = MidiNote(0, 0, 48, 100, 0, 300)
    n2 = MidiNote(1, 0, 60, 100, 0, 300)
    plan = build_playback_plan([n1, n2], settings, CURRENT_SCUM_PROFILE)
    assert {item.mapped_pitch for item in plan.planned_notes} == {60, 72}


def test_recommend_optimal_transpose():
    settings = AppSettings()
    # Empty notes
    shift, metrics = recommend_optimal_transpose([], settings)
    assert shift == 0
    assert metrics["in_bank_pct"] == 0.0

    # Notes already natively in C4-C5 (60, 64, 67)
    notes_c4 = [note(60), note(64), note(67)]
    shift, metrics = recommend_optimal_transpose(notes_c4, settings)
    assert shift == 0
    assert metrics["in_bank_pct"] == 100.0

    # Notes shifted down by 3 semitones (57, 61, 64) -> recommended shift should be +3
    notes_a3 = [note(57), note(61), note(64)]
    shift, metrics = recommend_optimal_transpose(notes_a3, settings)
    assert shift == 3
    assert metrics["in_bank_pct"] == 100.0


def test_scum_score_export_preserves_chord_membership_and_note_mapping(tmp_path):
    settings = AppSettings(
        arrangement_mode="intelligent",
        mapping_mode="fold_smart",
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_notes_per_second=60,
        max_polyphony=3,
        chord_spread_ms=12,
    )
    plan = build_playback_plan(
        [note(60), note(64), note(67)],
        settings,
        CURRENT_SCUM_PROFILE,
    )
    destination = tmp_path / "song_scum_score.csv"

    export_score_csv(plan, destination)

    with destination.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert {row["score_group"] for row in rows} == {"1"}
    assert {row["chord_size"] for row in rows} == {"3"}
    assert [row["voice"] for row in rows] == ["1", "2", "3"]
    assert {row["source_note"] for row in rows} == {"C4", "E4", "G4"}
    assert {row["scum_key"] for row in rows} == {"Y", "G", "K"}
    assert all(row["mapping_explanation"] for row in rows)
    assert not destination.with_suffix(".csv.tmp").exists()


def test_smart_octave_switch_releases_notes_before_standalone_bank_taps():
    settings = AppSettings(
        mapping_mode="melody3_contour",
        hold_ratio=1.0,
        min_hold_ms=10,
        max_hold_ms=1000,
        onset_group_ms=1,
        chord_spread_ms=0,
    )
    plan = build_playback_plan(
        [note(48, 0, 500), note(76, 100, 400)],
        settings,
        CURRENT_SCUM_PROFILE,
    )
    first_high_note = next(item for item in plan.planned_notes if item.modifier == 1)
    shift_events = [
        event for event in plan.events if event.key == "LSHIFT" and event.at_ms < first_high_note.start_ms
    ]
    assert [event.action for event in shift_events[-4:]] == ["down", "up", "down", "up"]
    assert all(
        up.at_ms - down.at_ms == 18.0
        for down, up in zip(shift_events[-4::2], shift_events[-3::2], strict=True)
    )
    final_shift_up = shift_events[-1]
    release_at = shift_events[-4].at_ms - settings.modifier_release_ms
    assert first_high_note.start_ms - final_shift_up.at_ms == settings.modifier_settle_ms
    assert any(
        event.action == "up"
        and event.key not in {"LCTRL", "LSHIFT"}
        and abs(event.at_ms - release_at) < 0.001
        for event in plan.events
    )


def test_polyphony_limit_prefers_melody_and_bass():
    settings = AppSettings(mapping_mode="fold_smart", max_polyphony=2, chord_spread_ms=0)
    plan = build_playback_plan(
        [note(60, velocity=30), note(64, velocity=120), note(67, velocity=50), note(72, velocity=80)],
        settings,
        CURRENT_SCUM_PROFILE,
    )
    pitches = {item.source_pitch for item in plan.planned_notes}
    assert 72 in pitches
    assert 60 in pitches
    assert plan.retained_notes == 2


def test_smart_register_planner_avoids_rapid_modifier_thrashing():
    settings = AppSettings(
        mapping_mode="smart3_harmonic",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        max_polyphony=1,
        chord_spread_ms=0,
    )
    notes = [
        note(48, start=0, end=120),
        note(84, start=60, end=180),
        note(48, start=120, end=240),
    ]
    plan = build_playback_plan(notes, settings, CURRENT_SCUM_PROFILE)
    modifiers = [item.modifier for item in plan.planned_notes]
    switches = sum(left != right for left, right in zip(modifiers, modifiers[1:], strict=False))
    assert switches <= 1


def test_melody_register_planner_preserves_guitar_arpeggio_contour():
    settings = AppSettings(
        mapping_mode="melody3_contour",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_polyphony=1,
        onset_group_ms=1,
        chord_spread_ms=0,
        key_retrigger_gap_ms=0,
    )
    pitches = [45, 52, 57, 60, 64, 60, 55, 48]
    source = [note(pitch, start=index * 260, end=index * 260 + 180) for index, pitch in enumerate(pitches)]

    plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)

    assert [item.mapped_pitch for item in plan.planned_notes] == [57, 52, 57, 60, 64, 60, 55, 48]
    assert [item.modifier for item in plan.planned_notes] == [-1, -1, -1, 0, 0, -1, -1, -1]
    assert plan.diagnostics["modifier_excursion_notes_folded"] == 0


def test_scum_pitch_match_uses_one_global_octave_shift_before_folding():
    settings = AppSettings(
        mapping_mode="match3_adaptive",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_polyphony=1,
        onset_group_ms=1,
        chord_spread_ms=0,
        key_retrigger_gap_ms=0,
    )
    pitches = [45, 52, 57, 60, 64, 60, 55, 48]
    source = [note(pitch, start=index * 260, end=index * 260 + 180) for index, pitch in enumerate(pitches)]

    plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)

    assert [item.source_pitch for item in plan.planned_notes] == pitches
    assert [item.mapped_pitch for item in plan.planned_notes] == [pitch + 12 for pitch in pitches]
    assert plan.diagnostics["automatic_pitch_shift_semitones"] == 12
    assert plan.diagnostics["pitch_match_exact_notes"] == len(pitches)
    assert plan.diagnostics["pitch_match_octave_folded_notes"] == 0
    assert any("Pitch classes and intervals are not scale-quantised" in warning for warning in plan.warnings)


def test_scum_pitch_match_does_not_shift_an_already_playable_register():
    settings = AppSettings(
        mapping_mode="match3_adaptive",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_polyphony=1,
        onset_group_ms=1,
        chord_spread_ms=0,
        key_retrigger_gap_ms=0,
    )
    pitches = [60, 64, 67, 72]
    source = [note(pitch, start=index * 260, end=index * 260 + 180) for index, pitch in enumerate(pitches)]

    plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)

    assert [item.mapped_pitch for item in plan.planned_notes] == pitches
    assert plan.diagnostics["automatic_pitch_shift_semitones"] == 0
    assert plan.diagnostics["pitch_match_exact_notes"] == len(pitches)


def test_optimal_plan_uses_solo_adaptive_mapping_and_zero_solo_stagger():
    source: list[MidiNote] = []
    solo_pitches = (84, 86, 88, 89, 91, 89, 88, 86)
    for index in range(20):
        start = index * 260.0
        source.append(MidiNote(1, 0, 64 + index % 3, 78, start, start + 210))
        source.append(MidiNote(3, 0, 40 + index % 2, 82, start, start + 230))
        if 6 <= index < 14:
            source.append(
                MidiNote(
                    2,
                    0,
                    solo_pitches[index - 6],
                    118,
                    start,
                    start + 190,
                )
            )

    plan = build_playback_plan(
        source,
        AppSettings(performance_preset="optimal"),
        CURRENT_SCUM_PROFILE,
        track_names={1: "Lead Vocal", 2: "Guitar Solo", 3: "Bass"},
    )

    assert plan.diagnostics["solo_segments"] == 1
    assert plan.diagnostics["effective_mapping_mode"] == "solo_adaptive"
    assert plan.diagnostics["solo_mapping_exact_notes"] == len(solo_pitches)
    assert plan.diagnostics["solo_mapping_folded_notes"] == 0
    assert plan.diagnostics["solo_chord_stagger_suppressed_groups"] == len(solo_pitches)
    solo_notes = [item for item in plan.planned_notes if item.source_pitch in solo_pitches]
    assert len(solo_notes) == len(solo_pitches)
    assert all(item.modifier == 1 for item in solo_notes)
    assert any("Solo-adaptive mapping" in warning for warning in plan.warnings)
    for score_group in {item.score_group for item in solo_notes}:
        group = [item for item in plan.planned_notes if item.score_group == score_group]
        assert len({item.start_ms for item in group}) == 1


def test_obsolete_guitar_preset_migrates_without_dropping_short_arpeggio_attack():
    from musical_scumme.config import apply_performance_preset

    settings = AppSettings()
    apply_performance_preset(settings, "guitar_smooth")
    source = [
        note(57, start=0, end=52),
        note(60, start=69, end=220),
        note(64, start=313, end=500),
    ]

    plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)

    assert [item.source_pitch for item in plan.planned_notes] == [57, 60, 64]
    assert min(item.end_ms - item.start_ms for item in plan.planned_notes) >= 60
    assert plan.diagnostics["performance_preset"] == "optimal"
    assert plan.diagnostics["score_texture"] == "melody"


def test_prepared_song_source_skips_second_duration_filter():
    settings = AppSettings(
        mapping_mode="melody3_contour",
        arrangement_mode="melody",
        min_source_note_ms=45,
        min_retrigger_ms=0,
        max_notes_per_second=60,
        max_polyphony=1,
    )
    source = [note(60, start=0, end=30), note(64, start=40, end=70)]

    raw_plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)
    prepared_plan = build_playback_plan(
        source,
        settings,
        CURRENT_SCUM_PROFILE,
        prepared_source=True,
    )

    assert raw_plan.retained_notes == 0
    assert prepared_plan.retained_notes == 2
    assert prepared_plan.diagnostics["prepared_source"] == 1


def test_melody_contour_transition_guard_prevents_tiny_emitted_note():
    settings = AppSettings(
        mapping_mode="melody3_contour",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_polyphony=1,
        onset_group_ms=1,
        chord_spread_ms=0,
        key_retrigger_gap_ms=0,
        min_hold_ms=105,
        modifier_release_ms=10,
        modifier_settle_ms=20,
    )

    plan = build_playback_plan(
        [note(57, start=0, end=200), note(64, start=60, end=260)],
        settings,
        CURRENT_SCUM_PROFILE,
    )

    first = plan.planned_notes[0]
    key_events = [event for event in plan.events if event.key == first.key]
    down = next(event for event in key_events if event.action == "down")
    up = next(event for event in key_events if event.action == "up")
    assert up.at_ms - down.at_ms >= 80
    assert plan.diagnostics["contour_transition_groups_delayed"] == 1


def test_upper_octave_bank_is_selected_with_one_standalone_shift_tap():
    settings = AppSettings(
        mapping_mode="melody3_contour",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_polyphony=1,
        onset_group_ms=1,
        chord_spread_ms=0,
        key_retrigger_gap_ms=0,
        min_hold_ms=90,
        modifier_release_ms=10,
        modifier_settle_ms=20,
    )
    plan = build_playback_plan(
        [note(73, start=0, end=180), note(76, start=240, end=420)],
        settings,
        CURRENT_SCUM_PROFILE,
    )

    shift_events = [event for event in plan.events if event.key == "LSHIFT"]
    assert [event.action for event in shift_events] == ["down", "up"]
    assert shift_events[1].at_ms - shift_events[0].at_ms == 18.0
    assert plan.diagnostics["octave_bank_taps"] == 1
    assert plan.diagnostics["octave_shift_taps"] == 1

    first_note = plan.planned_notes[0]
    assert first_note.start_ms - shift_events[1].at_ms == settings.modifier_settle_ms
    assert shift_events[1].at_ms < first_note.start_ms


def test_octave_bank_taps_never_overlap_a_musical_key():
    settings = AppSettings(
        mapping_mode="melody3_contour",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_polyphony=1,
        onset_group_ms=1,
        chord_spread_ms=0,
        key_retrigger_gap_ms=0,
        min_hold_ms=90,
        modifier_release_ms=10,
        modifier_settle_ms=20,
    )
    plan = build_playback_plan(
        [note(47, start=0, end=180), note(76, start=240, end=420)],
        settings,
        CURRENT_SCUM_PROFILE,
    )

    pressed: set[str] = set()
    note_keys = set(CURRENT_SCUM_PROFILE.base_notes)
    for event in plan.events:
        if event.action == "down":
            if event.key in {"LCTRL", "LSHIFT"}:
                assert not pressed.intersection(note_keys)
            elif event.key in note_keys:
                assert not pressed.intersection({"LCTRL", "LSHIFT"})
            pressed.add(event.key)
        else:
            pressed.remove(event.key)
    assert pressed == set()
    assert plan.diagnostics["octave_control_taps"] == 1
    assert plan.diagnostics["octave_shift_taps"] == 2


def test_smart_register_planner_folds_brief_enclosed_octave_excursion():
    settings = AppSettings(
        mapping_mode="smart3_harmonic",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        max_polyphony=1,
        onset_group_ms=1,
        chord_spread_ms=0,
        key_retrigger_gap_ms=0,
    )
    pitches = [48] * 5 + [66, 64] + [50] * 5
    source = [note(pitch, start=index * 300, end=index * 300 + 180) for index, pitch in enumerate(pitches)]

    plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)

    assert {item.modifier for item in plan.planned_notes} == {-1}
    assert plan.diagnostics["modifier_excursion_groups_smoothed"] == 2
    assert plan.diagnostics["modifier_excursion_notes_folded"] == 2


def test_smart_register_planner_preserves_sustained_register_phrase():
    settings = AppSettings(
        mapping_mode="smart3_harmonic",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        max_polyphony=1,
        onset_group_ms=1,
        chord_spread_ms=0,
        key_retrigger_gap_ms=0,
    )
    pitches = [48] * 5 + [66, 64, 67, 65] + [50] * 5
    source = [note(pitch, start=index * 300, end=index * 300 + 180) for index, pitch in enumerate(pitches)]

    plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)

    assert [item.modifier for item in plan.planned_notes][5:9] == [0, 0, 0, 0]
    assert plan.diagnostics["modifier_excursion_groups_smoothed"] == 0


def test_velocity_expression_changes_hold_length_deterministically():
    settings = AppSettings(
        mapping_mode="strict_auto",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        hold_ratio=0.5,
        velocity_expression=1.0,
        min_hold_ms=10,
        max_hold_ms=2000,
    )
    quiet = note(60, start=0, end=1000, velocity=20)
    loud = note(62, start=2000, end=3000, velocity=120)
    plan = build_playback_plan([quiet, loud], settings, CURRENT_SCUM_PROFILE)
    durations = {item.source_pitch: item.end_ms - item.start_ms for item in plan.planned_notes}
    assert durations[62] > durations[60]


def test_instrument_preparation_enforces_real_time_sustain_limits():
    expected = {"guitar": 2000.0, "harmonica": 4000.0, "banjo": 1000.0}
    for instrument, maximum_ms in expected.items():
        settings = AppSettings(
            target_instrument=instrument,
            mapping_mode="strict_auto",
            arrangement_mode="faithful",
            ignore_percussion=False,
            min_source_note_ms=0,
            min_retrigger_ms=0,
            hold_ratio=1.0,
            min_hold_ms=10,
            max_hold_ms=5000,
            speed=0.5,
        )

        plan = build_playback_plan([note(60, start=100, end=8100)], settings, CURRENT_SCUM_PROFILE)
        played = plan.planned_notes[0]

        assert played.start_ms == 200.0
        assert played.end_ms - played.start_ms == maximum_ms
        assert played.source_pitch == 60
        assert played.mapped_pitch == 60
        assert plan.diagnostics["target_instrument"] == instrument
        assert plan.diagnostics["instrument_max_sustain_ms"] == maximum_ms
        assert plan.diagnostics["instrument_sustain_capped_notes"] == 1
        assert plan.diagnostics["instrument_sustain_reduction_ms"] > 0
        assert plan.diagnostics["effective_max_hold_ms"] == maximum_ms
        assert any(f"{int(maximum_ms):,} ms" in warning for warning in plan.warnings)
        pressed: set[str] = set()
        for event in plan.events:
            if event.action == "down":
                pressed.add(event.key)
            else:
                pressed.discard(event.key)
        assert pressed == set()


def test_instrument_ceiling_takes_priority_over_conflicting_minimum_hold():
    settings = AppSettings(
        target_instrument="banjo",
        mapping_mode="strict_auto",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_hold_ms=2000,
        max_hold_ms=5000,
        hold_ratio=1.0,
    )

    plan = build_playback_plan([note(60, end=5000)], settings, CURRENT_SCUM_PROFILE)

    assert plan.planned_notes[0].end_ms - plan.planned_notes[0].start_ms == 1000.0
    assert plan.diagnostics["effective_min_hold_ms"] == 1000.0
    assert any("instrument limit takes priority" in warning for warning in plan.warnings)


def test_custom_maximum_below_instrument_ceiling_remains_authoritative():
    settings = AppSettings(
        target_instrument="harmonica",
        mapping_mode="strict_auto",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_hold_ms=10,
        max_hold_ms=750,
        hold_ratio=1.0,
    )

    plan = build_playback_plan([note(60, end=5000)], settings, CURRENT_SCUM_PROFILE)

    assert plan.planned_notes[0].end_ms - plan.planned_notes[0].start_ms == 750.0
    assert plan.diagnostics["effective_max_hold_ms"] == 750.0
    assert plan.diagnostics["instrument_sustain_capped_notes"] == 0


def test_empty_plan_still_discloses_complete_instrument_hold_policy():
    settings = AppSettings(
        target_instrument="banjo",
        min_hold_ms=2000,
        max_hold_ms=5000,
        speed=0.5,
    )

    plan = build_playback_plan([], settings, CURRENT_SCUM_PROFILE)

    assert plan.diagnostics["target_instrument"] == "banjo"
    assert plan.diagnostics["instrument_max_sustain_ms"] == 1000
    assert plan.diagnostics["effective_min_hold_ms"] == 1000.0
    assert plan.diagnostics["effective_max_hold_ms"] == 1000.0


def test_every_mapping_mode_keeps_actual_key_holds_within_instrument_ceiling():
    source = [
        note(45, 0, 8000, 30),
        note(60, 2200, 10000, 64),
        note(72, 4400, 12000, 100),
        note(84, 6600, 14000, 127),
    ]
    note_keys = set(CURRENT_SCUM_PROFILE.base_notes)
    for instrument, ceiling_ms in (("guitar", 2000.0), ("harmonica", 4000.0), ("banjo", 1000.0)):
        for mapping_mode in ("fold_smart", "strict_auto", "match3_adaptive", "melody3_contour", "smart3_harmonic"):
            settings = AppSettings(
                target_instrument=instrument,
                mapping_mode=mapping_mode,
                arrangement_mode="faithful",
                ignore_percussion=False,
                min_source_note_ms=0,
                min_retrigger_ms=0,
                max_notes_per_second=60,
                max_polyphony=1,
                hold_ratio=1.0,
                velocity_expression=1.0,
                min_hold_ms=10,
                max_hold_ms=5000,
                speed=0.25,
            )

            plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)

            assert all(item.end_ms - item.start_ms <= ceiling_ms for item in plan.planned_notes)
            held_since: dict[str, float] = {}
            for event in plan.events:
                if event.key not in note_keys:
                    continue
                if event.action == "down":
                    assert event.key not in held_since
                    held_since[event.key] = event.at_ms
                elif event.key in held_since:
                    assert event.at_ms - held_since.pop(event.key) <= ceiling_ms
            assert held_since == {}


def test_chord_stagger_is_per_note_and_lead_is_first():
    settings = AppSettings(
        mapping_mode="strict_auto",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        max_polyphony=3,
        chord_spread_ms=25,
        key_retrigger_gap_ms=0,
    )
    plan = build_playback_plan(
        [note(60, velocity=80), note(64, velocity=90), note(72, velocity=100)],
        settings,
        CURRENT_SCUM_PROFILE,
    )
    starts = sorted((item.start_ms, item.source_pitch) for item in plan.planned_notes)
    assert starts == [(0.0, 72), (25.0, 60), (50.0, 64)]


def test_physical_retrigger_gap_is_enforced_after_octave_folding():
    settings = AppSettings(
        mapping_mode="fold_smart",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        key_retrigger_gap_ms=35,
        min_hold_ms=10,
        max_hold_ms=1000,
        chord_spread_ms=0,
    )
    # C3 and C4 both use Y after one-octave folding.
    plan = build_playback_plan(
        [note(48, 0, 300), note(60, 40, 340)],
        settings,
        CURRENT_SCUM_PROFILE,
    )
    y_events = [event for event in plan.events if event.key == "Y"]
    first_up = next(event for event in y_events if event.action == "up")
    second_down = [event for event in y_events if event.action == "down"][1]
    assert second_down.at_ms - first_up.at_ms >= 35


def test_retrigger_gap_never_chops_note_below_configured_minimum_hold():
    settings = AppSettings(
        mapping_mode="fold_smart",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        key_retrigger_gap_ms=35,
        min_hold_ms=100,
        max_hold_ms=1000,
        chord_spread_ms=0,
    )
    plan = build_playback_plan(
        [note(48, 0, 300), note(60, 40, 340)],
        settings,
        CURRENT_SCUM_PROFILE,
    )

    first, second = plan.planned_notes
    assert first.end_ms - first.start_ms >= 100
    assert second.start_ms - first.end_ms >= 35
    assert plan.diagnostics["physical_retriggers_delayed"] == 1


def test_modifier_delays_are_reflected_in_event_timeline():
    settings = AppSettings(
        mapping_mode="smart3_harmonic",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        modifier_release_ms=30,
        modifier_settle_ms=45,
        chord_spread_ms=0,
    )
    plan = build_playback_plan([note(48, 0, 200)], settings, CURRENT_SCUM_PROFILE)
    note_down = next(event for event in plan.events if event.action == "down" and event.key == "Y")
    modifier_down = next(event for event in plan.events if event.action == "down" and event.key == "LCTRL")
    modifier_up = next(event for event in plan.events if event.action == "up" and event.key == "LCTRL")
    assert modifier_up.at_ms - modifier_down.at_ms == 18
    assert note_down.at_ms - modifier_up.at_ms == 45
    assert note_down.at_ms == 93


def test_all_performance_presets_finish_with_balanced_key_state():
    from musical_scumme.config import PERFORMANCE_PRESETS, apply_performance_preset

    source = [
        note(48, 0, 220),
        note(60, 80, 300),
        note(72, 160, 380),
        note(84, 240, 460),
    ]
    for preset_name in PERFORMANCE_PRESETS:
        settings = AppSettings(mapping_mode="smart3_harmonic", min_source_note_ms=0)
        apply_performance_preset(settings, preset_name)
        plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)
        pressed: set[str] = set()
        for event in plan.events:
            if event.action == "down":
                assert event.key not in pressed
                pressed.add(event.key)
            else:
                assert event.key in pressed
                pressed.remove(event.key)
        assert pressed == set()


def test_every_mapping_mode_produces_a_fully_deterministic_plan():
    source = [
        note(45, 0, 180, 72),
        note(60, 240, 460, 94),
        note(64, 240, 500, 82),
        note(76, 520, 780, 110),
        note(48, 820, 1060, 88),
    ]
    for mapping_mode in ("fold_smart", "strict_auto", "match3_adaptive", "melody3_contour", "smart3_harmonic"):
        settings = AppSettings(
            mapping_mode=mapping_mode,
            arrangement_mode="faithful",
            ignore_percussion=False,
            min_source_note_ms=0,
            min_retrigger_ms=0,
            max_notes_per_second=60,
            max_polyphony=3,
            onset_group_ms=12,
            chord_spread_ms=10,
        )

        first = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)
        second = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)

        assert first == second
        assert first.planned_notes == second.planned_notes
        assert first.events == second.events
        assert first.warnings == second.warnings
        assert first.diagnostics == second.diagnostics


def test_bank_switch_budget_folds_excess_rapid_transitions():
    source = [
        note(47, 0, 140),
        note(76, 180, 320),
        note(47, 360, 500),
        note(76, 540, 680),
    ]
    settings = AppSettings(
        mapping_mode="melody3_contour",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_polyphony=1,
        bank_switch_budget_per_second=1,
    )

    plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)

    assert plan.diagnostics["bank_budget_groups_folded"] > 0
    assert plan.diagnostics["bank_switch_budget_per_second"] == 1
    assert any("1/s budget" in warning for warning in plan.warnings)


def test_mapping_explanation_discloses_fold_and_bank():
    settings = AppSettings(
        mapping_mode="fold_smart",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
    )

    plan = build_playback_plan([note(48)], settings, CURRENT_SCUM_PROFILE)

    assert "folded up 1 octave(s)" in plan.planned_notes[0].mapping_reason
    assert "base SCUM bank" in plan.planned_notes[0].mapping_reason


def test_optional_final_bank_restoration_uses_standalone_tap():
    settings = AppSettings(
        mapping_mode="melody3_contour",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_polyphony=1,
        restore_base_bank=True,
    )

    plan = build_playback_plan([note(76, 0, 180)], settings, CURRENT_SCUM_PROFILE)

    restore_events = [event for event in plan.events if "restore base bank" in event.reason]
    assert [event.action for event in restore_events] == ["down", "up"]
    assert restore_events[0].key == "LCTRL"
    assert plan.diagnostics["base_bank_restored"] == 1
    assert restore_events[0].at_ms >= plan.planned_notes[-1].end_ms


def test_boundary_c_preference_resolves_equivalent_melody_banks():
    common = dict(
        mapping_mode="melody3_contour",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_polyphony=1,
    )

    lower = build_playback_plan(
        [note(60)],
        AppSettings(**common, c_boundary_preference="lower"),
        CURRENT_SCUM_PROFILE,
    )
    upper = build_playback_plan(
        [note(60)],
        AppSettings(**common, c_boundary_preference="upper"),
        CURRENT_SCUM_PROFILE,
    )

    assert lower.planned_notes[0].modifier == -1
    assert upper.planned_notes[0].modifier == 0


def test_fold_smart_resolves_octave_unison_collision():
    # Chord with C3 (48) and C4 (60). Under basic fold, both fold to 60. Under fold_smart, one maps to 60 and the other to 72.
    settings = AppSettings(
        mapping_mode="fold_smart",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_polyphony=2,
        chord_spread_ms=0,
    )
    plan = build_playback_plan([note(48), note(60)], settings, CURRENT_SCUM_PROFILE)
    assert plan.retained_notes == 2
    pitches = {item.mapped_pitch for item in plan.planned_notes}
    assert pitches == {60, 72}


def test_strict_auto_centers_low_score_into_playable_c4_c5():
    # Score in C3 octave (48, 52, 55). Under strict mode with 0 transpose, all would be dropped. Under strict_auto, shifted by +12.
    settings = AppSettings(
        mapping_mode="strict_auto",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_polyphony=3,
        chord_spread_ms=0,
    )
    plan = build_playback_plan([note(48), note(52), note(55)], settings, CURRENT_SCUM_PROFILE)
    assert plan.retained_notes == 3
    assert all(60 <= item.mapped_pitch <= 72 for item in plan.planned_notes)
    assert [item.mapped_pitch for item in plan.planned_notes] == [60, 64, 67]


def test_enhanced_fold_keeps_upper_c_octave_chord_in_source_register_order():
    settings = AppSettings(mapping_mode="fold_smart", arrangement_mode="faithful", max_polyphony=2)
    source = [note(72), note(84)]
    plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)
    assert sorted((n.source_pitch, n.mapped_pitch) for n in plan.planned_notes) == [(72, 60), (84, 72)]
    assert plan == build_playback_plan(list(reversed(source)), settings, CURRENT_SCUM_PROFILE)


def test_smart3_harmonic_prioritizes_bass_and_melody_register():
    settings = AppSettings(
        mapping_mode="smart3_harmonic",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_polyphony=2,
        chord_spread_ms=0,
    )
    # Chord in lower register with bass note 48 and melody 55
    plan = build_playback_plan([note(48), note(55)], settings, CURRENT_SCUM_PROFILE)
    assert plan.retained_notes == 2
    assert all(item.modifier == -1 for item in plan.planned_notes)


def test_smart3_harmonic_prefers_base_bank_when_pitch_fit_is_tied():
    settings = AppSettings(
        mapping_mode="smart3_harmonic",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_polyphony=1,
        chord_spread_ms=0,
    )
    plan = build_playback_plan([note(72)], settings, CURRENT_SCUM_PROFILE)
    assert plan.planned_notes[0].modifier == 0
    assert plan.planned_notes[0].mapped_pitch == 72


def test_melody3_contour_preserves_ascending_contour():
    settings = AppSettings(
        mapping_mode="melody3_contour",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_polyphony=1,
        onset_group_ms=1,
        chord_spread_ms=0,
    )
    # Ascending phrase reaching high note 76
    pitches = [60, 64, 67, 72, 76]
    source = [note(p, start=i * 200, end=i * 200 + 150) for i, p in enumerate(pitches)]
    plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)
    assert plan.retained_notes == 5
    # High note 76 should be in upper bank (modifier 1)
    assert plan.planned_notes[-1].modifier == 1
    assert plan.planned_notes[-1].mapped_pitch == 76


def test_match3_adaptive_shifts_and_plans_cleanly():
    settings = AppSettings(
        mapping_mode="match3_adaptive",
        arrangement_mode="faithful",
        ignore_percussion=False,
        min_source_note_ms=0,
        min_retrigger_ms=0,
        max_polyphony=2,
        chord_spread_ms=0,
    )
    notes = [note(36, 0, 300), note(48, 100, 400), note(60, 200, 500)]
    plan = build_playback_plan(notes, settings, CURRENT_SCUM_PROFILE)
    assert plan.retained_notes >= 2
    assert all(48 <= item.mapped_pitch <= 84 for item in plan.planned_notes)


@pytest.mark.parametrize("priority", ["balanced", "register", "rhythm", "stability"])
def test_enhanced_contour_keeps_fast_register_landmarks_under_every_priority(priority):
    settings = AppSettings(
        mapping_mode="melody3_contour", arrangement_mode="faithful",
        fidelity_priority=priority, mapping_stability=100,
        max_polyphony=1, onset_group_ms=1, chord_spread_ms=0,
    )
    pitches = [59, 61, 59, 73, 71, 73, 48, 84, 60]
    source = [note(p, i * 90, i * 90 + 80) for i, p in enumerate(pitches)]
    plan = build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)
    assert [n.mapped_pitch for n in plan.planned_notes] == pitches
    assert plan == build_playback_plan(source, settings, CURRENT_SCUM_PROFILE)
    held = set()
    for event in plan.events:
        if event.action == "down":
            held.add(event.key)
        else:
            held.discard(event.key)
        assert not (held & {"LCTRL", "LSHIFT"} and held - {"LCTRL", "LSHIFT"})
    assert not held


def test_enhanced_harmonic_discount_requires_silence_from_all_earlier_notes():
    from musical_scumme.planner import _smart_register_sequence_harmonic

    settings = AppSettings(mapping_mode="smart3_harmonic")
    # A low sustained foundation crosses the following attack. A long onset
    # interval is not a safe silent opportunity for a register change.
    sustained = [[note(59, 0, 1500)], [note(61, 500, 600)], [note(59, 1000, 1100)]]
    detached = [[note(59, 0, 100)], [note(61, 500, 600)], [note(59, 1000, 1100)]]
    held_sequence = _smart_register_sequence_harmonic(sustained, settings)
    rest_sequence = _smart_register_sequence_harmonic(detached, settings)
    assert len(set(held_sequence.values())) == 1
    assert rest_sequence == {0: -1, 1: 0, 2: -1}
