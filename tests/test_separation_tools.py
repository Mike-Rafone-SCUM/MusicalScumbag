import json
import os

import pytest

from musical_scumme import separation_tools


def test_separation_status_requires_matching_validated_marker(tmp_path, monkeypatch):
    runtime_root = tmp_path / "separation-runtime"
    runtime_python = runtime_root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_text("python", encoding="utf-8")
    worker = tmp_path / "separation_worker.py"
    worker.write_text("# worker\n", encoding="utf-8")

    monkeypatch.setattr(separation_tools, "separation_runtime_dir", lambda: runtime_root)
    monkeypatch.setattr(separation_tools, "resource_path", lambda _name: worker)

    incomplete = separation_tools.separation_tools_status()
    assert not incomplete.available
    assert "needs installation or repair" in incomplete.message

    marker = runtime_root / separation_tools.SEPARATION_RUNTIME_READY_MARKER
    marker.write_text(json.dumps({"model": "old.ckpt", "backend": "cuda"}), encoding="utf-8")
    stale = separation_tools.separation_tools_status()
    assert not stale.available
    assert "stale model marker" in stale.message

    marker.write_text(
        json.dumps({"model": separation_tools.SEPARATION_MODEL_FILENAME, "backend": "cuda"}),
        encoding="utf-8",
    )
    ready = separation_tools.separation_tools_status()
    assert ready.available
    assert ready.backend == "CUDA"


def test_separation_runtime_pointer_can_target_large_secondary_drive(tmp_path, monkeypatch):
    data_root = tmp_path / "local-data"
    target = tmp_path / "secondary-drive" / "separator"
    data_root.mkdir()
    (data_root / separation_tools.SEPARATION_RUNTIME_POINTER).write_text(str(target), encoding="utf-8")
    monkeypatch.delenv("MUSICALSCUMME_SEPARATION_RUNTIME", raising=False)
    monkeypatch.setattr(separation_tools, "musicalscumme_data_dir", lambda: data_root)

    assert separation_tools.separation_runtime_dir() == target


def test_separation_worker_uses_isolated_mode_and_explicit_stems(monkeypatch, tmp_path):
    runtime_python = tmp_path / "python.exe"
    worker = tmp_path / "separation_worker.py"
    model_dir = tmp_path / "models"
    monkeypatch.setattr(
        separation_tools,
        "separation_tools_status",
        lambda: separation_tools.SeparationToolsStatus(
            True,
            runtime_python,
            worker,
            model_dir,
            "ready",
            backend="CUDA",
        ),
    )

    program, arguments = separation_tools.separation_worker_command(
        "song.mp3",
        "song.vocals.wav",
        "song.instrumental.wav",
    )

    assert program == str(runtime_python)
    assert arguments[:4] == ["-I", "-X", "utf8", str(worker)]
    assert arguments[arguments.index("--model") + 1] == separation_tools.SEPARATION_MODEL_FILENAME
    assert arguments[arguments.index("--vocals-output") + 1].endswith("song.vocals.wav")
    assert arguments[arguments.index("--instrumental-output") + 1].endswith("song.instrumental.wav")


def test_separation_worker_rejects_colliding_stem_outputs(monkeypatch, tmp_path):
    monkeypatch.setattr(
        separation_tools,
        "separation_tools_status",
        lambda: separation_tools.SeparationToolsStatus(
            True,
            tmp_path / "python.exe",
            tmp_path / "worker.py",
            tmp_path / "models",
            "ready",
        ),
    )

    with pytest.raises(ValueError, match="different output files"):
        separation_tools.separation_worker_command("song.wav", "same.wav", "same.wav")


def test_separation_stem_paths_are_deterministic_and_user_visible(tmp_path):
    vocals, instrumental = separation_tools.separation_stem_paths(tmp_path / "My Song.mp3", tmp_path / "stems")

    assert vocals == tmp_path / "stems" / "My Song.vocals.wav"
    assert instrumental == tmp_path / "stems" / "My Song.instrumental.wav"
