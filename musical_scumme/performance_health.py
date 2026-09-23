from __future__ import annotations

from dataclasses import dataclass

from .model import PlaybackPlan


@dataclass(frozen=True, slots=True)
class PerformanceHealth:
    musical: str
    physical: str
    timing: str
    summary: str
    recommendations: tuple[str, ...] = ()


def _number(plan: PlaybackPlan, key: str) -> float:
    try:
        return float(plan.diagnostics.get(key, 0.0))
    except (TypeError, ValueError, OverflowError):
        return 0.0


def assess_performance(plan: PlaybackPlan) -> PerformanceHealth:
    """Describe what preparing this score cost in practical musical terms.

    This intentionally avoids a synthetic quality score.  The useful question is
    *what changed and why*, so each axis is based on directly observable plan data.
    """

    source = max(1, int(plan.source_notes))
    ignored = (
        _number(plan, "percussion_dropped")
        + _number(plan, "short_notes_dropped")
    )
    arrangement_drop = _number(plan, "arrangement_dropped")
    physical_drop = (
        _number(plan, "density_dropped")
        + _number(plan, "retrigger_dropped")
        + _number(plan, "planner_dropped")
    )
    musical_source = max(1.0, source - ignored)
    physical_drop_ratio = max(0.0, min(1.0, physical_drop / musical_source))
    arrangement_drop_ratio = max(0.0, min(1.0, arrangement_drop / musical_source))
    if physical_drop_ratio < 0.04 and arrangement_drop_ratio < 0.08:
        musical = "High note retention"
    elif physical_drop_ratio < 0.06 and arrangement_drop_ratio >= 0.25:
        musical = "Purposeful orchestration reduction"
    elif physical_drop_ratio < 0.10:
        musical = "Light simplification"
    elif physical_drop_ratio < 0.22:
        musical = "Moderate SCUM-driven simplification"
    else:
        musical = "Heavy SCUM-driven simplification"

    duration_minutes = max(1.0 / 60.0, plan.duration_ms / 60_000.0)
    bank_switches = _number(plan, "modifier_switches")
    bank_switches_per_minute = bank_switches / duration_minutes
    peak_onsets = _number(plan, "analysed_peak_onsets_per_second")
    retriggers = _number(plan, "physical_retriggers_delayed")
    physical_pressure = bank_switches_per_minute + peak_onsets * 1.5 + retriggers * 0.75
    if physical_pressure < 20:
        physical = "Low SCUM input pressure"
    elif physical_pressure < 55:
        physical = "Moderate SCUM input pressure"
    else:
        physical = "High SCUM input pressure"

    transition_delay = _number(plan, "contour_transition_delay_ms")
    retrigger_delay = _number(plan, "physical_retrigger_delay_ms")
    attack_delay = transition_delay + retrigger_delay
    delay_ratio = attack_delay / max(1.0, plan.duration_ms)
    if attack_delay < 5.0:
        timing = "Attacks stay on the MIDI timeline"
    elif delay_ratio < 0.0015 and attack_delay < 120.0:
        timing = "Tiny unavoidable timing corrections"
    elif delay_ratio < 0.006:
        timing = "Some attacks need physical correction"
    else:
        timing = "SCUM limits are audibly affecting timing"

    recommendations: list[str] = []
    if physical_drop_ratio >= 0.10:
        recommendations.append(
            "SCUM limits are removing a meaningful number of playable notes. In Advanced mode, compare a slightly higher voice limit with a more stable mapping rather than changing both at once."
        )
    elif arrangement_drop_ratio >= 0.25:
        recommendations.append(
            "Most removed notes are deliberate orchestration reduction, not input failure. Use a fuller arrangement only if you actually miss those layers."
        )
    if bank_switches_per_minute >= 35:
        recommendations.append(
            "Octave-bank activity is high; a more stable mapping or lower Mapping fidelity can reduce Ctrl/Shift churn."
        )
    if retriggers >= 3 or attack_delay >= 120.0:
        recommendations.append(
            "Repeated physical keys are under pressure; slowing the song slightly usually improves articulation more than increasing hold time."
        )
    if _number(plan, "rhythm_shortened_notes") >= max(4.0, plan.retained_notes * 0.04):
        recommendations.append(
            "Many sustains were shortened to protect rhythm. This is intentional; if the melody sounds too clipped, slow playback slightly rather than increasing hold time."
        )
    if not recommendations:
        recommendations.append("No obvious SCUM bottleneck was detected in the prepared plan.")

    summary = f"{musical} · {physical} · {timing}"
    return PerformanceHealth(
        musical=musical,
        physical=physical,
        timing=timing,
        summary=summary,
        recommendations=tuple(recommendations),
    )
