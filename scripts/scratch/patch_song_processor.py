from pathlib import Path

target_file = Path(r"e:\Users\james\Documents\Code\MusicalScumme_v2.2.0\musical_scumme\song_processor.py")
content = target_file.read_text(encoding="utf-8")

# 1. Update SongProcessingResult dataclass
old_result_dataclass = """    profile_name: str
    warnings: tuple[str, ...]

    @property"""

new_result_dataclass = """    profile_name: str
    warnings: tuple[str, ...]
    removed_ghosts: int = 0
    consolidated_strums: int = 0
    estimated_bpm: float = 120.0

    @property"""

assert old_result_dataclass in content, "old_result_dataclass not found"
content = content.replace(old_result_dataclass, new_result_dataclass, 1)

# 2. Add harmonic ghost suppression, micro-strum consolidation, and tempo estimation functions
helper_functions = '''


def _suppress_harmonic_ghosts(notes: list[MidiNote], profile_name: str) -> tuple[list[MidiNote], int]:
    """Remove acoustic body overtones (+12, +19, +24 st) and sub-bass rumble."""
    if not notes:
        return [], 0

    ghost_ids: set[int] = set()
    overtone_intervals = {12, 19, 24}
    guitar_like = profile_name in {"guitar_arpeggio", "melody_focus", "melody_bass"}

    for i, note in enumerate(notes):
        cutoff_pitch = 40 if guitar_like else 36
        if note.pitch < cutoff_pitch and (note.velocity < 70 or note.duration_ms < 200.0):
            ghost_ids.add(id(note))
            continue

        window_start = note.start_ms - 80.0
        window_end = note.start_ms + 40.0
        for j in range(max(0, i - 15), min(len(notes), i + 15)):
            if i == j:
                continue
            other = notes[j]
            if other.start_ms < window_start or other.start_ms > window_end:
                continue
            interval = note.pitch - other.pitch
            if interval in overtone_intervals:
                if note.velocity <= other.velocity * 0.82 or note.velocity < other.velocity - 18:
                    if note.duration_ms <= other.duration_ms * 1.25:
                        ghost_ids.add(id(note))
                        break

    kept = [note for note in notes if id(note) not in ghost_ids]
    return kept, len(ghost_ids)


def _consolidate_micro_strums(notes: list[MidiNote], max_strum_span_ms: float = 35.0) -> tuple[list[MidiNote], int]:
    """Align near-simultaneous strummed attacks (15-35 ms) to the anchor onset."""
    if len(notes) < 2:
        return list(notes), 0

    ordered = sorted(notes, key=lambda n: (n.start_ms, n.pitch))
    result: list[MidiNote] = []
    consolidated_count = 0
    strum_group: list[MidiNote] = [ordered[0]]

    for note in ordered[1:]:
        if (note.start_ms - strum_group[0].start_ms <= max_strum_span_ms) and (
            note.start_ms - strum_group[-1].start_ms <= 25.0
        ):
            strum_group.append(note)
        else:
            if len(strum_group) > 1:
                anchor_start = strum_group[0].start_ms
                for item in strum_group:
                    if item.start_ms != anchor_start:
                        consolidated_count += 1
                        result.append(
                            MidiNote(
                                track_index=item.track_index,
                                channel=item.channel,
                                pitch=item.pitch,
                                velocity=item.velocity,
                                start_ms=anchor_start,
                                end_ms=anchor_start + item.duration_ms,
                            )
                        )
                    else:
                        result.append(item)
            else:
                result.append(strum_group[0])
            strum_group = [note]

    if len(strum_group) > 1:
        anchor_start = strum_group[0].start_ms
        for item in strum_group:
            if item.start_ms != anchor_start:
                consolidated_count += 1
                result.append(
                    MidiNote(
                        track_index=item.track_index,
                        channel=item.channel,
                        pitch=item.pitch,
                        velocity=item.velocity,
                        start_ms=anchor_start,
                        end_ms=anchor_start + item.duration_ms,
                    )
                )
            else:
                result.append(item)
    elif strum_group:
        result.append(strum_group[0])

    result.sort(key=lambda n: (n.start_ms, n.pitch))
    return result, consolidated_count


def estimate_tempo_bpm(notes: list[MidiNote], default_bpm: float = 120.0) -> float:
    """Estimate musical BPM from inter-onset intervals (IOI)."""
    if len(notes) < 6:
        return default_bpm

    onsets = sorted({round(n.start_ms, 1) for n in notes})
    if len(onsets) < 6:
        return default_bpm

    iois: list[float] = []
    for i in range(len(onsets) - 1):
        gap = onsets[i + 1] - onsets[i]
        if 80.0 <= gap <= 1200.0:
            iois.append(gap)

    if len(iois) < 5:
        return default_bpm

    best_bpm = default_bpm
    best_score = -1.0

    for candidate_bpm in range(60, 181):
        beat_ms = 60_000.0 / candidate_bpm
        subdivisions = (beat_ms * 2.0, beat_ms, beat_ms / 2.0, beat_ms / 3.0, beat_ms / 4.0)
        score = 0.0
        for ioi in iois:
            min_dev = min(abs(ioi - sub) / sub for sub in subdivisions)
            if min_dev < 0.08:
                score += (1.0 - min_dev / 0.08)
        bpm_prior = 1.0 - abs(candidate_bpm - 120.0) * 0.001
        composite_score = score * bpm_prior
        if composite_score > best_score:
            best_score = composite_score
            best_bpm = float(candidate_bpm)

    return best_bpm
'''

