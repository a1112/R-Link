@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "BIN_DIR=..\..\binaries\networking"
set "EXE=netbird.exe"
set "PROC_NAME=netbird.exe"

echo ======================================
echo NetBird - Stop Service
echo ======================================
echo.

REM Check if service exists
sc query NetBirdService >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    echo [DETECT] NetBird service found
    echo.
    echo [1] Stop service (keep installed)
    echo [2] Stop and uninstall service
    echo [3] Disconnect only
    echo.
    set /p choice=Choose:

    if "!choice!"=="1" (
        echo [STOP] Stopping NetBird service...
        net stop NetBirdService >nul 2>&1
        if "!ERRORLEVEL!"=="0" (
            echo [DONE] Service stopped
        ) else (
            echo [INFO] Service not running or stop failed
        )
        goto :end
    )

    if "!choice!"=="2" (
        echo [STOP] Stopping service...
        net stop NetBirdService >nul 2>&1
        echo [UNINSTALL] Uninstalling service...
        "%BIN_DIR%\%EXE%" service uninstall
        echo [DONE] Service uninstalled
        goto :end
    )

    if "!choice!"=="3" (
        goto :disconnect
    )
)

:disconnect
REM Disconnect (if running as foreground)
echo [DISCONNECT] Disconnecting NetBird...
"%BIN_DIR%\%EXE%" down

:end
echo.
pause
