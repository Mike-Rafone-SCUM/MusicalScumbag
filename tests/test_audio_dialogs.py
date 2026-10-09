import os
import wave
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from musical_scumme import audio_tools, separation_tools, ui
from musical_scumme.ui import AudioConvertDialog, MainWindow, SongTransposerDialog

_APP: QApplication | None = None


@pytest.fixture
def app(monkeypatch):
    # Qt requires one application for the full process, including isolated runs.
    # Keep its Python wrapper alive after each function fixture releases it.
    global _APP
    monkeypatch.setattr(ui, "advanced_tools_status", lambda: audio_tools.AudioToolsStatus(False, None, None, "Not installed"))
    _APP = QApplication.instance() or QApplication([])
    existing = set(_APP.topLevelWidgets())
    yield _APP
    for widget in _APP.topLevelWidgets():
        if widget not in existing:
            widget.close()
            widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    _APP.processEvents()


def test_audio_convert_dialog_offscreen_construction(app, tmp_path):
    dialog = AudioConvertDialog()
    assert dialog.windowTitle() == "Audio to MIDI"
    assert dialog.convert_button is not None
    assert not dialog.convert_button.isEnabled()
    dialog.close()


def test_song_transposer_dialog_offscreen_construction_and_paths(app, tmp_path, monkeypatch):
    status_sep = separation_tools.SeparationToolsStatus(
        True,
        tmp_path / "python.exe",
        tmp_path / "worker.py",
        tmp_path / "models",
        "UVR ready",
        backend="CUDA",
    )
    status_audio = audio_tools.AudioToolsStatus(
        True,
        tmp_path / "python.exe",
        tmp_path / "worker.py",
        "Audio tools ready",
    )
    monkeypatch.setattr(ui, "separation_tools_status", lambda: status_sep)
    monkeypatch.setattr(ui, "audio_tools_status", lambda: status_audio)

    dialog = SongTransposerDialog()
    assert dialog.windowTitle() == "Song Transposer"
    assert dialog.process_button is not None
    assert dialog.separate_only_button is not None
    assert dialog.separation_quality_combo.currentData() == "best"
    assert dialog.separation_cleanup_combo.currentData() == "full"
    assert dialog.recover_quiet_notes_checkbox.isChecked()

    song_path = tmp_path / "Hotel California.mp3"
    song_path.write_bytes(b"dummy audio")

    dialog.set_input_path(song_path)

    assert Path(dialog.input_edit.text()) == song_path
    assert Path(dialog.raw_edit.text()) == tmp_path / "Hotel California.transcribed.mid"
    assert Path(dialog.stem_folder_edit.text()) == tmp_path / "Hotel California.uvr-stems"
    assert Path(dialog.output_edit.text()) == tmp_path / "Hotel California.transcription.mid"

    # Both process button and separate_only_button should now be enabled
    assert dialog.process_button.isEnabled()
    assert dialog.separate_only_button.isEnabled()

    # No legacy arrangement controls or game-specific default pitch filter.
    assert not hasattr(dialog, "profile_combo")
    assert dialog.stem_combo.currentData() == "both"
    assert dialog.pitch_focus_combo.currentData() == "full"

    # Selecting 'both' stems switches button label to full cover
    both_index = dialog.stem_combo.findData("both")
    assert both_index >= 0
    dialog.stem_combo.setCurrentIndex(both_index)
    dialog._stem_selected()
    assert dialog.stem_combo.currentData() == "both"
    assert "Cover" in dialog.process_button.text()

    dialog.close()


def test_song_transposer_finish_cover_processing_creates_cover_midi(app, tmp_path, monkeypatch):
    import mido

    from musical_scumme.midi_engine import load_midi

    dialog = SongTransposerDialog()

    # Create dummy raw vocal and instrumental MIDI files
    vox_path = tmp_path / "song.vocals.transcribed.mid"
    inst_path = tmp_path / "song.instrumental.transcribed.mid"
    output_path = tmp_path / "song.scum-ready.mid"

    def write_dummy_midi(p: Path, pitch: int):
        m = mido.MidiFile(type=0, ticks_per_beat=480)
        t = mido.MidiTrack()
        t.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
        t.append(mido.Message("note_on", note=pitch, velocity=64, time=0))
        t.append(mido.Message("note_off", note=pitch, velocity=0, time=480))
        t.append(mido.MetaMessage("end_of_track", time=0))
        m.tracks.append(t)
        m.save(p)

    write_dummy_midi(vox_path, 60)
    write_dummy_midi(inst_path, 48)

    # Monkeypatch QMessageBox to avoid popup in test
    monkeypatch.setattr(ui.QMessageBox, "information", lambda *args, **kwargs: None)

    dialog._finish_cover_processing(vox_path, inst_path, output_path)

    assert dialog.processed_path == output_path
    assert output_path.is_file()
    assert dialog.is_cover_arrangement is True
    assert dialog.use_button.isEnabled()

    # Check the resulting MIDI has both tracks
    project = load_midi(output_path)
    assert len(project.tracks) >= 2
    track_names = [t.name for t in project.tracks]
    assert any("Vocals" in n for n in track_names)
    assert any("Guitar" in n or "Instrumental" in n for n in track_names)
    dialog.close()


