@echo off
setlocal DisableDelayedExpansion
title R-Link Native Network Install
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -File "%~dp0.repository-consolidation-local\fabric-20261008\start-native-r9.ps1"
endlocal
