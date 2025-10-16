#!/usr/bin/env python3
"""Test if Playwright browsers are properly installed"""

import os
import sys
from playwright.async_api import async_playwright

async def test_browser():
    """Test if chromium browser is available"""
    try:
        print(f"PLAYWRIGHT_BROWSERS_PATH: {os.getenv('PLAYWRIGHT_BROWSERS_PATH', 'Not set')}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            print("✅ Chromium browser launched successfully!")
            await browser.close()
            return True
    except Exception as e:
        print(f"❌ Browser launch failed: {e}")
        return False

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(test_browser())
    sys.exit(0 if success else 1)