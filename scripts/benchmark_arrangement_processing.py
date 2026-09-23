"""Run with python -m scripts.benchmark_arrangement_processing; never sends input."""

import json
from dataclasses import replace
from time import perf_counter

from musical_scumme.arrangement_processing import _VoiceTimeline
from musical_scumme.arranger import arrange_notes
from musical_scumme.config import AppSettings
from musical_scumme.model import MidiNote


def main():
    intervals = [MidiNote(0, 0, 60, 90, i, i + 10000) for i in range(2500)]
    started = perf_counter()
    timeline = _VoiceTimeline(intervals)
    indexed = []
    for note in intervals:
        indexed.append(timeline.voices(note))
        timeline.voices(note, add=True)
    index_seconds = perf_counter() - started
    started = perf_counter()
    occupied = [0] * (len(timeline.times) - 1)
    reference = []
    for note in intervals:
        left, right = timeline.indices[note.start_ms], timeline.indices[note.end_ms]
        reference.append(max(occupied[left:right]))
        for index in range(left, right):
            occupied[index] += 1
    reference_seconds = perf_counter() - started
    assert indexed == reference
    source = [MidiNote(0, 0, 72 + i % 4, 80, i * 500, (i + 1) * 500) for i in range(120)]
    source += [MidiNote(track, 1, pitch + i % 3, 90, i * 125, i * 125 + 1100)
               for i in range(480) for track, pitch in [(1, 36), (2, 48), (3, 55), (4, 60)]]
    results = {}
    base = AppSettings(max_polyphony=3, min_source_note_ms=0, min_retrigger_ms=0,
                       max_notes_per_second=240, arrangement_lead_track=0)
    for mode in ("vocal_ballad", "vocal_director", "vocal_director_pulse"):
        started = perf_counter()
        result = arrange_notes(source, replace(base, arrangement_mode=mode))
        elapsed = perf_counter() - started
        sounding = peak = 0
        for _, change in sorted((time, delta) for n in result.notes
                                for time, delta in [(n.start_ms, 1), (n.end_ms, -1)]):
            sounding += change
            peak = max(peak, sounding)
        assert set(result.notes) <= set(source)
        assert len([n for n in result.notes if n.track_index == 0]) == 120
        results[mode] = {"seconds": round(elapsed, 6), "retained": len(result.notes), "peak_voices": peak}
    print(json.dumps({"interval_queries_equal": True, "indexed_seconds": round(index_seconds, 6),
                      "reference_seconds": round(reference_seconds, 6), "source_notes": len(source),
                      "arrangements": results}, indent=2))


if __name__ == "__main__":
    main()
