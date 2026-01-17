@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "BIN_DIR=..\..\binaries\storage"
set "EXE=rclone.exe"

echo ======================================
echo Rclone - Sync Files
echo ======================================
echo.
echo [WARNING] sync is dangerous!
echo           Files in destination that differ from source will be deleted
echo.
echo For safety, use copy command instead
echo.
echo Continue?
set /p confirm=(Y/N):

if /i not "!confirm!"=="Y" (
    echo Cancelled
    pause
    exit /b 0
)

echo.
if not exist "%BIN_DIR%\%EXE%" (
    echo [ERROR] %EXE% not found
    pause
    exit /b 1
)

echo [USAGE] Sync source to destination
echo.
echo Examples:
echo   Local to remote:  C:\files  gdrive:backup
echo   Remote to local:  gdrive:backup  C:\files
echo.

set /p source=Source path:
set /p dest=Destination path:

if "!source!"=="" or "!dest!"=="" (
    echo [ERROR] Path cannot be empty
    pause
    exit /b 1
)

echo.
echo [PREVIEW] About to sync:
echo   Source: !source!
echo   Dest:   !dest!
echo.
set /p final_confirm=Execute? (Y/N):

if /i not "!final_confirm!"=="Y" (
    echo Cancelled
    pause
    exit /b 0
)

echo.
echo [SYNC] Syncing...
echo.

"%BIN_DIR%\%EXE%" sync "!source!" "!dest!" --progress

echo.
echo [DONE]
pause
