@echo off
chcp 65001 >nul
set "PROC_NAME=frps.exe"
set "CONFIG=..\..\..\demos\tunnel\frps.ini"

echo ======================================
echo FRP Server - Status Check
echo ======================================
echo.

tasklist /FI "IMAGENAME eq %PROC_NAME%" 2>NUL | find /I /N "%PROC_NAME%">NUL
if "%ERRORLEVEL%"=="0" (
    echo [STATUS] Running
    echo.
    echo Access:
    echo   Dashboard:      http://localhost:7500
    echo   Client port:    7000
    echo.
    echo Process:
    tasklist /FI "IMAGENAME eq %PROC_NAME%" /V | findstr %PROC_NAME%
) else (
    echo [STATUS] Not running
    echo.
    echo Start with: server-start.bat
)

echo.
if exist "%CONFIG%" (
    echo Current config:
    type "%CONFIG%" | findstr /V "^;" | findstr /V "^$"
)

echo.
pause
