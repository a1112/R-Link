@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "BIN_DIR=..\..\binaries\storage"
set "EXE=rclone.exe"

echo ======================================
echo Rclone - Copy Files
echo ======================================
echo.

if not exist "%BIN_DIR%\%EXE%" (
    echo [ERROR] %EXE% not found
    pause
    exit /b 1
)

echo [USAGE] Copy files to/from remote storage
echo.
echo Examples:
echo   Local to remote:  C:\files  gdrive:backup
echo   Remote to local:  gdrive:file.txt  C:\downloads
echo.

set /p source=Source path:
set /p dest=Destination path:

if "!source!"=="" or "!dest!"=="" (
    echo [ERROR] Path cannot be empty
    pause
    exit /b 1
)

echo.
echo [COPY] !source! -^> !dest!
echo.

"%BIN_DIR%\%EXE%" copy "!source!" "!dest!"

echo.
pause
