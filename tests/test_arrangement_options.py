from collections import Counter

import pytest

from musical_scumme.arrangement_options import ARRANGEMENT_OPTIONS
from musical_scumme.arranger import arrange_notes
from musical_scumme.config import AppSettings, load_settings, save_settings
from musical_scumme.model import MidiNote


@pytest.mark.parametrize("mode", ARRANGEMENT_OPTIONS)
def test_arrangement_choice_round_trips_without_retuning(mode, tmp_path):
    path = tmp_path / "settings.json"
    settings = AppSettings(performance_preset="custom", arrangement_mode=mode, key_retrigger_gap_ms=31)
    save_settings(settings, path)
    restored = load_settings(path)
    assert restored.arrangement_mode == mode
    assert restored.key_retrigger_gap_ms == 31


@pytest.mark.parametrize("mode,limit", [("adaptive_lead", 1), ("melody_bass", 2)])
@pytest.mark.parametrize("polyphony", [1, 2, 8])
def test_sparse_arrangements_preserve_source_and_voice_ceiling(mode, limit, polyphony):
    source = [
        MidiNote(track, 0, pitch, 90, onset, onset + 300)
        for onset in range(0, 3000, 500)
        for track, pitch in enumerate([48, 64, 72, 79])
    ]
    settings = AppSettings(
        arrangement_mode=mode, max_polyphony=polyphony, min_source_note_ms=0,
        min_retrigger_ms=0, max_notes_per_second=60,
    )
    result = arrange_notes(source, settings, track_names={2: "Lead Melody", 0: "Bass"})
    assert result == arrange_notes(source, settings, track_names={2: "Lead Melody", 0: "Bass"})
    assert set(result.notes) <= set(source)
    assert max(Counter(n.start_ms for n in result.notes).values()) <= min(polyphony, limit)
    assert result.chord_notes_aligned == 0
    if mode == "melody_bass" and polyphony > 1:
        assert len(result.notes) == 12
        for onset in range(0, 3000, 500):
            pitches = sorted(n.pitch for n in result.notes if n.start_ms == onset)
            assert pitches[1] - pitches[0] >= 3


def test_adaptive_lead_follows_disjoint_track_handoff():
    source = [MidiNote(i // 4, 0, 60 + i, 90, i * 500, i * 500 + 300) for i in range(8)]
    result = arrange_notes(source, AppSettings(arrangement_mode="adaptive_lead", min_source_note_ms=0))
    assert set(result.notes) == set(source)
    assert result.melody_track_switches == 1


def test_melody_bass_does_not_fill_missing_bass_with_upper_harmony():
    source = [MidiNote(0, 0, 72, 100, 0, 400), MidiNote(1, 0, 79, 30, 0, 400)]
    result = arrange_notes(
        source, AppSettings(arrangement_mode="melody_bass", max_polyphony=8),
        track_names={0: "Lead Melody", 1: "Support"},
    )
    assert result.notes == (source[0],)
