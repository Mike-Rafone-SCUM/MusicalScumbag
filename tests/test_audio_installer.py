import os
import subprocess
import sys
from pathlib import Path

import pytest

from validate_audio_runtime import validate_model_path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install_audio_tools.ps1"
VALIDATOR = ROOT / "validate_audio_runtime.py"


def test_audio_installer_does_not_treat_missing_py_runtime_as_fatal_probe() -> None:
    script = INSTALLER.read_text(encoding="utf-8")

    assert "function Invoke-PythonProbe" in script
    assert "$ErrorActionPreference = 'Continue'" in script
    assert "2>$null" in script
    assert "& py " not in script


def test_audio_installer_bootstraps_private_signed_python_without_path_changes() -> None:
    script = INSTALLER.read_text(encoding="utf-8")

    assert "python-$bootstrapVersion-amd64.exe" in script
    assert "Get-AuthenticodeSignature" in script
    assert "Python Software Foundation" in script
    assert "InstallAllUsers=0" in script
    assert "PrependPath=0" in script
    assert "AssociateFiles=0" in script
    assert "Shortcuts=0" in script
    assert "[switch]$NoBootstrap" in script


def test_audio_installer_keeps_audio_environment_isolated() -> None:
    script = INSTALLER.read_text(encoding="utf-8")

    assert "'audio-runtime'" in script
    assert "-m', 'venv'" in script
    assert "requirements-audio.txt" in script
    assert "audio-tools-install.log" in script
    assert "@PrefixArguments -I -c $probe" in script
    assert "'-I', '-m', 'pip'" in script
    assert "'-I', $validationScript" in script


def test_audio_installer_marks_only_validated_runtimes_ready() -> None:
    installer = INSTALLER.read_text(encoding="utf-8")
    repair = (ROOT / "Repair Existing Audio Runtime v2.1.3.ps1").read_text(encoding="utf-8")

    for script in (installer, repair):
        assert ".musicalscumme-audio-ready-v1" in script
        assert "Remove-Item -LiteralPath $readyMarker" in script
        assert "Set-Content -LiteralPath $readyMarker" in script


def test_build_script_falls_back_when_py_launcher_has_no_runtime() -> None:
    script = (ROOT / "build_exe.ps1").read_text(encoding="utf-8")

    assert "function Test-BuildPython" in script
    assert "$ErrorActionPreference = 'Continue'" in script
    assert "python.exe" in script
    assert "python3.exe" in script
    assert "if (Get-Command py " not in script
    assert "[string]$OutputRoot" in script
    assert "--distpath $distRoot" in script


def test_audio_installer_pins_pkg_resources_compatible_setuptools() -> None:
    script = INSTALLER.read_text(encoding="utf-8")
    constraints = (ROOT / "requirements-audio-constraints.txt").read_text(encoding="utf-8")

    assert "$setuptoolsVersion = '80.10.2'" in script
    assert "setuptools==$setuptoolsVersion" in script
    assert "--constraint" in script
    assert "requirements-audio-constraints.txt" in script
    assert "import pkg_resources" in VALIDATOR.read_text(encoding="utf-8")
    assert "setuptools==80.10.2" in constraints


def test_audio_repair_preserves_existing_large_runtime() -> None:
    repair = (ROOT / "Repair Audio Tools.bat").read_text(encoding="utf-8")

    assert "install_audio_tools.ps1" in repair
    assert "-Reinstall" not in repair


def test_packaged_build_includes_audio_constraint_file() -> None:
    script = (ROOT / "build_exe.ps1").read_text(encoding="utf-8")

    assert "requirements-audio-constraints.txt;." in script
    assert "validate_audio_runtime.py;." in script


