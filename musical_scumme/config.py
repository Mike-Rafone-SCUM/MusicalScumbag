from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .arrangement_options import ARRANGEMENT_OPTIONS
from .instrument_profiles import DEFAULT_INSTRUMENT, INSTRUMENT_PROFILES
from .model import KeyBindingProfile

CURRENT_SCUM_PROFILE = KeyBindingProfile(
    name="SCUM bindings shown in game",
    description=(
        "Bindings confirmed from the current in-game control screen: "
        "Y, I, O, P, G, H, J, K, L, B, N, Q, E."
    ),
    base_notes=("Y", "I", "O", "P", "G", "H", "J", "K", "L", "B", "N", "Q", "E"),
    octave_down="LCTRL",
    octave_up="LSHIFT",
)

DOCUMENTED_2023_SCUM_PROFILE = KeyBindingProfile(
    name="SCUM 2023 documented defaults",
    description="Older documented SCUM layout: Z, 5, U, 6, I, O, 7, H, 8, J, 9, K, L.",
    base_notes=("Z", "5", "U", "6", "I", "O", "7", "H", "8", "J", "9", "K", "L"),
    octave_down="LCTRL",
    octave_up="LSHIFT",
)

LEGACY_MUSICALSCUMME_PROFILE = KeyBindingProfile(
    name="Legacy MusicalScumme",
    description="The original app's custom layout: Y, I, O, P, G, H, J, K, L, B, N, Q, E.",
    base_notes=tuple("YIOPGHJKLBNQE"),
    octave_down="LCTRL",
    octave_up="LSHIFT",
)

BUILTIN_PROFILES = {
    CURRENT_SCUM_PROFILE.name: CURRENT_SCUM_PROFILE,
    DOCUMENTED_2023_SCUM_PROFILE.name: DOCUMENTED_2023_SCUM_PROFILE,
    LEGACY_MUSICALSCUMME_PROFILE.name: LEGACY_MUSICALSCUMME_PROFILE,
}

PROFILE_NAME_ALIASES = {
    # 2.0.0 stored this obsolete label in settings.json. Keep migration automatic.
    "SCUM current defaults": CURRENT_SCUM_PROFILE.name,
}

# Read old settings without retaining the retired mapping implementations.
MAPPING_MODE_ALIASES = {
    "fold": "fold_smart",
    "strict": "strict_auto",
    "smart3": "smart3_harmonic",
    "melody3": "melody3_contour",
    "match3": "match3_adaptive",
}
ENHANCED_MAPPING_MODES = frozenset(MAPPING_MODE_ALIASES.values())


PERFORMANCE_PRESETS: dict[str, dict[str, Any]] = {
    "optimal": {
        "label": "Automatic",
        "description": (
            "Directs the selected MIDI as a complete SCUM performance: traces the lead, chooses source harmony, "
            "plans playable chord voicings across phrases, protects rhythm during repeated keys and octave changes, "
            "and adapts mapping, density and articulation to the score. It never invents notes."
        ),
        # These are safe values for the controls before a score is loaded. The
        # planner replaces them with deterministic source-aware values.
        "mapping_mode": "fold_smart",
        "arrangement_mode": "intelligent",
        "chord_recognition_mode": "auto",
        "ignore_percussion": True,
        "max_polyphony": 3,
        "chord_spread_ms": 10,
        "min_source_note_ms": 35,
        "min_retrigger_ms": 35,
        "max_notes_per_second": 18,
        "velocity_expression": 0.30,
        "speed": 1.00,
        "hold_ratio": 0.72,
        "min_hold_ms": 70,
        "max_hold_ms": 850,
        "key_retrigger_gap_ms": 22,
        "modifier_release_ms": 20,
        "modifier_settle_ms": 30,
        "fidelity_priority": "balanced",
        "mapping_stability": 50,
        "bank_switch_budget_per_second": 0,
        "c_boundary_preference": "auto",
        "restore_base_bank": True,
    },
    "scum_safe": {
        "label": "SCUM Safe",
        "description": "Most reliable for finicky in-game input: one-bank pitch folding, rolled two-note chords, generous key gaps, and a slight slowdown.",
        "mapping_mode": "fold_smart",
        "arrangement_mode": "intelligent",
        "chord_recognition_mode": "auto",
        "ignore_percussion": True,
        "max_polyphony": 2,
        "chord_spread_ms": 25,
        "min_source_note_ms": 90,
        "min_retrigger_ms": 70,
        "max_notes_per_second": 12,
        "velocity_expression": 0.20,
        "speed": 0.90,
        "hold_ratio": 0.78,
        "min_hold_ms": 110,
        "max_hold_ms": 900,
        "key_retrigger_gap_ms": 35,
        "modifier_release_ms": 30,
        "modifier_settle_ms": 45,
        "fidelity_priority": "stability",
        "mapping_stability": 80,
        "bank_switch_budget_per_second": 0,
        "c_boundary_preference": "auto",
        "restore_base_bank": True,
    },
}

