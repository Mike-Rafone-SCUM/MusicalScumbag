[CmdletBinding()]
param([string]$InstallRoot, [string]$PythonPath)

$ErrorActionPreference = 'Stop'
$DataRoot = Join-Path $env:LOCALAPPDATA 'MusicalScumme'
$PointerPath = Join-Path $DataRoot 'advanced-runtime.path'
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null
if (-not $InstallRoot -and (Test-Path -LiteralPath $PointerPath)) {
    $InstallRoot = (Get-Content -LiteralPath $PointerPath -Raw).Trim()
}
if (-not $InstallRoot) { $InstallRoot = Join-Path $DataRoot 'advanced-runtime' }
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$RuntimePython = Join-Path $InstallRoot 'Scripts\python.exe'
$Marker = Join-Path $InstallRoot '.musicalscumme-advanced-ready-v1'
Remove-Item -LiteralPath $Marker -Force -ErrorAction SilentlyContinue

if (-not (Test-Path -LiteralPath $RuntimePython)) {
    $candidates = @($PythonPath,
        (Join-Path $DataRoot 'python-3.11.9\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'))
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command) { $candidates += $command.Source }
    $BasePython = $null
    foreach ($candidate in $candidates) {
        if (-not $candidate -or -not (Test-Path -LiteralPath $candidate)) { continue }
        & $candidate -I -c "import sys,struct;raise SystemExit(0 if (3,11)<=sys.version_info[:2]<=(3,12) and struct.calcsize('P')==8 else 2)"
        if ($LASTEXITCODE -eq 0) { $BasePython = $candidate; break }
    }
    if (-not $BasePython) { throw 'Install 64-bit Python 3.11/3.12, or the normal Audio Tools, then retry.' }
    & $BasePython -I -m venv $InstallRoot
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated advanced transcription environment.' }
}

# Large CUDA wheels and extraction stay on the chosen runtime drive.
$PreviousTemp = $env:TEMP
$PreviousTmp = $env:TMP
$InstallTemp = Join-Path $InstallRoot 'install-temp'
New-Item -ItemType Directory -Force -Path $InstallTemp | Out-Null
$env:TEMP = $InstallTemp
$env:TMP = $InstallTemp
try {
    $Index = if (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue) { 'https://download.pytorch.org/whl/cu128' } else { 'https://download.pytorch.org/whl/cpu' }
    & $RuntimePython -I -m pip install --disable-pip-version-check --no-cache-dir 'torch==2.11.0' 'torchaudio==2.11.0' --index-url $Index
    if ($LASTEXITCODE -ne 0) { throw 'Advanced PyTorch installation failed.' }
    & $RuntimePython -I -m pip install --disable-pip-version-check --no-cache-dir -r (Join-Path $PSScriptRoot 'requirements-advanced.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Advanced transcription dependencies failed to install.' }
    & $RuntimePython -I -X utf8 (Join-Path $PSScriptRoot 'download_advanced_model.py') --runtime-dir $InstallRoot
    if ($LASTEXITCODE -ne 0) { throw 'Pinned YourMT3+ download or verification failed.' }
    & $RuntimePython -I -X utf8 (Join-Path $PSScriptRoot 'advanced_worker.py') --runtime-dir $InstallRoot --validate
    if ($LASTEXITCODE -ne 0) { throw 'YourMT3+ model loading/inference validation failed.' }
    Set-Content -LiteralPath $PointerPath -Value $InstallRoot -Encoding UTF8
    Write-Host "Advanced transcription installed in $InstallRoot"
}
finally {
    $env:TEMP = $PreviousTemp
    $env:TMP = $PreviousTmp
}
