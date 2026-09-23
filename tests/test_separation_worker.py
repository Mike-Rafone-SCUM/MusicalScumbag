from pathlib import Path

import pytest

from separation_worker import _atomic_publish, _locate_generated_stem, _validate_wav


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
