@echo off
chcp 65001 >nul
REM R-Link Quick Launch
REM For full control run: control.bat

echo ======================================
echo R-Link - Integrated Tools
echo ======================================
echo.
echo [1] Control Panel (recommended)
echo [2] Sunshine - Game streaming
echo [3] NetBird - Remote networking
echo [4] Rclone - Cloud storage
echo [5] FRP - Tunnel
echo [0] Exit
echo.

set /p choice=Choose:

if "%choice%"=="1" (
    call control.bat
)
if "%choice%"=="2" (
    call streaming\start.bat
)
if "%choice%"=="3" (
    call networking\start.bat
)
if "%choice%"=="4" (
    call storage\list-remotes.bat
)
if "%choice%"=="5" (
    call tunnel\client-start.bat
)
