@echo off
chcp 65001 >nul
set "PROC_NAME=frpc.exe"

echo ======================================
echo FRP Client - Stop Client
echo ======================================
echo.

tasklist /FI "IMAGENAME eq %PROC_NAME%" 2>NUL | find /I /N "%PROC_NAME%">NUL
if "%ERRORLEVEL%"=="0" (
    echo [STOP] Stopping FRP client...
    taskkill /F /IM %PROC_NAME% >nul 2>&1
    timeout /t 1 /nobreak >nul
    echo [DONE] FRP client stopped
) else (
    echo [STATUS] FRP client not running
)

echo.
pause
