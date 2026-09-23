from pathlib import Path

target_file = Path(r"e:\Users\james\Documents\Code\MusicalScumme_v2.2.0\musical_scumme\arranger.py")
content = target_file.read_text(encoding="utf-8")

# 1. Update ArrangementResult dataclass
old_dataclass = """    solo_density_dropped: int = 0
    solo_landmarks_preserved: int = 0"""

new_dataclass = """    solo_density_dropped: int = 0
    solo_landmarks_preserved: int = 0
    melody_landmarks_preserved: int = 0"""

assert old_dataclass in content, "dataclass snippet not found"
content = content.replace(old_dataclass, new_dataclass, 1)

# 2. Update _mark_solo_landmarks function to _mark_landmarks
old_mark_fn = """def _mark_solo_landmarks(selected: list[_Selected]) -> list[_Selected]:
    \"\"\"Protect the shape of fast solo runs before the physical density cap.

    Endpoints, accents, local extrema, direction changes, and regularly spaced
    phrase landmarks receive deterministic priority. The cap may still reduce
    an unplayable run, but it removes connective notes before its identity.
    \"\"\"

    solo_items = sorted(
        (item for item in selected if item.role == "solo"),
        key=lambda item: (item.note.start_ms, item.note.pitch),
    )
    if not solo_items:
        return selected
    gaps = [
        right.note.start_ms - left.note.start_ms
        for left, right in zip(solo_items, solo_items[1:], strict=False)
        if right.note.start_ms > left.note.start_ms
    ]
    typical_gap = median(gaps) if gaps else 250.0
    split_gap = max(320.0, typical_gap * 3.5)
    runs: list[list[_Selected]] = []
    for item in solo_items:
        if not runs or item.note.start_ms - runs[-1][-1].note.start_ms > split_gap:
            runs.append([item])
        else:
            runs[-1].append(item)

    replacements: dict[int, _Selected] = {}
    for run in runs:
        velocities = [item.note.velocity for item in run]
        velocity_centre = median(velocities)
        for index, item in enumerate(run):
            bonus = 0.0
            landmark = False
            if index in {0, len(run) - 1}:
                bonus += 3.0
                landmark = True
            if item.note.velocity >= velocity_centre + 10:
                bonus += 0.85
                landmark = True
            if 0 < index < len(run) - 1:
                left = run[index - 1].note.pitch
                current = item.note.pitch
                right = run[index + 1].note.pitch
                if (current - left) * (right - current) <= 0 and current not in {left, right}:
                    bonus += 1.65
                    landmark = True
                elif abs(current - left) >= 7 or abs(right - current) >= 7:
                    bonus += 0.65
                    landmark = True
            if index % 4 == 0:
                bonus += 0.35
                landmark = True
            if index and item.note.start_ms - run[index - 1].note.start_ms >= typical_gap * 1.45:
                bonus += 0.55
                landmark = True
            if landmark:
                replacements[id(item)] = replace(
                    item,
                    priority=item.priority + bonus,
                    landmark=True,
                )
    return [replacements.get(id(item), item) for item in selected]"""

new_mark_fn = """def _mark_landmarks(selected: list[_Selected]) -> list[_Selected]:
    \"\"\"Protect the shape of fast solo and melody runs before the physical density cap.

    Endpoints, accents, local extrema, direction changes, and regularly spaced
    phrase landmarks receive deterministic priority. The cap may still reduce
    an unplayable run, but it removes connective notes before its identity.
    \"\"\"

    lead_items = [item for item in selected if item.role in {"solo", "melody"}]
    if not lead_items:
        return selected

    replacements: dict[int, _Selected] = {}
    for role in ("solo", "melody"):
        items = sorted(
            (item for item in lead_items if item.role == role),
            key=lambda item: (item.note.start_ms, item.note.pitch),
        )
        if not items:
            continue
        gaps = [
            right.note.start_ms - left.note.start_ms
            for left, right in zip(items, items[1:], strict=False)
            if right.note.start_ms > left.note.start_ms
        ]
        typical_gap = median(gaps) if gaps else 250.0
        split_gap = max(320.0, typical_gap * 3.5)
        runs: list[list[_Selected]] = []
        for item in items:
            if not runs or item.note.start_ms - runs[-1][-1].note.start_ms > split_gap:
                runs.append([item])
            else:
                runs[-1].append(item)

        for run in runs:
            velocities = [item.note.velocity for item in run]
            velocity_centre = median(velocities)
            for index, item in enumerate(run):
                bonus = 0.0
                landmark = False
                if index in {0, len(run) - 1}:
                    bonus += 3.0
                    landmark = True
                if item.note.velocity >= velocity_centre + 10:
                    bonus += 0.85
                    landmark = True
                if 0 < index < len(run) - 1:
                    left = run[index - 1].note.pitch
                    current = item.note.pitch
                    right = run[index + 1].note.pitch
                    if (current - left) * (right - current) <= 0 and current not in {left, right}:
                        bonus += 1.65
                        landmark = True
                    elif abs(current - left) >= 7 or abs(right - current) >= 7:
                        bonus += 0.65
                        landmark = True
                if index % 4 == 0:
                    bonus += 0.35
                    landmark = True
                if index and item.note.start_ms - run[index - 1].note.start_ms >= typical_gap * 1.45:
                    bonus += 0.55
                    landmark = True
                if landmark:
                    replacements[id(item)] = replace(
                        item,
                        priority=item.priority + bonus,
                        landmark=True,
                    )
    return [replacements.get(id(item), item) for item in selected]


_mark_solo_landmarks = _mark_landmarks"""

