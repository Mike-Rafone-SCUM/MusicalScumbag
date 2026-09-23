from pathlib import Path

target_file = Path(r"e:\Users\james\Documents\Code\MusicalScumme_v2.2.0\musical_scumme\arranger.py")
content = target_file.read_text(encoding="utf-8")

# 1. Initialize melody_landmarks_preserved at line 1222
old_init = """    solo_accompaniment_dropped = 0
    solo_density_dropped = 0
    solo_landmarks_preserved = 0"""

new_init = """    solo_accompaniment_dropped = 0
    solo_density_dropped = 0
    solo_landmarks_preserved = 0
    melody_landmarks_preserved = 0"""

assert old_init in content, "old_init not found"
content = content.replace(old_init, new_init, 1)

# 2. Sequence retrigger filter before landmark marking
old_pipeline = """        dropped_arrangement = len(working) - len(selected)
        selected = _mark_landmarks(selected)
        selected, dropped_retrigger = _apply_retrigger_filter(selected, settings.min_retrigger_ms)
        selected, dropped_density, solo_density_dropped = _apply_density_limit(
            selected,
            settings.max_notes_per_second,
        )"""

new_pipeline = """        dropped_arrangement = len(working) - len(selected)
        selected, dropped_retrigger = _apply_retrigger_filter(selected, settings.min_retrigger_ms)
        selected = _mark_landmarks(selected)
        selected, dropped_density, solo_density_dropped = _apply_density_limit(
            selected,
            settings.max_notes_per_second,
        )"""

assert old_pipeline in content, "old_pipeline not found"
content = content.replace(old_pipeline, new_pipeline, 1)

target_file.write_text(content, encoding="utf-8")
print("Successfully updated arranger.py pipeline and init")
