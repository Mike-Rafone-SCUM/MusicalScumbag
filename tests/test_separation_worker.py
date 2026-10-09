from pathlib import Path

import pytest

from separation_worker import _atomic_publish, _locate_generated_stem, _validate_wav


def test_overlap_compatibility_uses_smaller_seconds_for_higher_quality(monkeypatch):
    import separation_worker

    monkeypatch.setattr(separation_worker.inspect, "getsource", lambda _: "desired_step = int(self.overlap * sample_rate)")
    assert separation_worker._overlap_value(None, "best") == 1.0
    assert separation_worker._overlap_value(None, "fast") == 4.0
    monkeypatch.setattr(separation_worker.inspect, "getsource", lambda _: "hop_size = chunk_size // self.overlap")
    assert separation_worker._overlap_value(None, "best") == 12


def test_shifted_predictions_restore_exact_timing_and_average():
    import numpy as np

    from separation_worker import _aligned_average

    first = np.array([[1, 2], [3, 4]], dtype=np.float32)
    shifted = np.array([[0, 0], [3, 4], [5, 6]], dtype=np.float32)
    result = _aligned_average([first, shifted], [0, 1], 2)
    np.testing.assert_array_equal(result, [[2, 3], [4, 5]])


@pytest.mark.parametrize("prediction", [[[1, 2]], [[float("nan"), 0], [0, 0]]])
def test_shifted_predictions_reject_corrupt_or_truncated_audio(prediction):
    import numpy as np

    from separation_worker import _aligned_average

    with pytest.raises(RuntimeError, match="truncated or nonfinite"):
        _aligned_average([np.array(prediction)], [0], 2)


def test_quality_passes_with_fake_separator_preserve_stereo_duration(tmp_path):
    import numpy as np
    sf = pytest.importorskip("soundfile", reason="Available in the isolated separation runtime")
    from separation_worker import _separate_passes

    source = tmp_path / "input.wav"
    mix = np.column_stack((np.linspace(-0.5, 0.5, 1000), np.linspace(0.5, -0.5, 1000)))
    sf.write(source, mix, 1000, subtype="FLOAT")

    class FakeSeparator:
        calls = 0

        def separate(self, path, names):
            self.calls += 1
            audio, rate = sf.read(path, always_2d=True)
            assert len(audio) >= 12 * rate
            for stem, name in names.items():
                sf.write(tmp_path / f"{name}.wav", audio * (0.25 if stem == "Vocals" else 0.75), rate, subtype="FLOAT")

    separator = FakeSeparator()
    paths = _separate_passes(separator, source, tmp_path, "best")
    assert separator.calls == 3
    vocals, rate = sf.read(paths[0], always_2d=True)
    band, _ = sf.read(paths[1], always_2d=True)
    assert rate == 1000
    assert vocals.shape == mix.shape
    np.testing.assert_allclose(vocals + band, mix, atol=3e-7)


def test_atomic_publish_replaces_destination_without_leaving_temporary_file(tmp_path: Path):
    source = tmp_path / "generated.wav"
    destination = tmp_path / "published.wav"
    import wave

    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(44100)
        audio.writeframes(b"\x00\x00" * 100)
    destination.write_bytes(b"old stem")

    _atomic_publish(source, destination)

    _validate_wav(destination)
    assert not destination.with_suffix(".wav.tmp").exists()


def test_atomic_publish_rejects_zero_byte_separator_output(tmp_path: Path):
    source = tmp_path / "empty.wav"
    source.write_bytes(b"")

    with pytest.raises(RuntimeError, match="empty WAV stem"):
        _atomic_publish(source, tmp_path / "published.wav")


def test_locate_generated_stem_prefers_explicit_output_name(tmp_path: Path):
    explicit = tmp_path / "musicalscumme_vocals.wav"
    explicit.write_bytes(b"stem")

    assert _locate_generated_stem(tmp_path, "musicalscumme_vocals", "Vocals") == explicit

    explicit.unlink()
    with pytest.raises(RuntimeError, match="did not produce"):
        _locate_generated_stem(tmp_path, "musicalscumme_vocals", "Vocals")


