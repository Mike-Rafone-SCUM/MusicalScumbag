@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Repair Existing Audio Runtime v2.1.3.ps1"
if errorlevel 1 pause
