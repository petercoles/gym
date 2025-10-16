#!/usr/bin/env bash
# Render.com build script for Playwright browser installation

set -e  # Exit on any error

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Setting Playwright browser path..."
export PLAYWRIGHT_BROWSERS_PATH=/opt/render/project/.playwright-browsers
mkdir -p $PLAYWRIGHT_BROWSERS_PATH

echo "Installing Playwright browsers..."
playwright install chromium

echo "Verifying browser installation..."
if [ -d "$PLAYWRIGHT_BROWSERS_PATH" ]; then
    echo "✅ Browser path exists: $PLAYWRIGHT_BROWSERS_PATH"
    ls -la $PLAYWRIGHT_BROWSERS_PATH/
else
    echo "❌ Browser path not found: $PLAYWRIGHT_BROWSERS_PATH"
fi

echo "Testing browser launch..."
python test_browser.py || echo "⚠️ Browser test failed"

echo "Build complete!"