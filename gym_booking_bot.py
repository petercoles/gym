"""
Gym Class and Swim Lane Booking Automation Bot using Playwright

This script automates the process of logging into a gym website and booking classes
or swim lanes 8 days ahead of the current date.

Simplified version without state management - relies on 15-minute booking windows
to prevent duplicates naturally.
"""

import asyncio
import os
from datetime import datetime, timedelta
import pytz
from playwright.async_api import async_playwright, Page, Browser

class GymBookingBot:
    def __init__(self, user_name: str = "peter"):
        self.gym_url = os.getenv('GYM_URL')
        if not self.gym_url:
            raise ValueError("Please set GYM_URL in your .env file")
        self.user_name = user_name.upper()
        
        # Load credentials for the specified user
        self.username = os.getenv(f'{self.user_name}_USERNAME')
        self.password = os.getenv(f'{self.user_name}_PASSWORD')
        self.headless = os.getenv('HEADLESS', 'false').lower() == 'true'
        
        if not self.username or not self.password:
            raise ValueError(f"Please set {self.user_name}_USERNAME and {self.user_name}_PASSWORD in your .env file")

    async def login(self, page: Page) -> bool:
        """
        Log into the gym website
        
        Args:
            page: Playwright page object
            
        Returns:
            True if login successful, False otherwise
        """
        try:
            # Navigate to gym website
            await page.goto(self.gym_url)
            await page.wait_for_load_state('networkidle')
            
            # Look for login form
            username_field = page.locator('input[name="username"], input[type="email"], input[id*="user"], input[id*="email"]').first
            password_field = page.locator('input[name="password"], input[type="password"], input[id*="pass"]').first
            login_button = page.locator('button[type="submit"], input[type="submit"], button:has-text("Log"), button:has-text("Sign")').first
            
            # Fill credentials
            await username_field.fill(self.username)
            await password_field.fill(self.password)
            
            # Click login
            await login_button.click()
            await page.wait_for_load_state('networkidle')
            
            # Check if login was successful
            if await page.locator('text=Dashboard, text=Welcome, text=Bookings').count() > 0:
                print(f"✅ Login successful for {self.user_name}")
                return True
            else:
                print(f"❌ Login failed for {self.user_name}")
                return False
                
        except Exception as e:
            print(f"❌ Login error for {self.user_name}: {e}")
            return False

    async def book_class(self, page: Page, target_date: datetime, instructor: str, time: str) -> bool:
        """
        Book a gym class by instructor and time
        
        Args:
            page: Playwright page object
            target_date: Date to book for
            instructor: Instructor name
            time: Class time (HH:MM format)
            
        Returns:
            True if booking successful, False otherwise
        """
        try:
            # Navigate to bookings page
            bookings_link = page.locator('a:has-text("Book"), a:has-text("Classes"), a:has-text("Schedule")').first
            await bookings_link.click()
            await page.wait_for_load_state('networkidle')
            
            # Navigate to target date
            target_date_str = target_date.strftime("%Y-%m-%d")
            date_element = page.locator(f'[data-date="{target_date_str}"], text="{target_date.day}"').first
            
            if await date_element.count() > 0:
                await date_element.click()
                await page.wait_for_load_state('networkidle')
            
            # Look for class with matching instructor and time
            class_locator = page.locator(f'text="{instructor}"').locator('..').locator(f'text="{time}"').locator('..')
            book_button = class_locator.locator('button:has-text("Book"), a:has-text("Book")').first
            
            if await book_button.count() > 0:
                await book_button.click()
                await page.wait_for_load_state('networkidle')
                
                # Confirm booking if needed
                confirm_button = page.locator('button:has-text("Confirm"), button:has-text("Yes")').first
                if await confirm_button.count() > 0:
                    await confirm_button.click()
                    await page.wait_for_load_state('networkidle')
                
                print(f"✅ Class booked: {instructor} at {time} on {target_date_str}")
                return True
            else:
                print(f"❌ Class not available: {instructor} at {time} on {target_date_str}")
                return False
                
        except Exception as e:
            print(f"❌ Error booking class {instructor} at {time}: {e}")
            return False

    async def book_swim_lane(self, page: Page, target_date: datetime, duration: int, time: str) -> bool:
        """
        Book a swim lane
        
        Args:
            page: Playwright page object
            target_date: Date to book for
            duration: Duration in minutes (15 or 30)
            time: Start time (HH:MM format)
            
        Returns:
            True if booking successful, False otherwise
        """
        try:
            # Navigate to swim bookings
            swim_link = page.locator('a:has-text("Swim"), a:has-text("Pool"), a:has-text("Lane")').first
            await swim_link.click()
            await page.wait_for_load_state('networkidle')
            
            # Navigate to target date
            target_date_str = target_date.strftime("%Y-%m-%d")
            date_element = page.locator(f'[data-date="{target_date_str}"], text="{target_date.day}"').first
            
            if await date_element.count() > 0:
                await date_element.click()
                await page.wait_for_load_state('networkidle')
            
            # Look for swim slot with matching time and duration
            time_slot = page.locator(f'text="{time}"').locator('..').locator(f'text="{duration}"').locator('..')
            book_button = time_slot.locator('button:has-text("Book"), a:has-text("Book")').first
            
            if await book_button.count() > 0:
                await book_button.click()
                await page.wait_for_load_state('networkidle')
                
                # Confirm booking if needed
                confirm_button = page.locator('button:has-text("Confirm"), button:has-text("Yes")').first
                if await confirm_button.count() > 0:
                    await confirm_button.click()
                    await page.wait_for_load_state('networkidle')
                
                print(f"✅ Swim booked: {duration}min at {time} on {target_date_str}")
                return True
            else:
                print(f"❌ Swim slot not available: {duration}min at {time} on {target_date_str}")
                return False
                
        except Exception as e:
            print(f"❌ Error booking swim {duration}min at {time}: {e}")
            return False

    async def _load_schedule(self) -> list:
        """
        Load schedule from S3 bucket
        
        Returns:
            List of schedule entries
        """
        # Get S3 configuration (required)
        s3_bucket = os.getenv('SCHEDULE_S3_BUCKET')
        s3_key = os.getenv('SCHEDULE_S3_KEY', 'schedule.csv')
        
        if not s3_bucket:
            raise ValueError("SCHEDULE_S3_BUCKET environment variable is required")
        
        print(f"Loading schedule from S3: s3://{s3_bucket}/{s3_key}")
        return await self._load_schedule_from_s3(s3_bucket, s3_key)

    async def _load_schedule_from_s3(self, s3_bucket: str, s3_key: str) -> list:
        """
        Load schedule from S3 bucket
        
        Args:
            s3_bucket: S3 bucket name
            s3_key: S3 object key (file path)
            
        Returns:
            List of schedule entries
        """
        try:
            import boto3
            s3_client = boto3.client('s3')
            
            # Download schedule from S3
            response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
            schedule_content = response['Body'].read().decode('utf-8')
            
            print(f"Successfully downloaded schedule from s3://{s3_bucket}/{s3_key}")
            
            # Parse CSV content
            return self._parse_schedule_content(schedule_content)
            
        except ImportError:
            print("Error: boto3 package required for S3 schedule loading. Install with: pip install boto3")
            return []
        except Exception as e:
            print(f"Error loading schedule from S3 s3://{s3_bucket}/{s3_key}: {e}")
            return []

    def _parse_schedule_content(self, content: str) -> list:
        """
        Parse schedule content from CSV string
        
        Args:
            content: CSV content as string
            
        Returns:
            List of schedule entries
        """
        import csv
        from io import StringIO
        
        schedule = []
        
        try:
            # Skip comment lines and empty lines
            lines = []
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    lines.append(line)
            
            if not lines:
                print("Schedule content is empty or contains only comments")
                return []
            
            # Parse CSV from the cleaned lines
            csv_reader = csv.DictReader(lines)
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 because of header
                try:
                    # Clean up the row data
                    user = row.get('user', '').strip().lower()
                    instructor = row.get('instructor', '').strip()
                    day_of_week = row.get('day_of_week', '').strip().lower()
                    time = row.get('time', '').strip()
                    
                    # Validate required fields
                    if not all([user, instructor, day_of_week, time]):
                        print(f"Skipping incomplete row {row_num}: {row}")
                        continue
                    
                    # Validate user
                    if user not in ['peter', 'adrienne', 'lucy']:
                        print(f"Skipping row {row_num}: Invalid user '{user}' (must be peter, adrienne, or lucy)")
                        continue
                    
                    # Validate day of week
                    valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                    if day_of_week not in valid_days:
                        print(f"Skipping row {row_num}: Invalid day_of_week '{day_of_week}' (must be monday-sunday)")
                        continue
                    
                    # Validate time format
                    try:
                        time_parts = time.split(':')
                        if len(time_parts) != 2:
                            raise ValueError("Invalid format")
                        hour, minute = int(time_parts[0]), int(time_parts[1])
                        if not (0 <= hour <= 23 and 0 <= minute <= 59):
                            raise ValueError("Invalid time range")
                        # Check if time is on quarter hour
                        if minute not in [0, 15, 30, 45]:
                            print(f"Warning row {row_num}: Time '{time}' is not on quarter hour (00, 15, 30, 45)")
                    except ValueError:
                        print(f"Skipping row {row_num}: Invalid time format '{time}' (must be HH:MM)")
                        continue
                    
                    schedule.append({
                        'user': user,
                        'instructor': instructor,
                        'day_of_week': day_of_week,
                        'time': time,
                        'row_num': row_num
                    })
                    
                except Exception as e:
                    print(f"Error processing row {row_num}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error parsing schedule content: {e}")
            return []
        
        print(f"Loaded {len(schedule)} valid schedule entries")
        return schedule

    def _is_booking_time(self, schedule_entry: dict, current_time: datetime) -> tuple[bool, datetime]:
        """
        Check if it's time to make a booking for a schedule entry
        
        Args:
            schedule_entry: Schedule entry dictionary
            current_time: Current datetime (timezone-aware UK time)
            
        Returns:
            Tuple of (should_book: bool, target_date: datetime)
        """
        # Calculate target date (8 days from now)
        target_date = current_time.date() + timedelta(days=8)
        
        # Check if target date matches the scheduled day of week
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        target_day_name = day_names[target_date.weekday()]
        
        if target_day_name != schedule_entry['day_of_week']:
            return False, target_date
        
        # Parse scheduled time
        scheduled_time_parts = schedule_entry['time'].split(':')
        scheduled_hour = int(scheduled_time_parts[0])
        scheduled_minute = int(scheduled_time_parts[1])
        
        # Check if current time has reached the scheduled time for booking
        current_time = current_time.replace(second=0, microsecond=0)  # Remove seconds/microseconds
        scheduled_time = current_time.replace(hour=scheduled_hour, minute=scheduled_minute)
        
        # Should book if current time >= scheduled time and within the same 15-minute window
        if current_time >= scheduled_time:
            # Check we're still in the same 15-minute window (to avoid re-booking)
            minutes_passed = (current_time - scheduled_time).total_seconds() / 60
            if minutes_passed < 15:  # Within 15 minutes of booking time
                return True, target_date
        
        return False, target_date

    def _parse_swim_instructor(self, instructor: str) -> tuple[bool, int]:
        """
        Parse instructor string to determine if it's a swim booking and extract duration
        
        Args:
            instructor: Instructor string (e.g., 'Mari' or 'Swim(30)')
            
        Returns:
            Tuple of (is_swim: bool, duration: int)
        """
        import re
        
        if not instructor.lower().startswith('swim'):
            return False, 0
        
        # Extract duration from "Swim(30)" format
        match = re.search(r'swim\((\d+)\)', instructor.lower())
        if match:
            duration = int(match.group(1))
            if duration in [15, 30]:
                return True, duration
        
        print(f"Invalid swim format '{instructor}' - should be 'Swim(15)' or 'Swim(30)'")
        return False, 0

    async def run_scheduled_bookings(self):
        """
        Process the schedule from S3 and make any bookings that are due
        """        
        # Use UK timezone (handles BST automatically)
        uk_tz = pytz.timezone('Europe/London')
        current_time = datetime.now(uk_tz)
        
        print(f"🔍 Checking schedule at {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        # Load schedule from S3
        schedule = await self._load_schedule()
        if not schedule:
            print("No valid schedule entries found. Exiting gracefully.")
            return True
        
        bookings_made = 0
        
        # Process each schedule entry
        for entry in schedule:
            try:
                # Check if it's time to make this booking
                should_book, target_date = self._is_booking_time(entry, current_time)
                
                if not should_book:
                    continue
                
                print(f"🎯 Booking due: {entry['user']} - {entry['instructor']} on {target_date.strftime('%A, %Y-%m-%d')} at {entry['time']}")
                
                # Determine if this is a swim or class booking
                is_swim, duration = self._parse_swim_instructor(entry['instructor'])
                
                # Create bot instance for the specific user
                user_bot = GymBookingBot(user_name=entry['user'])
                
                success = False
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=self.headless)
                    context = await browser.new_context()
                    page = await context.new_page()
                    
                    try:
                        # Login
                        if not await user_bot.login(page):
                            print(f"❌ Login failed for {entry['user']}")
                            continue
                        
                        if is_swim:
                            # Make swim booking
                            success = await user_bot.book_swim_lane(page, target_date, duration, entry['time'])
                            if success:
                                print(f"🏊 Swim booking successful: {entry['user']} - {duration}min at {entry['time']}")
                                bookings_made += 1
                            else:
                                print(f"❌ Swim booking failed: {entry['user']} - {duration}min at {entry['time']}")
                        else:
                            # Make class booking
                            success = await user_bot.book_class(page, target_date, entry['instructor'], entry['time'])
                            if success:
                                print(f"🏃 Class booking successful: {entry['user']} - {entry['instructor']} at {entry['time']}")
                                bookings_made += 1
                            else:
                                print(f"❌ Class booking failed: {entry['user']} - {entry['instructor']} at {entry['time']}")
                        
                    except Exception as e:
                        print(f"❌ Error processing booking for {entry['user']}: {e}")
                    finally:
                        await browser.close()
                
            except Exception as e:
                print(f"❌ Error processing schedule entry {entry}: {e}")
                continue
        
        print(f"✅ Schedule processing complete. Bookings made: {bookings_made}")
        return True