@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "BIN_DIR=..\..\binaries\streaming"
set "SRC_CONFIG=%~dp0config"
set "PROGRAMDATA_CONFIG=C:\ProgramData\Sunshine"

echo ======================================
echo Sunshine - Initialize Config
echo ======================================
echo.

REM Check binary
if not exist "%BIN_DIR%\sunshine.exe" (
    echo [ERROR] sunshine.exe not found
    pause
    exit /b 1
)

echo Sunshine requires config files in:
echo   %PROGRAMDATA_CONFIG%
echo.
echo [1] Install to ProgramData (recommended)
echo [2] Use portable config (current directory)
echo.
set /p choice=Choose:

if "%choice%"=="1" goto :install_programdata
if "%choice%"=="2" goto :install_portable

:install_programdata
echo.
echo [INSTALL] Installing to ProgramData...

REM Create directory
if not exist "%PROGRAMDATA_CONFIG%" (
    mkdir "%PROGRAMDATA_CONFIG%"
    mkdir "%PROGRAMDATA_CONFIG%\config"
)

REM Copy config files
if exist "%SRC_CONFIG%\sunshine.conf" (
    copy "%SRC_CONFIG%\sunshine.conf" "%PROGRAMDATA_CONFIG%\config\" /Y >nul
    echo [COPY] sunshine.conf
)

REM Copy assets from submodule if available
set "SUBMODULEAssets=..\..\..\submodules\sunshine\src_assets\windows\assets"
if exist "%SUBMODULEAssets%" (
    if not exist "%PROGRAMDATA_CONFIG%\config\assets" (
        mkdir "%PROGRAMDATA_CONFIG%\config\assets"
    )
    xcopy "%SUBMODULEAssets%" "%PROGRAMDATA_CONFIG%\config\assets\" /E /I /Y >nul
    echo [COPY] assets directory
)

REM Copy web assets
set "WEB_ASSETS=..\..\..\submodules\sunshine\src_assets\common\assets\web\public"
if exist "%WEB_ASSETS%" (
    if not exist "%PROGRAMDATA_CONFIG%\config\web" (
        mkdir "%PROGRAMDATA_CONFIG%\config\web"
    )
    xcopy "%WEB_ASSETS%" "%PROGRAMDATA_CONFIG%\config\web\" /E /I /Y >nul
    echo [COPY] web assets
)

echo.
echo [DONE] Config installed to %PROGRAMDATA_CONFIG%
echo.
echo You can now run: start.bat
pause
exit /b 0

:install_portable
echo.
echo [PORTABLE] Setting up portable config...

REM Create config in binary directory
if not exist "%BIN_DIR%\config" (
    mkdir "%BIN_DIR%\config"
)

if exist "%SRC_CONFIG%\sunshine.conf" (
    copy "%SRC_CONFIG%\sunshine.conf" "%BIN_DIR%\config\" /Y >nul
    echo [COPY] sunshine.conf
)

REM Copy assets
if not exist "%BIN_DIR%\config\assets" (
    mkdir "%BIN_DIR%\config\assets"
)

set "SUBMODULEAssets=..\..\..\submodules\sunshine\src_assets\windows\assets"
if exist "%SUBMODULEAssets%" (
    xcopy "%SUBMODULEAssets%" "%BIN_DIR%\config\assets\" /E /I /Y >nul
    echo [COPY] assets
)

REM Copy web assets
if not exist "%BIN_DIR%\config\web" (
    mkdir "%BIN_DIR%\config\web"
)

set "WEB_ASSETS=..\..\..\submodules\sunshine\src_assets\common\assets\web\public"
if exist "%WEB_ASSETS%" (
    xcopy "%WEB_ASSETS%" "%BIN_DIR%\config\web\" /E /I /Y >nul
    echo [COPY] web assets
)

echo.
echo [DONE] Portable config ready
echo.
echo Note: Sunshine in portable mode may have limited functionality
pause
exit /b 0