assert old_mark_fn in content, "old_mark_fn not found"
content = content.replace(old_mark_fn, new_mark_fn, 1)

# 3. Update _apply_density_limit to allow melody replacement
old_density_body = """        elif item.role == "solo":
            weakest_solo = min(
                (entry for entry in window if entry[0].role == "solo"),
                key=lambda entry: entry[0].priority,
                default=None,
            )
            if weakest_solo is not None and item.priority > weakest_solo[0].priority:
                window.remove(weakest_solo)
                kept[weakest_solo[1]] = None
                kept_index = len(kept)
                kept.append(item)
                window.append((item, kept_index))
            solo_dropped += 1
            dropped += 1
        else:
            dropped += 1"""

new_density_body = """        elif item.role == "solo":
            weakest_solo = min(
                (entry for entry in window if entry[0].role == "solo"),
                key=lambda entry: entry[0].priority,
                default=None,
            )
            if weakest_solo is not None and item.priority > weakest_solo[0].priority:
                window.remove(weakest_solo)
                kept[weakest_solo[1]] = None
                kept_index = len(kept)
                kept.append(item)
                window.append((item, kept_index))
            solo_dropped += 1
            dropped += 1
        elif item.role == "melody":
            weakest_melody = min(
                (entry for entry in window if entry[0].role == "melody"),
                key=lambda entry: entry[0].priority,
                default=None,
            )
            if weakest_melody is not None and item.priority > weakest_melody[0].priority:
                window.remove(weakest_melody)
                kept[weakest_melody[1]] = None
                kept_index = len(kept)
                kept.append(item)
                window.append((item, kept_index))
            dropped += 1
        else:
            dropped += 1"""

assert old_density_body in content, "old_density_body not found"
content = content.replace(old_density_body, new_density_body, 1)

# 4. Update arrange_notes call and return
old_arrange_call = """        dropped_arrangement = len(working) - len(selected)
        selected = _mark_solo_landmarks(selected)
        selected, dropped_retrigger = _apply_retrigger_filter(selected, settings.min_retrigger_ms)
        selected, dropped_density, solo_density_dropped = _apply_density_limit(
            selected,
            settings.max_notes_per_second,
        )
        solo_landmarks_preserved = sum(
            item.role == "solo" and item.landmark for item in selected
        )"""

new_arrange_call = """        dropped_arrangement = len(working) - len(selected)
        selected = _mark_landmarks(selected)
        selected, dropped_retrigger = _apply_retrigger_filter(selected, settings.min_retrigger_ms)
        selected, dropped_density, solo_density_dropped = _apply_density_limit(
            selected,
            settings.max_notes_per_second,
        )
        solo_landmarks_preserved = sum(
            item.role == "solo" and item.landmark for item in selected
        )
        melody_landmarks_preserved = sum(
            item.role == "melody" and item.landmark for item in selected
        )"""

assert old_arrange_call in content, "old_arrange_call not found"
content = content.replace(old_arrange_call, new_arrange_call, 1)

old_return = """        solo_density_dropped=solo_density_dropped,
        solo_landmarks_preserved=solo_landmarks_preserved,
    )"""

new_return = """        solo_density_dropped=solo_density_dropped,
        solo_landmarks_preserved=solo_landmarks_preserved,
        melody_landmarks_preserved=melody_landmarks_preserved,
    )"""

assert old_return in content, "old_return not found"
content = content.replace(old_return, new_return, 1)

target_file.write_text(content, encoding="utf-8")
print("Successfully patched arranger.py")
