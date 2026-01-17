@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "BIN_DIR=..\..\binaries\networking"
set "EXE=netbird.exe"
set "PROC_NAME=netbird.exe"
set "CONFIG_DIR=%USERPROFILE%\.config\netbird"

echo ======================================
echo NetBird - Remote Networking
echo ======================================
echo.

REM Check binary
if not exist "%BIN_DIR%\%EXE%" (
    echo [ERROR] %EXE% not found
    echo Path: %BIN_DIR%\%EXE%
    echo.
    echo Download from:
    echo https://github.com/netbirdio/netbird/releases
    pause
    exit /b 1
)

REM Create config dir
if not exist "%CONFIG_DIR%" (
    mkdir "%CONFIG_DIR%"
)

REM Check if service installed
sc query NetBirdService >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    echo [MODE] NetBird service detected
    echo.
    echo [1] Start service (recommended)
    echo [2] Run directly (foreground)
    echo [3] Uninstall service
    echo [0] Cancel
    echo.
    set /p svc_choice=Choose:

    if "!svc_choice!"=="1" (
        echo [START] Starting NetBird service...
        net start NetBirdService >nul 2>&1
        if "!ERRORLEVEL!"=="0" (
            echo [SUCCESS] NetBird service started
        ) else (
            echo [INFO] Service may already be running
        )
        goto :show_status
    )
    if "!svc_choice!"=="3" (
        echo [UNINSTALL] Uninstalling NetBird service...
        "%BIN_DIR%\%EXE%" service uninstall
        echo [DONE] Service uninstalled
        pause
        exit /b 0
    )
)

echo.
echo [CONFIG] Select connection mode:
echo.
echo [1] Connect to NetBird official server (free)
echo [2] Connect to self-hosted server
echo [3] Start only (use saved config)
echo.
set /p conn_choice=Choose:

if "!conn_choice!"=="1" (
    echo.
    echo [MODE] Connecting to NetBird official server
    echo.
    echo First time: complete authentication in browser...
    echo.
    "%BIN_DIR%\%EXE%" up
    goto :end
)

if "!conn_choice!"=="2" (
    echo.
    set /p nb_url=Enter server URL (e.g. https://netbird.example.com:33073):
    set /p nb_key=Enter Setup Key (create in dashboard):
    echo.
    echo [CONNECT] Connecting to self-hosted server...
    echo Server: !nb_url!
    echo.
    "%BIN_DIR%\%EXE%" up --setup-key !nb_key! --management-url !nb_url!
    goto :end
)

if "!conn_choice!"=="3" (
    echo [START] Starting NetBird...
    "%BIN_DIR%\%EXE%" up
    goto :end
)

:show_status
echo.
echo [STATUS] Checking connection...
timeout /t 2 /nobreak >nul
"%BIN_DIR%\%EXE%" status

:end
echo.
pause