# Old named presets represented partial source-specific guesses. Migrate them
# to the maintained analyser while preserving Custom settings exactly.
PERFORMANCE_PRESET_ALIASES = {
    "guitar_smooth": "optimal",
    "balanced": "optimal",
    "fidelity": "optimal",
}

MAX_RECENT_MIDI_FILES = 10
CUSTOM_MAX_POLYPHONY = 26
CUSTOM_MAX_NOTES_PER_SECOND = 240
CUSTOM_MAX_CHORD_SPREAD_MS = 250


def apply_performance_preset(settings: "AppSettings", preset_name: str) -> None:
    """Apply one named SCUM reliability preset to mutable application settings."""

    preset_name = PERFORMANCE_PRESET_ALIASES.get(preset_name, preset_name)
    values = PERFORMANCE_PRESETS.get(preset_name)
    if values is None:
        settings.performance_preset = "custom"
        return
    for key, value in values.items():
        if key not in {"label", "description"}:
            setattr(settings, key, value)
    settings.performance_preset = preset_name
    settings.normalize()



def legacy_app_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "MusicalScumme"


def app_data_dir() -> Path:
    """Return directory for configuration and log files.

    Saves config files in the portable directory where the executable (or application)
    is located. Environment overrides (MUSICALSCUMME_DATA_DIR / pytest isolation)
    are respected during automated tests.
    """
    if "MUSICALSCUMME_DATA_DIR" in os.environ:
        return Path(os.environ["MUSICALSCUMME_DATA_DIR"])
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    if "PYTEST_CURRENT_TEST" in os.environ:
        return legacy_app_data_dir()
    return Path(__file__).resolve().parent.parent


def default_config_path() -> Path:
    return app_data_dir() / "settings.json"


