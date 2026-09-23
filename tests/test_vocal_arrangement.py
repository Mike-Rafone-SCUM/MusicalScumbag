from musical_scumme.arranger import _is_vocal_name, arrange_notes
from musical_scumme.config import AppSettings
from musical_scumme.model import MidiNote


def make_note(pitch: int, start: float, end: float, velocity: int = 90, track: int = 0) -> MidiNote:
    return MidiNote(track_index=track, channel=0, pitch=pitch, velocity=velocity, start_ms=start, end_ms=end)


def test_is_vocal_name():
    assert _is_vocal_name('Vocals')
    assert _is_vocal_name('Lead Vocal')
    assert _is_vocal_name('vox_main')
    assert _is_vocal_name('Singer Solo')
    assert _is_vocal_name('Voice')
    assert not _is_vocal_name('Piano Accompaniment')
    assert not _is_vocal_name('Bass Guitar')


def test_vocal_arrangement_mode_prioritizes_vocal_track():
    piano_notes = [
        make_note(pitch=76, start=i * 200.0, end=i * 200.0 + 150.0, velocity=100, track=0)
        for i in range(10)
    ]
    vocal_notes = [
        make_note(pitch=65, start=i * 400.0, end=i * 400.0 + 350.0, velocity=90, track=1)
        for i in range(5)
    ]
    all_notes = piano_notes + vocal_notes
    track_names = {0: 'Piano Accompaniment', 1: 'Lead Vocal'}

    settings = AppSettings(
        arrangement_mode='vocal',
        max_polyphony=1,
        min_source_note_ms=0,
        min_retrigger_ms=0,
    )
    result = arrange_notes(all_notes, settings, track_names=track_names)

    assert result.melody_track == 1
    vocal_pitches = {n.pitch for n in result.notes if n.track_index == 1}
    assert 65 in vocal_pitches
    assert any('Vocal lead focus' in w for w in result.warnings)


def test_vocal_mode_falls_back_when_no_vocal_track():
    notes = [
        make_note(pitch=60, start=0.0, end=400.0, track=0),
        make_note(pitch=67, start=0.0, end=400.0, track=1),
    ]
    track_names = {0: 'Acoustic Guitar', 1: 'Electric Bass'}
    settings = AppSettings(
        arrangement_mode='vocal',
        max_polyphony=2,
        min_source_note_ms=0,
    )
    result = arrange_notes(notes, settings, track_names=track_names)
    assert len(result.notes) > 0
    assert result.melody_track in {0, 1}
