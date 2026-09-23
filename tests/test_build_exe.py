import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_qt_packaging_keeps_native_input_and_rendering_without_unused_plugin_stacks(monkeypatch):
    plugins = [
        (name, "PySide6/plugins") for name in (
            "qtvirtualkeyboardplugin.dll", "qpdf.dll", "qtuiotouchplugin.dll",
            "qwindows.dll", "qoffscreen.dll", "qjpeg.dll", "qsvg.dll",
            "qwindowsvistastyle.dll", "opengl32sw.dll",
        )
    ]
    monkeypatch.setitem(sys.modules, "PyInstaller.utils.hooks.qt", SimpleNamespace(
        add_qt6_dependencies=lambda _path: (["PySide6.QtCore"], plugins, [("qt_en.qm", "translations")]),
    ))
    hook = Path(__file__).resolve().parents[1] / "packaging_hooks/hook-PySide6.QtGui.py"
    result = runpy.run_path(str(hook))
    assert result["binaries"] == plugins[3:]
    assert result["hiddenimports"] == ["PySide6.QtCore"]
    assert result["datas"] == [("qt_en.qm", "translations")]


@pytest.mark.skipif(os.name != "nt", reason="Windows packaging environment")
@pytest.mark.parametrize("fail_build", [False, True])
def test_build_path_prefers_system_runtime_and_restores_caller_path(tmp_path, fail_build):
    shell = shutil.which("pwsh.exe") or shutil.which("powershell.exe")
    assert shell
    source = (Path(__file__).resolve().parents[1] / "build_exe.ps1").read_text(encoding="utf-8")
    # Execute the real environment guard with a simulated build body. Never
    # run dependency installation or delete build/output directories in tests.
    prefix = source[source.index("$originalBuildPath ="):source.index("& $venvPython -m PyInstaller")]
    suffix = source[source.index("}\nfinally {", source.index("& $venvPython -m PyInstaller")):]
    suffix = suffix[:suffix.index('Write-Host "Built:')]
    probe = tmp_path / "build-path-probe.ps1"
    body = r"""
if (($env:PATH -split ';')[0] -ne "$env:SystemRoot\System32") { throw 'Wrong runtime priority' }
$script:enteredBuild = $true
"""
    if fail_build:
        body += "throw 'simulated build failure'\n"
    probe.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        "$env:PATH = 'C:\\unrelated-tools;C:\\other-tools'\n"
        "$expectedPath = $env:PATH\n$script:enteredBuild = $false\n"
        "try {\n" + prefix + body + suffix + "\n} catch {\n"
        "if ($_.Exception.Message -ne 'simulated build failure') { throw }\n}\n"
        "if (-not $script:enteredBuild) { throw 'Build body was not run' }\n"
        "if ($env:PATH -ne $expectedPath) { throw 'Caller PATH was not restored' }\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(probe)],
        capture_output=True, text=True, timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, result.stdout + result.stderr
