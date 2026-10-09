import importlib.util
import json
import sys
from pathlib import Path

import mido
import pytest

from musical_scumme import advanced_tools
from musical_scumme.audio_tools import AudioToolsStatus
from musical_scumme.midi_engine import load_midi

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("musical_scumme_advanced_worker", ROOT / "advanced_worker.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
Note = MODULE.TranscribedNote


def test_native_export_preserves_vocal_sustain_across_backing_attacks_and_reattacks(tmp_path):
    notes = [Note(100, 69, 1.123, 3.456), Note(24, 48, 1.20, 1.50),
             Note(24, 48, 1.50, 1.80), Note(32, 36, 2.0, 2.7)]
    normalized = MODULE.valid_notes(notes, 5)
    path = tmp_path / "native.mid"
    MODULE.write_native_midi(normalized, path)
    project = load_midi(path)
    vocals = [n for n in project.notes if n.pitch == 69]
    assert len(vocals) == 1
    assert vocals[0].start_ms == pytest.approx(1123, abs=0.5)
    assert vocals[0].end_ms == pytest.approx(3456, abs=0.5)
    guitar = sorted((n.start_ms, n.end_ms) for n in project.notes if n.pitch == 48)
    assert guitar == [(1200, 1500), (1500, 1800)]
    assert {n.pitch for n in project.notes} == {69, 48, 36}
    assert {t.name for t in project.tracks} >= {"Vocals", "Clean guitar", "Bass"}
    midi = mido.MidiFile(path)
    vocal_track = next(t for t in midi.tracks if any(m.type == "track_name" and m.name == "Vocals" for m in t))
    assert next(m.program for m in vocal_track if m.type == "program_change") == 53


def test_role_filtering_keeps_chorus_and_excludes_drums_and_padding():
    notes = [Note(100, 60, 0, 1), Note(101, 64, 0, 1), Note(29, 48, 0, 1),
             Note(128, 36, 0, 0, is_drum=True), Note(100, 65, 9, 12),
             Note(100, 67, 11, 12), Note(100, 68, float("nan"), 2),
             Note(100, 69, 3, 2), Note(100, 150, 1, 2), Note(129, 60, 0, 1)]
    vocals = MODULE.valid_notes(notes, 10, role="vocals")
    assert [(n.program, n.pitch, n.offset) for n in vocals] == [(100, 60, 1), (101, 64, 1), (100, 65, 10)]
    backing = MODULE.valid_notes(notes, 10, role="instrumental")
    assert [(n.program, n.pitch) for n in backing] == [(30, 48)]
    raw = MODULE.valid_notes(notes, 10, include_drums=True)
    assert any(n.is_drum and n.offset == 0.12 for n in raw)


def test_native_program_classes_and_duplicate_predictions():
    notes = [Note(41, 60, 0, 1), Note(42, 60, 0, 1), Note(61, 65, 1, 2), Note(66, 67, 1, 2)]
    assert [n.program for n in MODULE.valid_notes(notes, 3)] == [48, 56, 64]


def test_failed_atomic_export_preserves_destination_and_cleans_temporary(tmp_path, monkeypatch):
    output = tmp_path / "previous.mid"
    output.write_bytes(b"previous output")

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(mido.MidiFile, "save", fail)
    with pytest.raises(OSError, match="disk full"):
        MODULE.write_native_midi([Note(24, 60, 0, 1)], output)
    assert output.read_bytes() == b"previous output"
    assert list(tmp_path.iterdir()) == [output]


def test_empty_requested_role_preserves_both_outputs(tmp_path, monkeypatch):
    monkeypatch.setenv("NUMBA_CACHE_DIR", str(tmp_path / "inherited-cache"))
    source = tmp_path / "source.wav"
    raw, prepared = tmp_path / "raw.mid", tmp_path / "prepared.mid"
    source.write_bytes(b"audio")
    for path in (raw, prepared):
        path.write_bytes(b"original")
    monkeypatch.setattr(MODULE, "load_model", lambda runtime: (object(), "cpu"))
    monkeypatch.setattr(MODULE, "infer", lambda *args: ([Note(24, 60, 0, 1)], 2))
    assert MODULE.main(["--runtime-dir", str(tmp_path), "--input", str(source), "--output", str(raw),
                        "--prepared-output", str(prepared), "--role", "vocals"]) == 1
    assert raw.read_bytes() == prepared.read_bytes() == b"original"


def test_command_validation_and_runtime_isolation(tmp_path, monkeypatch):
    status = AudioToolsStatus(True, tmp_path / "runtime/python.exe", tmp_path / "worker.py", "Ready")
    monkeypatch.setattr(advanced_tools, "advanced_tools_status", lambda: status)
    monkeypatch.setattr(advanced_tools, "advanced_runtime_dir", lambda: tmp_path / "runtime")
    source, second = tmp_path / "vocal.wav", tmp_path / "band.wav"
    raw, prepared = tmp_path / "raw.mid", tmp_path / "prepared.mid"
    program, args = advanced_tools.advanced_worker_command(source, raw, prepared, second_input=second)
    assert program == str(status.python_path)
    assert args[:3] == ["-I", "-X", "utf8"]
    assert args[args.index("--second-input") + 1] == str(second.resolve())
    assert "--onset-threshold" not in args
    with pytest.raises(ValueError, match="separate"):
        advanced_tools.advanced_worker_command(source, raw, raw)
    with pytest.raises(ValueError, match="separate"):
        advanced_tools.advanced_worker_command(source, raw, source)
    with pytest.raises(ValueError, match="role"):
        advanced_tools.advanced_worker_command(source, raw, prepared, role="both")


def test_discovery_requires_pinned_validation_marker_and_handles_bom(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    data = advanced_tools.advanced_data_dir()
    root = tmp_path / "other-drive-runtime"
    (root / "Scripts").mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "Scripts/python.exe").touch()
    (root / "bin/python").touch()
    (root / "vendor").mkdir()
    (root / "vendor/model_helper.py").touch()
    data.mkdir()
    (data / "advanced-runtime.path").write_text(str(root), encoding="utf-8-sig")
    assert advanced_tools.advanced_runtime_dir() == root
    assert not advanced_tools.advanced_tools_status().available
    marker = root / advanced_tools.READY_MARKER
    marker.write_text(json.dumps({"revision": "old"}), encoding="utf-8")
    assert not advanced_tools.advanced_tools_status().available
    marker.write_text(json.dumps({"revision": advanced_tools.MODEL_REVISION}), encoding="utf-8")
    assert not advanced_tools.advanced_tools_status().available
    marker.write_text(json.dumps({"revision": advanced_tools.MODEL_REVISION, "backend": "cuda",
                                  "evidence_version": advanced_tools.EVIDENCE_VERSION}), encoding="utf-8-sig")
    assert advanced_tools.advanced_tools_status().available


def test_downloader_excludes_unrelated_code_and_traversal():
    spec = importlib.util.spec_from_file_location("advanced_download", ROOT / "download_advanced_model.py")
    downloader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(downloader)
    for path in ["extras/auth2", "app.py", "../model_helper.py", "/model_helper.py",
                 "amt/src/utils/preprocess/a.py", "amt/src/utils/mirdata_dev/a.py", "amt/src/model/../../extras/a.py"]:
        assert not downloader.selected_path(path)
    assert downloader.selected_path("amt/src/model/ymt3.py")
    assert downloader.selected_path(downloader.MODEL)
    assert downloader.git_digest(b"test\n") == "9daeafb9864cf43055ae93beb0afd6c7d144bfa4"


def test_independent_stems_keep_vocals_from_vocal_audio_and_backing_from_backing_audio(monkeypatch):
    calls = []

    def infer(model, device, source, second_input=None, limit=None):
        calls.append((source, second_input))
        if source == Path("vocals.wav"):
            return [Note(100, 60, 1, 2), Note(24, 48, 0, 1)], 5
        return [Note(100, 72, 1, 2), Note(24, 48, 1.5, 2.5), Note(128, 36, 1, 1, is_drum=True)], 5

    monkeypatch.setattr(MODULE, "infer", infer)
    model = type("Model", (), {"audio_cfg": {"sample_rate": 16000}})()
    raw, prepared = MODULE.transcribe_parts(model, "cpu", Path("vocals.wav"), Path("backing.wav"), None, "full", True)
    assert [(n.program, n.pitch, n.onset) for n in prepared] == [(100, 60, 1), (24, 48, 1.5)]
    assert any(n.is_drum for n in raw)
    assert calls == [(Path("vocals.wav"), None), (Path("backing.wav"), None)]


def test_independent_stems_reject_different_durations(monkeypatch):
    monkeypatch.setattr(MODULE, "infer", lambda model, device, source, **kw: ([Note(100, 60, 0, 1)], 3 if source == Path("v.wav") else 4))
    model = type("Model", (), {"audio_cfg": {"sample_rate": 16000}})()
    with pytest.raises(ValueError, match="durations differ"):
        MODULE.transcribe_parts(model, "cpu", Path("v.wav"), Path("b.wav"), None, "full", True)


def test_audio_checked_export_does_not_present_guessed_instruments_as_real_tracks(tmp_path):
    path = tmp_path / "checked.mid"
    MODULE.write_native_midi([Note(100, 60, 1, 2, 90), Note(0, 48, 1, 2, 70)], path, audio_checked=True)
    project = load_midi(path)
    assert [t.name for t in project.tracks if t.note_count] == ["Vocals", "Backing (unlabelled)"]
    assert len(project.notes) == 2
    assert any("not instrument identification" in message.text
               for track in mido.MidiFile(path).tracks for message in track if message.type == "text")


@pytest.mark.parametrize("recovery", [False, True])
def test_audio_checks_use_vocal_audio_for_f0_and_backing_audio_for_spectrum(monkeypatch, recovery):
    from types import SimpleNamespace

    loads, checks = [], []

    def load(source, **kwargs):
        loads.append(source)
        return list(range(16000)), 16000

    evidence = SimpleNamespace(
        track_vocal_audio=lambda audio, rate, device, **kw: ([220], [.9], [.2], .01),
        vocal_notes_from_track=lambda *args, **kw: checks.append(
            ("vocal", kw["attack_hints"], kw["recover_quiet_notes"])) or [Note(100, 57, 0, 1)],
        harmonic_activations=lambda *args, **kw: ([48], [[1]], .02),
        supported_backing_notes=lambda notes, *args, **kw: checks.append(
            ("backing", len(notes), kw["recover_quiet_notes"])) or [Note(0, 48, 0, 1)],
    )
    monkeypatch.setitem(sys.modules, "librosa", SimpleNamespace(load=load))
    monkeypatch.setattr(MODULE, "evidence_module", lambda: evidence)
    original = [Note(100, 60, .2, .7), Note(24, 48, 0, 1)]
    selected = MODULE.checked_parts("cpu", Path("v.wav"), Path("b.wav"), None, "full", True, original,
                                    recover_quiet_notes=recovery)
    assert loads == [Path("v.wav"), Path("b.wav")]
    assert checks == [("vocal", [.2], recovery), ("backing", 2, recovery)]
    assert {(n.program, n.pitch) for n in selected} == {(100, 57), (0, 48)}


def test_audio_checked_mix_rejected_before_loading_models_or_touching_outputs(tmp_path, monkeypatch):
    source, raw, prepared = [tmp_path / name for name in ("audio.wav", "raw.mid", "prepared.mid")]
    source.write_bytes(b"audio source")
    raw.write_bytes(b"previous raw")
    prepared.write_bytes(b"previous prepared")
    monkeypatch.setattr(MODULE, "load_model", lambda *args: pytest.fail("Invalid request must fail before ML loading"))
    assert MODULE.main(["--runtime-dir", str(tmp_path), "--input", str(source), "--output", str(raw),
                        "--prepared-output", str(prepared), "--audio-checked"]) == 1
    assert source.read_bytes() == b"audio source"
    assert raw.read_bytes() == b"previous raw"
    assert prepared.read_bytes() == b"previous prepared"
    with pytest.raises(ValueError, match="both synchronized"):
        advanced_tools.advanced_worker_command(source, raw, prepared, audio_checked=True)


def test_quiet_recovery_command_requires_audio_checks_and_remains_opt_in(tmp_path, monkeypatch):
    status = AudioToolsStatus(True, tmp_path / "runtime/python.exe", tmp_path / "worker.py", "Ready")
    monkeypatch.setattr(advanced_tools, "advanced_tools_status", lambda: status)
    monkeypatch.setattr(advanced_tools, "advanced_runtime_dir", lambda: tmp_path / "runtime")
    source, raw, prepared = [tmp_path / name for name in ("audio.wav", "raw.mid", "prepared.mid")]
    _, original_args = advanced_tools.advanced_worker_command(source, raw, prepared, role="vocals", audio_checked=True)
    assert "--recover-quiet-notes" not in original_args
    _, recovery_args = advanced_tools.advanced_worker_command(
        source, raw, prepared, role="vocals", audio_checked=True, recover_quiet_notes=True)
    assert "--recover-quiet-notes" in recovery_args
    assert "--audio-checked" in recovery_args
    with pytest.raises(ValueError, match="requires audio checking"):
        advanced_tools.advanced_worker_command(source, raw, prepared, recover_quiet_notes=True)
    source.write_bytes(b"source")
    monkeypatch.setattr(MODULE, "load_model", lambda *args: pytest.fail("Invalid recovery must fail before ML loading"))
    assert MODULE.main(["--runtime-dir", str(tmp_path), "--input", str(source), "--output", str(raw),
                        "--prepared-output", str(prepared), "--recover-quiet-notes"]) == 1
    assert source.read_bytes() == b"source"
    assert not raw.exists() and not prepared.exists()


def test_quiet_recovery_changes_only_checked_output_and_preserves_native_predictions(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("NUMBA_CACHE_DIR", str(tmp_path / "inherited-cache"))
    source, raw_path, prepared_path = [tmp_path / name for name in ("audio.wav", "raw.mid", "prepared.mid")]
    source.write_bytes(b"source")
    raw = [Note(100, 70, .2, .7), Note(128, 36, .3, .42, is_drum=True)]
    selected = [Note(100, 70, .2, .7)]
    recovered = [Note(100, 60, .2, .4, 90), Note(100, 62, .4, .45, 50)]
    calls, writes = [], []
    monkeypatch.setattr(MODULE, "load_model", lambda *args: (object(), "cpu"))
    monkeypatch.setattr(MODULE, "transcribe_parts", lambda *args: (raw, selected))

    def checked(*args, **kwargs):
        calls.append((args[-1], kwargs["recover_quiet_notes"]))
        kwargs["diagnostics"].update({"recovery_enabled": True, "vocals": {
            "standard_notes": 1, "output_notes": 2, "note_count_change": 1}})
        return recovered

    monkeypatch.setattr(MODULE, "checked_parts", checked)
    monkeypatch.setattr(MODULE, "write_native_midi", lambda notes, path, **kwargs: writes.append((notes, path, kwargs)))
    assert MODULE.main(["--runtime-dir", str(tmp_path), "--input", str(source), "--output", str(raw_path),
                        "--prepared-output", str(prepared_path), "--role", "vocals",
                        "--audio-checked", "--recover-quiet-notes"]) == 0
    assert calls == [(selected, True)]
    assert writes == [(raw, raw_path, {}), (recovered, prepared_path, {"audio_checked": True})]
    assert raw == [Note(100, 70, .2, .7), Note(128, 36, .3, .42, is_drum=True)]
    assert source.read_bytes() == b"source"
    completion = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert completion["audio_evidence"] == {"recovery_enabled": True, "vocals": {
        "standard_notes": 1, "output_notes": 2, "note_count_change": 1}}


@pytest.mark.parametrize("recovery", [False, True])
def test_audio_check_diagnostics_reuse_pitch_and_spectral_inference(monkeypatch, recovery):
    from types import SimpleNamespace

    pitch, periodicity, rms = [220], [.9], [.2]
    spectral_pitches, coefficients = [48], [[1]]
    calls = {"track": 0, "spectrum": 0, "vocal_policy": 0, "backing_policy": 0}

    def track(*args, **kwargs):
        calls["track"] += 1
        return pitch, periodicity, rms, .01

    def spectrum(*args, **kwargs):
        calls["spectrum"] += 1
        return spectral_pitches, coefficients, .02

    def vocal_policy(f0, confidence, energy, **kwargs):
        calls["vocal_policy"] += 1
        assert f0 is pitch and confidence is periodicity and energy is rms
        notes = [Note(100, 57, 0, 1)]
        return notes + [Note(100, 59, 1, 1.1)] if kwargs.get("recover_quiet_notes") else notes

    def backing_policy(native, pitches, values, **kwargs):
        calls["backing_policy"] += 1
        assert pitches is spectral_pitches and values is coefficients
        notes = [Note(0, 48, 0, 1)]
        return notes + [Note(0, 52, 0, 1)] if kwargs.get("recover_quiet_notes") else notes

    monkeypatch.setitem(sys.modules, "librosa", SimpleNamespace(load=lambda *a, **kw: (list(range(32000)), 16000)))
    monkeypatch.setattr(MODULE, "evidence_module", lambda: SimpleNamespace(
        track_vocal_audio=track, harmonic_activations=spectrum,
        vocal_notes_from_track=vocal_policy, supported_backing_notes=backing_policy))
    diagnostics = {}
    selected = MODULE.checked_parts("cpu", Path("v.wav"), Path("b.wav"), None, "full", True,
                                    [Note(100, 60, 0, 1), Note(24, 48, 0, 1)],
                                    recover_quiet_notes=recovery, diagnostics=diagnostics)
    assert len(selected) == (4 if recovery else 2)
    assert calls == {"track": 1, "spectrum": 1, "vocal_policy": 2 if recovery else 1,
                     "backing_policy": 2 if recovery else 1}
    counts = {"standard_notes": 1, "output_notes": 2 if recovery else 1, "note_count_change": int(recovery)}
    assert diagnostics == {"recovery_enabled": recovery, "vocals": counts, "backing": counts}


def test_numba_cache_creation_is_verified_and_does_not_touch_package_cache(tmp_path, monkeypatch):
    inherited = tmp_path / "package" / "__pycache__"
    inherited.mkdir(parents=True)
    previous = inherited / "prior.nbc"
    previous.write_bytes(b"existing library cache")
    monkeypatch.setenv("NUMBA_CACHE_DIR", str(inherited))
    runtime = tmp_path / "runtime"
    cache = MODULE._configure_numba_cache(runtime)
    assert cache == runtime / "cache" / "numba"
    assert cache.is_dir()
    assert list(cache.iterdir()) == []
    assert MODULE.os.environ["NUMBA_CACHE_DIR"] == str(cache)
    assert previous.read_bytes() == b"existing library cache"


@pytest.mark.parametrize("failure", ["create_directory", "write_probe"])
def test_numba_cache_denial_fails_before_ml_and_preserves_midi_outputs(tmp_path, monkeypatch, capsys, failure):
    source, raw, prepared = [tmp_path / name for name in ("source.wav", "raw.mid", "prepared.mid")]
    source.write_bytes(b"source audio")
    raw.write_bytes(b"previous raw")
    prepared.write_bytes(b"previous checked")
    runtime = tmp_path / "runtime"
    cache = runtime / "cache" / "numba"
    inherited = str(tmp_path / "previous-cache")
    monkeypatch.setenv("NUMBA_CACHE_DIR", inherited)
    if failure == "create_directory":
        original_mkdir = Path.mkdir

        def denied_mkdir(path, *args, **kwargs):
            if path == cache:
                raise PermissionError("Directory ACL denies creation")
            return original_mkdir(path, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", denied_mkdir)
    else:
        original_open = Path.open

        def denied_probe(path, *args, **kwargs):
            if path.parent == cache and path.name.startswith(".write-check-"):
                raise PermissionError("Directory ACL denies writing")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(Path, "open", denied_probe)
    monkeypatch.setattr(MODULE, "load_model", lambda *args: pytest.fail("Denied cache must fail before ML import"))
    assert MODULE.main(["--runtime-dir", str(runtime), "--input", str(source), "--output", str(raw),
                        "--prepared-output", str(prepared)]) == 1
    error = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert error["event"] == "error"
    assert "advanced inference cache is not writable" in error["message"]
    assert str(cache) in error["message"]
    assert "Move or repair" in error["message"]
    assert MODULE.os.environ["NUMBA_CACHE_DIR"] == inherited
    assert source.read_bytes() == b"source audio"
    assert raw.read_bytes() == b"previous raw" and prepared.read_bytes() == b"previous checked"
    assert not list(cache.glob(".write-check-*"))
