from pathlib import Path

import pytest

from musical_scumme.config import (
    CURRENT_SCUM_PROFILE,
    DOCUMENTED_2023_SCUM_PROFILE,
    LEGACY_MUSICALSCUMME_PROFILE,
    MAX_RECENT_MIDI_FILES,
    AppSettings,
    load_settings,
    save_settings,
)


@pytest.mark.parametrize("legacy,enhanced", [
    ("fold", "fold_smart"), ("strict", "strict_auto"),
    ("smart3", "smart3_harmonic"), ("melody3", "melody3_contour"),
    ("match3", "match3_adaptive"), ("unsupported", "fold_smart"),
])
def test_retired_mapping_migrates_without_changing_custom_timings(tmp_path, legacy, enhanced):
    settings = AppSettings(mapping_mode=legacy, speed=1.17, key_retrigger_gap_ms=37,
                           max_polyphony=2, performance_preset="custom")
    destination = tmp_path / "settings.json"
    save_settings(settings, destination)
    loaded = load_settings(destination)
    assert loaded.mapping_mode == enhanced
    assert loaded.speed == 1.17
    assert loaded.key_retrigger_gap_ms == 37
    assert loaded.max_polyphony == 2
    assert loaded.performance_preset == "custom"


def test_config_round_trip(tmp_path: Path):
    path = tmp_path / "settings.json"
    original = AppSettings(
        performance_preset="custom",
        target_instrument="harmonica",
        speed=1.35,
        mapping_mode="smart3",
        transpose=-2,
        arrangement_mode="melody",
        chord_recognition_mode="exact",
        ignore_percussion=False,
        min_source_note_ms=44,
        min_retrigger_ms=67,
        max_notes_per_second=23,
        velocity_expression=0.72,
        midi_input_name="  Test Keyboard  ",
        live_midi_mapping_mode="strict",
        live_midi_transpose=7,
        live_midi_channel=15,
        live_midi_ignore_channel_10=False,
        live_midi_max_polyphony=5,
        section_gap_ms=750,
        loop_playback=True,
        recent_files=[str(tmp_path / "song.mid")],
        playback_sections_by_file={
            "song.mid": [
                {"mode": "include", "start_ms": 1000, "end_ms": 2000, "label": "Verse"}
            ]
        },
    )
    save_settings(original, path)
    loaded = load_settings(path)
    assert loaded.speed == 1.35
    assert loaded.target_instrument == "harmonica"
    assert loaded.mapping_mode == "smart3_harmonic"
    assert loaded.transpose == -2
    assert loaded.arrangement_mode == "melody"
    assert loaded.chord_recognition_mode == "exact"
    assert loaded.ignore_percussion is False
    assert loaded.min_source_note_ms == 44
    assert loaded.min_retrigger_ms == 67
    assert loaded.max_notes_per_second == 23
    assert loaded.velocity_expression == 0.72
    assert loaded.midi_input_name == "Test Keyboard"
    assert loaded.live_midi_mapping_mode == "strict"
    assert loaded.live_midi_transpose == 7
    assert loaded.live_midi_channel == 15
    assert loaded.live_midi_ignore_channel_10 is False
    assert loaded.live_midi_max_polyphony == 5
    assert loaded.section_gap_ms == 750
    assert loaded.loop_playback is True
    assert loaded.recent_files == [str((tmp_path / "song.mid").resolve())]
    assert loaded.playback_sections_by_file["song.mid"][0]["label"] == "Verse"


def test_recent_midi_history_is_normalized_deduplicated_and_bounded(tmp_path: Path):
    paths = [tmp_path / f"song-{index}.mid" for index in range(MAX_RECENT_MIDI_FILES + 2)]
    settings = AppSettings(
        recent_files=[
            str(paths[0]),
            str(paths[0]),
            "not-midi.txt",
            *[str(path) for path in paths[1:]],
        ]
    )

    settings.normalize()

    assert len(settings.recent_files) == MAX_RECENT_MIDI_FILES
    assert settings.recent_files[0] == str(paths[0].resolve())
    assert len(set(settings.recent_files)) == MAX_RECENT_MIDI_FILES
    assert all(Path(path).suffix == ".mid" for path in settings.recent_files)


