@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_audio_tools.ps1"
if errorlevel 1 pause
endlocal