anchor_code = "def _support_for_group("
assert anchor_code in content, "anchor_code not found"
content = content.replace(anchor_code, helper_functions.lstrip() + "\n\n" + anchor_code, 1)

# 3. Connect in process_song_notes
old_process = """    removed_percussion = sum(note.channel == 9 for note in source)
    non_percussion = [note for note in source if note.channel != 9]
    removed_short = sum(note.duration_ms < profile.minimum_note_ms for note in non_percussion)
    working = [note for note in non_percussion if note.duration_ms >= profile.minimum_note_ms]"""

new_process = """    removed_percussion = sum(note.channel == 9 for note in source)
    non_percussion = [note for note in source if note.channel != 9]
    cleaned_notes, removed_ghosts = _suppress_harmonic_ghosts(non_percussion, profile_name)
    cleaned_notes, consolidated_strums = _consolidate_micro_strums(cleaned_notes)
    removed_short = sum(note.duration_ms < profile.minimum_note_ms for note in cleaned_notes)
    working = [note for note in cleaned_notes if note.duration_ms >= profile.minimum_note_ms]"""

assert old_process in content, "old_process not found"
content = content.replace(old_process, new_process, 1)

# 4. Return in process_song_notes
old_return = """        profile_name=profile_name,
        warnings=tuple(warnings),
    )"""

new_return = """        profile_name=profile_name,
        warnings=tuple(warnings),
        removed_ghosts=removed_ghosts,
        consolidated_strums=consolidated_strums,
        estimated_bpm=estimate_tempo_bpm(source, default_bpm=120.0),
    )"""

assert old_return in content, "old_return not found"
content = content.replace(old_return, new_return, 1)

# 5. Connect in process_midi_file
old_file_process = """    write_processed_midi(result, destination_path, bpm=project.first_bpm, overwrite=overwrite)
    return result"""

new_file_process = """    output_bpm = result.estimated_bpm if project.first_bpm == 120.0 else project.first_bpm
    write_processed_midi(result, destination_path, bpm=output_bpm, overwrite=overwrite)
    return result"""

assert old_file_process in content, "old_file_process not found"
content = content.replace(old_file_process, new_file_process, 1)

target_file.write_text(content, encoding="utf-8")
print("Successfully patched song_processor.py")
