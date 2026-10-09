import json

import pytest

from musical_scumme.config import (
    AppSettings,
    apply_performance_preset,
    create_default_settings,
    load_settings,
    save_settings,
)


@pytest.mark.parametrize("unlimited", [False, True])
@pytest.mark.parametrize(
    "value,expected",
    [
        (-20, 0),
        (0, 0),
        (42, 42),
        (100, 100),
        (140, 100),
        ("65", 65),
        (35.9, 35),
        (None, 0),
        ("invalid", 0),
        ([], 0),
        ({"strength": 65}, 0),
        (float("nan"), 0),
        (float("inf"), 0),
    ],
)
def test_fluid_strength_is_always_bounded_and_malformed_values_are_off(value, expected, unlimited):
    settings = AppSettings(fluid_phrasing=value, unlimited_number_inputs=unlimited)

    settings.normalize()

    assert settings.fluid_phrasing == expected


def test_fluid_phrasing_defaults_off_for_new_and_legacy_settings(tmp_path):
    assert AppSettings().fluid_phrasing == 0
    assert create_default_settings().fluid_phrasing == 0
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"performance_preset": "scum_safe"}), encoding="utf-8")

    assert load_settings(path).fluid_phrasing == 0


@pytest.mark.parametrize("preset", ["custom", "optimal", "scum_safe"])
def test_fluid_preference_survives_persistence_and_preset_refresh(tmp_path, preset):
    path = tmp_path / "settings.json"
    settings = AppSettings(performance_preset=preset, fluid_phrasing=42)

    save_settings(settings, path)
    loaded = load_settings(path)

    assert loaded.fluid_phrasing == 42
    assert loaded.performance_preset == preset
    for next_preset in ("scum_safe", "optimal", "custom"):
        apply_performance_preset(loaded, next_preset)
        assert loaded.fluid_phrasing == 42
        assert loaded.performance_preset == next_preset


def test_bad_fluid_value_does_not_discard_other_saved_preferences(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"performance_preset": "custom", "fluid_phrasing": [65], "speed": 1.17}),
        encoding="utf-8",
    )

    loaded = load_settings(path)

    assert loaded.fluid_phrasing == 0
    assert loaded.speed == 1.17
    assert loaded.performance_preset == "custom"
