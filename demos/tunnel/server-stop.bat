@echo off
chcp 65001 >nul
set "PROC_NAME=frps.exe"

echo ======================================
echo FRP Server - Stop Server
echo ======================================
echo.

tasklist /FI "IMAGENAME eq %PROC_NAME%" 2>NUL | find /I /N "%PROC_NAME%">NUL
if "%ERRORLEVEL%"=="0" (
    echo [STOP] Stopping FRP server...
    taskkill /F /IM %PROC_NAME% >nul 2>&1
    timeout /t 1 /nobreak >nul
    echo [DONE] FRP server stopped
) else (
    echo [STATUS] FRP server not running
)

echo.
pause