def test_builtin_profiles_preserve_current_and_legacy_layouts():
    assert CURRENT_SCUM_PROFILE.base_notes == (
        "Y", "I", "O", "P", "G", "H", "J", "K", "L", "B", "N", "Q", "E"
    )
    assert DOCUMENTED_2023_SCUM_PROFILE.base_notes == (
        "Z", "5", "U", "6", "I", "O", "7", "H", "8", "J", "9", "K", "L"
    )
    assert LEGACY_MUSICALSCUMME_PROFILE.base_notes == tuple("YIOPGHJKLBNQE")


def test_existing_profile_name_migrates_to_corrected_mapping():
    settings = AppSettings(profile_name="SCUM current defaults")
    settings.normalize()
    assert settings.profile_name == CURRENT_SCUM_PROFILE.name
    assert settings.resolved_profile().base_notes[11] == "Q"


def test_performance_presets_apply_expected_scum_safe_values():
    from musical_scumme.config import apply_performance_preset

    settings = AppSettings()
    apply_performance_preset(settings, "scum_safe")
    assert settings.performance_preset == "scum_safe"
    assert settings.max_polyphony == 2
    assert settings.chord_spread_ms == 25
    assert settings.min_hold_ms == 110
    assert settings.key_retrigger_gap_ms == 35
    assert settings.modifier_release_ms == 30
    assert settings.modifier_settle_ms == 45
    assert settings.max_notes_per_second == 12
    assert settings.speed == 0.90


def test_obsolete_guitar_smooth_preset_migrates_to_optimal_sound_policy():
    from musical_scumme.config import apply_performance_preset

    settings = AppSettings(mapping_mode="fold", arrangement_mode="faithful", ignore_percussion=False)
    apply_performance_preset(settings, "guitar_smooth")

    assert settings.performance_preset == "optimal"
    assert settings.mapping_mode == "fold_smart"
    assert settings.arrangement_mode == "intelligent"
    assert settings.ignore_percussion is True
    assert settings.max_polyphony == 3
    assert settings.min_source_note_ms == 35
    assert settings.min_retrigger_ms == 35
    assert settings.max_notes_per_second == 18
    assert settings.min_hold_ms == 70
    assert settings.key_retrigger_gap_ms == 22
    assert settings.modifier_release_ms == 20
    assert settings.modifier_settle_ms == 30
    assert settings.speed == 1.0


def test_named_preset_refreshes_stale_saved_values(tmp_path: Path):
    import json

    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "performance_preset": "guitar_smooth",
                "mapping_mode": "smart3",
                "arrangement_mode": "melody",
                "max_notes_per_second": 12,
                "min_hold_ms": 105,
                "key_retrigger_gap_ms": 35,
                "modifier_release_ms": 30,
                "modifier_settle_ms": 45,
                "speed": 1.0,
            }
        ),
        encoding="utf-8",
    )

    loaded = load_settings(path)

    assert loaded.performance_preset == "optimal"
    assert loaded.mapping_mode == "fold_smart"
    assert loaded.max_notes_per_second == 18
    assert loaded.min_hold_ms == 70
    assert loaded.key_retrigger_gap_ms == 22
    assert loaded.modifier_release_ms == 20
    assert loaded.modifier_settle_ms == 30
    assert loaded.speed == 1.0


def test_old_settings_without_preset_identity_migrate_to_custom(tmp_path: Path):
    import json

    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"speed": 0.93, "chord_spread_ms": 17}), encoding="utf-8")
    loaded = load_settings(path)
    assert loaded.performance_preset == "custom"
    assert loaded.speed == 0.93
    assert loaded.chord_spread_ms == 17


def test_legacy_blanket_track_selections_are_discarded_once(tmp_path: Path):
    import json

    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "performance_preset": "custom",
                "selected_tracks_by_file": {"song.mid": [1, 2, 3, 4]},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_settings(path)

    assert loaded.selection_strategy_version == 2
    assert loaded.selected_tracks_by_file == {}


def test_invalid_selection_migration_marker_does_not_reset_other_settings(tmp_path: Path):
    import json

    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "performance_preset": "custom",
                "speed": 0.93,
                "selection_strategy_version": "invalid",
                "selected_tracks_by_file": {"song.mid": [1, 2]},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_settings(path)

    assert loaded.performance_preset == "custom"
    assert loaded.speed == 0.93
    assert loaded.selected_tracks_by_file == {}


