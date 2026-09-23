import os

from musical_scumme import audio_tools


def test_audio_status_requires_successful_validation_marker(tmp_path, monkeypatch):
    runtime_root = tmp_path / "audio-runtime"
    runtime_python = runtime_root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_text("python", encoding="utf-8")
    worker = tmp_path / "audio_worker.py"
    worker.write_text("# worker\n", encoding="utf-8")

    monkeypatch.setattr(audio_tools, "audio_runtime_dir", lambda: runtime_root)
    monkeypatch.setattr(audio_tools, "resource_path", lambda _name: worker)

    incomplete = audio_tools.audio_tools_status()
    assert not incomplete.available
    assert "needs validation or repair" in incomplete.message

    (runtime_root / audio_tools.AUDIO_RUNTIME_READY_MARKER).write_text("validated", encoding="ascii")
    ready = audio_tools.audio_tools_status()
    assert ready.available


def test_audio_worker_uses_isolated_python_mode(monkeypatch, tmp_path):
    runtime_python = tmp_path / "python.exe"
    worker = tmp_path / "audio_worker.py"
    monkeypatch.setattr(
        audio_tools,
        "audio_tools_status",
        lambda: audio_tools.AudioToolsStatus(True, runtime_python, worker, "ready"),
    )

    program, arguments = audio_tools.audio_worker_command(
        "input.wav",
        "output.mid",
        onset_threshold=0.5,
        frame_threshold=0.3,
        minimum_note_ms=100,
    )

    assert program == str(runtime_python)
    assert arguments[:4] == ["-I", "-X", "utf8", str(worker)]


def test_audio_worker_command_passes_scum_pitch_focus(monkeypatch, tmp_path):
    runtime_python = tmp_path / "python.exe"
    worker = tmp_path / "audio_worker.py"
    monkeypatch.setattr(
        audio_tools,
        "audio_tools_status",
        lambda: audio_tools.AudioToolsStatus(True, runtime_python, worker, "ready"),
    )

    _program, arguments = audio_tools.audio_worker_command(
        "input.wav",
        "output.mid",
        onset_threshold=0.45,
        frame_threshold=0.30,
        minimum_note_ms=90,
        minimum_frequency=65.406,
        maximum_frequency=2093.005,
    )

    assert arguments[-4:] == [
        "--minimum-frequency",
        "65.406",
        "--maximum-frequency",
        "2093.005",
    ]
