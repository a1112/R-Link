@echo off
setlocal DisableDelayedExpansion
title R-Link NetBird Install and Join
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -File "%~dp0.repository-consolidation-local\netbird-20261007\start-netbird-install.ps1"
endlocal
