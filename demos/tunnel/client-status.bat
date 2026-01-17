@echo off
chcp 65001 >nul
set "PROC_NAME=frpc.exe"
set "CONFIG=..\..\..\demos\tunnel\frpc.ini"

echo ======================================
echo FRP Client - Status Check
echo ======================================
echo.

tasklist /FI "IMAGENAME eq %PROC_NAME%" 2>NUL | find /I /N "%PROC_NAME%">NUL
if "%ERRORLEVEL%"=="0" (
    echo [STATUS] Running
    echo.
    echo Process:
    tasklist /FI "IMAGENAME eq %PROC_NAME%" /V | findstr %PROC_NAME%
) else (
    echo [STATUS] Not running
    echo.
    echo Start with: client-start.bat
)

echo.
if exist "%CONFIG%" (
    echo Configured tunnels:
    type "%CONFIG%" | findstr "["
)

echo.
pause
