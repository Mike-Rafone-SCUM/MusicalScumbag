from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InstrumentProfile:
    key: str
    label: str
    max_sustain_ms: int
    preparation_note: str


INSTRUMENT_PROFILES: dict[str, InstrumentProfile] = {
    "guitar": InstrumentProfile(
        key="guitar",
        label="Guitar",
        max_sustain_ms=2000,
        preparation_note="Balances connected melody with a firm two-second decay ceiling.",
    ),
    "harmonica": InstrumentProfile(
        key="harmonica",
        label="Harmonica",
        max_sustain_ms=4000,
        preparation_note="Preserves long breath-like phrases up to a four-second sustain.",
    ),
    "banjo": InstrumentProfile(
        key="banjo",
        label="Banjo",
        max_sustain_ms=1000,
        preparation_note="Keeps articulation short and percussive with a one-second ceiling.",
    ),
}

DEFAULT_INSTRUMENT = "guitar"


def resolve_instrument_profile(value: object) -> InstrumentProfile:
    key = str(value).strip().casefold() if isinstance(value, str) else ""
    return INSTRUMENT_PROFILES.get(key, INSTRUMENT_PROFILES[DEFAULT_INSTRUMENT])
