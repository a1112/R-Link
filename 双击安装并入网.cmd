@echo off
setlocal DisableDelayedExpansion
title R-Link NetBird Install and Join
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0.repository-consolidation-local\netbird-20261007\launch-network-admin.ps1"
if errorlevel 1 pause
endlocal
