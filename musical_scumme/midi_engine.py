from __future__ import annotations

import bisect
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Iterable

import mido

from .gm import describe_program
from .model import MidiNote, MidiProject, MidiTrack

INVALID_DATA_BYTE_ERROR = "data byte must be in range 0..127"
CLIPPED_DATA_BYTE_WARNING = (
    "This MIDI contained data bytes outside the legal 0..127 range. "
    "MusicalScumme recovered it by clipping those values to 127; inspect the prepared result before playback."
)


def _is_generic_track_name(name: str, index: int) -> bool:
    compact = " ".join(str(name).strip().casefold().split())
    return compact in {
        "",
        f"track {index}",
        f"track {index + 1}",
        "untitled",
        "midi",
    }


def _type0_part_name(
    source_name: str,
    source_index: int,
    channel: int,
    primary_program: int | None,
) -> str:
    """Build a useful label for one logical channel extracted from Type-0 MIDI."""

    channel_label = f"Ch {channel + 1}"
    if channel == 9:
        role_label = "Percussion"
    else:
        program = describe_program(primary_program)
        role_label = program.family if program is not None else "MIDI part"

    if _is_generic_track_name(source_name, source_index):
        return f"{channel_label} · {role_label}"
    return f"{source_name} · {channel_label} · {role_label}"


def _tempo_map(midi: mido.MidiFile) -> tuple[list[int], list[int], list[float]]:
    changes: list[tuple[int, int]] = [(0, 500_000)]
    # Scan only tempo messages in-place. mido.merge_tracks() clones and
    # revalidates every event in the file, even though the tempo map needs only
    # absolute ticks for set_tempo events. Track-order collection plus Python's
    # stable tick-only sort retains the same same-tick precedence as Mido's
    # stable merge without its large allocation and validation cost.
    for track in midi.tracks:
        absolute_tick = 0
        for message in track:
            absolute_tick += int(message.time)
            if message.is_meta and message.type == "set_tempo":
                if int(message.tempo) <= 0:
                    raise ValueError("MIDI tempo must be greater than zero; repair the source tempo before importing.")
                changes.append((absolute_tick, int(message.tempo)))

    deduped: list[tuple[int, int]] = []
    # Sort by tick only. The stable order lets a real tick-zero tempo replace
    # the synthetic 120 BPM fallback. Sorting the full tuple put faster tempos
    # before the fallback and silently stretched them back to 120 BPM.
    for tick, tempo in sorted(changes, key=lambda change: change[0]):
        if deduped and deduped[-1][0] == tick:
            deduped[-1] = (tick, tempo)
        else:
            deduped.append((tick, tempo))

    ticks = [t for t, _ in deduped]
    tempos = [tempo for _, tempo in deduped]
    ms_at = [0.0] * len(deduped)
    for index in range(1, len(deduped)):
        previous_tick = ticks[index - 1]
        current_tick = ticks[index]
        previous_tempo = tempos[index - 1]
        ms_at[index] = ms_at[index - 1] + mido.tick2second(
            current_tick - previous_tick,
            midi.ticks_per_beat,
            previous_tempo,
        ) * 1000.0
    return ticks, tempos, ms_at


def _tick_to_ms(tick: int, ticks: list[int], tempos: list[int], ms_at: list[float], tpq: int) -> float:
    index = max(0, bisect.bisect_right(ticks, tick) - 1)
    return ms_at[index] + mido.tick2second(tick - ticks[index], tpq, tempos[index]) * 1000.0


