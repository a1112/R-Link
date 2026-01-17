@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "BIN_DIR=..\..\binaries\tunnel"
set "EXE=frpc.exe"
set "PROC_NAME=frpc.exe"
set "CONFIG=..\..\..\demos\tunnel\frpc.ini"

echo ======================================
echo FRP Client - Tunnel Client
echo ======================================
echo.

REM Check binary
if not exist "%BIN_DIR%\%EXE%" (
    echo [ERROR] %EXE% not found
    echo Path: %BIN_DIR%\%EXE%
    pause
    exit /b 1
)

REM Check config file
if not exist "%CONFIG%" (
    echo [ERROR] Config file not found
    echo Path: %CONFIG%
    echo.
    echo Please edit frpc.ini first
    pause
    exit /b 1
)

REM Check if already running
tasklist /FI "IMAGENAME eq %PROC_NAME%" 2>NUL | find /I /N "%PROC_NAME%">NUL
if "%ERRORLEVEL%"=="0" (
    echo [STATUS] FRP client already running
    pause
    exit /b 0
)

echo [CONFIG] Using: %CONFIG%
echo.

REM Show configured tunnels
echo Configured tunnels:
type "%CONFIG%" | findstr /V "^;" | findstr /V "^common" | findstr /V "^$" | findstr "["
echo.

echo [START] Starting FRP client...
echo.

REM Start client
start "FRP Client" /D "%BIN_DIR%" "%BIN_DIR%\%EXE%" -c "%CONFIG%"

REM Wait for startup
timeout /t 2 /nobreak >nul

REM Check if started successfully
tasklist /FI "IMAGENAME eq %PROC_NAME%" 2>NUL | find /I /N "%PROC_NAME%">NUL
if "%ERRORLEVEL%"=="0" (
    echo [SUCCESS] FRP client started!
    echo.
    echo Client running in background
    echo Check status: client-status.bat
) else (
    echo [FAILED] FRP client failed to start
    echo.
    echo Check:
    echo   1. Config file is correct
    echo   2. Server address is reachable
    echo   3. Token matches server
)

echo.
pause
