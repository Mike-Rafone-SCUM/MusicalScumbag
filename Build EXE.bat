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
