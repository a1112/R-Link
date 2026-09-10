@echo off
REM R-Link Tauri Build Script for Windows

echo ========================================
echo R-Link Tauri Build Script
echo ========================================

REM Check if Rust is installed
where cargo >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Rust/Cargo not found. Please install Rust from https://rustup.rs/
    pause
    exit /b 1
)

REM Check if Node.js is installed
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js not found. Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

echo.
echo [1/3] Installing dependencies...
call npm install
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo [2/3] Building frontend...
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to build frontend
    pause
    exit /b 1
)

echo.
echo [3/3] Building Tauri application...
call npm run tauri:build
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to build Tauri application
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build completed successfully!
echo Output directory: src-tauri\target\release\bundle\
echo ========================================
pause
