import json
import os
import wave

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
    assert arguments[arguments.index("--quality") + 1] == "best"
    assert arguments[arguments.index("--cleanup") + 1] == "none"
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


def test_reuse_rejects_old_and_truncated_stems(tmp_path):
    source = tmp_path / "song.mp3"
    source.write_bytes(b"source")
    stem = tmp_path / "vocals.wav"
    with wave.open(str(stem), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(3)
        audio.setframerate(44100)
        audio.writeframes(b"\x00" * 600)
    assert separation_tools.reusable_stem(source, stem)
    os.utime(stem, ns=(1, 1))
    assert not separation_tools.reusable_stem(source, stem)
    os.utime(stem, ns=(source.stat().st_mtime_ns + 1, source.stat().st_mtime_ns + 1))
    stem.write_bytes(stem.read_bytes()[:-6])
    assert not separation_tools.reusable_stem(source, stem)


@pytest.mark.parametrize("cleanup", ["none", "dereverb", "full"])
def test_worker_command_requests_selected_cleanup(monkeypatch, tmp_path, cleanup):
    monkeypatch.setattr(separation_tools, "separation_tools_status", lambda: separation_tools.SeparationToolsStatus(
        True, tmp_path / "python.exe", tmp_path / "worker.py", tmp_path / "models", "ready",
    ))
    _, arguments = separation_tools.separation_worker_command(
        tmp_path / "song.mp3", tmp_path / "vocals.wav", tmp_path / "instrumental.wav", cleanup=cleanup,
    )
    assert arguments[arguments.index("--cleanup") + 1] == cleanup


def test_worker_command_rejects_cleanup_source_and_output_collisions(monkeypatch, tmp_path):
    monkeypatch.setattr(separation_tools, "separation_tools_status", lambda: separation_tools.SeparationToolsStatus(
        True, tmp_path / "python.exe", tmp_path / "worker.py", tmp_path / "models", "ready",
    ))
    with pytest.raises(ValueError, match="Unknown UVR cleanup"):
        separation_tools.separation_worker_command("song.mp3", "vocals.wav", "band.wav", cleanup="magic")
    with pytest.raises(ValueError, match="source audio"):
        separation_tools.separation_worker_command("vocals.raw.wav", "vocals.wav", "band.wav", cleanup="full")
    with pytest.raises(ValueError, match="different output"):
        separation_tools.separation_worker_command("song.mp3", "vocals.wav", "vocals.raw.wav", cleanup="full")


def _write_stem(path, frames=100):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(3)
        audio.setframerate(44100)
        audio.writeframes(b"\x00" * frames * 6)


def _cached_stems(tmp_path, cleanup="full"):
    source = tmp_path / "song.mp3"
    source.write_bytes(b"source")
    vocals, backing = separation_tools.separation_stem_paths(source, tmp_path)
    outputs = separation_tools.separation_output_paths(vocals, backing, cleanup=cleanup)
    recorded = []
    for stem in outputs[:-1]:
        _write_stem(stem)
        file_stat = stem.stat()
        recorded.append({"path": str(stem.resolve()), "size": file_stat.st_size, "mtime_ns": file_stat.st_mtime_ns,
                         "rate": 44100, "frames": 100, "channels": 2})
    treatment = []
    if cleanup != "none":
        treatment.append({"stage": "dereverb", "model": separation_tools.SEPARATION_DEREVERB_MODEL,
                          "stems": ["vocals"], "blend": 1.0})
    if cleanup == "full":
        treatment.append({"stage": "denoise", "model": separation_tools.SEPARATION_DENOISE_MODEL,
                          "stems": ["vocals"], "blend": 0.75})
    source_stat = source.stat()
    metadata = {"version": 1, "model": separation_tools.SEPARATION_MODEL_FILENAME, "quality": "best", "cleanup": cleanup,
                "segment_size": separation_tools.SEPARATION_SEGMENT_SIZE,
                "source": {"path": str(source.resolve()), "size": source_stat.st_size, "mtime_ns": source_stat.st_mtime_ns},
                "outputs": recorded, "treatment": treatment}
    outputs[-1].write_text(json.dumps(metadata), encoding="utf-8")
    return source, vocals, backing, outputs[-1], metadata


@pytest.mark.parametrize("cleanup", ["none", "dereverb", "full"])
def test_reuse_accepts_only_matching_complete_treatment(tmp_path, cleanup):
    source, vocals, backing, _manifest, _metadata = _cached_stems(tmp_path, cleanup)
    assert separation_tools.reusable_stems(source, vocals, backing, quality="best", cleanup=cleanup)
    assert not separation_tools.reusable_stems(source, vocals, backing, quality="balanced", cleanup=cleanup)
    other_cleanup = "none" if cleanup != "none" else "full"
    assert not separation_tools.reusable_stems(source, vocals, backing, quality="best", cleanup=other_cleanup)


def test_legacy_raw_stems_cannot_skip_cleanup(tmp_path):
    source, vocals, backing, manifest, _metadata = _cached_stems(tmp_path, "none")
    manifest.unlink()
    assert separation_tools.reusable_stems(source, vocals, backing, quality="best", cleanup="none")
    assert not separation_tools.reusable_stems(source, vocals, backing, quality="best", cleanup="full")
    assert not separation_tools.reusable_stems(source, vocals, backing, quality="best", cleanup="dereverb")


@pytest.mark.parametrize("cleanup", ["none", "dereverb", "full"])
def test_reuse_reads_actual_worker_provenance_without_runtime_imports(tmp_path, cleanup):
    import separation_worker

    source, vocals, backing, manifest, metadata = _cached_stems(tmp_path, cleanup)
    manifest.unlink()
    outputs = list(separation_tools.separation_output_paths(vocals, backing, cleanup=cleanup)[:-1])
    separation_worker._publish_stems(
        separation_worker._stat_record(source), outputs, outputs,
        model=separation_tools.SEPARATION_MODEL_FILENAME, quality="best", cleanup=cleanup,
        treatment=metadata["treatment"],
    )
    assert separation_tools.reusable_stems(source, vocals, backing, quality="best", cleanup=cleanup)


@pytest.mark.parametrize("damage", [
    "source", "model", "segment_size", "missing_segment_size", "treatment", "missing_raw", "changed_raw",
    "truncated", "unaligned", "corrupt",
])
def test_reuse_rejects_stale_incomplete_or_unaligned_treatment(tmp_path, damage):
    source, vocals, backing, manifest, metadata = _cached_stems(tmp_path)
    raw = vocals.with_name(f"{vocals.stem}.raw.wav")
    if damage == "source":
        source.write_bytes(b"changed source")
    elif damage == "model":
        metadata["model"] = "older.ckpt"
    elif damage == "segment_size":
        metadata["segment_size"] = 801
    elif damage == "missing_segment_size":
        metadata.pop("segment_size")
    elif damage == "treatment":
        metadata["treatment"][1]["blend"] = 1.0
    elif damage == "missing_raw":
        raw.unlink()
    elif damage == "changed_raw":
        _write_stem(raw, frames=90)
    elif damage == "truncated":
        backing.write_bytes(backing.read_bytes()[:-6])
    elif damage == "unaligned":
        _write_stem(backing, frames=99)
        metadata["outputs"][1].update(size=backing.stat().st_size, mtime_ns=backing.stat().st_mtime_ns, frames=99)
    if damage == "corrupt":
        manifest.write_text("not json", encoding="utf-8")
    else:
        manifest.write_text(json.dumps(metadata), encoding="utf-8")
    assert not separation_tools.reusable_stems(source, vocals, backing, quality="best", cleanup="full")
