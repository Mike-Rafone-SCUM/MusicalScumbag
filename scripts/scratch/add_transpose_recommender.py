from pathlib import Path

target_file = Path(r"e:\Users\james\Documents\Code\MusicalScumme_v2.2.0\musical_scumme\planner.py")
content = target_file.read_text(encoding="utf-8")

# Add Any to typing
assert "from typing import Iterable" in content
content = content.replace("from typing import Iterable", "from typing import Any, Iterable", 1)

fn_code = '''


def recommend_optimal_transpose(
    notes: list[MidiNote],
    settings: AppSettings,
    semitone_range: tuple[int, int] = (-12, 12),
) -> tuple[int, dict[str, Any]]:
    """Analyze pitch coverage and voice leading to recommend the optimal transpose shift."""

    if not notes:
        return 0, {
            "best_shift": 0,
            "in_bank_pct": 0.0,
            "in_range_pct": 0.0,
            "bank_switches": 0,
            "score": 0.0,
            "candidates": [],
        }

    total_weight = sum(
        min(note.duration_ms, 2000.0) * (0.35 + note.velocity / 127.0)
        for note in notes
    )
    if total_weight <= 0:
        total_weight = float(len(notes))

    groups = _group_onsets(notes, settings.onset_group_ms)
    candidates: list[dict[str, Any]] = []

    for shift in range(semitone_range[0], semitone_range[1] + 1):
        in_bank_w = 0.0
        in_range_w = 0.0
        fold_dist_w = 0.0
        for note in notes:
            p = max(0, min(127, note.pitch + shift))
            w = min(note.duration_ms, 2000.0) * (0.35 + note.velocity / 127.0)
            if 60 <= p <= 72:
                in_bank_w += w
            if 48 <= p <= 84:
                in_range_w += w
            else:
                fold_dist_w += abs(_fold_to_window(p, 48, 84) - p) * w

        bank_switches = 0
        current_bank = 0
        for group in groups:
            avg_pitch = sum(n.pitch + shift for n in group) / len(group)
            target_bank = -1 if avg_pitch < 54 else (1 if avg_pitch > 78 else 0)
            if target_bank != current_bank:
                bank_switches += abs(target_bank - current_bank)
                current_bank = target_bank

        in_bank_pct = (in_bank_w / total_weight) * 100.0
        in_range_pct = (in_range_w / total_weight) * 100.0
        shift_penalty = abs(shift) * 0.4

        score = (
            in_bank_w * 2.5
            + in_range_w * 1.5
            - fold_dist_w * 0.8
            - (bank_switches * 12.0)
            - shift_penalty
        )

        candidates.append(
            {
                "shift": shift,
                "in_bank_pct": round(in_bank_pct, 1),
                "in_range_pct": round(in_range_pct, 1),
                "bank_switches": bank_switches,
                "score": round(score, 2),
            }
        )

    best = max(candidates, key=lambda c: (c["score"], c["in_bank_pct"], -abs(c["shift"])))
    return best["shift"], {
        "best_shift": best["shift"],
        "in_bank_pct": best["in_bank_pct"],
        "in_range_pct": best["in_range_pct"],
        "bank_switches": best["bank_switches"],
        "score": best["score"],
        "candidates": candidates,
    }
'''

content = content.rstrip() + fn_code + "\n"
target_file.write_text(content, encoding="utf-8")
print("Added recommend_optimal_transpose to planner.py")
