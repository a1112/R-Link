@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "BIN_DIR=..\..\binaries\streaming"
set "EXE=sunshine.exe"
set "SVC_EXE=sunshinesvc.exe"
set "PROC_NAME=sunshine.exe"
set "CONFIG_DIR=C:\ProgramData\Sunshine"

echo ======================================
echo Sunshine - Game Streaming Server
echo ======================================
echo.

REM Check binary
if not exist "%BIN_DIR%\%EXE%" (
    echo [ERROR] %EXE% not found
    echo Path: %BIN_DIR%\%EXE%
    echo.
    echo Download from:
    echo https://github.com/LizardByte/Sunshine/releases
    pause
    exit /b 1
)

REM Check if config exists, if not initialize
if not exist "%CONFIG_DIR%\config\sunshine.conf" (
    echo [INIT] Config not found, initializing...
    echo.
    powershell -ExecutionPolicy Bypass -File "%~dp0init-sunshine.ps1"
    if "%ERRORLEVEL%" neq "0" (
        echo [ERROR] Initialization failed
        pause
        exit /b 1
    )
    echo.
)

REM Check if service is installed
sc query SunshineService >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    echo [MODE] Service detected

    REM Check if service is running
    sc query SunshineService | findstr RUNNING >nul
    if "%ERRORLEVEL%"=="0" (
        echo [STATUS] Service already running
        echo.
        echo Web UI: http://localhost:47990
        echo Config:  %CONFIG_DIR%
        pause
        exit /b 0
    )

    echo [START] Starting Sunshine service...
    net start SunshineService

    if "%ERRORLEVEL%"=="0" (
        echo [SUCCESS] Service started!
        echo.
        echo Web UI: http://localhost:47990
        echo Config:  %CONFIG_DIR%
    ) else (
        echo [FAILED] Service failed to start
        echo.
        echo Try reinstalling: install-service.bat
    )
    pause
    exit /b 0
)

REM Service not installed - ask user
echo [INFO] Service not installed
echo.
echo Sunshine works best as a Windows service.
echo.
echo [1] Install service (recommended)
echo [2] Run directly (may not work properly)
echo [0] Cancel
echo.
set /p choice=Choose:

if "%choice%"=="1" (
    call "%~dp0install-service.bat"
    exit /b 0
)

if "%choice%"=="2" (
    echo.
    echo [START] Starting Sunshine directly...
    echo [WARNING] This may not work correctly
    echo.

    start "" "%BIN_DIR%\%EXE%"

    timeout /t 3 /nobreak >nul

    tasklist /FI "IMAGENAME eq %PROC_NAME%" 2>NUL | find /I /N "%PROC_NAME%">NUL
    if "%ERRORLEVEL%"=="0" (
        echo [SUCCESS] Sunshine started!
        echo.
        echo Web UI: http://localhost:47990
    ) else (
        echo [FAILED] Sunshine exited
        echo.
        echo Please install as service: install-service.bat
    )
    pause
    exit /b 0
)

echo Cancelled.
pause
exit /b 0
