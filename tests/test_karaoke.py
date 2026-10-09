import os

import pytest

from musical_scumme.lyric_sources import parse_lrc
from musical_scumme.lyrics import LyricTimeline, lyric_cues
from musical_scumme.model import MidiLyric
from musical_scumme.playback_sections import PlaybackInterval, PlaybackSelectionResult


def test_complete_midi_phrase_is_visible_before_all_syllables_are_sung():
    cues = lyric_cues((MidiLyric(1000, "Hel"), MidiLyric(1200, "lo "),
                      MidiLyric(1700, "world"), MidiLyric(3000, "/Next line")))
    timeline = LyricTimeline(cues)
    frame = timeline.frame_at(1200)
    assert frame.current == "Hello world"
    assert frame.highlight == 3
    assert frame.upcoming == "Next line"
    assert frame.timed_words
    assert timeline.frame_at(3000).previous == "Hello world"
    assert timeline.frame_at(1000).highlight == 0


def test_unmarked_midi_lines_do_not_run_together():
    cues = lyric_cues((MidiLyric(0, "A complete phrase"), MidiLyric(4000, "A second phrase")))
    assert [cue.text for cue in cues] == ["A complete phrase", "A second phrase"]


def test_line_sync_has_read_ahead_countdown_and_rewinds():
    timeline = LyricTimeline(parse_lrc("[00:02]First line\n[00:06]Second line\n[00:09]Third line"), end_ms=12000)
    frame = timeline.frame_at(500)
    assert frame.current == ""
    assert frame.upcoming == "First line"
    assert frame.following == "Second line"
    assert frame.countdown_ms == 1500
    frame = timeline.frame_at(4000)
    assert frame.current == "First line"
    assert frame.progress == 0.5
    assert frame.highlight == len("First line") / 2
    assert not frame.timed_words
    assert timeline.frame_at(6000).current == "Second line"
    assert timeline.frame_at(4000) == frame  # seek back or pause: same source clock, same display
    assert timeline.frame_at(0).countdown_ms == 2000  # repeat


def test_enhanced_word_timing_survives_speed_offset_and_repeated_lines():
    events = parse_lrc("[00:02][00:12]<00:02>Hello <00:03>world", offset_ms=500)
    assert events[0].word_times == ((0, 2500), (6, 3500))
    assert events[1].word_times == ((0, 12500), (6, 13500))
    timeline = LyricTimeline(lyric_cues(events, timed_lines=True, speed=2, pre_roll_ms=100))
    frame = timeline.frame_at(1850)
    assert frame.current == "Hello world"
    assert frame.highlight == 6
    assert frame.timed_words


def test_section_beginning_inside_phrase_restores_phrase_and_clears_gap():
    events = parse_lrc("[00:01]<00:01>Hello <00:03>world\n[00:09]Last line")
    selection = PlaybackSelectionResult((), (PlaybackInterval(2500, 4000), PlaybackInterval(9500, 10500)),
                                       0, 0, 0, 2500, 2700, 2, 0, 200)
    timeline = LyricTimeline(lyric_cues(events, timed_lines=True, selection=selection))
    assert timeline.frame_at(0).current == "Hello world"
    assert timeline.frame_at(0).highlight > 0
    assert timeline.frame_at(1500).current == ""
    assert timeline.frame_at(1500).upcoming == "Last line"
    assert timeline.frame_at(1700).current == "Last line"
    assert timeline.frame_at(2700).current == ""


def test_blank_line_clears_current_and_previews_next():
    timeline = LyricTimeline(parse_lrc("[00:01]First\n[00:05]\n[00:10]Second"))
    frame = timeline.frame_at(6000)
    assert frame.current == ""
    assert frame.previous == "First"
    assert frame.upcoming == "Second"
    assert frame.countdown_ms == 4000


@pytest.mark.parametrize("width", [500, 620, 900])
def test_karaoke_view_wraps_long_literal_text_without_clipping(width):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    from musical_scumme.karaoke_view import KaraokeView
    from musical_scumme.lyrics import KaraokeFrame

    app = QApplication.instance() or QApplication([])
    if not QFontDatabase.families() and os.path.exists("C:/Windows/Fonts/segoeui.ttf"):
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    view = KaraokeView()
    view.resize(width, 280)
    text = "<Here & now> we carry this much longer lyric phrase across the room and let every word stay readable"
    frame = KaraokeFrame(current=text, upcoming="The next phrase", highlight=18, progress=0.3)
    view.show_frame(frame)
    view.show()
    app.processEvents()
    assert not view.grab().isNull()
    assert view.current.text() == text
    assert view.current._layout_height <= view.current.height()
    assert view.upcoming.text() == "The next phrase"
    assert view.line_progress.value() == 300
    view.close()


def test_score_word_events_join_only_hyphenated_syllables_and_hide_melisma():
    tokens = ("Bright", "lights", "are", "glow-", "ing_", "Who", "can", "see", "them?", "We", "can")
    events = tuple(MidiLyric(index * 300, text) for index, text in enumerate(tokens))
    cues = lyric_cues(events)
    assert [cue.text for cue in cues] == ["Bright lights are glowing", "Who can see them?", "We can"]
    assert cues[0].word_times == ((0, 0), (7, 300), (14, 600), (18, 900), (22, 1200))
    assert LyricTimeline(cues).frame_at(1200).highlight == 22


def test_score_standalone_hold_markers_do_not_add_words():
    cues = lyric_cues((MidiLyric(0, "Hold_"), MidiLyric(200, "_"), MidiLyric(400, "on")))
    assert cues[0].text == "Hold on"
    assert cues[0].word_times == ((0, 0), (5, 400))


def test_space_free_word_stream_is_wrapped_at_word_boundaries():
    events = tuple(MidiLyric(index * 200, "word") for index in range(30))
    cues = lyric_cues(events)
    assert len(cues) == 3
    assert all(cue.text == " ".join(["word"] * 10) for cue in cues)
    assert [cue.time_ms for cue in cues] == [0, 2000, 4000]


def test_explicit_spaces_keep_unmarked_syllables_joined():
    events = (MidiLyric(0, "Shin"), MidiLyric(100, "ing "), MidiLyric(200, "lights"))
    assert lyric_cues(events)[0].text == "Shining lights"


def test_parallel_midi_lyric_tracks_do_not_interleave(tmp_path):
    import mido

    from musical_scumme.midi_engine import load_midi
    midi = mido.MidiFile()
    midi.tracks.append(mido.MidiTrack([
        mido.MetaMessage("lyrics", text="Bright"),
        mido.MetaMessage("lyrics", text="lights", time=480),
        mido.MetaMessage("lyrics", text="shine_", time=480),
    ]))
    midi.tracks.append(mido.MidiTrack([
        mido.MetaMessage("lyrics", text="Oh", time=240),
        mido.MetaMessage("lyrics", text="oh", time=480),
    ]))
    path = tmp_path / "parallel.mid"
    midi.save(path)
    before = path.read_bytes()
    project = load_midi(path)
    assert [cue.text for cue in project.lyrics] == ["Bright", "lights", "shine_"]
    assert lyric_cues(project.lyrics)[0].text == "Bright lights shine"
    assert path.read_bytes() == before
