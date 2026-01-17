@echo off
chcp 65001 >nul

set "BIN_DIR=..\..\binaries\streaming"
set "EXE=sunshinesvc.exe"

echo ======================================
echo Sunshine - Install as Service
echo ======================================
echo.

if not exist "%BIN_DIR%\%EXE%" (
    echo [ERROR] %EXE% not found
    pause
    exit /b 1
)

echo [INSTALL] Installing Sunshine as Windows service...
echo.

cd /D "%BIN_DIR%"
"%EXE%" install

if "%ERRORLEVEL%"=="0" (
    echo.
    echo [SUCCESS] Service installed!
    echo.
    echo Starting service...
    net start SunshineService
    echo.
    echo Web UI: http://localhost:47990
) else (
    echo [FAILED] Installation failed
)

echo.
pause
