from pathlib import Path

target_file = Path(r"e:\Users\james\Documents\Code\MusicalScumme_v2.2.0\musical_scumme\planner.py")
content = target_file.read_text(encoding="utf-8")

target = """def _map_group(
    group: list[MidiNote],
    group_index: int,
    settings: AppSettings,
    smart_modifier: int | None = None,
    solo_track_index: int | None = None,
) -> list[_MappedCandidate]:
    transposed = group if settings.transpose == 0 and all(0 <= n.pitch <= 127 for n in group) else [
        MidiNote(
            track_index=n.track_index,
            channel=n.channel,
            pitch=max(0, min(127, n.pitch + settings.transpose)),
            velocity=n.velocity,
            start_ms=n.start_ms,
    for note in transposed:
        target = _fold_to_window(note.pitch, low, high)
        base_pitch = target - modifier * 12
        base_pitch = max(60, min(72, base_pitch))
        mapped.append(
            _MappedCandidate(
                note,
                target,
                base_pitch,
                modifier,
                group_index,
                settings.transpose,
                note.track_index == solo_track_index,
            )
        )
    return mapped"""

replacement = """def _map_group(
    group: list[MidiNote],
    group_index: int,
    settings: AppSettings,
    smart_modifier: int | None = None,
    solo_track_index: int | None = None,
) -> list[_MappedCandidate]:
    transposed = group if settings.transpose == 0 and all(0 <= n.pitch <= 127 for n in group) else [
        MidiNote(
            track_index=n.track_index,
            channel=n.channel,
            pitch=max(0, min(127, n.pitch + settings.transpose)),
            velocity=n.velocity,
            start_ms=n.start_ms,
            end_ms=n.end_ms,
        )
        for n in group
    ]

    mapped: list[_MappedCandidate] = []
    if settings.mapping_mode == "strict_auto":
        for note in transposed:
            if 60 <= note.pitch <= 72:
                mapped.append(
                    _MappedCandidate(
                        note,
                        note.pitch,
                        note.pitch,
                        0,
                        group_index,
                        settings.transpose,
                        note.track_index == solo_track_index,
                    )
                )
        return mapped

    if settings.mapping_mode == "fold_smart":
        sorted_notes = sorted(transposed, key=lambda n: (n.pitch, -n.velocity))
        c_pitches = sorted({n.pitch for n in transposed if n.pitch % 12 == 0})
        used_pitches: set[int] = set()
        for note in sorted_notes:
            target = _fold_to_window(note.pitch, 60, 72)
            if len(c_pitches) > 1 and note.pitch % 12 == 0:
                # Allocate boundary Cs by source register, not first available
                # key: C5/C6 must not become C5/C4 and invert the chord.
                target = 60 if note.pitch == c_pitches[0] else 72
            if target in used_pitches and note.pitch % 12 == 0:
                has_distinct_c = any(n.pitch % 12 == 0 and n.pitch != note.pitch for n in transposed)
                if has_distinct_c:
                    if target == 60 and 72 not in used_pitches:
                        target = 72
                    elif target == 72 and 60 not in used_pitches:
                        target = 60
            used_pitches.add(target)
            mapped.append(
                _MappedCandidate(
                    note,
                    target,
                    target,
                    0,
                    group_index,
                    settings.transpose,
                    note.track_index == solo_track_index,
                )
            )
        return mapped

    # Smart three-octave mode. SCUM's octave modifier is global, so every onset
    # group is kept inside one octave window to avoid impossible cross-octave chords.
    if smart_modifier is None:
        anchor = max(transposed, key=lambda n: (n.velocity, n.pitch))
        anchor_pitch = max(48, min(84, anchor.pitch))
        modifier = -1 if anchor_pitch < 60 else (1 if anchor_pitch > 72 else 0)
    else:
        modifier = smart_modifier
    low = 60 + modifier * 12
    high = 72 + modifier * 12

    for note in transposed:
        target = _fold_to_window(note.pitch, low, high)
        base_pitch = target - modifier * 12
        base_pitch = max(60, min(72, base_pitch))
        mapped.append(
            _MappedCandidate(
                note,
                target,
                base_pitch,
                modifier,
                group_index,
                settings.transpose,
                note.track_index == solo_track_index,
            )
        )
    return mapped"""

assert target in content, "Target block not found in planner.py"
new_content = content.replace(target, replacement, 1)
target_file.write_text(new_content, encoding="utf-8")
print("Successfully patched planner.py")
