@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "PROC_NAME=sunshine.exe"
set "SERVICE_NAME=SunshineService"

echo ======================================
echo Sunshine - Stop Service
echo ======================================
echo.

REM Check if service exists
sc query %SERVICE_NAME% >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    echo [MODE] Service detected
    echo [STOP] Stopping Sunshine service...
    net stop %SERVICE_NAME% >nul 2>&1
    if "%ERRORLEVEL%"=="0" (
        echo [DONE] Service stopped
    ) else (
        echo [INFO] Service was not running
    )
    goto :end
)

REM No service - kill process
tasklist /FI "IMAGENAME eq %PROC_NAME%" 2>NUL | find /I /N "%PROC_NAME%">NUL
if "%ERRORLEVEL%"=="0" (
    echo [STOP] Stopping Sunshine process...
    taskkill /F /IM %PROC_NAME% >nul 2>&1
    timeout /t 1 /nobreak >nul
    echo [DONE] Sunshine stopped
) else (
    echo [STATUS] Sunshine not running
)

:end
echo.
pause
