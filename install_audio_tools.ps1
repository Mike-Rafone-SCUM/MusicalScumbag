[CmdletBinding()]
param(
    [switch]$Reinstall,
    [switch]$NoBootstrap,
    [string]$PythonPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

$applicationRoot = Join-Path $env:LOCALAPPDATA 'MusicalScumme'
$runtimeRoot = Join-Path $applicationRoot 'audio-runtime'
$runtimePython = Join-Path $runtimeRoot 'Scripts\python.exe'
$readyMarker = Join-Path $runtimeRoot '.musicalscumme-audio-ready-v1'
$bootstrapVersion = '3.11.9'
$bootstrapRoot = Join-Path $applicationRoot "python-$bootstrapVersion"
$bootstrapPython = Join-Path $bootstrapRoot 'python.exe'
$installerUrl = "https://www.python.org/ftp/python/$bootstrapVersion/python-$bootstrapVersion-amd64.exe"
$logRoot = Join-Path $applicationRoot 'logs'
$logPath = Join-Path $logRoot 'audio-tools-install.log'
$setuptoolsVersion = '80.10.2'
$audioRequirements = Join-Path $PSScriptRoot 'requirements-audio.txt'
$audioConstraints = Join-Path $PSScriptRoot 'requirements-audio-constraints.txt'
$validationScript = Join-Path $PSScriptRoot 'validate_audio_runtime.py'

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

function Write-InstallLog {
    param([Parameter(Mandatory = $true)][string]$Message)

    $line = '{0:yyyy-MM-dd HH:mm:ss}  {1}' -f (Get-Date), $Message
    Write-Host $Message
    Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
}

function Invoke-PythonProbe {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [string[]]$PrefixArguments = @()
    )

    $probe = @"
import json, struct, sys
version = sys.version_info[:2]
ok = version in ((3, 10), (3, 11)) and struct.calcsize('P') == 8
print(json.dumps({'executable': sys.executable, 'version': list(version), 'bits': struct.calcsize('P') * 8}))
raise SystemExit(0 if ok else 2)
"@

    $oldPreference = $ErrorActionPreference
    try {
        # The Windows py launcher writes "No suitable Python runtime found" to stderr.
        # With ErrorActionPreference=Stop that becomes a terminating NativeCommandError,
        # so probes must run with native stderr treated as ordinary process output.
        $ErrorActionPreference = 'Continue'
        # The packaged app directory contains Python 3.12 extension modules. Isolated
        # mode prevents a selected 3.10/3.11 interpreter from importing those files.
        $output = & $Executable @PrefixArguments -I -c $probe 2>$null
        $exitCode = $LASTEXITCODE
    }
    catch {
        return $null
    }
    finally {
        $ErrorActionPreference = $oldPreference
    }

    if ($exitCode -ne 0 -or -not $output) {
        return $null
    }

    try {
        $details = ($output | Select-Object -Last 1 | ConvertFrom-Json)
        return [pscustomobject]@{
            Exe = $Executable
            Args = @($PrefixArguments)
            ResolvedPath = [string]$details.executable
            Version = '{0}.{1}' -f $details.version[0], $details.version[1]
            Bits = [int]$details.bits
        }
    }
    catch {
        return $null
    }
}

function Find-CompatiblePython {
    $candidates = New-Object System.Collections.Generic.List[object]

    if ($PythonPath) {
        $candidates.Add([pscustomobject]@{ Exe = $PythonPath; Args = @() })
    }

    if (Test-Path -LiteralPath $bootstrapPython) {
        $candidates.Add([pscustomobject]@{ Exe = $bootstrapPython; Args = @() })
    }

    $pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyCommand) {
        $candidates.Add([pscustomobject]@{ Exe = $pyCommand.Source; Args = @('-3.11') })
        $candidates.Add([pscustomobject]@{ Exe = $pyCommand.Source; Args = @('-3.10') })
    }

    foreach ($commandName in @('python.exe', 'python3.exe')) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($command) {
            $candidates.Add([pscustomobject]@{ Exe = $command.Source; Args = @() })
        }
    }

    foreach ($knownPath in @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python310\python.exe'),
        (Join-Path $env:ProgramFiles 'Python311\python.exe'),
        (Join-Path $env:ProgramFiles 'Python310\python.exe')
    )) {
        if (Test-Path -LiteralPath $knownPath) {
            $candidates.Add([pscustomobject]@{ Exe = $knownPath; Args = @() })
        }
    }

    $seen = @{}
    foreach ($candidate in $candidates) {
        $key = ('{0}|{1}' -f $candidate.Exe, ($candidate.Args -join ' ')).ToLowerInvariant()
        if ($seen.ContainsKey($key)) {
            continue
        }
        $seen[$key] = $true

        $result = Invoke-PythonProbe -Executable $candidate.Exe -PrefixArguments $candidate.Args
        if ($null -ne $result) {
            Write-InstallLog "Using 64-bit Python $($result.Version): $($result.ResolvedPath)"
            return $result
        }
    }

    return $null
}