@dataclass(slots=True)
class AppSettings:
    profile_name: str = CURRENT_SCUM_PROFILE.name
    # Direct engine callers receive explicit baseline values. The desktop app
    # uses create_default_settings(), whose product default is Automatic.
    performance_preset: str = "custom"  # optimal | scum_safe | custom
    custom_profile: dict[str, Any] = field(default_factory=dict)
    mapping_mode: str = "fold_smart"
    arrangement_mode: str = "intelligent"  # See ARRANGEMENT_OPTIONS
    chord_recognition_mode: str = "auto"  # auto | exact
    ignore_percussion: bool = True
    min_source_note_ms: int = 35
    min_retrigger_ms: int = 45
    max_notes_per_second: int = 18
    velocity_expression: float = 0.35
    transpose: int = 0
    speed: float = 1.0
    hold_ratio: float = 0.72
    min_hold_ms: int = 70
    max_hold_ms: int = 850
    max_polyphony: int = 3
    onset_group_ms: int = 12
    chord_spread_ms: int = 12  # per-note rolled-chord stagger
    key_retrigger_gap_ms: int = 22
    modifier_release_ms: int = 20
    modifier_settle_ms: int = 30
    bank_switch_budget_per_second: int = 0
    c_boundary_preference: str = "auto"  # auto | lower | upper
    mapping_stability: int = 50
    fidelity_priority: str = "balanced"  # balanced | register | rhythm | stability
    restore_base_bank: bool = False
    countdown_s: int = 4
    require_scum_focus: bool = True
    pause_on_focus_loss: bool = True
    # Retained only so settings written by older releases continue to load
    # without changing the positional dataclass layout. The redesigned player
    # no longer minimises itself when playback begins.
    minimize_on_start: bool = False
    input_mode: str = "scan_code"  # scan_code | virtual_key | dry_run
    midi_input_name: str = ""
    live_midi_mapping_mode: str = "fold"  # fold | strict
    live_midi_transpose: int = 0
    live_midi_channel: int = -1  # -1 = omni, 0..15 = MIDI channels 1..16
    live_midi_ignore_channel_10: bool = True
    live_midi_max_polyphony: int = 3
    last_file: str = ""
    recent_files: list[str] = field(default_factory=list)
    selected_tracks_by_file: dict[str, list[int]] = field(default_factory=dict)
    playback_sections_by_file: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    section_gap_ms: int = 500
    loop_playback: bool = False
    selection_strategy_version: int = 3
    window_width: int = 1180
    window_height: int = 760
    # Appended to preserve the positional constructor order of every setting
    # that existed before instrument-aware preparation.
    target_instrument: str = DEFAULT_INSTRUMENT  # guitar | harmonica | banjo
    unlimited_number_inputs: bool = False
    arrangement_lead_track: int = -1
    window_on_top: bool = False
    ui_mode: str = "simple"  # simple | advanced

    def resolved_profile(self) -> KeyBindingProfile:
        if self.profile_name == "Custom":
            try:
                return KeyBindingProfile(
                    name="Custom",
                    description="User-defined profile",
                    base_notes=tuple(str(x).upper() for x in self.custom_profile["base_notes"]),
                    octave_down=str(self.custom_profile.get("octave_down", "LCTRL")).upper(),
                    octave_up=str(self.custom_profile.get("octave_up", "LSHIFT")).upper(),
                )
            except (KeyError, TypeError, ValueError):
                return CURRENT_SCUM_PROFILE
        migrated_name = PROFILE_NAME_ALIASES.get(self.profile_name, self.profile_name)
        return BUILTIN_PROFILES.get(migrated_name, CURRENT_SCUM_PROFILE)

    def normalize(self) -> None:
        try:
            self.arrangement_lead_track = max(-1, int(self.arrangement_lead_track))
        except (TypeError, ValueError, OverflowError):
            self.arrangement_lead_track = -1
        self.profile_name = PROFILE_NAME_ALIASES.get(self.profile_name, self.profile_name)
        if self.profile_name not in BUILTIN_PROFILES and self.profile_name != "Custom":
            self.profile_name = CURRENT_SCUM_PROFILE.name
        instrument_key = (
            self.target_instrument.strip().casefold()
            if isinstance(self.target_instrument, str)
            else ""
        )
        self.target_instrument = (
            instrument_key if instrument_key in INSTRUMENT_PROFILES else DEFAULT_INSTRUMENT
        )
        self.unlimited_number_inputs = bool(self.unlimited_number_inputs)
        self.performance_preset = PERFORMANCE_PRESET_ALIASES.get(
            self.performance_preset, self.performance_preset
        )
        self.performance_preset = (
            self.performance_preset
            if self.performance_preset in {*PERFORMANCE_PRESETS, "custom"}
            else "custom"
        )
        self.mapping_mode = MAPPING_MODE_ALIASES.get(self.mapping_mode, self.mapping_mode)
        self.mapping_mode = (
            self.mapping_mode
            if self.mapping_mode in ENHANCED_MAPPING_MODES
            else "fold_smart"
        )
        self.arrangement_mode = (
            self.arrangement_mode
            if self.arrangement_mode in ARRANGEMENT_OPTIONS
            else "intelligent"
        )
        self.chord_recognition_mode = (
            self.chord_recognition_mode if self.chord_recognition_mode in {"auto", "exact"} else "auto"
        )
        self.ignore_percussion = bool(self.ignore_percussion)
        if self.unlimited_number_inputs:
            self.min_source_note_ms = max(0, int(self.min_source_note_ms))
            self.min_retrigger_ms = max(0, int(self.min_retrigger_ms))
            self.max_notes_per_second = max(1, int(self.max_notes_per_second))
            self.velocity_expression = max(0.0, float(self.velocity_expression))
            self.transpose = int(self.transpose)
            self.speed = max(0.001, float(self.speed))
            self.hold_ratio = max(0.01, float(self.hold_ratio))
            self.min_hold_ms = max(0, int(self.min_hold_ms))
            self.max_hold_ms = max(self.min_hold_ms, int(self.max_hold_ms))
            self.max_polyphony = max(1, int(self.max_polyphony))
            self.onset_group_ms = max(0, int(self.onset_group_ms))
            self.chord_spread_ms = max(0, int(self.chord_spread_ms))
            self.key_retrigger_gap_ms = max(0, int(self.key_retrigger_gap_ms))
            self.modifier_release_ms = max(0, int(self.modifier_release_ms))
            self.modifier_settle_ms = max(0, int(self.modifier_settle_ms))
            self.bank_switch_budget_per_second = max(0, int(self.bank_switch_budget_per_second))
            self.mapping_stability = max(0, int(self.mapping_stability))
            self.countdown_s = max(0, int(self.countdown_s))
            self.live_midi_transpose = int(self.live_midi_transpose)
            self.live_midi_max_polyphony = max(1, int(self.live_midi_max_polyphony))
            self.section_gap_ms = max(0, int(self.section_gap_ms))
        else:
            self.min_source_note_ms = max(0, min(1000, int(self.min_source_note_ms)))
            self.min_retrigger_ms = max(0, min(500, int(self.min_retrigger_ms)))
            self.max_notes_per_second = max(4, min(CUSTOM_MAX_NOTES_PER_SECOND, int(self.max_notes_per_second)))
            self.velocity_expression = max(0.0, min(1.0, float(self.velocity_expression)))
            self.transpose = max(-36, min(36, int(self.transpose)))
            self.speed = max(0.25, min(3.0, float(self.speed)))
            self.hold_ratio = max(0.05, min(1.0, float(self.hold_ratio)))
            self.min_hold_ms = max(10, min(2000, int(self.min_hold_ms)))
            self.max_hold_ms = max(self.min_hold_ms, min(5000, int(self.max_hold_ms)))
            self.max_polyphony = max(1, min(CUSTOM_MAX_POLYPHONY, int(self.max_polyphony)))
            self.onset_group_ms = max(0, min(100, int(self.onset_group_ms)))
            self.chord_spread_ms = max(0, min(CUSTOM_MAX_CHORD_SPREAD_MS, int(self.chord_spread_ms)))
            self.key_retrigger_gap_ms = max(0, min(250, int(self.key_retrigger_gap_ms)))
            self.modifier_release_ms = max(0, min(250, int(self.modifier_release_ms)))
            self.modifier_settle_ms = max(0, min(250, int(self.modifier_settle_ms)))
            self.bank_switch_budget_per_second = max(0, min(20, int(self.bank_switch_budget_per_second)))
            self.mapping_stability = max(0, min(100, int(self.mapping_stability)))
            self.countdown_s = max(0, min(30, int(self.countdown_s)))
            self.live_midi_transpose = max(-36, min(36, int(self.live_midi_transpose)))
            self.live_midi_max_polyphony = max(1, min(8, int(self.live_midi_max_polyphony)))
            self.section_gap_ms = max(0, min(5000, int(self.section_gap_ms)))
        self.c_boundary_preference = (
            self.c_boundary_preference
            if self.c_boundary_preference in {"auto", "lower", "upper"}
            else "auto"
        )
        self.fidelity_priority = (
            self.fidelity_priority
            if self.fidelity_priority in {"balanced", "register", "rhythm", "stability"}
            else "balanced"
        )
        self.restore_base_bank = bool(self.restore_base_bank)
        self.minimize_on_start = bool(self.minimize_on_start)
        self.input_mode = self.input_mode if self.input_mode in {"scan_code", "virtual_key", "dry_run"} else "scan_code"
        self.midi_input_name = (
            self.midi_input_name.strip() if isinstance(self.midi_input_name, str) else ""
        )
        self.live_midi_mapping_mode = (
            self.live_midi_mapping_mode
            if self.live_midi_mapping_mode in {"fold", "strict"}
            else "fold"
        )
        self.live_midi_transpose = max(-36, min(36, int(self.live_midi_transpose)))
        self.live_midi_channel = max(-1, min(15, int(self.live_midi_channel)))
        self.live_midi_ignore_channel_10 = bool(self.live_midi_ignore_channel_10)
        self.live_midi_max_polyphony = max(
            1, min(8, int(self.live_midi_max_polyphony))
        )
        self.last_file = str(self.last_file).strip() if isinstance(self.last_file, (str, Path)) else ""
        recent_files: list[str] = []
        seen_recent_files: set[str] = set()
        if isinstance(self.recent_files, list):
            for value in self.recent_files:
                if not isinstance(value, (str, Path)):
                    continue
                candidate = str(value).strip()
                try:
                    candidate_path = Path(candidate)
                    resolved = str(candidate_path.expanduser().resolve())
                except (OSError, RuntimeError, ValueError):
                    continue
                if not candidate or candidate_path.suffix.lower() not in {".mid", ".midi"}:
                    continue
                identity = os.path.normcase(resolved)
                if identity in seen_recent_files:
                    continue
                seen_recent_files.add(identity)
                recent_files.append(resolved)
                if len(recent_files) >= MAX_RECENT_MIDI_FILES:
                    break
        self.recent_files = recent_files
        if not isinstance(self.selected_tracks_by_file, dict):
            self.selected_tracks_by_file = {}
        if not isinstance(self.playback_sections_by_file, dict):
            self.playback_sections_by_file = {}
        self.section_gap_ms = max(0, min(5000, int(self.section_gap_ms)))
        self.loop_playback = bool(self.loop_playback)
        self.window_width = max(900, min(2400, int(self.window_width)))
        self.window_height = max(600, min(1600, int(self.window_height)))
        self.window_on_top = bool(self.window_on_top)
        self.ui_mode = self.ui_mode if self.ui_mode in {"simple", "advanced"} else "simple"
        self.selection_strategy_version = 3