@pytest.fixture
def learned_separator(tmp_path):
    """A predictable dry-stem model; tests exercise the actual worker stages."""
    from types import SimpleNamespace

    sf = pytest.importorskip("soundfile")
    import separation_worker as worker

    class FakeSeparator:
        def __init__(self, **kwargs):
            self.output_dir = kwargs.get("output_dir", str(tmp_path))
            self.output_single_stem = None
            self.arch_specific_params = {"MDXC": kwargs.get("mdxc_params", {})}
            self.model_instance = SimpleNamespace(model_run=SimpleNamespace(parameters=lambda: iter([SimpleNamespace(device="cpu")])))
            self.models = []
            self.corruption = None

        def load_model(self, model_filename):
            if model_filename in {worker.DEREVERB_MODEL, worker.DENOISE_MODEL}:
                assert self.model_instance is None, "Previous GPU weights must be released."
                assert self.output_single_stem == "dry"
                assert self.arch_specific_params["MDXC"]["override_model_segment_size"]
                assert self.arch_specific_params["MDXC"]["segment_size"] == 256
                assert self.arch_specific_params["MDXC"]["batch_size"] == 1
            self.model_instance = SimpleNamespace(model_run=SimpleNamespace(parameters=lambda: iter([SimpleNamespace(device="cpu")])))
            self.models.append(model_filename)

        def separate(self, path, names):
            import numpy as np

            audio, rate = sf.read(path, always_2d=True, dtype="float32")
            assert len(audio) >= rate * 12
            for stem, name in names.items():
                factor = (0.8 if self.models[-1] == worker.DEREVERB_MODEL else 0.5) if stem == "dry" else 0.5
                output = audio * factor
                if stem == "dry" and self.corruption:
                    if self.corruption == "frames":
                        output = output[:-1]
                    elif self.corruption == "rate":
                        rate += 1
                    elif self.corruption == "channels":
                        output = output[:, :1]
                    elif self.corruption == "nan":
                        output[10, 0] = np.nan
                    elif self.corruption == "clip":
                        output[10, 0] = 1.5
                    elif self.corruption == "missing":
                        continue
                    elif self.corruption == "load_exit":
                        raise SystemExit(1)
                sf.write(Path(self.output_dir) / f"{name}.wav", output, rate, subtype="FLOAT")

    return FakeSeparator


def _stereo_vocal(path, *, rate=44100, frames=4410):
    import numpy as np
    sf = pytest.importorskip("soundfile")

    audio = np.column_stack((np.linspace(-.4, .4, frames), np.linspace(.25, -.25, frames)))
    sf.write(path, audio, rate, subtype="PCM_24")
    return sf.read(path, always_2d=True, dtype="float32")[0]


@pytest.mark.parametrize("cleanup,expected_factor,models", [
    ("none", 1.0, []), ("dereverb", .8, ["dereverb"]), ("full", .5, ["dereverb", "denoise"]),
])
def test_learned_cleanup_order_blend_and_exact_stereo_timing(tmp_path, learned_separator, cleanup, expected_factor, models):
    import numpy as np
    import soundfile as sf

    import separation_worker as worker

    source = tmp_path / "vocals.wav"
    audio = _stereo_vocal(source)
    original = source.read_bytes()
    separator = learned_separator()
    output, treatment = worker._treat_vocals(separator, source, tmp_path, cleanup)
    actual, rate = sf.read(output, always_2d=True, dtype="float32")
    assert rate == 44100
    assert actual.shape == audio.shape
    np.testing.assert_allclose(actual, audio * expected_factor, atol=3e-7)
    assert [row["stage"] for row in treatment] == models
    assert all(row["stems"] == ["vocals"] for row in treatment)
    if cleanup != "none":
        assert separator.models[0] == worker.DEREVERB_MODEL
        assert treatment[0]["blend"] == 1.0
        assert separator.model_instance is None
    if cleanup == "full":
        assert separator.models[1] == worker.DENOISE_MODEL
        assert treatment[1]["blend"] == .75
    assert source.read_bytes() == original


@pytest.mark.parametrize("corruption", ["frames", "rate", "channels", "nan", "clip", "missing", "load_exit"])
def test_learned_stage_rejects_invalid_output_and_releases_weights(tmp_path, learned_separator, corruption):
    import separation_worker as worker

    source = tmp_path / "vocals.wav"
    _stereo_vocal(source)
    separator = learned_separator()
    separator.corruption = corruption
    with pytest.raises(RuntimeError, match="cleaned stems were not published"):
        worker._treat_vocals(separator, source, tmp_path, "full")
    assert separator.model_instance is None
    assert not (tmp_path / "dereverb/synchronized.wav").exists()


