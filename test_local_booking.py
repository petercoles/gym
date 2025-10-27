#!/usr/bin/env python3
"""
Local testing script for gym booking bot
Run this locally to test booking functionality without deploying to Render
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from gym_booking_bot import GymBookingBot
from playwright.async_api import async_playwright
import os

DAY_NAME_TO_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

def _normalize_day(day_name: str) -> str:
    """Validate and normalize a day-of-week string."""
    if not day_name:
        raise ValueError("Day name is required")
    day = day_name.strip().lower()
    if day not in DAY_NAME_TO_INDEX:
        raise ValueError(f"Invalid day '{day_name}'. Expected one of {', '.join(DAY_NAME_TO_INDEX.keys())}.")
    return day

def _compute_target_date_from_offset(days_ahead: int) -> datetime:
    """Return the date that is exactly `days_ahead` days from today."""
    base_date = datetime.now().date() + timedelta(days=days_ahead)
    return datetime.combine(base_date, datetime.min.time())

def _parse_env_int(name: str, default: int) -> int:
    """Parse an integer from environment variables with a fallback."""
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default

async def test_swim_booking(
    user: Optional[str] = None,
    day_name: Optional[str] = None,
    time_str: Optional[str] = None,
    duration: Optional[int] = None,
    target_date_override: Optional[str] = None,
    days_ahead: Optional[int] = None,
) -> bool:
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
    
    user = (user or os.getenv('TEST_SWIM_USER') or "peter").lower()
    day_name = day_name or os.getenv('TEST_SWIM_DAY') or "tuesday"
    time_str = time_str or os.getenv('TEST_SWIM_TIME') or "16:00"
    duration = duration or _parse_env_int('TEST_SWIM_DURATION', 30)
    days_ahead_value = days_ahead if days_ahead is not None else _parse_env_int('TEST_SWIM_DAYS_AHEAD', 8)

    if target_date_override:
        try:
            target_date = datetime.strptime(target_date_override, "%Y-%m-%d")
        except ValueError:
            print(f"❌ Invalid target date override '{target_date_override}'. Expected YYYY-MM-DD.")
            return False
    else:
        target_date = _compute_target_date_from_offset(days_ahead_value)

    # Warn if the computed day does not line up with the schedule day
    try:
        normalized_day = _normalize_day(day_name)
    except ValueError as exc:
        print(f"❌ {exc}")
        return False

    actual_day = target_date.strftime('%A').lower()
    days_out = (target_date.date() - datetime.now().date()).days
    if actual_day != normalized_day:
        print(f"⚠️  Target date {target_date.strftime('%Y-%m-%d')} is a {actual_day.title()}, not {normalized_day.title()}.")
        print("   Adjust TEST_SWIM_DAYS_AHEAD or use the custom option to enter an exact date.")

    print(f"➡️  Swim test is {days_out} days ahead (configured {days_ahead_value} days).")
    
    print(f"📅 Target date: {target_date.strftime('%Y-%m-%d (%A)')}")
    
    # Test parameters - use actual schedule values
    test_user = user
    test_duration = duration  # 15 or 30 minutes  
    test_time = time_str  # Configurable via env/arguments
    
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
        temp_bot = GymBookingBot(user_name=test_user)
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

async def test_class_booking(
    user: Optional[str] = None,
    day_name: Optional[str] = None,
    time_str: Optional[str] = None,
    instructor: Optional[str] = None,
    target_date_override: Optional[str] = None,
    days_ahead: Optional[int] = None,
) -> bool:
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
    
    user = (user or os.getenv('TEST_CLASS_USER') or "peter").lower()
    day_name = day_name or os.getenv('TEST_CLASS_DAY') or "saturday"
    time_str = time_str or os.getenv('TEST_CLASS_TIME') or "08:15"
    instructor = instructor or os.getenv('TEST_CLASS_INSTRUCTOR') or "Mari"
    days_ahead_value = days_ahead if days_ahead is not None else _parse_env_int('TEST_CLASS_DAYS_AHEAD', 3)

    if target_date_override:
        try:
            target_date = datetime.strptime(target_date_override, "%Y-%m-%d")
        except ValueError:
            print(f"❌ Invalid target date override '{target_date_override}'. Expected YYYY-MM-DD.")
            return False
    else:
        target_date = _compute_target_date_from_offset(days_ahead_value)

    try:
        normalized_day = _normalize_day(day_name)
    except ValueError as exc:
        print(f"❌ {exc}")
        return False

    actual_day = target_date.strftime('%A').lower()
    days_out = (target_date.date() - datetime.now().date()).days
    if actual_day != normalized_day:
        print(f"⚠️  Target date {target_date.strftime('%Y-%m-%d')} is a {actual_day.title()}, not {normalized_day.title()}.")
        print("   Adjust TEST_CLASS_DAYS_AHEAD or use the custom option to enter an exact date.")

    print(f"➡️  Class test is {days_out} days ahead (configured {days_ahead_value} days).")
    
    print(f"📅 Target date: {target_date.strftime('%Y-%m-%d (%A)')}")
    
    # Test parameters - use Mari's class which should have spaces
    test_user = user
    test_instructor = instructor
    test_time = time_str
    
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
    default_day = os.getenv('TEST_SWIM_DAY') or "tuesday"
    default_time = os.getenv('TEST_SWIM_TIME') or "16:00"
    default_duration = _parse_env_int('TEST_SWIM_DURATION', 30)
    default_days_ahead = _parse_env_int('TEST_SWIM_DAYS_AHEAD', 8)

    suggested_date = _compute_target_date_from_offset(default_days_ahead)

    print("Enter test parameters (leave blank to use defaults):")
    date_str = input(f"Date (YYYY-MM-DD) [{suggested_date.strftime('%Y-%m-%d')}]: ").strip()
    time_str = input(f"Time (HH:MM) [{default_time}]: ").strip()
    duration_str = input(f"Duration (15 or 30) [{default_duration}]: ").strip()

    try:
        if date_str:
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            target_date = suggested_date

        test_duration = int(duration_str) if duration_str else default_duration
        if test_duration not in [15, 30]:
            raise ValueError("Duration must be 15 or 30")

        time_str = time_str or default_time
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

    swim_day = os.getenv('TEST_SWIM_DAY') or "tuesday"
    swim_time = os.getenv('TEST_SWIM_TIME') or "16:00"
    swim_duration = _parse_env_int('TEST_SWIM_DURATION', 30)
    swim_days_ahead = _parse_env_int('TEST_SWIM_DAYS_AHEAD', 8)

    try:
        normalized_swim_day = _normalize_day(swim_day)
    except ValueError as exc:
        swim_preview = f"⚠️  {exc}"
    else:
        swim_preview_date = _compute_target_date_from_offset(swim_days_ahead)
        actual_day = swim_preview_date.strftime('%A').lower()
        warning = ""
        if actual_day != normalized_swim_day:
            warning = f" ⚠️ (falls on {actual_day.title()})"
        swim_preview = f"{swim_preview_date.strftime('%Y-%m-%d (%A)')} at {swim_time} ({swim_duration}min){warning}"

    class_day = os.getenv('TEST_CLASS_DAY') or "saturday"
    class_time = os.getenv('TEST_CLASS_TIME') or "08:15"
    class_instructor = os.getenv('TEST_CLASS_INSTRUCTOR') or "Mari"
    class_days_ahead = _parse_env_int('TEST_CLASS_DAYS_AHEAD', 3)

    try:
        normalized_class_day = _normalize_day(class_day)
    except ValueError as exc:
        class_preview = f"⚠️  {exc}"
    else:
        class_preview_date = _compute_target_date_from_offset(class_days_ahead)
        actual_day = class_preview_date.strftime('%A').lower()
        warning = ""
        if actual_day != normalized_class_day:
            warning = f" ⚠️ (falls on {actual_day.title()})"
        class_preview = f"{class_preview_date.strftime('%Y-%m-%d (%A)')} at {class_time} with {class_instructor}{warning}"
    
    # Test what you need
    print("Choose test type:")
    print(f"1. Swim booking ({swim_preview})")
    print(f"2. Class booking ({class_preview})")
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