function Install-PrivatePython {
    if ($NoBootstrap) {
        throw 'No compatible 64-bit Python 3.10/3.11 runtime was found and automatic bootstrap was disabled.'
    }

    Write-InstallLog "No compatible Python runtime was found. Installing a private Python $bootstrapVersion runtime for audio conversion."
    Write-InstallLog 'This runtime is installed only under LOCALAPPDATA; it is not added to PATH and does not change file associations.'

    New-Item -ItemType Directory -Force -Path $applicationRoot | Out-Null
    $installerPath = Join-Path ([System.IO.Path]::GetTempPath()) "MusicalScumme-python-$bootstrapVersion-amd64.exe"

    try {
        Write-InstallLog "Downloading the official Python installer from python.org..."
        Invoke-WebRequest -UseBasicParsing -Uri $installerUrl -OutFile $installerPath

        $signature = Get-AuthenticodeSignature -FilePath $installerPath
        $subject = if ($signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { '' }
        if ($signature.Status -ne 'Valid' -or $subject -notmatch 'Python Software Foundation') {
            throw "Downloaded Python installer failed signature validation. Status=$($signature.Status); Signer=$subject"
        }
        Write-InstallLog 'Python installer signature validated.'

        if (Test-Path -LiteralPath $bootstrapRoot) {
            Remove-Item -LiteralPath $bootstrapRoot -Recurse -Force
        }

        $arguments = @(
            '/quiet',
            'InstallAllUsers=0',
            "TargetDir=`"$bootstrapRoot`"",
            'Include_launcher=0',
            'Include_test=0',
            'Include_doc=0',
            'Include_tcltk=0',
            'Include_pip=1',
            'PrependPath=0',
            'AssociateFiles=0',
            'Shortcuts=0'
        )
        $process = Start-Process -FilePath $installerPath -ArgumentList $arguments -Wait -PassThru
        if ($process.ExitCode -notin @(0, 3010)) {
            throw "Python installer exited with code $($process.ExitCode)."
        }
        if (-not (Test-Path -LiteralPath $bootstrapPython)) {
            throw "Python installer completed but $bootstrapPython was not created."
        }
    }
    finally {
        Remove-Item -LiteralPath $installerPath -Force -ErrorAction SilentlyContinue
    }

    $result = Invoke-PythonProbe -Executable $bootstrapPython
    if ($null -eq $result) {
        throw 'The private Python runtime was installed but failed its compatibility check.'
    }
    Write-InstallLog "Private Python $($result.Version) runtime installed successfully."
    return $result
}

function Invoke-CheckedPython {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Executable @Arguments 2>&1 | ForEach-Object {
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

Write-InstallLog 'Starting MusicalScumme audio-tools installation.'
$python = Find-CompatiblePython
if ($null -eq $python) {
    $python = Install-PrivatePython
}

if ($Reinstall -and (Test-Path -LiteralPath $runtimeRoot)) {
    Write-InstallLog "Removing existing audio runtime: $runtimeRoot"
    Remove-Item -LiteralPath $runtimeRoot -Recurse -Force
}

if (Test-Path -LiteralPath $runtimePython) {
    $existingRuntime = Invoke-PythonProbe -Executable $runtimePython
    if ($null -eq $existingRuntime) {
        Write-InstallLog 'Existing audio runtime is incomplete or incompatible; rebuilding it.'
        Remove-Item -LiteralPath $runtimeRoot -Recurse -Force
    }
}

if (-not (Test-Path -LiteralPath $runtimePython)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $runtimeRoot -Parent) | Out-Null
    Write-InstallLog "Creating isolated audio runtime at $runtimeRoot"
    Invoke-CheckedPython -Executable $python.Exe -Arguments @($python.Args + @('-I', '-m', 'venv', $runtimeRoot)) -FailureMessage 'Could not create the audio runtime.'
}

if (-not (Test-Path -LiteralPath $audioRequirements)) {
    throw "Missing audio requirements file: $audioRequirements"
}
if (-not (Test-Path -LiteralPath $audioConstraints)) {
    throw "Missing audio constraints file: $audioConstraints"
}
if (-not (Test-Path -LiteralPath $validationScript)) {
    throw "Missing audio validation script: $validationScript"
}

# A marker is written only after the complete stack validates. Removing it before
# package work prevents the UI from advertising a partially repaired runtime.
Remove-Item -LiteralPath $readyMarker -Force -ErrorAction SilentlyContinue

Write-InstallLog 'Preparing the isolated Python packaging runtime.'
Write-InstallLog "Pinning setuptools $setuptoolsVersion because Basic Pitch 0.4.0 -> resampy 0.4.2 still imports pkg_resources at runtime."
Invoke-CheckedPython -Executable $runtimePython -Arguments @(
    '-I', '-m', 'pip', 'install', '--disable-pip-version-check', '--quiet', '--upgrade',
    'pip>=24,<27', "setuptools==$setuptoolsVersion", 'wheel>=0.45,<1'
) -FailureMessage 'pip bootstrap failed.'

Write-InstallLog 'Installing Spotify Basic Pitch and its Windows inference runtime. The first installation is a large download.'
Invoke-CheckedPython -Executable $runtimePython -Arguments @(
    '-I', '-m', 'pip', 'install', '--disable-pip-version-check', '--quiet',
    '--constraint', $audioConstraints,
    '-r', $audioRequirements
) -FailureMessage 'Audio dependency installation failed.'

# Reassert the compatibility pin after dependency resolution. This is intentionally
# idempotent and repairs v2.1.1 environments without deleting the downloaded model stack.
Invoke-CheckedPython -Executable $runtimePython -Arguments @(
    '-I', '-m', 'pip', 'install', '--disable-pip-version-check', '--quiet', '--no-deps',
    "setuptools==$setuptoolsVersion"
) -FailureMessage 'Could not apply the pkg_resources compatibility pin.'

# Use a real .py file rather than `python -c`. Windows PowerShell 5.1 can strip
# embedded quotes from native-process arguments, which previously changed
# metadata.version("basic-pitch") into metadata.version(basic-pitch).
Invoke-CheckedPython -Executable $runtimePython -Arguments @(
    '-I', $validationScript, '--expected-setuptools', $setuptoolsVersion
) -FailureMessage 'Audio runtime validation failed.'

Set-Content -LiteralPath $readyMarker -Value 'validated' -Encoding ASCII
Write-InstallLog 'Audio tools installed and validated successfully.'
Write-InstallLog "Installation log: $logPath"
