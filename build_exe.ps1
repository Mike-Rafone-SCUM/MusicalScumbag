[CmdletBinding()]
param(
    [switch]$OneFile,
    [switch]$CleanEnvironment,
    [string]$OutputRoot
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if ($CleanEnvironment -and (Test-Path -LiteralPath '.build-venv')) {
    Remove-Item -LiteralPath '.build-venv' -Recurse -Force
}

function Test-BuildPython {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [string[]]$PrefixArguments = @()
    )

    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Executable @PrefixArguments -c "import struct, sys; raise SystemExit(0 if sys.version_info >= (3,11) and struct.calcsize('P') == 8 else 2)" 2>$null
        $exitCode = $LASTEXITCODE
    }
    catch {
        return $false
    }
    finally {
        $ErrorActionPreference = $oldPreference
    }
    return $exitCode -eq 0
}

$pythonExe = $null
$pythonArgs = @()
$candidates = @()
$pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
if ($pyCommand) {
    $candidates += [pscustomobject]@{ Exe = $pyCommand.Source; Args = @('-3') }
}
foreach ($commandName in @('python.exe', 'python3.exe')) {
    $command = Get-Command $commandName -ErrorAction SilentlyContinue
    if ($command) {
        $candidates += [pscustomobject]@{ Exe = $command.Source; Args = @() }
    }
}

foreach ($candidate in $candidates) {
    if (Test-BuildPython -Executable $candidate.Exe -PrefixArguments $candidate.Args) {
        $pythonExe = $candidate.Exe
        $pythonArgs = @($candidate.Args)
        break
    }
}
if (-not $pythonExe) {
    throw '64-bit Python 3.11 or newer was not found. The Python launcher may exist without an installed runtime.'
}

$venvPython = Join-Path $PSScriptRoot '.build-venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    & $pythonExe @pythonArgs -m venv .build-venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the build environment.' }
}

& $venvPython -m pip install --disable-pip-version-check --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
& $venvPython -m pip install --disable-pip-version-check -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }

$distRoot = if ($OutputRoot) {
    [System.IO.Path]::GetFullPath($OutputRoot)
}
else {
    Join-Path $PSScriptRoot 'release'
}
$workDir = if ($OutputRoot) { Join-Path $PSScriptRoot ("build\" + (Split-Path -Leaf $distRoot)) } else { Join-Path $PSScriptRoot 'build\MusicalScumbag' }
Remove-Item -LiteralPath $workDir, $distRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath MusicalScumbag.spec, MusicalScumme.spec -Force -ErrorAction SilentlyContinue

# Qt imports the Windows ICU API. Prefer System32 over unrelated developer
# tools on PATH (for example Poppler's incompatible, version-suffixed ICU).
$originalBuildPath = $env:PATH
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot;$originalBuildPath"
try {
& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name MusicalScumbag `
    --version-file "$PSScriptRoot\version_info.txt" `
    --distpath $distRoot `
    --paths $PSScriptRoot `
    --additional-hooks-dir "$PSScriptRoot\packaging_hooks" `
    --hidden-import rtmidi `
    --add-data "$PSScriptRoot\audio_worker.py;." `
    --add-data "$PSScriptRoot\advanced_worker.py;." `
    --add-data "$PSScriptRoot\audio_evidence.py;." `
    --add-data "$PSScriptRoot\install_advanced_tools.ps1;." `
    --add-data "$PSScriptRoot\download_advanced_model.py;." `
    --add-data "$PSScriptRoot\requirements-advanced.txt;." `
    --add-data "$PSScriptRoot\install_audio_tools.ps1;." `
    --add-data "$PSScriptRoot\requirements-audio.txt;." `
    --add-data "$PSScriptRoot\requirements-audio-constraints.txt;." `
    --add-data "$PSScriptRoot\validate_audio_runtime.py;." `
    --add-data "$PSScriptRoot\separation_worker.py;." `
    --add-data "$PSScriptRoot\install_separation_tools.ps1;." `
    --add-data "$PSScriptRoot\requirements-separation.txt;." `
    --add-data "$PSScriptRoot\requirements-separation-cuda.txt;." `
    --add-data "$PSScriptRoot\validate_separation_runtime.py;." `
    --exclude-module PySide6.QtWebEngineCore `
    --exclude-module PySide6.QtWebEngineWidgets `
    --exclude-module PySide6.QtPdf `
    --exclude-module PySide6.QtPdfWidgets `
    --exclude-module torch `
    --exclude-module torchcrepe `
    --exclude-module tensorflow `
    --exclude-module basic_pitch `
    --exclude-module librosa `
    --exclude-module numpy `
    --exclude-module soundfile `
    --exclude-module PySide6.QtNetwork `
    run.py

if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }
}
finally {
    $env:PATH = $originalBuildPath
}

Write-Host "Built: $distRoot\MusicalScumbag.exe"

$targetExe = Join-Path $distRoot 'MusicalScumbag.exe'
if (Test-Path -LiteralPath $targetExe) {
    $hash = (Get-FileHash -LiteralPath $targetExe -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath "$targetExe.sha256" -Value "$hash  MusicalScumbag.exe" -Encoding ascii
}
