@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "BIN_DIR=..\..\binaries\networking"
set "EXE=netbird.exe"

echo ======================================
echo NetBird - Service Install
echo ======================================
echo.

REM Check binary
if not exist "%BIN_DIR%\%EXE%" (
    echo [ERROR] %EXE% not found
    pause
    exit /b 1
)

REM Check if already installed
sc query NetBirdService >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    echo [STATUS] NetBird service already installed
    echo.
    echo [1] Uninstall service
    echo [2] Reinstall service
    echo [0] Cancel
    echo.
    set /p choice=Choose:

    if "!choice!"=="1" (
        echo [UNINSTALL] Uninstalling service...
        "%BIN_DIR%\%EXE%" service uninstall
        echo [DONE] Service uninstalled
        pause
        exit /b 0
    )

    if "!choice!"=="2" (
        echo [UNINSTALL] Uninstalling old service first...
        net stop NetBirdService >nul 2>&1
        "%BIN_DIR%\%EXE%" service uninstall
        timeout /t 2 /nobreak >nul
    )
)

echo.
echo [INSTALL] Installing NetBird service...
echo.
echo After installation, NetBird will:
echo   - Auto start on boot
echo   - Run in background
echo   - Auto reconnect
echo.

"%BIN_DIR%\%EXE%" service install

if "%ERRORLEVEL%"=="0" (
    echo.
    echo [SUCCESS] Service installed!
    echo.
    echo First time setup:
    echo   1. Run: start.bat
    echo   2. Or use: netbird up --setup-key YOUR_KEY
) else (
    echo.
    echo [FAILED] Service installation failed
)

echo.
pause
