@echo off
setlocal
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0.repository-consolidation-local\fabric-agent\staging\local\launch-admin.ps1"
if errorlevel 1 pause
