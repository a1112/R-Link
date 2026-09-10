#!/bin/bash
# R-Link Tauri Development Build Script for macOS and Linux

echo "========================================"
echo "R-Link Tauri Development Mode"
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
echo "Installing dependencies..."
npm install

echo ""
echo "Starting Tauri development mode..."
npm run tauri:dev
