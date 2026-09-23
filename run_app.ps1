[CmdletBinding()]
param(
    [switch]$Reinstall
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

function Find-Python {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            & py -3 -c "import struct, sys; raise SystemExit(0 if sys.version_info >= (3,11) and struct.calcsize('P') == 8 else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { return @{ Exe = 'py'; Args = @('-3') } }
        } catch { }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        try {
            & python -c "import struct, sys; raise SystemExit(0 if sys.version_info >= (3,11) and struct.calcsize('P') == 8 else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) { return @{ Exe = 'python'; Args = @() } }
        } catch { }
    }
    throw 'Python 3.11 or newer was not found. Install 64-bit Python and enable "Add Python to PATH".'
}

$python = Find-Python
$pythonExe = $python.Exe
$pythonArgs = $python.Args
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host 'Creating isolated Python environment...'
    & $pythonExe @pythonArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}

if ($Reinstall -or -not (Test-Path -LiteralPath '.venv\.installed-v2.1')) {
    Write-Host 'Installing MusicalScumme dependencies...'
    & $venvPython -m pip install --disable-pip-version-check --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
    & $venvPython -m pip install --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    New-Item -ItemType File -Force -Path '.venv\.installed-v2.1' | Out-Null
}

& $venvPython run.py
exit $LASTEXITCODE
