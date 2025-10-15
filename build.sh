#!/usr/bin/env bash
# Render.com build script for Playwright browser installation

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Playwright browsers..."
playwright install chromium

echo "Build complete!"