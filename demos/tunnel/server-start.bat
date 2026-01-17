@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "BIN_DIR=..\..\binaries\tunnel"
set "EXE=frps.exe"
set "PROC_NAME=frps.exe"
set "CONFIG=..\..\..\demos\tunnel\frps.ini"

echo ======================================
echo FRP Server - Tunnel Server
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
    echo Please edit frps.ini first
    pause
    exit /b 1
)

REM Check if already running
tasklist /FI "IMAGENAME eq %PROC_NAME%" 2>NUL | find /I /N "%PROC_NAME%">NUL
if "%ERRORLEVEL%"=="0" (
    echo [STATUS] FRP server already running
    echo.
    echo Dashboard: http://localhost:7500
    pause
    exit /b 0
)

echo [CONFIG] Using: %CONFIG%
echo.
echo [START] Starting FRP server...
echo.

REM Show config summary
echo Config summary:
type "%CONFIG%" | findstr /V "^;" | findstr /V "^$"
echo.

REM Start server
start "FRP Server" /D "%BIN_DIR%" "%BIN_DIR%\%EXE%" -c "%CONFIG%"

REM Wait for startup
timeout /t 2 /nobreak >nul

REM Check if started successfully
tasklist /FI "IMAGENAME eq %PROC_NAME%" 2>NUL | find /I /N "%PROC_NAME%">NUL
if "%ERRORLEVEL%"=="0" (
    echo [SUCCESS] FRP server started!
    echo.
    echo Server info:
    echo   Bind port:    7000 (TCP)
    echo   Dashboard:    http://localhost:7500
    echo   Credentials:  admin / admin (change this!)
    echo.
    echo Client needs:
    echo   server_addr = your_server_ip
    echo   server_port = 7000
) else (
    echo [FAILED] FRP server failed to start
    echo.
    echo Check:
    echo   1. Config file is correct
    echo   2. Port not in use
    echo   3. Firewall settings
)

echo.
pause