def test_main_window_audio_actions_exist(app, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    window = MainWindow()

    assert hasattr(window, "song_action")
    assert hasattr(window, "audio_action")
    assert hasattr(window, "separate_action")
    assert window.song_action in window._plan_actions
    window.close()


def test_cover_export_preserves_dense_chords_short_notes_and_wide_register(app, tmp_path):
    import mido

    from musical_scumme.midi_engine import load_midi

    source = tmp_path / "stem.mid"
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    pitches = [24, 48, 60, 67, 72, 96]
    for pitch in pitches:
        track.append(mido.Message("note_on", note=pitch, velocity=42))
    for index, pitch in enumerate(pitches):
        track.append(mido.Message("note_off", note=pitch, time=30 if index == 0 else 0))
    track.append(mido.Message("note_on", note=80, velocity=100, time=12))
    track.append(mido.Message("note_off", note=80, time=3000))
    midi.save(source)
    expected = load_midi(source).notes
    dialog = SongTransposerDialog()
    output = tmp_path / "cover.mid"
    dialog._finish_cover_processing(source, source, output)
    actual = load_midi(output).notes
    def signature(notes):
        return sorted((n.pitch, n.velocity, n.start_ms, n.end_ms) for n in notes)
    assert signature(actual) == signature([*expected, *expected])
    dialog.close()


@pytest.mark.parametrize("cover", [False, True])
def test_loading_transcription_keeps_playback_configuration(app, tmp_path, monkeypatch, cover):
    from types import SimpleNamespace

    from musical_scumme.config import AppSettings

    settings = AppSettings(performance_preset="custom", transpose=7, arrangement_mode="faithful")
    before = repr(settings)
    dialog = SimpleNamespace(processed_path=tmp_path / "song.mid", is_cover_arrangement=cover,
                             exec=lambda: ui.QDialog.DialogCode.Accepted)
    monkeypatch.setattr(ui, "SongTransposerDialog", lambda parent: dialog)
    loaded = []
    window = SimpleNamespace(settings=settings, _output_busy=lambda: False,
                             file_edit=SimpleNamespace(text=lambda: ""),
                             load_file=loaded.append, _set_status=lambda message: None)
    MainWindow.open_song_transposer(window)
    assert loaded == [str(dialog.processed_path)]
    assert repr(settings) == before


def test_song_transposer_cover_step_dispatchers(app, tmp_path, monkeypatch):
    dialog = SongTransposerDialog()

    vox_wav = tmp_path / "song.vocals.wav"
    vox_wav.write_bytes(b"dummy wav")
    inst_wav = tmp_path / "song.instrumental.wav"
    inst_wav.write_bytes(b"dummy wav")
    vox_raw = tmp_path / "song.vocals.transcribed.mid"
    inst_raw = tmp_path / "song.instrumental.transcribed.mid"

    dialog._vocals_wav_path = vox_wav
    dialog._inst_wav_path = inst_wav
    dialog._vocals_raw_path = vox_raw
    dialog._inst_raw_path = inst_raw

    started_processes = []
    worker_modes = []

    def mock_start_process(kind, prog, args, clear_log=True):
        started_processes.append((kind, prog, args))

    monkeypatch.setattr(dialog, "_start_process", mock_start_process)
    def mock_worker(*args, **kwargs):
        worker_modes.append(kwargs["mode"])
        return "python.exe", ["worker.py"]

    monkeypatch.setattr(ui, "audio_worker_command", mock_worker)

    # Test vocals step dispatch
    dialog._start_vocals_cover_transcription()
    assert len(started_processes) == 1
    assert started_processes[0][0] == "transcribe_both_vocals"

    # Test instrumental step dispatch
    dialog._start_instrumental_cover_transcription()
    assert len(started_processes) == 2
    assert started_processes[1][0] == "transcribe_both_inst"
    assert worker_modes == ["vocals", "instrumental"]
    dialog.transcription_method_combo.setCurrentIndex(dialog.transcription_method_combo.findData("polyphonic"))
    dialog._start_vocals_cover_transcription()
    assert worker_modes[-1] == "polyphonic"
    dialog._set_operation_controls_enabled(False)
    assert not dialog.transcription_method_combo.isEnabled()
    assert not dialog.separation_cleanup_combo.isEnabled()

    dialog.close()


def test_advanced_cover_dispatch_preserves_native_tracks_and_skips_old_cleanup(app, tmp_path, monkeypatch):
    from PySide6.QtCore import QProcess

    monkeypatch.setattr(ui, "advanced_tools_status", lambda: audio_tools.AudioToolsStatus(True, tmp_path / "python.exe", tmp_path / "worker.py", "Ready"))
    dialog = SongTransposerDialog()
    assert dialog.transcription_method_combo.currentData() == "advanced"
    assert dialog.stem_combo.currentData() == "both"
    assert not dialog.onset_spin.isEnabled()
    assert not dialog.frame_spin.isEnabled()
    assert dialog.recover_quiet_notes_checkbox.isEnabled()
    assert not hasattr(dialog, "profile_combo")
    dialog._vocals_wav_path = tmp_path / "vocals.wav"
    dialog._inst_wav_path = tmp_path / "backing.wav"
    dialog._pending_raw_path = tmp_path / "raw.mid"
    dialog._pending_output_path = tmp_path / "native.mid"
    calls = []

    def worker(source, raw, prepared, **kwargs):
        calls.append((source, raw, prepared, kwargs))
        return "python.exe", ["isolated.py"]

    monkeypatch.setattr(ui, "advanced_worker_command", worker)
    monkeypatch.setattr(dialog, "_start_process", lambda *args, **kwargs: None)
    dialog._start_vocals_cover_transcription()
    assert calls == [(dialog._vocals_wav_path, dialog._pending_raw_path, dialog._pending_output_path,
                      {"role": "full", "second_input": dialog._inst_wav_path, "stem_passes": True,
                       "audio_checked": True, "recover_quiet_notes": True})]
    assert dialog.is_cover_arrangement
    dialog._pending_output_path.write_bytes(b"native model MIDI")

    def forbidden(*args, **kwargs):
        pytest.fail("Native model output must bypass legacy melody/octave cleanup")

    monkeypatch.setattr(dialog, "_finish_processing", forbidden)
    monkeypatch.setattr(dialog, "_finish_cover_processing", forbidden)
    dialog._process_kind = "transcribe_advanced"
    dialog._process_finished(0, QProcess.ExitStatus.NormalExit)
    assert dialog.processed_path == dialog._pending_output_path.resolve()
    assert dialog.use_button.isEnabled()
    assert dialog._pending_output_path.read_bytes() == b"native model MIDI"
    dialog.close()


def _ready_separation_dialog(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "separation_tools_status", lambda: separation_tools.SeparationToolsStatus(
        True, tmp_path / "python.exe", tmp_path / "worker.py", tmp_path / "models", "Ready",
    ))
    monkeypatch.setattr(ui, "audio_tools_status", lambda: audio_tools.AudioToolsStatus(
        True, tmp_path / "python.exe", tmp_path / "worker.py", "Ready",
    ))
    dialog = SongTransposerDialog()
    source = tmp_path / "song.mp3"
    source.write_bytes(b"source")
    dialog.set_input_path(source)
    folder = Path(dialog.stem_folder_edit.text())
    folder.mkdir()
    return dialog, source, separation_tools.separation_stem_paths(source, folder)


def _write_test_wav(path):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(3)
        audio.setframerate(44100)
        audio.writeframes(b"\x00" * 600)


def test_separate_only_requests_full_cleanup_and_confirms_raw_outputs(app, tmp_path, monkeypatch):
    dialog, _source, (vocals, backing) = _ready_separation_dialog(tmp_path, monkeypatch)
    raw_vocals = vocals.with_name(f"{vocals.stem}.raw.wav")
    raw_vocals.write_bytes(b"old raw wav")
    prompts, commands, started = [], [], []
    monkeypatch.setattr(ui.QMessageBox, "question", lambda _parent, _title, prompt: (
        prompts.append(prompt) or ui.QMessageBox.StandardButton.Yes
    ))
    monkeypatch.setattr(ui, "separation_worker_command", lambda *args, **kwargs: (
        commands.append((args, kwargs)) or ("python.exe", ["worker.py"])
    ))
    monkeypatch.setattr(dialog, "_start_process", lambda *args, **kwargs: started.append(args))
    dialog.separate_stems_only()
    assert raw_vocals.name in prompts[0]
    assert commands[0][0][1:] == (vocals, backing)
    assert commands[0][1] == {"quality": "best", "cleanup": "full"}
    assert started[0][0] == "separate_only"
    dialog.close()


def test_full_cleanup_never_reuses_old_raw_only_stems(app, tmp_path, monkeypatch):
    dialog, _source, stems = _ready_separation_dialog(tmp_path, monkeypatch)
    for stem in stems:
        _write_test_wav(stem)
    commands, started, prompts = [], [], []
    monkeypatch.setattr(ui.QMessageBox, "question", lambda _parent, _title, prompt: (
        prompts.append(prompt) or ui.QMessageBox.StandardButton.Yes
    ))
    monkeypatch.setattr(ui.QMessageBox, "exec", lambda self: pytest.fail("Legacy stems must not be offered for full reuse"))
    monkeypatch.setattr(ui, "separation_worker_command", lambda *args, **kwargs: (
        commands.append(kwargs) or ("python.exe", ["worker.py"])
    ))
    monkeypatch.setattr(dialog, "_start_process", lambda *args, **kwargs: started.append(args))
    dialog.build_song()
    assert commands == [{"quality": "best", "cleanup": "full"}]
    assert "full cleanup" in prompts[0]
    assert started[0][0] == "separate_both"
    dialog.close()


def test_separation_only_offers_legacy_reuse_and_can_cancel_overwrite(app, tmp_path, monkeypatch):
    dialog, _source, stems = _ready_separation_dialog(tmp_path, monkeypatch)
    for stem in stems:
        _write_test_wav(stem)
    dialog.separation_cleanup_combo.setCurrentIndex(dialog.separation_cleanup_combo.findData("none"))
    transcription = []
    monkeypatch.setattr(ui.QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(ui.QMessageBox, "clickedButton", lambda self: next(
        button for button in self.buttons() if button.text() == "Reuse Stems"
    ))
    monkeypatch.setattr(dialog, "_start_vocals_cover_transcription", lambda: transcription.append(True))
    monkeypatch.setattr(ui, "separation_worker_command", lambda *args, **kwargs: pytest.fail("Reuse must skip separation"))
    dialog.build_song()
    assert transcription == [True]
    # Closing the reuse prompt does not authorize a new separation/overwrite run.
    monkeypatch.setattr(ui.QMessageBox, "clickedButton", lambda self: None)
    dialog.build_song()
    assert transcription == [True]
    dialog.close()


def test_cleanup_and_recovery_controls_follow_audio_mode_and_lock(app, tmp_path, monkeypatch):
    dialog, _source, _stems = _ready_separation_dialog(tmp_path, monkeypatch)
    assert dialog.separation_cleanup_combo.isEnabled()
    assert not dialog.recover_quiet_notes_checkbox.isEnabled()
    dialog.transcription_method_combo.setCurrentIndex(dialog.transcription_method_combo.findData("advanced"))
    assert dialog.recover_quiet_notes_checkbox.isEnabled()
    dialog._set_operation_controls_enabled(False)
    assert not dialog.separation_cleanup_combo.isEnabled()
    assert not dialog.recover_quiet_notes_checkbox.isEnabled()
    dialog._set_operation_controls_enabled(True)
    dialog.separate_checkbox.setChecked(False)
    assert not dialog.separation_cleanup_combo.isEnabled()
    dialog.transcription_method_combo.setCurrentIndex(dialog.transcription_method_combo.findData("advanced_native"))
    assert not dialog.recover_quiet_notes_checkbox.isEnabled()
    dialog.input_edit.setText(str(tmp_path / "song.mid"))
    assert not dialog.separation_cleanup_combo.isEnabled()
    assert not dialog.recover_quiet_notes_checkbox.isEnabled()
    dialog.close()


@pytest.mark.parametrize("accept", [False, True])
def test_basic_pitch_cover_confirms_both_existing_stem_midis_before_separation(app, tmp_path, monkeypatch, accept):
    dialog, source, _stems = _ready_separation_dialog(tmp_path, monkeypatch)
    vocal_midi = tmp_path / f"{source.stem}.vocals.transcribed.mid"
    backing_midi = tmp_path / f"{source.stem}.instrumental.transcribed.mid"
    vocal_midi.write_bytes(b"original vocal MIDI")
    backing_midi.write_bytes(b"original backing MIDI")
    prompts, starts = [], []

    def confirm(_parent, _title, prompt):
        prompts.append(prompt)
        return ui.QMessageBox.StandardButton.Yes if accept or backing_midi.name not in prompt else ui.QMessageBox.StandardButton.No

    monkeypatch.setattr(ui.QMessageBox, "question", confirm)
    monkeypatch.setattr(ui, "separation_worker_command", lambda *args, **kwargs: ("python.exe", ["worker.py"]))
    monkeypatch.setattr(dialog, "_start_process", lambda *args, **kwargs: starts.append(args))
    dialog.build_song()
    assert len(prompts) == 2
    assert vocal_midi.name in prompts[0]
    assert backing_midi.name in prompts[1]
    assert bool(starts) is accept
    if starts:
        assert starts[0][0] == "separate_both"
    else:
        assert dialog.progress.maximum() == 1
        assert dialog.progress.value() == 0
    assert vocal_midi.read_bytes() == b"original vocal MIDI"
    assert backing_midi.read_bytes() == b"original backing MIDI"
    dialog.close()


def test_advanced_cover_skips_unused_basic_pitch_midi_overwrite_prompts(app, tmp_path, monkeypatch):
    dialog, source, _stems = _ready_separation_dialog(tmp_path, monkeypatch)
    for role in ("vocals", "instrumental"):
        (tmp_path / f"{source.stem}.{role}.transcribed.mid").write_bytes(b"unused Basic Pitch MIDI")
    dialog.transcription_method_combo.setCurrentIndex(dialog.transcription_method_combo.findData("advanced"))
    starts = []
    monkeypatch.setattr(ui.QMessageBox, "question", lambda *args, **kwargs: pytest.fail("Advanced route does not write per-stem MIDIs"))
    monkeypatch.setattr(ui, "separation_worker_command", lambda *args, **kwargs: ("python.exe", ["worker.py"]))
    monkeypatch.setattr(dialog, "_start_process", lambda *args, **kwargs: starts.append(args))
    dialog.build_song()
    assert starts[0][0] == "separate_both"
    dialog.close()


@pytest.mark.parametrize("method,recover,expected", [
    ("advanced", True, True), ("advanced", False, False), ("advanced_native", True, False),
])
def test_quiet_recovery_dispatch_is_explicit_and_audio_checked_only(app, tmp_path, monkeypatch, method, recover, expected):
    dialog = SongTransposerDialog()
    dialog.transcription_method_combo.setCurrentIndex(dialog.transcription_method_combo.findData(method))
    dialog.recover_quiet_notes_checkbox.setChecked(recover)
    dialog._pending_raw_path = tmp_path / "raw.mid"
    dialog._pending_output_path = tmp_path / "prepared.mid"
    calls = []
    monkeypatch.setattr(ui, "advanced_worker_command", lambda *args, **kwargs: (
        calls.append(kwargs) or ("python.exe", ["worker.py"])
    ))
    monkeypatch.setattr(dialog, "_start_process", lambda *args, **kwargs: None)
    dialog._start_advanced_transcription(tmp_path / "vocals.wav", second_input=tmp_path / "backing.wav")
    assert calls[0]["recover_quiet_notes"] is expected
    assert calls[0]["audio_checked"] is (method == "advanced")
    dialog.close()


def test_advanced_uses_own_runtime_and_raw_audio_without_uvr(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "advanced_tools_status", lambda: audio_tools.AudioToolsStatus(True, tmp_path / "python.exe", tmp_path / "worker.py", "Ready"))
    monkeypatch.setattr(ui, "audio_tools_status", lambda: audio_tools.AudioToolsStatus(False, None, None, "Basic Pitch missing"))
    dialog = SongTransposerDialog()
    source = tmp_path / "song.wav"
    source.write_bytes(b"audio")
    dialog.set_input_path(source)
    dialog.separate_checkbox.setChecked(False)
    assert not dialog.process_button.isEnabled()
    dialog.transcription_method_combo.setCurrentIndex(dialog.transcription_method_combo.findData("advanced_mix"))
    assert dialog.process_button.isEnabled()
    calls = []
    dialog._pending_transcription_path = source
    dialog._pending_raw_path = tmp_path / "raw.mid"
    dialog._pending_output_path = tmp_path / "prepared.mid"
    monkeypatch.setattr(dialog, "_start_advanced_transcription", lambda path, **kwargs: calls.append((path, kwargs)))
    dialog._start_pending_transcription()
    assert calls == [(source, {"role": "full"})]
    dialog.close()
