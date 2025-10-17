#!/usr/bin/env python3
"""
Local testing script for gym booking bot
Run this locally to test booking functionality without deploying to Render
"""

import asyncio
from datetime import datetime, timedelta
from gym_booking_bot import GymBookingBot
from playwright.async_api import async_playwright
import os

async def test_swim_booking():
    """Test swim booking functionality locally"""
    print("🧪 Testing swim booking locally...")
    
    # Check for required environment variables
    if not os.getenv('PETER_USERNAME') or not os.getenv('PETER_PASSWORD'):
        print("❌ Missing credentials in .env file")
        print("   Please set PETER_USERNAME and PETER_PASSWORD")
        return False
    
    if not os.getenv('GYM_URL'):
        print("❌ Missing GYM_URL in .env file")
        return False
    
    # Create a test date (Saturday, October 25th - future date with full slot availability)
    target_date = datetime(2025, 10, 25)  # Force a specific future Saturday
    
    print(f"📅 Target date: {target_date.strftime('%Y-%m-%d (%A)')}")
    
    # Test parameters - use actual schedule values
    test_user = "peter"
    test_duration = 15  # 15 or 30 minutes  
    test_time = "14:00"  # Time from schedule: peter,Swim(15),saturday,14:00
    
    print(f"👤 User: {test_user}")
    print(f"⏱️  Duration: {test_duration} minutes")
    print(f"🕐 Time: {test_time}")
    
    # Create bot instance
    # Set headless=False via environment variable for testing
    os.environ['HEADLESS'] = 'false'
    bot = GymBookingBot(user_name=test_user)
    
    async with async_playwright() as p:
        # Use the same browser detection logic as the main bot
        import platform
        
        # Use bot's browser detection method
        temp_bot = GymBookingBot(user_name="peter")
        is_local, browser_path = temp_bot._detect_browser_environment()
        
        if is_local and browser_path:
            browser = await p.chromium.launch(
                headless=False,  # Always show browser for testing
                executable_path=browser_path
            )
        else:
            browser = await p.chromium.launch(headless=False)
        
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # Login
            print("🔑 Attempting login...")
            if not await bot.login(page):
                print("❌ Login failed")
                return False
            
            print("✅ Login successful!")
            
            # Test swim booking
            print(f"🏊 Testing swim booking for {target_date.strftime('%Y-%m-%d')} at {test_time}...")
            success = await bot.book_swim_lane(page, target_date, test_duration, test_time)
            
            if success:
                print(f"🎉 Swim booking test SUCCESSFUL: {test_duration}min at {test_time}")
                return True
            else:
                print(f"❌ Swim booking test FAILED: {test_duration}min at {test_time}")
                return False
                
        except Exception as e:
            print(f"❌ Test error: {e}")
            return False
        finally:
            await browser.close()

async def test_class_booking():
    """Test class booking functionality locally"""
    print("🧪 Testing class booking locally...")
    
    # Check for required environment variables
    if not os.getenv('PETER_USERNAME') or not os.getenv('PETER_PASSWORD'):
        print("❌ Missing credentials in .env file")
        print("   Please set PETER_USERNAME and PETER_PASSWORD")
        return False
    
    if not os.getenv('GYM_URL'):
        print("❌ Missing GYM_URL in .env file")
        return False
    
    # Find a Saturday within the bookable window - be more conservative
    today = datetime.now()
    
    # Start with next Saturday
    days_ahead = 5 - today.weekday()  # Saturday is 5
    if days_ahead <= 0:  # Today is Saturday or later in the week
        days_ahead += 7  # Get next Saturday
    
    # For classes, bookable window is usually shorter - try 3-5 days ahead first
    if days_ahead < 3:  # Too close
        days_ahead += 7
    elif days_ahead > 5:  # Might be too far, try the Saturday before
        days_ahead -= 7
        if days_ahead < 3:  # If that's too close, go back to the later one
            days_ahead += 7
        
    target_date = today + timedelta(days=days_ahead)
    
    print(f"🗓️  Calculated target date: {target_date.strftime('%Y-%m-%d (%A)')} ({days_ahead} days from today)")
    print("   This should be within the class booking window")
    
    print(f"📅 Target date: {target_date.strftime('%Y-%m-%d (%A)')}")
    
    # Test parameters - use Mari's Saturday class which should have spaces
    test_user = "peter"
    test_instructor = "Mari"  # From schedule: peter,Mari,saturday,08:15
    test_time = "08:15"  # Time from schedule
    
    print(f"👤 User: {test_user}")
    print(f"👨‍🏫 Instructor: {test_instructor}")
    print(f"🕐 Time: {test_time}")
    
    # Create bot instance
    # Set headless=False via environment variable for testing
    os.environ['HEADLESS'] = 'false'
    bot = GymBookingBot(user_name=test_user)
    
    async with async_playwright() as p:
        # Use the same browser detection logic
        import platform
        
        is_local = (
            os.getenv('RENDER') is None and
            platform.system() == 'Darwin'
        )
        
        if is_local:
            print("🏠 Running locally - using local Chromium installation")
            local_chromium_paths = [
                '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                '/usr/local/bin/chromium',
                '/opt/homebrew/bin/chromium',
                '/Applications/Chromium.app/Contents/MacOS/Chromium'
            ]
            
            browser_path = None
            for path in local_chromium_paths:
                if os.path.exists(path):
                    browser_path = path
                    print(f"✅ Found browser at: {browser_path}")
                    break
            
            if browser_path:
                browser = await p.chromium.launch(
                    headless=False,
                    executable_path=browser_path
                )
            else:
                print("⚠️  No local browser found, trying default Playwright installation")
                browser = await p.chromium.launch(headless=False)
        else:
            browser = await p.chromium.launch(headless=False)
        
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # Login
            print("🔑 Attempting login...")
            if not await bot.login(page):
                print("❌ Login failed")
                return False
            
            print("✅ Login successful!")
            
            # Test class booking
            print(f"💪 Testing class booking for {target_date.strftime('%Y-%m-%d')} at {test_time}...")
            success = await bot.book_class(page, target_date, test_instructor, test_time)
            
            if success:
                print(f"🎉 Class booking test SUCCESSFUL: {test_instructor} at {test_time}")
                return True
            else:
                print(f"❌ Class booking test FAILED: {test_instructor} at {test_time}")
                return False
                
        except Exception as e:
            print(f"❌ Test error: {e}")
            return False
        finally:
            await browser.close()