def create_default_settings() -> AppSettings:
    settings = AppSettings()
    apply_performance_preset(settings, "optimal")
    return settings


def load_settings(path: Path | None = None) -> AppSettings:
    if path is None:
        target = default_config_path()
        if not target.exists() and "PYTEST_CURRENT_TEST" not in os.environ:
            legacy = legacy_app_data_dir() / "settings.json"
            if legacy.exists():
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(legacy, target)
                    legacy_bak = legacy.with_suffix(legacy.suffix + ".bak")
                    if legacy_bak.exists():
                        shutil.copy2(legacy_bak, target.with_suffix(target.suffix + ".bak"))
                except OSError:
                    pass
        path = target
    candidates = [path, path.with_suffix(path.suffix + ".bak")]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            raw = json.loads(candidate.read_text(encoding="utf-8"))
            # Existing 2.1.x settings had no preset identity. Preserve their exact
            # values and present them as Custom rather than claiming a preset match.
            if "performance_preset" not in raw:
                raw["performance_preset"] = "custom"
            # Version 3 understands Type-0 logical channel expansion.  Preserve
            # established multi-track choices, but discard the ambiguous legacy
            # [0] selection: in older builds that meant "the one physical Type-0
            # track" whereas it can now mean only the first logical channel.
            try:
                selection_strategy_version = int(raw.get("selection_strategy_version", 0))
            except (TypeError, ValueError):
                selection_strategy_version = 0
            if selection_strategy_version < 3:
                remembered = raw.get("selected_tracks_by_file", {})
                if isinstance(remembered, dict):
                    raw["selected_tracks_by_file"] = {
                        file_name: values
                        for file_name, values in remembered.items()
                        if values != [0]
                    }
                else:
                    raw["selected_tracks_by_file"] = {}
                raw["selection_strategy_version"] = 3
            allowed = set(AppSettings.__dataclass_fields__)
            settings = AppSettings(**{k: v for k, v in raw.items() if k in allowed})
            settings.normalize()
            # A named preset requests the maintained preset, not a frozen copy of
            # values from the release that first saved it. Manual UI edits already
            # change the identity to Custom, and those values remain exact.
            if settings.performance_preset in PERFORMANCE_PRESETS:
                apply_performance_preset(settings, settings.performance_preset)
            return settings
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError, AttributeError):
            continue
    return create_default_settings()


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    settings.normalize()
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings), indent=2, ensure_ascii=False), encoding="utf-8")
    if path.exists():
        try:
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        except OSError:
            pass
    tmp.replace(path)
