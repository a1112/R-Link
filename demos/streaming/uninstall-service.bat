@echo off
chcp 65001 >nul

set "BIN_DIR=..\..\binaries\streaming"
set "EXE=sunshinesvc.exe"

echo ======================================
echo Sunshine - Uninstall Service
echo ======================================
echo.

echo [STOP] Stopping service...
net stop SunshineService >nul 2>&1

echo [UNINSTALL] Uninstalling service...
cd /D "%BIN_DIR%"
"%EXE%" uninstall

echo [DONE] Service uninstalled
echo.
pause
