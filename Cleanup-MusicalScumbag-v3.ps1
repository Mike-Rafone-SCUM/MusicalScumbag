[CmdletBinding()]
param(
    [string]$RepoPath = ".",
    [switch]$SkipTests,
    [switch]$SkipBuild,
    [switch]$ForceAudioRemoval
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

$repo = (Resolve-Path -LiteralPath $RepoPath).Path
$repoName = Split-Path -Leaf $repo
$parent = Split-Path -Parent $repo
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path $parent "${repoName}_cleanup_backup_${timestamp}"

Push-Location -LiteralPath $repo

# Windows PowerShell 5.1 runs on .NET Framework, which does not provide
# [System.IO.Path]::GetRelativePath(). Keep this script compatible with both
# Windows PowerShell 5.1 and modern PowerShell.
function Get-RepoRelativePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $rootFull = [System.IO.Path]::GetFullPath($repo).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $pathFull = [System.IO.Path]::GetFullPath($Path)

    if ($pathFull.Equals($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        return "."
    }

    $prefix = $rootFull + [System.IO.Path]::DirectorySeparatorChar
    if (-not $pathFull.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside the repository: $pathFull"
    }

    return $pathFull.Substring($prefix.Length)
}

try {
    Write-Step "Validating MusicalScumbag repository"

    foreach ($required in @(
        "musical_scumme",
        "build_exe.ps1",
        "requirements.txt",
        "requirements-dev.txt",
        "run.py"
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $repo $required))) {
            throw "Required path is missing: $required`nRun this script from the MusicalScumbag repository root, or pass -RepoPath."
        }
    }

    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    Write-Host "Backup: $backupRoot"

    function Backup-Path {
        param([Parameter(Mandatory = $true)][string]$Path)

        if (-not (Test-Path -LiteralPath $Path)) {
            return
        }

        $full = [System.IO.Path]::GetFullPath($Path)
        $relative = Get-RepoRelativePath -Path $full

        if ($relative.StartsWith("..")) {
            throw "Refusing to back up a path outside the repository: $full"
        }

        $destination = Join-Path $backupRoot $relative
        $destinationParent = Split-Path -Parent $destination
        if ($destinationParent) {
            New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
        }

        if (Test-Path -LiteralPath $full -PathType Container) {
            Copy-Item -LiteralPath $full -Destination $destination -Recurse -Force
        }
        else {
            Copy-Item -LiteralPath $full -Destination $destination -Force
        }
    }

    function Remove-RepoItem {
        param([Parameter(Mandatory = $true)][string]$Path)

        $full = if ([System.IO.Path]::IsPathRooted($Path)) {
            $Path
        }
        else {
            Join-Path $repo $Path
        }

        if (Test-Path -LiteralPath $full) {
            $relative = Get-RepoRelativePath -Path $full
            Backup-Path -Path $full
            Remove-Item -LiteralPath $full -Recurse -Force
            Write-Host "Removed  $relative"
        }
    }

    function Remove-RootPattern {
        param([Parameter(Mandatory = $true)][string]$Pattern)

        Get-ChildItem -LiteralPath $repo -File -Filter $Pattern -ErrorAction SilentlyContinue |
            ForEach-Object { Remove-RepoItem -Path $_.FullName }
    }

    # -------------------------------------------------------------------------
    # SAFETY GATE: do not remove the retired subsystem while active app code
    # still references it. Use -ForceAudioRemoval only if you intentionally
    # want to override this protection.
    # -------------------------------------------------------------------------
    Write-Step "Checking that the retired Audio / Song Transposer code is disconnected"

    $retiredModuleFiles = @(
        "audio_tools.py",
        "separation_tools.py",
        "song_processor.py"
    )

    $sourceFiles = Get-ChildItem -LiteralPath (Join-Path $repo "musical_scumme") -Recurse -File -Filter "*.py" |
        Where-Object { $_.Name -notin $retiredModuleFiles }

    $retiredReferencePattern =
        'audio_tools|separation_tools|song_processor|audio_worker|separation_worker|' +
        'install_audio_tools|install_separation_tools|validate_audio_runtime|' +
        'validate_separation_runtime|requirements-audio|requirements-separation|' +
        'Song\s+Transposer|Audio\s*(?:->|→|to)\s*MIDI'

    $liveReferences = @(
        $sourceFiles |
            Select-String -Pattern $retiredReferencePattern -CaseSensitive:$false -ErrorAction SilentlyContinue
    )

    if ($liveReferences.Count -gt 0 -and -not $ForceAudioRemoval) {
        Write-Host ""
        Write-Host "STOPPED: the current app source still references the subsystem you are trying to delete." -ForegroundColor Yellow
        Write-Host "Nothing destructive has been done yet." -ForegroundColor Yellow
        Write-Host ""
        $liveReferences |
            Select-Object -First 30 |
            ForEach-Object {
                $rel = Get-RepoRelativePath -Path $_.Path
                Write-Host ("  {0}:{1}: {2}" -f $rel, $_.LineNumber, $_.Line.Trim())
            }

        Write-Host ""
        Write-Host "Use your newer MIDI-only source first, or rerun with -ForceAudioRemoval if you deliberately want to override this guard."
        throw "Retired audio/transposer references are still present."
    }

    # -------------------------------------------------------------------------
    # BACK UP files we will edit before touching them.
    # -------------------------------------------------------------------------
    foreach ($file in @(
        "build_exe.ps1",
        "README.md",
        "Build EXE - One File.bat",
        "Build EXE.bat"
    )) {
        $full = Join-Path $repo $file
        if (Test-Path -LiteralPath $full) {
            Backup-Path -Path $full
        }
    }

    # -------------------------------------------------------------------------
    # REMOVE historical root clutter.
    # -------------------------------------------------------------------------
    Write-Step "Removing historical reports and UI preview images"

    Remove-RootPattern "IMPLEMENTATION_REPORT_*.md"
    Remove-RootPattern "PATCH_REPORT_*.md"

    $previewFiles = @(
        "SONG_TRANSPOSER_PREVIEW_2.3.0.png",
        "UI_PREVIEW_2.1.0.png",
        "UI_PREVIEW_2.2.0.png",
        "UI_PREVIEW_2.3.0.png",
        "compact_dark_bg.png",
        "compact_overlay_preview.png",
        "final_compact_hud.png",
        "final_main_daw.png",
        "main_dark_bg.png",
        "main_window_preview.png",
        "new_compact_preview.png",
        "new_main_preview.png",
        "real_styled_compact.png",
        "real_styled_main.png"
    )
    foreach ($file in $previewFiles) {
        Remove-RepoItem $file
    }

    # -------------------------------------------------------------------------
    # REMOVE retired Audio -> MIDI / separation / Song Transposer subsystem.
    # -------------------------------------------------------------------------
    Write-Step "Removing retired Audio / Song Transposer subsystem"

    $retiredFiles = @(
        "audio_worker.py",
        "separation_worker.py",
        "install_audio_tools.ps1",
        "install_separation_tools.ps1",
        "Install Audio Tools.bat",
        "Install Separation Tools.bat",
        "Repair Audio Tools.bat",
        "Repair Existing Audio Runtime v2.1.3.bat",
        "Repair Existing Audio Runtime v2.1.3.ps1",
        "requirements-audio.txt",
        "requirements-audio-constraints.txt",
        "requirements-separation.txt",
        "requirements-separation-cuda.txt",
        "validate_audio_runtime.py",
        "validate_separation_runtime.py",
        "musical_scumme\audio_tools.py",
        "musical_scumme\separation_tools.py",
        "musical_scumme\song_processor.py",
        "tests\test_audio_installer.py",
        "tests\test_audio_tools.py",
        "tests\test_audio_worker.py",
        "tests\test_separation_tools.py",
        "tests\test_separation_worker.py",
        "tests\test_song_processor.py"
    )
    foreach ($file in $retiredFiles) {
        Remove-RepoItem $file
    }

    # Catch similarly named retired tests if the local branch contains newer ones.
    foreach ($pattern in @(
        "test_audio_*.py",
        "test_separation_*.py"
    )) {
        Get-ChildItem -LiteralPath (Join-Path $repo "tests") -File -Filter $pattern -ErrorAction SilentlyContinue |
            ForEach-Object { Remove-RepoItem -Path $_.FullName }
    }

    # -------------------------------------------------------------------------
    # REMOVE redundant launch/build/checksum wrappers.
    # -------------------------------------------------------------------------
    Write-Step "Removing redundant wrappers"

    foreach ($file in @(
        "Launch MusicalScumme.bat",
        "SHA256SUMS.txt",
        "build_exe.py"
    )) {
        Remove-RepoItem $file
    }

    # The old Build EXE.bat is the onedir wrapper. It will be replaced below
    # with one single one-file build shortcut.
    Remove-RepoItem "Build EXE.bat"

    # -------------------------------------------------------------------------
    # REWRITE build_exe.ps1 to be one-file only and remove bundled audio files.
    # -------------------------------------------------------------------------
    Write-Step "Converting build_exe.ps1 to one-file-only packaging"

    $buildPath = Join-Path $repo "build_exe.ps1"
    $buildLines = @(Get-Content -LiteralPath $buildPath)

    # Remove the -OneFile parameter and dynamic mode selection.
    $filtered = New-Object System.Collections.Generic.List[string]
    foreach ($line in $buildLines) {
        if ($line -match '^\s*\[switch\]\$OneFile,\s*$') {
            continue
        }
        if ($line -match '^\s*\$mode\s*=\s*if\s*\(\$OneFile\)') {
            continue
        }

        # Remove retired files from PyInstaller data.
        if (
            $line -match '--add-data' -and
            $line -match '(audio_worker|separation_worker|install_audio_tools|install_separation_tools|requirements-audio|requirements-separation|validate_audio_runtime|validate_separation_runtime)'
        ) {
            continue
        }

        # Replace the old variable argument with a permanent --onefile argument.
        if ($line -match '^\s*\$mode\s*`\s*$') {
            $filtered.Add('    --onefile `')
            continue
        }

        $filtered.Add($line)
    }

    # Replace the old OneFile/onedir result message at the end.
    $footerIndex = -1
    for ($i = 0; $i -lt $filtered.Count; $i++) {
        if ($filtered[$i].Trim() -eq 'if ($OneFile) {') {
            $footerIndex = $i
            break
        }
    }

    if ($footerIndex -ge 0) {
        $replacement = New-Object System.Collections.Generic.List[string]
        for ($i = 0; $i -lt $footerIndex; $i++) {
            $replacement.Add($filtered[$i])
        }
        $replacement.Add("")
        $replacement.Add('Write-Host "Built: $distRoot\MusicalScumbag.exe"')
        $filtered = $replacement
    }

    Set-Content -LiteralPath $buildPath -Value $filtered -Encoding UTF8

    # -------------------------------------------------------------------------
    # REPLACE build BAT with one simple permanent one-file build command.
    # -------------------------------------------------------------------------
    Write-Step "Creating the single Build EXE.bat"

    $oldOneFileBat = Join-Path $repo "Build EXE - One File.bat"
    if (Test-Path -LiteralPath $oldOneFileBat) {
        Remove-RepoItem "Build EXE - One File.bat"
    }

    $buildBat = @'
