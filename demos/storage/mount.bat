@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "BIN_DIR=..\..\binaries\storage"
set "EXE=rclone.exe"

echo ======================================
echo Rclone - Mount as Drive
echo ======================================
echo.

if not exist "%BIN_DIR%\%EXE%" (
    echo [ERROR] %EXE% not found
    pause
    exit /b 1
)

REM Check WinFsp
where mount >nul 2>&1
if "%ERRORLEVEL%" neq "0" (
    echo [WARNING] WinFsp not detected
    echo.
    echo Mount feature requires WinFsp:
    echo https://winfsp.dev/
    echo.
    pause
    exit /b 1
)

REM List available remotes
echo [Available remotes]:
"%BIN_DIR%\%EXE%" listremotes
echo.

set /p remote=Enter remote to mount (e.g. gdrive:):
set /p drive=Enter drive letter (e.g. R):

if "!remote!"=="" (
    echo [ERROR] Remote path cannot be empty
    pause
    exit /b 1
)

REM Default drive
if "!drive!"=="" set drive=R

echo.
echo [MOUNT] !remote! -^> !drive!:
echo.
echo Press Ctrl+C to unmount
echo.

"%BIN_DIR%\%EXE%" mount !remote! !drive!: --vfs-cache-mode full

echo.
echo [UNMOUNTED]
pause
