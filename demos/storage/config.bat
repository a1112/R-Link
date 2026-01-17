@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "BIN_DIR=..\..\binaries\storage"
set "EXE=rclone.exe"
set "CONFIG_FILE=%USERPROFILE%\.config\rclone\rclone.conf"

echo ======================================
echo Rclone - Cloud Storage Config
echo ======================================
echo.

REM Check binary
if not exist "%BIN_DIR%\%EXE%" (
    echo [ERROR] %EXE% not found
    echo Path: %BIN_DIR%\%EXE%
    pause
    exit /b 1
)

echo Supported storage:
echo   - Google Drive, Dropbox, OneDrive
echo   - Amazon S3, Aliyun OSS
echo   - WebDav (Jianguoyun, Nextcloud, etc.)
echo   - FTP, SFTP
echo   - Local folder
echo.

set /p choice=Start configuration? (Y/N):

if /i not "!choice!"=="Y" (
    exit /b 0
)

echo.
echo [START] Starting configuration wizard...
echo.
echo Config file: %CONFIG_FILE%
echo.

"%BIN_DIR%\%EXE%" config

echo.
echo ======================================
echo Configuration Complete!
echo ======================================
echo.
echo Common commands:
echo   list-remotes.bat    - List all remotes
echo   mount.bat           - Mount as network drive
echo   sync.bat            - Sync files
echo.

pause
