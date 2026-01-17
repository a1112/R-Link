@echo off
chcp 65001 >nul
set "BIN_DIR=..\..\binaries\storage"
set "EXE=rclone.exe"

echo ======================================
echo Rclone - List Remotes
echo ======================================
echo.

if not exist "%BIN_DIR%\%EXE%" (
    echo [ERROR] %EXE% not found
    pause
    exit /b 1
)

"%BIN_DIR%\%EXE%" listremotes

echo.
pause
