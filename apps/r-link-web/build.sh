#!/bin/bash
# R-Link Tauri Build Script for macOS and Linux

echo "========================================"
echo "R-Link Tauri Build Script"
echo "========================================"

# Check if Rust is installed
if ! command -v cargo &> /dev/null; then
    echo "[ERROR] Rust/Cargo not found. Please install Rust from https://rustup.rs/"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "[ERROR] Node.js not found. Please install Node.js from https://nodejs.org/"
    exit 1
fi

echo ""
echo "[1/3] Installing dependencies..."
npm install
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install dependencies"
    exit 1
fi

echo ""
echo "[2/3] Building frontend..."
npm run build
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to build frontend"
    exit 1
fi

echo ""
echo "[3/3] Building Tauri application..."
npm run tauri:build
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to build Tauri application"
    exit 1
fi

echo ""
echo "========================================"
echo "Build completed successfully!"
echo "Output directory: src-tauri/target/release/bundle/"
echo "========================================"
