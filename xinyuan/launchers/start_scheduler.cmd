@echo off
setlocal
cd /d "%~dp0.."

powershell -NoProfile -ExecutionPolicy Bypass -File ".\launchers\start_scheduler.ps1"
if errorlevel 1 pause