def test_mapping_policy_settings_normalize_and_round_trip(tmp_path: Path):
    path = tmp_path / "settings.json"
    settings = AppSettings(
        bank_switch_budget_per_second=99,
        c_boundary_preference="invalid",
        mapping_stability=-10,
        fidelity_priority="invalid",
        restore_base_bank=True,
    )

    save_settings(settings, path)
    loaded = load_settings(path)

    assert loaded.bank_switch_budget_per_second == 20
    assert loaded.c_boundary_preference == "auto"
    assert loaded.mapping_stability == 0
    assert loaded.fidelity_priority == "balanced"
    assert loaded.restore_base_bank is True


def test_custom_mode_allows_wider_experimental_density_and_chords():
    settings = AppSettings(
        max_polyphony=99,
        max_notes_per_second=999,
        chord_spread_ms=999,
    )

    settings.normalize()

    assert settings.max_polyphony == 26
    assert settings.max_notes_per_second == 240
    assert settings.chord_spread_ms == 250


def test_live_midi_settings_normalize_to_safe_bounds():
    settings = AppSettings(
        midi_input_name={"not": "a device name"},  # type: ignore[arg-type]
        live_midi_mapping_mode="unsupported",
        live_midi_transpose=99,
        live_midi_channel=99,
        live_midi_ignore_channel_10=0,
        live_midi_max_polyphony=99,
    )

    settings.normalize()

    assert settings.midi_input_name == ""
    assert settings.live_midi_mapping_mode == "fold"
    assert settings.live_midi_transpose == 36
    assert settings.live_midi_channel == 15
    assert settings.live_midi_ignore_channel_10 is False
    assert settings.live_midi_max_polyphony == 8


def test_unknown_target_instrument_normalizes_to_guitar():
    settings = AppSettings(target_instrument="unsupported")

    settings.normalize()

    assert settings.target_instrument == "guitar"


def test_target_instrument_normalizes_case_and_surrounding_whitespace():
    settings = AppSettings(target_instrument="  BANJO  ")

    settings.normalize()

    assert settings.target_instrument == "banjo"


def test_target_instrument_does_not_shift_legacy_positional_settings_arguments():
    settings = AppSettings(CURRENT_SCUM_PROFILE.name, "custom")

    assert settings.performance_preset == "custom"
    assert settings.target_instrument == "guitar"


def test_old_settings_without_live_midi_fields_load_safe_defaults(tmp_path: Path):
    import json

    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "performance_preset": "custom",
                "speed": 0.93,
            }
        ),
        encoding="utf-8",
    )

    loaded = load_settings(path)

    assert loaded.speed == 0.93
    assert loaded.midi_input_name == ""
    assert loaded.live_midi_mapping_mode == "fold"
    assert loaded.live_midi_transpose == 0
    assert loaded.live_midi_channel == -1
    assert loaded.live_midi_ignore_channel_10 is True
    assert loaded.live_midi_max_polyphony == 3
    assert loaded.minimize_on_start is False


def test_minimize_on_start_defaults_to_false_for_compact_hud():
    settings = AppSettings()
    assert settings.minimize_on_start is False


def test_unlimited_number_inputs_normalization():
    # When disabled (default), standard safety ceilings clamp extreme inputs
    default_settings = AppSettings(
        unlimited_number_inputs=False,
        max_polyphony=999,
        max_notes_per_second=9999,
        speed=15.5,
        chord_spread_ms=5000,
        min_hold_ms=5000,
        max_hold_ms=100000,
        transpose=100,
        countdown_s=120,
    )
    default_settings.normalize()
    assert default_settings.max_polyphony == 26
    assert default_settings.max_notes_per_second == 240
    assert default_settings.speed == 3.0
    assert default_settings.chord_spread_ms == 250
    assert default_settings.min_hold_ms == 2000
    assert default_settings.max_hold_ms == 5000
    assert default_settings.transpose == 36
    assert default_settings.countdown_s == 30

    # When enabled, extreme numeric values are preserved without standard clamping
    unlimited_settings = AppSettings(
        unlimited_number_inputs=True,
        max_polyphony=999,
        max_notes_per_second=9999,
        speed=15.5,
        chord_spread_ms=5000,
        min_hold_ms=5000,
        max_hold_ms=100000,
        transpose=100,
        countdown_s=120,
    )
    unlimited_settings.normalize()
    assert unlimited_settings.max_polyphony == 999
    assert unlimited_settings.max_notes_per_second == 9999
    assert unlimited_settings.speed == 15.5
    assert unlimited_settings.chord_spread_ms == 5000
    assert unlimited_settings.min_hold_ms == 5000
    assert unlimited_settings.max_hold_ms == 100000
    assert unlimited_settings.transpose == 100
    assert unlimited_settings.countdown_s == 120