def test_cleanup_paths_reject_raw_destination_collision_and_source_overwrite(tmp_path):
    import separation_worker as worker

    vocals = tmp_path / "song.vocals.wav"
    raw_vocals = tmp_path / "song.vocals.raw.wav"
    with pytest.raises(ValueError, match="different files"):
        worker._validate_output_paths(tmp_path / "song.mp3", vocals, raw_vocals, "full")
    with pytest.raises(ValueError, match="source audio"):
        worker._validate_output_paths(raw_vocals, vocals, tmp_path / "band.wav", "full")


def test_complete_provenance_lists_exact_final_and_raw_headers(tmp_path):
    import json

    import separation_worker as worker

    source = tmp_path / "source.wav"
    _stereo_vocal(source)
    before = source.read_bytes()
    vocal = tmp_path / "source.vocals.wav"
    instrumental = tmp_path / "source.instrumental.wav"
    destinations = worker._validate_output_paths(source, vocal, instrumental, "full")
    treatment = [{"stage": "dereverb", "model": worker.DEREVERB_MODEL, "stems": ["vocals"], "blend": 1.0},
                 {"stage": "denoise", "model": worker.DENOISE_MODEL, "stems": ["vocals"], "blend": .75}]
    receipt = worker._publish_stems(worker._stat_record(source), [source] * 4, destinations,
                                    model="test.ckpt", quality="best", cleanup="full", treatment=treatment)
    metadata = json.loads(receipt.read_text())
    assert receipt == vocal.with_suffix(".uvr.json")
    assert metadata["version"] == 1
    assert metadata["source"] == worker._stat_record(source)
    assert metadata["model"] == "test.ckpt"
    assert metadata["quality"] == "best"
    assert metadata["cleanup"] == "full"
    assert metadata["segment_size"] == 256
    assert metadata["segment_seconds"] == 2.55
    assert metadata["treatment"] == treatment
    assert [row["path"] for row in metadata["outputs"]] == [str(p) for p in destinations]
    assert {(row["rate"], row["frames"], row["channels"]) for row in metadata["outputs"]} == {(44100, 4410, 2)}
    assert all(row == worker._wav_record(path) for row, path in zip(metadata["outputs"], destinations, strict=True))
    assert source.read_bytes() == before
    assert not receipt.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize("problem", ["source_changed", "mismatched_stems"])
def test_provenance_rejects_source_changes_or_desynchronized_stems_before_publication(tmp_path, problem):
    import separation_worker as worker

    source, other = tmp_path / "source.wav", tmp_path / "other.wav"
    _stereo_vocal(source)
    metadata = worker._stat_record(source)
    _stereo_vocal(other, frames=4411 if problem == "mismatched_stems" else 4410)
    if problem == "source_changed":
        source.write_bytes(source.read_bytes() + b"changed")
    destinations = [tmp_path / "vocals.wav", tmp_path / "band.wav"]
    with pytest.raises(RuntimeError, match="no stems were published"):
        worker._publish_stems(metadata, [source, other], destinations,
                             model="test", quality="best", cleanup="none", treatment=[])
    assert not any(p.exists() for p in destinations)


def test_worker_cli_defaults_to_legacy_no_cleanup(monkeypatch):
    import sys

    import separation_worker as worker

    required = ["--input", "source.mp3", "--vocals-output", "v.wav", "--instrumental-output", "i.wav",
                "--model-dir", "models", "--model", "model.ckpt"]
    monkeypatch.setattr(sys, "argv", ["separation_worker.py", *required])
    assert worker.parse_args().cleanup == "none"
    monkeypatch.setattr(sys, "argv", ["separation_worker.py", *required, "--cleanup", "full"])
    assert worker.parse_args().cleanup == "full"


