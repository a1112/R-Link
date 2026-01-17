@echo off
chcp 65001 >nul
set "BIN_DIR=..\..\binaries\storage"
set "EXE=rclone.exe"

echo ======================================
echo Rclone - List Remote Files
echo ======================================
echo.

if not exist "%BIN_DIR%\%EXE%" (
    echo [ERROR] %EXE% not found
    pause
    exit /b 1
)

REM List available remotes first
echo [Available remotes]:
"%BIN_DIR%\%EXE%" listremotes
echo.

set /p remote=Enter remote path (e.g. gdrive:folder):

if "!remote!"=="" (
    echo [ERROR] Path cannot be empty
    pause
    exit /b 1
)

echo.
echo [LISTING]: !remote!
echo.

"%BIN_DIR%\%EXE%" ls !remote!

echo.
pause