def test_packaged_build_includes_isolated_uvr_resources() -> None:
    script = (ROOT / "build_exe.ps1").read_text(encoding="utf-8")
    installer = (ROOT / "install_separation_tools.ps1").read_text(encoding="utf-8")

    for resource in (
        "separation_worker.py;.",
        "install_separation_tools.ps1;.",
        "requirements-separation.txt;.",
        "requirements-separation-cuda.txt;.",
        "validate_separation_runtime.py;.",
    ):
        assert resource in script
    assert ".musicalscumme-separation-ready-v1" in installer
    assert "audio-separator==0.44.3" not in installer
    assert "requirements-separation.txt" in installer
    assert "requirements-separation-cuda.txt" in installer
    assert "https://download.pytorch.org/whl/cu128" in installer
    assert "--force-reinstall" not in installer
    assert "--download_model_only" in installer
    assert "model_bs_roformer_ep_317_sdr_12.9755.ckpt" in installer


def test_audio_validation_uses_script_file_not_fragile_inline_python() -> None:
    installer = INSTALLER.read_text(encoding="utf-8")
    repair = (ROOT / "Repair Existing Audio Runtime v2.1.3.ps1").read_text(encoding="utf-8")

    assert "$validationScript" in installer
    assert "$validationCode" not in installer
    assert "@('-c', $validationCode)" not in installer
    assert "$validationScript" in repair
    assert "$validationCode" not in repair


def test_audio_runtime_validator_is_valid_python_and_checks_required_stack() -> None:
    source = VALIDATOR.read_text(encoding="utf-8")
    compile(source, str(VALIDATOR), "exec")

    assert 'metadata.version("basic-pitch")' not in source  # helper centralises metadata access
    assert "installed_version('basic-pitch')" in source
    assert 'installed_version("setuptools")' in source
    assert "import pkg_resources" in source
    assert "ICASSP_2022_MODEL_PATH" in source
    assert "callable(predict)" in source


def test_audio_runtime_validator_accepts_savedmodel_directory(tmp_path: Path) -> None:
    saved_model = tmp_path / "nmp"
    saved_model.mkdir()
    (saved_model / "saved_model.pb").write_bytes(b"model")

    validate_model_path(saved_model)

    with pytest.raises(SystemExit, match="missing or incomplete"):
        validate_model_path(tmp_path / "missing")


def test_standalone_repair_runs_validator_by_file_path() -> None:
    repair = (ROOT / "Repair Existing Audio Runtime v2.1.3.ps1").read_text(encoding="utf-8")

    assert "validate_audio_runtime.py" in repair
    assert "--expected-setuptools" in repair
    assert "python -c" in repair  # retained only in explanatory comment
    assert "@('-c'" not in repair


def test_audio_runtime_validator_executes_from_a_real_script_file(tmp_path: Path) -> None:
    fake_root = tmp_path / "fake_runtime"
    fake_root.mkdir()
    (fake_root / "pkg_resources.py").write_text("# compatibility shim\n", encoding="utf-8")
    (fake_root / "mido.py").write_text("class MidiFile:\n    pass\n", encoding="utf-8")

    package = fake_root / "basic_pitch"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    model = package / "model.savedmodel"
    model.write_text("model", encoding="utf-8")
    (package / "inference.py").write_text(
        f'ICASSP_2022_MODEL_PATH = r"{model}"\n'
        "def predict(*args, **kwargs):\n"
        "    return None\n",
        encoding="utf-8",
    )

    for distribution, version in (
        ("setuptools", "80.10.2"),
        ("basic-pitch", "0.4.0"),
        ("mido", "1.3.3"),
    ):
        metadata_dir = fake_root / f"{distribution.replace('-', '_')}-{version}.dist-info"
        metadata_dir.mkdir()
        (metadata_dir / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {distribution}\nVersion: {version}\n",
            encoding="utf-8",
        )

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(fake_root)
    result = subprocess.run(
        [sys.executable, "-S", str(VALIDATOR), "--expected-setuptools", "80.10.2"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert "Audio runtime validated:" in result.stdout
    assert "BasicPitch=0.4.0" in result.stdout
    assert "Setuptools=80.10.2" in result.stdout
