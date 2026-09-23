from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GeneralMidiProgram:
    number: int
    family: str
    role_hint: str
    lead_bias: float = 0.0
    support_bias: float = 0.0
    bass_bias: float = 0.0
    noise_bias: float = 0.0


_FAMILIES: tuple[tuple[str, str, float, float, float, float], ...] = (
    ("Piano", "keys", 0.35, 1.15, 0.15, 0.0),
    ("Chromatic percussion", "pitched percussion", 0.65, 0.55, 0.0, 0.0),
    ("Organ", "keys / support", 0.25, 1.45, 0.2, 0.0),
    ("Guitar", "guitar", 1.15, 0.85, 0.15, 0.0),
    ("Bass", "bass", -1.75, 0.15, 4.0, 0.0),
    ("Strings", "strings", 1.05, 1.2, 0.15, 0.0),
    ("Ensemble", "ensemble / choir", 0.75, 1.75, 0.1, 0.0),
    ("Brass", "brass", 1.15, 0.65, 0.1, 0.0),
    ("Reed", "lead", 1.7, 0.25, 0.0, 0.0),
    ("Pipe", "lead", 1.75, 0.15, 0.0, 0.0),
    ("Synth lead", "lead", 2.25, 0.15, 0.0, 0.0),
    ("Synth pad", "pad / support", -0.2, 2.05, 0.0, 0.0),
    ("Synth effects", "effect", -0.65, -0.25, 0.0, 1.25),
    ("Ethnic", "lead / texture", 1.0, 0.45, 0.15, 0.0),
    ("Percussive", "percussive texture", 0.15, 0.45, 0.0, 0.6),
    ("Sound effects", "effect", -2.0, -1.5, -0.5, 4.5),
)


def describe_program(program: int | None) -> GeneralMidiProgram | None:
    """Return coarse General MIDI role information for a zero-based program number.

    MIDI program changes are only hints.  The score analyser deliberately combines
    these small semantic biases with the actual note behaviour instead of treating
    the program as authoritative.
    """

    if program is None:
        return None
    try:
        number = int(program)
    except (TypeError, ValueError, OverflowError):
        return None
    if not 0 <= number <= 127:
        return None
    family, role, lead, support, bass, noise = _FAMILIES[number // 8]
    return GeneralMidiProgram(
        number=number,
        family=family,
        role_hint=role,
        lead_bias=lead,
        support_bias=support,
        bass_bias=bass,
        noise_bias=noise,
    )