def test_failed_cleanup_preserves_new_raw_pair_and_prior_finals_without_success_receipt(tmp_path, monkeypatch, learned_separator):
    import shutil
    import sys
    import types
    from argparse import Namespace

    import numpy as np
    import soundfile as sf

    import separation_worker as worker
    from musical_scumme.separation_tools import SEPARATION_MODEL_FILENAME, reusable_stems

    source = tmp_path / "source.wav"
    audio = _stereo_vocal(source)
    original = source.read_bytes()
    vocals, instrumental = tmp_path / "source.vocals.wav", tmp_path / "source.instrumental.wav"
    destinations = worker._validate_output_paths(source, vocals, instrumental, "full")
    treatment = [{"stage": "dereverb", "model": worker.DEREVERB_MODEL, "stems": ["vocals"], "blend": 1.0},
                 {"stage": "denoise", "model": worker.DENOISE_MODEL, "stems": ["vocals"], "blend": .75}]
    sidecar = worker._publish_stems(worker._stat_record(source), [source] * 4, destinations,
                                    model=SEPARATION_MODEL_FILENAME, quality="fast", cleanup="full", treatment=treatment)
    assert reusable_stems(source, vocals, instrumental, quality="fast", cleanup="full")
    prior_finals = [p.read_bytes() for p in destinations[:2]]
    args = Namespace(input=source, vocals_output=vocals, instrumental_output=instrumental,
                     model_dir=tmp_path / "models", model=SEPARATION_MODEL_FILENAME, quality="fast", cleanup="full")
    fake = learned_separator()
    fake.corruption = "missing"

    def factory(**kwargs):
        fake.output_dir = kwargs["output_dir"]
        fake.arch_specific_params = {"MDXC": kwargs["mdxc_params"]}
        return fake

    separator_module = types.ModuleType("audio_separator.separator")
    separator_module.Separator = factory
    mdxc_module = types.ModuleType("audio_separator.separator.architectures.mdxc_separator")
    mdxc_module.MDXCSeparator = types.SimpleNamespace(demix=None)
    monkeypatch.setitem(sys.modules, "audio_separator.separator", separator_module)
    monkeypatch.setitem(sys.modules, "audio_separator.separator.architectures.mdxc_separator", mdxc_module)
    monkeypatch.setitem(sys.modules, "torch", types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False)))
    monkeypatch.setattr(worker, "parse_args", lambda: args)
    monkeypatch.setenv("NUMBA_CACHE_DIR", str(tmp_path / "old-cache"))
    monkeypatch.setattr(worker, "_add_ffmpeg_to_path", lambda: "ffmpeg")
    monkeypatch.setattr(worker, "_decode_to_pcm_wav", lambda _, src, dst: shutil.copy2(src, dst))
    monkeypatch.setattr(worker.inspect, "getsource", lambda _: "desired_step = int(self.overlap * sample_rate)")
    events = []
    monkeypatch.setattr(worker, "emit", lambda event, **payload: events.append((event, payload)))
    with pytest.raises(RuntimeError, match="cleaned stems were not published"):
        worker.main()

    assert [p.read_bytes() for p in destinations[:2]] == prior_finals
    for raw in destinations[2:]:
        actual, rate = sf.read(raw, always_2d=True)
        assert rate == 44100
        np.testing.assert_allclose(actual, audio * .5, atol=3e-7)
    assert not sidecar.exists()
    assert not reusable_stems(source, vocals, instrumental, quality="fast", cleanup="full")
    assert not any(event == "complete" for event, _ in events)
    assert fake.model_instance is None
    assert source.read_bytes() == original


def test_cuda_availability_cannot_mask_cpu_model_placement(monkeypatch):
    import sys
    from types import SimpleNamespace

    import separation_worker as worker

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True)))
    separator = SimpleNamespace(model_instance=SimpleNamespace(
        model_run=SimpleNamespace(parameters=lambda: iter([SimpleNamespace(device="cpu")]))))
    with pytest.raises(RuntimeError, match="not loaded on CUDA"):
        worker._loaded_model_device(separator)
    separator.model_instance.model_run.parameters = lambda: iter([SimpleNamespace(device="cuda:0")])
    assert worker._loaded_model_device(separator) == "cuda:0"


def test_inference_cache_uses_writable_model_cache_before_numba_import(tmp_path, monkeypatch):
    import os

    import separation_worker as worker

    monkeypatch.setenv("NUMBA_CACHE_DIR", "an-old-unwritable-cache")
    cache = worker._configure_numba_cache(tmp_path / "models")
    assert cache.is_dir()
    assert os.environ["NUMBA_CACHE_DIR"] == str(cache.resolve())
    assert not list(cache.glob(".write-check-*"))


def test_inference_cache_fails_immediately_when_writes_are_denied(tmp_path, monkeypatch):
    import separation_worker as worker

    def denied(*args, **kwargs):
        raise PermissionError("Denied cache write")

    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(RuntimeError, match="cache is not writable"):
        worker._configure_numba_cache(tmp_path / "models")
