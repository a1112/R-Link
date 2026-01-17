@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "BIN_DIR=..\..\binaries\networking"
set "EXE=netbird.exe"
set "PROC_NAME=netbird.exe"

echo ======================================
echo NetBird - Status Check
echo ======================================
echo.

REM Check binary
if not exist "%BIN_DIR%\%EXE%" (
    echo [ERROR] %EXE% not found
    pause
    exit /b 1
)

REM Check service status
sc query NetBirdService >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    echo [SERVICE] NetBird service installed
    sc query NetBirdService | findstr STATE
) else (
    echo [SERVICE] Not installed
)

echo.
echo [CONNECTION] Getting connection status...
echo.

REM Get status
"%BIN_DIR%\%EXE%" status

echo.
echo [LIST] Peers in network:
echo.

"%BIN_DIR%\%EXE%" list 2>nul

echo.
pause