@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_exe.ps1"

if errorlevel 1 (
  echo.
  echo Build failed. See the error above.
  pause
  exit /b 1
)

echo.
echo Build complete:
echo   %~dp0release\MusicalScumbag.exe
pause
'@
    Set-Content -LiteralPath (Join-Path $repo "Build EXE.bat") -Value $buildBat -Encoding ASCII

    # -------------------------------------------------------------------------
    # CLEAN the README where the public branch still describes the removed
    # audio/transposer features and onedir build.
    # -------------------------------------------------------------------------
    Write-Step "Cleaning stale README references"

    $readmePath = Join-Path $repo "README.md"
    if (Test-Path -LiteralPath $readmePath) {
        $readme = Get-Content -LiteralPath $readmePath -Raw

        $readme = $readme -replace `
            'MusicalScumbag converts MIDI and user-selected audio into a deterministic, auditable SCUM instrument score', `
            'MusicalScumbag converts MIDI into a deterministic, auditable SCUM instrument score'

        $readme = [regex]::Replace(
            $readme,
            '(?m)^The primary workflow uses the untouched .*?MusicalScumbag never rewrites the imported source file\.\s*\r?\n',
            'The primary workflow uses the untouched `.mid` or `.midi` file downloaded from MIDI Find or another score source. MusicalScumbag never rewrites the imported source file.' + [Environment]::NewLine
        )

        $readme = [regex]::Replace(
            $readme,
            '(?m)^Audio-to-MIDI and Song Transposer .*?\r?\n',
            ''
        )

        $readme = [regex]::Replace(
            $readme,
            '(?ms)^## Song Transposer and audio\s*.*?(?=^## Run from source)',
            ''
        )

        $newBuildSection = @'
## Build the Windows release

Run:

```powershell
.\Build EXE.bat
```

or directly:

```powershell
.\build_exe.ps1
```

The release build is a single self-contained Windows executable. The final distributable is copied to:

```text
release\MusicalScumbag.exe
```

'@

        $readme = [regex]::Replace(
            $readme,
            '(?ms)^## Build the Windows release\s*.*?(?=^## Safety and validation boundaries)',
            $newBuildSection
        )

        $readme = [regex]::Replace(
            $readme,
            '(?m)^- Audio conversion .*?\r?\n',
            ''
        )
        $readme = [regex]::Replace(
            $readme,
            '(?m)^- Audio conversion is not fully validated .*?\r?\n',
            ''
        )

        Set-Content -LiteralPath $readmePath -Value $readme.TrimEnd() -Encoding UTF8
        Add-Content -LiteralPath $readmePath -Value ""
    }

    # -------------------------------------------------------------------------
    # CLEAN transient Python/build junk.
    # -------------------------------------------------------------------------
    Write-Step "Removing transient caches and previous build output"

    Get-ChildItem -LiteralPath $repo -Directory -Recurse -Force -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

    foreach ($junk in @(
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "dist",
        "release",
        "MusicalScumbag.spec",
        "MusicalScumme.spec"
    )) {
        $full = Join-Path $repo $junk
        if (Test-Path -LiteralPath $full) {
            Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    # -------------------------------------------------------------------------
    # CHECK for references to files that have just been removed.
    # -------------------------------------------------------------------------
    Write-Step "Checking for broken retired-module references"

    $remainingPython = Get-ChildItem -LiteralPath (Join-Path $repo "musical_scumme") -Recurse -File -Filter "*.py"
    $remainingReferences = @(
        $remainingPython |
            Select-String -Pattern 'audio_tools|separation_tools|song_processor|audio_worker|separation_worker' -CaseSensitive:$false -ErrorAction SilentlyContinue
    )

    if ($remainingReferences.Count -gt 0) {
        $remainingReferences |
            Select-Object -First 30 |
            ForEach-Object {
                $rel = Get-RepoRelativePath -Path $_.Path
                Write-Host ("  {0}:{1}: {2}" -f $rel, $_.LineNumber, $_.Line.Trim())
            }
        throw "Retired-module references remain after cleanup. Restore from $backupRoot if needed."
    }

    # -------------------------------------------------------------------------
    # BUILD the one-file application. build_exe.ps1 creates .build-venv,
    # installs build requirements, and invokes PyInstaller.
    # -------------------------------------------------------------------------
    if (-not $SkipBuild) {
        Write-Step "Preparing clean build output"

        # PyInstaller cannot overwrite dist\MusicalScumbag.exe while an older
        # copy is still running. Stop only MusicalScumbag processes.
        Get-Process -Name "MusicalScumbag" -ErrorAction SilentlyContinue |
            Stop-Process -Force -ErrorAction SilentlyContinue

        Start-Sleep -Milliseconds 750

        # Remove stale PyInstaller output before the next build.
        foreach ($stale in @(
            (Join-Path $repo "dist"),
            (Join-Path $repo "build"),
            (Join-Path $repo "MusicalScumbag.spec"),
            (Join-Path $repo "MusicalScumme.spec")
        )) {
            if (Test-Path -LiteralPath $stale) {
                try {
                    Remove-Item -LiteralPath $stale -Recurse -Force -ErrorAction Stop
                }
                catch {
                    Write-Host ""
                    Write-Host "Could not remove stale build output:" -ForegroundColor Yellow
                    Write-Host "  $stale"
                    Write-Host ""
                    Write-Host "Close MusicalScumbag.exe and any Explorer preview/window using that file, then rerun this script." -ForegroundColor Yellow
                    throw
                }
            }
        }

        Write-Step "Building MusicalScumbag.exe"

        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $buildPath -CleanEnvironment
        if ($LASTEXITCODE -ne 0) {
            throw "EXE build failed with exit code $LASTEXITCODE."
        }

        $exe = Join-Path $repo "dist\MusicalScumbag.exe"
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
            throw "Build completed without producing dist\MusicalScumbag.exe."
        }

        # ---------------------------------------------------------------------
        # TEST with the build environment after dependencies have been installed.
        # ---------------------------------------------------------------------
        if (-not $SkipTests) {
            Write-Step "Running compile and regression tests"

            $testPython = Join-Path $repo ".build-venv\Scripts\python.exe"
            if (-not (Test-Path -LiteralPath $testPython)) {
                throw "Build Python environment was not found: $testPython"
            }

            & $testPython -m compileall -q musical_scumme run.py
            if ($LASTEXITCODE -ne 0) {
                throw "Python compile check failed."
            }

            & $testPython -m pytest
            if ($LASTEXITCODE -ne 0) {
                throw "Tests failed. The EXE was built, but the cleanup is not considered validated."
            }
        }

        # ---------------------------------------------------------------------
        # PUBLISH a release directory containing literally one file.
        # ---------------------------------------------------------------------
        Write-Step "Publishing the one-file release"

        $releaseDir = Join-Path $repo "release"
        New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
        Copy-Item -LiteralPath $exe -Destination (Join-Path $releaseDir "MusicalScumbag.exe") -Force

        # Delete PyInstaller/build environment output after copying the final EXE.
        Remove-Item -LiteralPath (Join-Path $repo "dist") -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Join-Path $repo "build") -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Join-Path $repo ".build-venv") -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Join-Path $repo "MusicalScumbag.spec") -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Join-Path $repo "MusicalScumme.spec") -Force -ErrorAction SilentlyContinue

        $releaseFiles = @(Get-ChildItem -LiteralPath $releaseDir -File)
        if ($releaseFiles.Count -ne 1 -or $releaseFiles[0].Name -ne "MusicalScumbag.exe") {
            throw "Release folder validation failed: expected exactly one file, MusicalScumbag.exe."
        }

        $sizeMb = [math]::Round($releaseFiles[0].Length / 1MB, 1)
        Write-Host ""
        Write-Host "SUCCESS" -ForegroundColor Green
        Write-Host "Release: $($releaseFiles[0].FullName)"
        Write-Host "Size:    $sizeMb MB"
        Write-Host "Backup:  $backupRoot"
    }
    else {
        Write-Host ""
        Write-Host "Cleanup completed. Build was skipped." -ForegroundColor Green
        Write-Host "Backup: $backupRoot"
    }

    # Git is optional, but show the exact resulting changes when available.
    if (Get-Command git.exe -ErrorAction SilentlyContinue) {
        if (Test-Path -LiteralPath (Join-Path $repo ".git")) {
            Write-Step "Git changes"
            & git status --short
            & git diff --check
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "git diff --check reported whitespace/errors above."
            }
        }
    }
}
catch {
    Write-Host ""
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Backup location: $backupRoot" -ForegroundColor Yellow
    exit 1
}
finally {
    Pop-Location
}
