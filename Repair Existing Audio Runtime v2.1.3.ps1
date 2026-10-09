[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$runtimePython = Join-Path $env:LOCALAPPDATA 'MusicalScumme\audio-runtime\Scripts\python.exe'
$readyMarker = Join-Path $env:LOCALAPPDATA 'MusicalScumme\audio-runtime\.musicalscumme-audio-ready-v1'
$setuptoolsVersion = '80.10.2'
$validationScript = Join-Path $PSScriptRoot 'validate_audio_runtime.py'
$logRoot = Join-Path $env:LOCALAPPDATA 'MusicalScumme\logs'
$logPath = Join-Path $logRoot 'audio-tools-repair.log'

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

function Write-RepairLog {
    param([Parameter(Mandatory = $true)][string]$Message)
    $line = '{0:yyyy-MM-dd HH:mm:ss}  {1}' -f (Get-Date), $Message
    Write-Host $Message
    Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
}

function Invoke-CheckedPython {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $runtimePython @Arguments 2>&1 | ForEach-Object {
            $text = [string]$_
            Write-Host $text
            Add-Content -LiteralPath $logPath -Value $text -Encoding UTF8
        }
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldPreference
    }

    if ($exitCode -ne 0) {
        throw "$FailureMessage Exit code: $exitCode. Full log: $logPath"
    }
}

Write-RepairLog 'Starting MusicalScumme audio-runtime validation repair.'

if (-not (Test-Path -LiteralPath $runtimePython)) {
    throw "The MusicalScumme audio runtime was not found at $runtimePython. Run install_audio_tools.ps1 instead."
}
if (-not (Test-Path -LiteralPath $validationScript)) {
    throw "The validation helper is missing: $validationScript"
}

Write-RepairLog "Ensuring setuptools $setuptoolsVersion is installed inside the isolated audio runtime."
Remove-Item -LiteralPath $readyMarker -Force -ErrorAction SilentlyContinue
Invoke-CheckedPython -Arguments @(
    '-I', '-m', 'pip', 'install', '--disable-pip-version-check', '--quiet', '--no-deps',
    "setuptools==$setuptoolsVersion"
) -FailureMessage 'Could not install the compatible setuptools release.'

# Run a script file, not `python -c`. Windows PowerShell 5.1 can remove embedded
# quotes from native command-line arguments and corrupt otherwise valid Python code.
Invoke-CheckedPython -Arguments @(
    '-I', $validationScript, '--expected-setuptools', $setuptoolsVersion
) -FailureMessage 'The repaired audio runtime did not validate.'

Set-Content -LiteralPath $readyMarker -Value 'validated' -Encoding ASCII
Write-RepairLog 'Audio runtime repaired and validated successfully.'
Write-RepairLog "Repair log: $logPath"
