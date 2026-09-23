[CmdletBinding()]
param(
    [string]$InstallRoot,
    [string]$PythonPath,
    [switch]$Reinstall
)

$ErrorActionPreference = 'Stop'
$Model = 'model_bs_roformer_ep_317_sdr_12.9755.ckpt'
$ReadyMarker = '.musicalscumme-separation-ready-v1'
$DataRoot = Join-Path $env:LOCALAPPDATA 'MusicalScumme'
$PointerPath = Join-Path $DataRoot 'separation-runtime.path'
$LogRoot = Join-Path $DataRoot 'logs'
New-Item -ItemType Directory -Force -Path $DataRoot, $LogRoot | Out-Null
$LogPath = Join-Path $LogRoot 'separation-tools-install.log'
Start-Transcript -LiteralPath $LogPath -Append | Out-Null

function Test-CompatiblePython {
    param([Parameter(Mandatory = $true)][string]$Executable)
    if (-not (Test-Path -LiteralPath $Executable)) { return $false }
    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Executable -I -c "import struct,sys;raise SystemExit(0 if (3,10)<=sys.version_info[:2]<=(3,12) and struct.calcsize('P')==8 else 2)" 2>$null
        $code = $LASTEXITCODE
    }
    catch { return $false }
    finally { $ErrorActionPreference = $oldPreference }
    return $code -eq 0
}

function Find-CompatiblePython {
    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($PythonPath) { $candidates.Add($PythonPath) }
    $audioPython = Join-Path $DataRoot 'audio-runtime\Scripts\python.exe'
    if (Test-Path -LiteralPath $audioPython) {
        $oldPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $base = (& $audioPython -I -c "import sys;print(sys._base_executable)" 2>$null | Select-Object -Last 1)
            if ($LASTEXITCODE -eq 0 -and $base) { $candidates.Add($base.Trim()) }
        }
        finally { $ErrorActionPreference = $oldPreference }
    }
    $privatePython = Join-Path $DataRoot 'python-3.11.9\python.exe'
    $candidates.Add($privatePython)
    foreach ($known in @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')
    )) { $candidates.Add($known) }
    foreach ($name in @('python.exe', 'python3.exe')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { $candidates.Add($command.Source) }
    }
    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (Test-CompatiblePython -Executable $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    throw 'A 64-bit Python 3.10-3.12 runtime was not found. Install the normal Audio Tools first, then retry UVR.'
}

try {
    if (-not $InstallRoot) {
        if (Test-Path -LiteralPath $PointerPath) {
            $storedRoot = (Get-Content -LiteralPath $PointerPath -Raw).Trim()
            if ($storedRoot) { $InstallRoot = $storedRoot }
        }
        if (-not $InstallRoot) { $InstallRoot = Join-Path $DataRoot 'separation-runtime' }
    }
    $InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
    $RuntimePython = Join-Path $InstallRoot 'Scripts\python.exe'
    $RuntimeCli = Join-Path $InstallRoot 'Scripts\audio-separator.exe'
    $ModelDir = Join-Path $InstallRoot 'models'
    $MarkerPath = Join-Path $InstallRoot $ReadyMarker
    Remove-Item -LiteralPath $MarkerPath -Force -ErrorAction SilentlyContinue

    if ($Reinstall -and (Test-Path -LiteralPath $InstallRoot)) {
        Remove-Item -LiteralPath $InstallRoot -Recurse -Force
    }
    if (-not (Test-Path -LiteralPath $RuntimePython)) {
        $BasePython = Find-CompatiblePython
        Write-Host "Creating isolated UVR runtime with $BasePython"
        & $BasePython -I -m venv $InstallRoot
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the UVR virtual environment.' }
    }

    & $RuntimePython -I -m pip install --disable-pip-version-check --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'UVR pip upgrade failed.' }
    & $RuntimePython -I -m pip install --disable-pip-version-check -r (Join-Path $PSScriptRoot 'requirements-separation.txt')
    if ($LASTEXITCODE -ne 0) { throw 'UVR dependency installation failed.' }
    if (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue) {
        & $RuntimePython -I -m pip install --disable-pip-version-check --no-deps `
            -r (Join-Path $PSScriptRoot 'requirements-separation-cuda.txt') `
            --index-url 'https://download.pytorch.org/whl/cu128'
        if ($LASTEXITCODE -ne 0) { throw 'CUDA PyTorch installation failed.' }
    }
    else {
        Write-Warning 'No NVIDIA driver was detected. UVR will use the slower CPU runtime.'
    }

    New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null
    Write-Host "Downloading/verifying $Model"
    & $RuntimeCli --model_filename $Model --model_file_dir $ModelDir --download_model_only
    if ($LASTEXITCODE -ne 0) { throw 'UVR model download failed.' }

    $validator = Join-Path $PSScriptRoot 'validate_separation_runtime.py'
    & $RuntimePython -I -X utf8 $validator --runtime-dir $InstallRoot --model-dir $ModelDir --model $Model
    if ($LASTEXITCODE -ne 0) { throw 'UVR runtime validation failed.' }

    Set-Content -LiteralPath $PointerPath -Value $InstallRoot -Encoding UTF8
    $backend = if ((& $RuntimePython -I -c "import torch;print('cuda' if torch.cuda.is_available() else 'cpu')" | Select-Object -Last 1) -eq 'cuda') { 'cuda' } else { 'cpu' }
    if ((Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue) -and $backend -ne 'cuda') {
        throw 'An NVIDIA GPU was detected, but CUDA is unavailable to the UVR runtime.'
    }
    $ready = [ordered]@{ model = $Model; backend = $backend; audio_separator = '0.44.3' } | ConvertTo-Json -Compress
    Set-Content -LiteralPath $MarkerPath -Value $ready -Encoding UTF8
    Write-Host "UVR separation runtime installed: $InstallRoot"
    Write-Host "Model cache: $ModelDir"
}
finally {
    Stop-Transcript | Out-Null
}