def load_midi(path: str | Path) -> MidiProject:
    midi_path = Path(path).expanduser().resolve()
    if not midi_path.exists():
        raise FileNotFoundError(midi_path)

    project_warnings: list[str] = []
    try:
        midi = mido.MidiFile(midi_path)
    except OSError as exc:
        if str(exc) != INVALID_DATA_BYTE_ERROR:
            raise
        # Mido provides a deliberately narrow recovery mode for malformed data
        # bytes. It does not hide broken chunks, undefined status bytes, or
        # truncated tracks; those still fail normally.
        midi = mido.MidiFile(midi_path, clip=True)
        project_warnings.append(CLIPPED_DATA_BYTE_WARNING)
    if midi.type == 2:
        raise ValueError("Type 2 MIDI contains independent sequences. Export a Type 0 or Type 1 MIDI before importing.")
    if midi.ticks_per_beat <= 0:
        raise ValueError("MIDI requires positive beat-based timing. Export with PPQ timing instead of SMPTE timing.")
    tempo_ticks, tempos, ms_at = _tempo_map(midi)
    first_bpm = float(mido.tempo2bpm(tempos[0]))
    tick_ms_cache: dict[int, float] = {}

    def tick_to_ms(tick: int) -> float:
        cached = tick_ms_cache.get(tick)
        if cached is None:
            cached = _tick_to_ms(tick, tempo_ticks, tempos, ms_at, midi.ticks_per_beat)
            tick_ms_cache[tick] = cached
        return cached

    all_notes: list[MidiNote] = []
    track_summaries: list[MidiTrack] = []
    pitch_bend_events = 0

    for track_index, track in enumerate(midi.tracks):
        absolute_tick = 0
        track_name = f"Track {track_index}"
        active: dict[tuple[int, int], deque[tuple[int, int, int | None]]] = defaultdict(deque)
        sustain_on: dict[int, bool] = defaultdict(bool)
        sustained: dict[int, list[tuple[int, int, int, int | None]]] = defaultdict(list)
        # Program changes are useful semantic evidence for anonymous MIDI tracks.
        # Only explicitly declared programs are recorded; assuming GM piano for a
        # channel with no program message would make the analyser overconfident.
        current_program: dict[int, int] = {}
        program_note_counts: Counter[int] = Counter()
        program_note_counts_by_channel: dict[int, Counter[int]] = defaultdict(Counter)
        track_notes: list[MidiNote] = []

        def close_note(
            channel: int,
            pitch: int,
            start_tick: int,
            velocity: int,
            end_tick: int,
            program: int | None,
            _track_index: int = track_index,
            _track_notes: list[MidiNote] = track_notes,
        ) -> None:
            start_ms = tick_to_ms(start_tick)
            end_ms = tick_to_ms(max(start_tick + 1, end_tick))
            _track_notes.append(
                MidiNote(
                    track_index=_track_index,
                    channel=channel,
                    pitch=pitch,
                    velocity=velocity,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    program=program,
                )
            )

        for message in track:
            absolute_tick += int(message.time)

            if message.is_meta:
                if message.type == "track_name" and message.name.strip():
                    track_name = message.name.strip()
                continue

            channel = int(getattr(message, "channel", 0))
            if message.type == "pitchwheel" and int(message.pitch) != 0:
                pitch_bend_events += 1
                continue
            if message.type == "program_change":
                current_program[channel] = max(0, min(127, int(message.program)))
                continue
            if message.type == "control_change" and int(message.control) in (120, 121, 123):
                controller = int(message.control)
                # All Notes Off behaves like individual releases (including
                # sustain); All Sound Off silences even pedal-held notes.
                # Reset Controllers releases the pedal, not physically held notes.
                if controller in (120, 123):
                    for (note_channel, pitch), starts in active.items():
                        if note_channel != channel:
                            continue
                        while starts:
                            start_tick, velocity, program = starts.popleft()
                            if controller == 123 and sustain_on[channel]:
                                sustained[channel].append((pitch, start_tick, velocity, program))
                            else:
                                close_note(
                                    channel, pitch, start_tick, velocity, absolute_tick, program
                                )
                if controller in (120, 121):
                    for pitch, start_tick, velocity, program in sustained[channel]:
                        close_note(channel, pitch, start_tick, velocity, absolute_tick, program)
                    sustained[channel].clear()
                if controller == 121:
                    sustain_on[channel] = False
                continue
            if message.type == "control_change" and int(message.control) == 64:
                pedal_down = int(message.value) >= 64
                if sustain_on[channel] and not pedal_down:
                    for pitch, start_tick, velocity, program in sustained[channel]:
                        close_note(channel, pitch, start_tick, velocity, absolute_tick, program)
                    sustained[channel].clear()
                sustain_on[channel] = pedal_down
                continue

            if message.type == "note_on" and int(message.velocity) > 0:
                if channel != 9 and channel in current_program:
                    program = current_program[channel]
                    program_note_counts[program] += 1
                    program_note_counts_by_channel[channel][program] += 1
                active[(channel, int(message.note))].append(
                    (
                        absolute_tick,
                        int(message.velocity),
                        current_program.get(channel) if channel != 9 else None,
                    )
                )
                continue

            is_note_release = message.type == "note_off" or (
                message.type == "note_on" and int(message.velocity) == 0
            )
            if is_note_release:
                key = (channel, int(message.note))
                if not active[key]:
                    continue
                start_tick, velocity, program = active[key].popleft()
                if sustain_on[channel]:
                    sustained[channel].append((key[1], start_tick, velocity, program))
                else:
                    close_note(channel, key[1], start_tick, velocity, absolute_tick, program)

        forced_end = absolute_tick + max(1, midi.ticks_per_beat // 4)
        for (channel, pitch), starts in active.items():
            for start_tick, velocity, program in starts:
                close_note(channel, pitch, start_tick, velocity, forced_end, program)
        for channel, pending in sustained.items():
            for pitch, start_tick, velocity, program in pending:
                close_note(channel, pitch, start_tick, velocity, forced_end, program)

        track_notes.sort(key=lambda note: (note.start_ms, note.channel, note.pitch, note.end_ms))

        # Type-0 MIDI deliberately stores every channel inside one physical
        # track.  Treating that file as one selectable part throws away the
        # exact separation information that General MIDI gives us.  Expand a
        # genuinely multichannel Type-0 file into logical parts so the normal
        # track analyser/selector/arranger can reason about lead, bass, support
        # and drums independently.  Type-1 files retain their authored tracks.
        channels_with_notes = sorted({note.channel for note in track_notes})
        split_type0 = midi.type == 0 and len(channels_with_notes) > 1
        if split_type0:
            first_logical_index = len(track_summaries)
            for channel in channels_with_notes:
                logical_index = len(track_summaries)
                channel_source_notes = [note for note in track_notes if note.channel == channel]
                channel_notes = [
                    MidiNote(
                        track_index=logical_index,
                        channel=note.channel,
                        pitch=note.pitch,
                        velocity=note.velocity,
                        start_ms=note.start_ms,
                        end_ms=note.end_ms,
                        program=note.program,
                    )
                    for note in channel_source_notes
                ]
                all_notes.extend(channel_notes)
                counts = program_note_counts_by_channel.get(channel, Counter())
                primary_program = (
                    max(counts, key=lambda program: (counts[program], -program))
                    if counts else None
                )
                track_summaries.append(
                    MidiTrack(
                        index=logical_index,
                        name=_type0_part_name(
                            track_name,
                            track_index,
                            channel,
                            primary_program,
                        ),
                        note_count=len(channel_notes),
                        min_pitch=min(note.pitch for note in channel_notes),
                        max_pitch=max(note.pitch for note in channel_notes),
                        duration_ms=max(note.end_ms for note in channel_notes),
                        percussion_note_count=(len(channel_notes) if channel == 9 else 0),
                        programs=tuple(sorted(counts)),
                        primary_program=primary_program,
                    )
                )
            project_warnings.append(
                "This Type 0 MIDI stored multiple instruments in one track. "
                f"MusicalScumme separated it into {len(channels_with_notes)} channel parts "
                "so Smart Select and the performance arranger can treat them independently."
            )
            # This assertion guards future refactors from accidentally reusing
            # the physical track index after logical expansion.
            assert len(track_summaries) - first_logical_index == len(channels_with_notes)
        else:
            all_notes.extend(track_notes)
            if track_notes:
                min_pitch = min(note.pitch for note in track_notes)
                max_pitch = max(note.pitch for note in track_notes)
                duration_ms = max(note.end_ms for note in track_notes)
                percussion_note_count = sum(note.channel == 9 for note in track_notes)
            else:
                min_pitch = max_pitch = None
                duration_ms = 0.0
                percussion_note_count = 0
            track_summaries.append(
                MidiTrack(
                    index=track_index,
                    name=track_name,
                    note_count=len(track_notes),
                    min_pitch=min_pitch,
                    max_pitch=max_pitch,
                    duration_ms=duration_ms,
                    percussion_note_count=percussion_note_count,
                    programs=tuple(sorted(program_note_counts)),
                    primary_program=(
                        max(
                            program_note_counts,
                            key=lambda program: (program_note_counts[program], -program),
                        )
                        if program_note_counts
                        else None
                    ),
                )
            )
        # Tempo discovery has already finished and the parsed notes now own
        # all musical data. Drop this private Mido message buffer before the
        # next track so large imports need not retain raw and parsed copies.
        track.clear()

    all_notes.sort(key=lambda note: (note.start_ms, note.track_index, note.pitch, note.end_ms))
    duration_ms = max((note.end_ms for note in all_notes), default=0.0)
    if pitch_bend_events:
        project_warnings.append(
            f"This MIDI contains {pitch_bend_events:,} non-centre pitch-bend event(s). "
            "SCUM has no continuous pitch-bend control, so MusicalScumme preserves the written note "
            "attacks but cannot reproduce those bends."
        )
    return MidiProject(
        path=midi_path,
        ticks_per_beat=midi.ticks_per_beat,
        tracks=track_summaries,
        notes=all_notes,
        duration_ms=duration_ms,
        first_bpm=first_bpm,
        warnings=tuple(project_warnings),
    )


def selected_track_indices(
    project: MidiProject,
    requested: Iterable[int] | None = None,
    *,
    prefer_non_percussion: bool = True,
) -> list[int]:
    available = {track.index for track in project.tracks if track.note_count > 0}
    preferred = {track.index for track in project.tracks if track.playable_note_count > 0}
    if requested is None:
        return sorted(preferred if prefer_non_percussion and preferred else available)
    selected = sorted(available.intersection(int(index) for index in requested))
    return selected or sorted(preferred if prefer_non_percussion and preferred else available)
