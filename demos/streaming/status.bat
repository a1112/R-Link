@echo off
chcp 65001 >nul
set "PROC_NAME=sunshine.exe"

echo ======================================
echo Sunshine - Status Check
echo ======================================
echo.

tasklist /FI "IMAGENAME eq %PROC_NAME%" 2>NUL | find /I /N "%PROC_NAME%">NUL
if "%ERRORLEVEL%"=="0" (
    echo [STATUS] Running
    echo.
    echo Access:
    echo   Web UI:      http://localhost:47990
    echo.
    echo Process:
    tasklist /FI "IMAGENAME eq %PROC_NAME%" /V | findstr %PROC_NAME%
) else (
    echo [STATUS] Not running
    echo.
    echo Start with: start.bat
)

echo.
pause