async def test_custom_swim_booking():
    """Test swim booking with custom parameters"""
    print("🧪 Custom swim booking test...")
    
    # Check for required environment variables
    if not os.getenv('PETER_USERNAME') or not os.getenv('PETER_PASSWORD'):
        print("❌ Missing credentials in .env file")
        return False
    
    if not os.getenv('GYM_URL'):
        print("❌ Missing GYM_URL in .env file")
        return False
    
    # Get custom parameters
    print("Enter test parameters:")
    date_str = input("Date (YYYY-MM-DD, e.g., 2025-10-25): ").strip()
    time_str = input("Time (HH:MM, e.g., 14:00): ").strip()
    duration_str = input("Duration (15 or 30): ").strip()
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        test_duration = int(duration_str)
        if test_duration not in [15, 30]:
            raise ValueError("Duration must be 15 or 30")
    except ValueError as e:
        print(f"❌ Invalid input: {e}")
        return False
    
    print(f"📅 Target date: {target_date.strftime('%Y-%m-%d (%A)')}")
    print(f"⏱️  Duration: {test_duration} minutes")
    print(f"🕐 Time: {time_str}")
    
    # Set headless=False via environment variable for testing
    os.environ['HEADLESS'] = 'false'
    bot = GymBookingBot(user_name="peter")
    
    async with async_playwright() as p:
        # Use the same browser detection logic as the main bot
        import platform
        
        is_local = (
            os.getenv('RENDER') is None and
            platform.system() == 'Darwin'
        )
        
        if is_local:
            print("🏠 Running locally - using local Chromium installation")
            local_chromium_paths = [
                '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                '/usr/local/bin/chromium',
                '/opt/homebrew/bin/chromium',
                '/Applications/Chromium.app/Contents/MacOS/Chromium'
            ]
            
            browser_path = None
            for path in local_chromium_paths:
                if os.path.exists(path):
                    browser_path = path
                    print(f"✅ Found browser at: {browser_path}")
                    break
            
            if browser_path:
                browser = await p.chromium.launch(
                    headless=False,
                    executable_path=browser_path
                )
            else:
                print("⚠️  No local browser found, trying default Playwright installation")
                browser = await p.chromium.launch(headless=False)
        else:
            browser = await p.chromium.launch(headless=False)
        
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # Login
            print("🔑 Attempting login...")
            if not await bot.login(page):
                print("❌ Login failed")
                return False
            
            print("✅ Login successful!")
            
            # Test swim booking
            print(f"🏊 Testing custom swim booking for {target_date.strftime('%Y-%m-%d')} at {time_str}...")
            success = await bot.book_swim_lane(page, target_date, test_duration, time_str)
            
            if success:
                print(f"🎉 Custom swim booking test SUCCESSFUL: {test_duration}min at {time_str}")
                return True
            else:
                print(f"❌ Custom swim booking test FAILED: {test_duration}min at {time_str}")
                return False
                
        except Exception as e:
            print(f"❌ Test error: {e}")
            return False
        finally:
            await browser.close()

async def main():
    """Main test function"""
    print("🧪 Local Gym Booking Bot Test")
    print("=" * 40)
    
    # Test what you need
    print("Choose test type:")
    print("1. Swim booking (Saturday Oct 25th, 14:00)")
    print("2. Class booking (Next Saturday, Mari 08:15)")
    print("3. Both")
    print("4. Custom swim test")
    
    choice = input("Enter choice (1-4): ").strip()
    
    if choice == "1":
        await test_swim_booking()
    elif choice == "2":
        await test_class_booking()
    elif choice == "3":
        print("\n🏊 Testing swim booking first...")
        await test_swim_booking()
        print("\n💪 Testing class booking next...")
        await test_class_booking()
    elif choice == "4":
        await test_custom_swim_booking()
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    asyncio.run(main())