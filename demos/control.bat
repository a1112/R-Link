@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "VERSION=1.0.0"
set "TITLE=R-Link Control Panel v%VERSION%"

title %TITLE%

:main
cls
echo.
echo ======================================
echo   R-Link Integrated Tools
echo   Version: %VERSION%
echo ======================================
echo.
echo [Functions]
echo.
echo   [1] Streaming (Sunshine)
echo   [2] Networking (NetBird)
echo   [3] Storage (Rclone)
echo   [4] Tunnel (FRP)
echo.
echo   [9] Show all service status
echo   [0] Exit
echo.
set /p main_choice=Choose function:

if "%main_choice%"=="1" goto :streaming
if "%main_choice%"=="2" goto :networking
if "%main_choice%"=="3" goto :storage
if "%main_choice%"=="4" goto :tunnel
if "%main_choice%"=="9" goto :all_status
if "%main_choice%"=="0" exit /b 0

goto :main

:streaming
cls
echo.
echo ======================================
echo   Streaming (Sunshine)
echo ======================================
echo.
echo [1] Start service
echo [2] Stop service
echo [3] Show status
echo [0] Back to main menu
echo.
set /p choice=Choose:

if "%choice%"=="1" call streaming\start.bat
if "%choice%"=="2" call streaming\stop.bat
if "%choice%"=="3" call streaming\status.bat

goto :main

:networking
cls
echo.
echo ======================================
echo   Networking (NetBird)
echo ======================================
echo.
echo [1] Start/Connect
echo [2] Stop/Disconnect
echo [3] Show status
echo [4] Install service
echo [0] Back to main menu
echo.
set /p choice=Choose:

if "%choice%"=="1" call networking\start.bat
if "%choice%"=="2" call networking\stop.bat
if "%choice%"=="3" call networking\status.bat
if "%choice%"=="4" call networking\install.bat

goto :main

:storage
cls
echo.
echo ======================================
echo   Storage (Rclone)
echo ======================================
echo.
echo [1] Configuration wizard
echo [2] List remotes
echo [3] Browse files
echo [4] Copy files
echo [5] Sync files
echo [6] Mount as drive
echo [0] Back to main menu
echo.
set /p choice=Choose:

if "%choice%"=="1" call storage\config.bat
if "%choice%"=="2" call storage\list-remotes.bat
if "%choice%"=="3" call storage\ls.bat
if "%choice%"=="4" call storage\copy.bat
if "%choice%"=="5" call storage\sync.bat
if "%choice%"=="6" call storage\mount.bat

goto :main

:tunnel
cls
echo.
echo ======================================
echo   Tunnel (FRP)
echo ======================================
echo.
echo [1] Server operations
echo [2] Client operations
echo [0] Back to main menu
echo.
set /p choice=Choose:

if "%choice%"=="1" goto :frp_server
if "%choice%"=="2" goto :frp_client

goto :main

:frp_server
cls
echo.
echo ======================================
echo   FRP Server
echo ======================================
echo.
echo [1] Start server
echo [2] Stop server
echo [3] Show status
echo [0] Back
echo.
set /p choice=Choose:

if "%choice%"=="1" call tunnel\server-start.bat
if "%choice%"=="2" call tunnel\server-stop.bat
if "%choice%"=="3" call tunnel\server-status.bat

goto :tunnel

:frp_client
cls
echo.
echo ======================================
echo   FRP Client
echo ======================================
echo.
echo [1] Start client
echo [2] Stop client
echo [3] Show status
echo [0] Back
echo.
set /p choice=Choose:

if "%choice%"=="1" call tunnel\client-start.bat
if "%choice%"=="2" call tunnel\client-stop.bat
if "%choice%"=="3" call tunnel\client-status.bat

goto :tunnel

:all_status
cls
echo.
echo ======================================
echo   All Service Status
echo ======================================
echo.

echo [Streaming - Sunshine]
tasklist /FI "IMAGENAME eq sunshine.exe" 2>NUL | find /I /N "sunshine.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo   Status: Running
) else (
    echo   Status: Not running
)
echo.

echo [Networking - NetBird]
sc query NetBirdService >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    echo   Status: Service installed
    sc query NetBirdService | findstr STATE | findstr RUNNING >nul
    if "%ERRORLEVEL%"=="0" (
        echo           Running
    ) else (
        echo           Stopped
    )
) else (
    echo   Status: Service not installed
)
echo.

echo [Tunnel - FRP Server]
tasklist /FI "IMAGENAME eq frps.exe" 2>NUL | find /I /N "frps.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo   Status: Running
) else (
    echo   Status: Not running
)
echo.

echo [Tunnel - FRP Client]
tasklist /FI "IMAGENAME eq frpc.exe" 2>NUL | find /I /N "frpc.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo   Status: Running
) else (
    echo   Status: Not running
)
echo.

echo [Storage - Rclone]
echo   Status: On-demand
if exist "%USERPROFILE%\.config\rclone\rclone.conf" (
    echo   Config: Configured
) else (
    echo   Config: Not configured
)
echo.

pause
goto :main
