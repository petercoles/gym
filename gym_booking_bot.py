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
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page, Browser

# Load environment variables
load_dotenv()

# Ensure Playwright finds browsers in Render environment  
if not os.getenv('PLAYWRIGHT_BROWSERS_PATH'):
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/opt/render/project/.playwright-browsers'

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
        Log into the Hogarth gym website
        
        Args:
            page: Playwright page object
            
        Returns:
            True if login successful, False otherwise
        """
        try:
            print(f"Navigating to {self.gym_url}...")
            await page.goto(self.gym_url)
            await page.wait_for_load_state('networkidle')
            
            # Hogarth-specific login selectors
            login_selectors = [
                'input[name="ctl00$mainContent$Login1$UserName"]',
            ]
            
            password_selectors = [
                'input[name="ctl00$mainContent$Login1$Password"]',
            ]
            
            # Find username field
            username_field = None
            for selector in login_selectors:
                try:
                    username_field = await page.wait_for_selector(selector, timeout=3000)
                    if username_field:
                        break
                except:
                    continue
            
            if not username_field:
                print("Could not find username field. Please check the website structure.")
                return False
            
            # Find password field
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = await page.wait_for_selector(selector, timeout=3000)
                    if password_field:
                        break
                except:
                    continue
            
            if not password_field:
                print("Could not find password field. Please check the website structure.")
                return False
            
            # Fill in credentials
            print("Entering login credentials...")
            await username_field.fill(self.username)
            await password_field.fill(self.password)
            
            # Look for submit button
            submit_selectors = [
                'a#ctl00_mainContent_Login1_LoginImageButton',
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = await page.wait_for_selector(selector, timeout=3000)
                    if submit_button:
                        break
                except:
                    continue
            
            if submit_button:
                print("Clicking login button...")
                await submit_button.click()
            else:
                # Try pressing Enter on password field
                print("No submit button found, pressing Enter...")
                await password_field.press('Enter')
            
            # Wait for login to complete
            await page.wait_for_load_state('networkidle')
            
            # Check if login was successful by looking for success indicators
            success_indicators = [
                'h1:has-text("Members Area")',
            ]
            
            for indicator in success_indicators:
                try:
                    element = await page.wait_for_selector(indicator, timeout=5000)
                    if element:
                        print(f"✅ Login successful for {self.user_name}")
                        return True
                except:
                    continue
            
            print(f"✅ Login successful for {self.user_name} (assumed)")
            
            # Debug: Print current URL and page title
            current_url = page.url
            try:
                page_title = await page.title()
                print(f"📍 Current page: {page_title} ({current_url})")
            except:
                print(f"📍 Current URL: {current_url}")
            
            return True  # Assume success if we can't verify
                
        except Exception as e:
            print(f"❌ Login error for {self.user_name}: {e}")
            return False

    async def book_class(self, page: Page, target_date: datetime, instructor: str, time: str) -> bool:
        """
        Book a gym class by instructor and time at Hogarth gym
        
        Args:
            page: Playwright page object
            target_date: Date to book for
            instructor: Instructor name
            time: Class time (HH:MM format)
            
        Returns:
            True if booking successful, False otherwise
        """
        try:
            print(f"Looking for {instructor} class at {time} on {target_date.strftime('%Y-%m-%d %A')}...")
            
            # Step 1: Try to navigate to Class Calendar page (stay within authenticated session)
            print("Looking for Classes navigation...")
            
            # First try to find a classes link on the current authenticated page
            class_link_selectors = [
                'a[href="../CCE/ClassCalendar.aspx"]',
                'a[href*="ClassCalendar"]',
                'a:has-text("Classes")',
                'a:has-text("Class Calendar")',
                'a:has-text("Book Classes")',
                '*:has-text("Classes")',
                '*:has-text("Class")'
            ]
            
            navigated = False
            for link_selector in class_link_selectors:
                try:
                    print(f"Looking for link: {link_selector}")
                    class_link = await page.wait_for_selector(link_selector, timeout=3000)
                    if class_link:
                        print(f"✅ Found classes link: {link_selector}")
                        await class_link.click()
                        await page.wait_for_load_state('networkidle')
                        navigated = True
                        break
                except Exception as e:
                    print(f"⚠️  Link not found: {link_selector}")
                    continue
            
            # If no link found, try direct navigation (but within the same session)
            if not navigated:
                print("No classes link found, trying direct navigation...")
                try:
                    class_url = "https://online.thehogarth.co.uk/CCE/ClassCalendar.aspx"
                    print(f"Navigating to: {class_url}")
                    await page.goto(class_url, timeout=15000)
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    print("✅ Direct navigation successful")
                    navigated = True
                except Exception as e:
                    print(f"❌ Direct navigation failed: {e}")
            
            if not navigated:
                print("❌ Could not navigate to class calendar page")
                return False
                
            print("✅ Successfully reached class calendar page")
            
            # Step 2: Click "Next" to advance to the bookable week (8 days ahead)
            print("Clicking Next to advance to bookable week...")
            next_selectors = [
                'a#ctl00_mainContent_ucCalendar_lnkNextWeek',
                'a:has-text("Next")',
                '*:has-text("Next")'
            ]
            
            next_clicked = False
            for selector in next_selectors:
                try:
                    next_button = await page.wait_for_selector(selector, timeout=5000)
                    if next_button:
                        print(f"✅ Found Next button: {selector}")
                        await next_button.click()
                        await page.wait_for_load_state('networkidle')
                        next_clicked = True
                        break
                except:
                    continue
            
            if not next_clicked:
                print("❌ Could not find Next button to advance to bookable week")
                return False
            
            # Step 3: Find target date section
            print(f"Looking for {target_date.strftime('%A')} section...")
            
            # Debug: Let's see what's actually on the page
            print("🔍 Debugging page content...")
            try:
                page_title = await page.title()
                current_url = page.url
                print(f"📍 Current page: {page_title} ({current_url})")
                
                # Get a sample of page text to see the structure
                body_text = await page.text_content('body')
                if body_text:
                    # Look for date-related text
                    text_sample = body_text[:1000] if len(body_text) > 1000 else body_text
                    print(f"📄 Page sample: {text_sample[:500]}...")
                    
                    # Check for various day name formats
                    day_name = target_date.strftime('%A')  # Friday
                    day_header = target_date.strftime('%a %d %b')  # Fri 24 Oct
                    day_variants = [
                        day_header,  # Fri 24 Oct (expected format)
                        day_name,  # Friday
                        day_name[:3],  # Fri
                        target_date.strftime('%a'),  # Fri
                        target_date.strftime('%d'),  # 24
                        target_date.strftime('%d/%m'),  # 24/10
                        target_date.strftime('%B %d')  # October 24
                    ]
                    
                    print(f"🔍 Checking for day variants: {day_variants}")
                    for variant in day_variants:
                        if variant in body_text:
                            print(f"✅ Found '{variant}' in page text")
                        else:
                            print(f"❌ '{variant}' not found in page text")
            except Exception as e:
                print(f"⚠️  Debug error: {e}")
            
            # Find the day section for our target date
            day_name = target_date.strftime('%A')  # e.g., "Friday"
            day_header = target_date.strftime('%a %d %b')  # e.g., "Fri 24 Oct"
            day_selectors = [
                f'*:has-text("{day_header}")',  # Try full format first: "Fri 24 Oct"
                f'h2:has-text("{day_header}")',
                f'h3:has-text("{day_header}")',
                f'h1:has-text("{day_header}")',
                f'td:has-text("{day_header}")',
                f'th:has-text("{day_header}")',
                f'div:has-text("{day_header}")',
                f'*:has-text("{day_name[:3]}")',  # Fallback to "Fri"
                f'*:has-text("{day_name}")',  # Fallback to "Friday"
            ]
            
            day_section = None
            print(f"Looking for day section: '{day_header}' (or fallbacks)")
            for selector in day_selectors:
                try:
                    day_section = await page.wait_for_selector(selector, timeout=3000)
                    if day_section:
                        print(f"✅ Found {day_name} section with: {selector}")
                        break
                except:
                    continue
            
            if not day_section:
                print(f"❌ Could not find {day_name} section with any selector")
                print("🔍 Let's try to find any classes on the page...")
                
                # Try to find any class elements regardless of day
                class_elements = await page.query_selector_all('*')
                print(f"📊 Found {len(class_elements)} total elements on page")
                return False
                
            # Step 4: Look for class with matching instructor and time
            print(f"Looking for {instructor} at {time}...")
            
            # Find class containers that have both instructor and time
            # Look for div.classDesktopWrapper containers (the main class container)
            class_containers = await page.query_selector_all('div.classDesktopWrapper')
            
            class_booked = False
            for container in class_containers:
                try:
                    # Get all text content from this class container
                    container_text = await container.text_content()
                    
                    # Check if this container has both the instructor and time
                    has_instructor = instructor in container_text
                    has_time = time in container_text or time.replace(':', '') in container_text
                    
                    if has_instructor and has_time:
                        print(f"✅ Found {instructor} class at {time}")
                        
                        # First, we need to make the overlay visible by clicking on the main class card
                        # The booking button is in the overlay which is hidden by default
                        try:
                            # Try to click on the main class card to trigger the overlay
                            class_card_selectors = [
                                'div.classSelectFire',
                                'div.uk-panel-box',
                                'div.className'
                            ]
                            
                            card_clicked = False
                            for card_selector in class_card_selectors:
                                try:
                                    class_card = await container.query_selector(card_selector)
                                    if class_card:
                                        print(f"✅ Clicking class card: {card_selector}")
                                        await class_card.click()
                                        await page.wait_for_timeout(1000)  # Wait for overlay animation
                                        card_clicked = True
                                        break
                                except Exception as e:
                                    print(f"⚠️  Failed to click class card {card_selector}: {e}")
                                    continue
                            
                            if not card_clicked:
                                print("❌ Could not click class card to open overlay")
                                continue
                                
                        except Exception as e:
                            print(f"⚠️  Error opening class overlay: {e}")
                            continue
                        
                        # Now look for booking button in the hopefully visible overlay
                        booking_selectors = [
                            'a.bookClassButton',
                            'a:has-text("Book")',
                            'a[href*="book" i]',
                            'button:has-text("Book")',
                            'a[id*="imBook"]'
                        ]
                        
                        for book_selector in booking_selectors:
                            try:
                                # Wait for the button to be visible after the overlay opens
                                book_element = await container.wait_for_selector(book_selector, timeout=5000)
                                if book_element:
                                    # Check if the element is visible
                                    is_visible = await book_element.is_visible()
                                    if is_visible:
                                        print(f"✅ Found visible booking element: {book_selector}")
                                        await book_element.click()
                                        await page.wait_for_load_state('networkidle')
                                        class_booked = True
                                        break
                                    else:
                                        print(f"📍 Found booking element but not visible: {book_selector}")
                            except Exception as e:
                                print(f"⚠️  Failed to click {book_selector}: {e}")
                                continue
                        
                        if class_booked:
                            break
                    else:
                        # Debug: show what we found in this container
                        if instructor in container_text:
                            print(f"📍 Found {instructor} but not {time} in: {container_text[:100]}...")
                        elif time in container_text:
                            print(f"📍 Found {time} but not {instructor} in: {container_text[:100]}...")
                            
                except Exception as e:
                    print(f"⚠️  Error checking container: {e}")
                    continue
            
            if not class_booked:
                print(f"❌ Could not find bookable {instructor} class at {time}")
                return False
            
            # Step 5: Handle booking confirmation flow
            print("✅ Class booking clicked! Looking for confirmation...")
            
            # Accept terms if they appear
            checkbox_selectors = [
                'input#ctl00_mainContent_chkTerms',  # Updated to match actual HTML
                'input#ctl00_mainContent_Terms',     # Keep old one as fallback
                'input[type="checkbox"]'
            ]
            
            for selector in checkbox_selectors:
                try:
                    checkbox = await page.wait_for_selector(selector, timeout=3000)
                    if checkbox:
                        is_checked = await checkbox.is_checked()
                        if not is_checked:
                            print("✅ Checking terms and conditions...")
                            await checkbox.check()
                        break
                except:
                    continue
            
            # Look for final confirm/book button
            confirm_selectors = [
                'a#ctl00_mainContent_PageNavControl_ibNext',
                'button:has-text("Book")',
                'button:has-text("Confirm")',
                'input[value="Book"]',
                'input[value="Confirm"]'
            ]
            
            for selector in confirm_selectors:
                try:
                    confirm_button = await page.wait_for_selector(selector, timeout=5000)
                    if confirm_button:
                        print(f"✅ Found confirmation button: {selector}")
                        await confirm_button.click()
                        await page.wait_for_load_state('networkidle')
                        
                        # Check for success indicators
                        success_selectors = [
                            'h1:has-text("Booking Complete")',
                            '*:has-text("booked")',
                            '*:has-text("confirmed")',
                            '*:has-text("success")'
                        ]
                        
                        for success_selector in success_selectors:
                            try:
                                success_element = await page.wait_for_selector(success_selector, timeout=5000)
                                if success_element:
                                    success_text = await success_element.text_content()
                                    print(f"🎉 Class booking successful! {success_text}")
                                    return True
                            except:
                                continue
                        
                        print(f"✅ Class booking likely successful: {instructor} at {time}")
                        return True
                except:
                    continue
            
            print("✅ Class booking completed (no confirmation button found)")
            return True
                
        except Exception as e:
            print(f"❌ Error booking class {instructor} at {time}: {e}")
            return False

    def _infer_time_period(self, specific_time: str) -> str:
        """
        Infer the general time period from a specific time
        
        Args:
            specific_time: Time in format "HH:MM" (e.g., "09:00", "18:30")
            
        Returns:
            "morning", "afternoon", or "evening"
        """
        try:
            # Parse the hour from the time string
            hour = int(specific_time.split(':')[0])
            
            if hour < 12:
                return "morning"
            elif hour < 17:
                return "afternoon"
            else:
                return "evening"
        except:
            # If we can't parse the time, default to morning
            return "morning"

    async def book_swim_lane(self, page: Page, target_date: datetime, duration: int, time: str) -> bool:
        """
        Book a swim lane for the target date at Hogarth gym
        
        Args:
            page: Playwright page object
            target_date: Date to book for
            duration: Duration in minutes (15 or 30)
            time: Start time (HH:MM format)
            
        Returns:
            True if booking successful, False otherwise
        """
        try:
            # Infer the general time period from the specific time
            time_period = self._infer_time_period(time)
            print(f"Booking swim lane for {target_date.strftime('%Y-%m-%d')} - {duration} minutes - {time} ({time_period})")
            
            # Step 1: Try to navigate to Swim page (stay within authenticated session)
            print("Looking for Swim navigation...")
            
            # First try to find a swim link on the current authenticated page
            swim_link_selectors = [
                'a[href="../swim/Swim.aspx"]',
                'a[href*="Swim.aspx"]',
                'a[href*="swim"]',
                'a:has-text("Swim")',
                'a:has-text("Swimming")',
                'a:has-text("Pool")',
                '*:has-text("Swim")',
                '*:has-text("Pool")'
            ]
            
            navigated = False
            for link_selector in swim_link_selectors:
                try:
                    print(f"Looking for swim link: {link_selector}")
                    swim_link = await page.wait_for_selector(link_selector, timeout=3000)
                    if swim_link:
                        print(f"✅ Found swim link: {link_selector}")
                        await swim_link.click()
                        await page.wait_for_load_state('networkidle')
                        navigated = True
                        break
                except Exception as e:
                    print(f"⚠️  Swim link not found: {link_selector}")
                    continue
            
            # If no link found, try direct navigation (but within the same session)
            if not navigated:
                print("No swim link found, trying direct navigation...")
                try:
                    swim_url = "https://online.thehogarth.co.uk/swim/Swim.aspx"
                    print(f"Navigating to: {swim_url}")
                    await page.goto(swim_url, timeout=15000)
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    print("✅ Direct swim navigation successful")
                    navigated = True
                except Exception as e:
                    print(f"❌ Direct swim navigation failed: {e}")
            
            if not navigated:
                print("❌ Could not navigate to swim page")
                return False
                
            print("✅ Successfully reached swim page")
            
            # Step 2: Fill in date, duration, and time period
            
            # Select date
            print("Selecting date...")
            date_selectors = [
                'input#ctl00_mainContent_SessionDatePicker'
            ]
            
            target_date_str = target_date.strftime('%d/%m/%Y')  # Format: 25/10/2025
            date_selected = False
            
            for selector in date_selectors:
                try:
                    date_input = await page.wait_for_selector(selector, timeout=3000)
                    if date_input:
                        # Check current value
                        current_value = await date_input.get_attribute('value')
                        print(f"📅 Current date value: {current_value}, Target: {target_date_str}")
                        
                        if current_value == target_date_str:
                            print(f"✅ Date already set correctly: {current_value}")
                            date_selected = True
                        else:
                            # Try to set the date value directly
                            try:
                                await date_input.fill(target_date_str)
                                await page.wait_for_timeout(500)  # Wait for any onchange events
                                print(f"✅ Set date to: {target_date_str}")
                                date_selected = True
                            except Exception as e:
                                print(f"⚠️  Could not set date directly: {e}")
                        break
                except Exception as e:
                    print(f"⚠️  Date selector error: {e}")
                    continue
            
            if not date_selected:
                print("⚠️  Could not verify date selection, continuing with default")
            
            # Select duration
            print(f"Selecting duration: {duration} minutes...")
            duration_selectors = [
                'select#ctl00_mainContent_minutes'
            ]
            
            duration_selected = False
            for selector in duration_selectors:
                try:
                    duration_select = await page.wait_for_selector(selector, timeout=3000)
                    if duration_select:
                        options = await page.query_selector_all(f'{selector} option')
                        for option in options:
                            option_text = await option.text_content()
                            option_value = await option.get_attribute('value')
                            if str(duration) in option_text:
                                print(f"✅ Selecting duration: {option_text}")
                                await duration_select.select_option(value=option_value)
                                await page.wait_for_timeout(1000)  # Wait for onchange event
                                duration_selected = True
                                break
                        if duration_selected:
                            break
                except:
                    continue
            
            if not duration_selected:
                print("⚠️  Could not select specific duration, using default")
            
            # Select time period first (morning/afternoon/evening)
            print(f"Selecting time period: {time_period}...")
            time_period_selectors = [
                '#ctl00_mainContent_timeOfDay',
            ]
            
            time_period_keywords = {
                "morning": ["Morning (Before 12:00)"],
                "afternoon": ["Afternoon (12:00 - 17:00)"],  # Fixed: added spaces around hyphen
                "evening": ["Evening (After 17:00)"]
            }
            
            period_selected = False
            for selector in time_period_selectors:
                try:
                    period_select = await page.wait_for_selector(selector, timeout=3000)
                    if period_select:
                        options = await page.query_selector_all(f'{selector} option')
                        for option in options:
                            option_text = await option.text_content()
                            option_value = await option.get_attribute('value')
                            
                            # Check if this option matches our time period
                            if any(keyword in option_text for keyword in time_period_keywords.get(time_period, [])):
                                print(f"✅ Selecting time period: {option_text}")
                                await period_select.select_option(value=option_value)
                                await page.wait_for_timeout(1000)  # Wait for onchange event
                                period_selected = True
                                break
                        if period_selected:
                            break
                except:
                    continue
            
            if not period_selected:
                print(f"⚠️  Could not select time period '{time_period}'")
            
            # Step 3: Click Go button to load time slots
            # The Go button only appears after both duration and time period are selected
            if not duration_selected or not period_selected:
                print("❌ Cannot proceed without both duration and time period selected")
                return False
                
            print("Both dropdowns selected, looking for Go button...")
            await page.wait_for_timeout(1000)  # Give time for Go button to appear
            
            go_selectors = [
                'a#ctl00_mainContent_goBtn',
                'button:has-text("Go")',
                'input[value="Go"]',
                '.goBtn'
            ]
            
            go_clicked = False
            for selector in go_selectors:
                try:
                    go_button = await page.wait_for_selector(selector, timeout=5000)
                    if go_button:
                        print(f"✅ Found Go button: {selector}")
                        await go_button.click()
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        await page.wait_for_timeout(3000)  # Extra time for time slots to load
                        go_clicked = True
                        break
                except Exception as e:
                    print(f"⚠️  Go button click failed for {selector}: {e}")
                    continue
            
            if not go_clicked:
                print("❌ Could not find or click Go button after dropdown selections")
                return False
            
            # Step 4: Look for available time slots in preferred lanes (2, 3, then 1, 4)
            print(f"Looking for {time} time slot in preferred lanes...")
            
            # Priority order: Lane 2, Lane 3, Lane 4, Lane 1
            lane_priority = [2, 3, 4, 1]
            slot_booked = False
            
            # Debug: Check what timeSlotInner elements we have
            time_slot_inners = await page.query_selector_all('div.timeSlotInner')
            print(f"📊 Found {len(time_slot_inners)} lane containers")
            
            for lane_num in lane_priority:
                if slot_booked:
                    break
                    
                print(f"Checking Lane {lane_num} for {time}...")
                
                if len(time_slot_inners) >= lane_num:
                    # Get the timeSlotInner for this specific lane (0-indexed)
                    lane_div = time_slot_inners[lane_num - 1]
                    print(f"✅ Found Lane {lane_num} container")
                    
                    # Debug: Check the structure of this lane
                    lane_html = await lane_div.inner_html()
                    print(f"🔍 Lane {lane_num} HTML length: {len(lane_html)} chars")
                    
                    # Find all timeSlot divs within this lane - try multiple selectors
                    time_slots = await lane_div.query_selector_all('div.timeSlot')
                    print(f"🔍 Found {len(time_slots)} time slots in Lane {lane_num} with 'div.timeSlot'")
                    
                    # If no slots found, try alternative selectors
                    if len(time_slots) == 0:
                        time_slots = await lane_div.query_selector_all('.timeSlot')
                        print(f"🔍 Found {len(time_slots)} time slots in Lane {lane_num} with '.timeSlot'")
                        
                    if len(time_slots) == 0:
                        # Try finding all elements with class containing timeSlot
                        time_slots = await lane_div.query_selector_all('[class*="timeSlot"]')
                        print(f"🔍 Found {len(time_slots)} time slots in Lane {lane_num} with '[class*=\"timeSlot\"]'")
                        
                    if len(time_slots) == 0:
                        # Debug: Look for any divs
                        all_divs = await lane_div.query_selector_all('div')
                        print(f"🔍 Found {len(all_divs)} total divs in Lane {lane_num}")
                        
                        # Look for booking buttons
                        booking_buttons = await lane_div.query_selector_all('a.bookButton')
                        print(f"🔍 Found {len(booking_buttons)} booking buttons in Lane {lane_num}")
                        
                        # If we have booking buttons but no timeSlot divs, use the buttons directly
                        if len(booking_buttons) > 0:
                            print(f"🔄 Using booking buttons directly for Lane {lane_num}")
                            for button in booking_buttons:
                                try:
                                    # Get the button text content directly
                                    link_text = await button.text_content()
                                    print(f"🕐 Lane {lane_num} button raw text: '{repr(link_text)}'")
                                    
                                    # Extract time pattern
                                    import re
                                    clean_text = re.sub(r'\s+', ' ', link_text).strip()
                                    time_match_obj = re.search(r'\b(\d{1,2}:\d{2})\b', clean_text)
                                    
                                    if time_match_obj:
                                        extracted_time = time_match_obj.group(1)
                                        print(f"🕐 Lane {lane_num} extracted time: '{extracted_time}' (looking for '{time}')")
                                        
                                        if extracted_time == time:
                                            print(f"✅ Found {time} slot in Lane {lane_num}: '{extracted_time}'")
                                            await button.click()
                                            slot_booked = True
                                            break
                                except Exception as e:
                                    print(f"⚠️  Error checking button: {e}")
                                    continue
                                    
                            if slot_booked:
                                break
                    
                    # If we found timeSlot divs, process them normally
                    if len(time_slots) > 0 and not slot_booked:
                        for time_slot in time_slots:
                            try:
                                # Look for the link within this time slot
                                link = await time_slot.query_selector('a.bookButton')
                                if link:
                                    # Get the link text content, which should contain the time
                                    link_text = await link.text_content()
                                    print(f"🕐 Lane {lane_num} slot raw text: '{repr(link_text)}'")
                                    
                                    # Aggressively clean the text - strip all whitespace and extract time pattern
                                    import re
                                    clean_text = re.sub(r'\s+', ' ', link_text).strip()  # Replace all whitespace with single spaces
                                    # Look for time pattern HH:MM at the start
                                    time_match_obj = re.search(r'\b(\d{1,2}:\d{2})\b', clean_text)
                                    
                                    if time_match_obj:
                                        extracted_time = time_match_obj.group(1)
                                        print(f"🕐 Lane {lane_num} extracted time: '{extracted_time}' (looking for '{time}')")
                                        
                                        # Check if this matches our target time
                                        if extracted_time == time:
                                            print(f"✅ Found {time} slot in Lane {lane_num}: '{extracted_time}'")
                                            await link.click()
                                            slot_booked = True
                                            break
                                    else:
                                        print(f"🕐 Lane {lane_num} no time pattern found in: '{clean_text}'")
                            except Exception as e:
                                print(f"⚠️  Error checking time slot: {e}")
                                continue
                            
                    if not slot_booked:
                        print(f"⚠️  No {time} slot available in Lane {lane_num}")
                else:
                    print(f"⚠️  Could not find Lane {lane_num} div")
            
            if not slot_booked:
                print(f"❌ Could not find {time} slot in any lane")
                return False
            
            # Step 5: Click "Next" button after selecting time slot
            print("✅ Time slot selected! Looking for Next button...")
            await page.wait_for_timeout(2000)
            
            next_selectors = [
                'button:has-text("Next")',
                'input[value="Next"]',
                'a:has-text("Next")',
                '*:has-text("Next")'
            ]
            
            next_clicked = False
            for selector in next_selectors:
                try:
                    next_button = await page.wait_for_selector(selector, timeout=5000)
                    if next_button:
                        print(f"✅ Found Next button: {selector}")
                        await next_button.click()
                        next_clicked = True
                        break
                except:
                    continue
            
            if not next_clicked:
                print("❌ Could not find Next button")
                return False
            
            # Step 6: Accept terms and conditions
            print("✅ Next clicked! Looking for terms and conditions...")
            await page.wait_for_load_state('networkidle')
            
            checkbox_selectors = [
                'input#ctl00_mainContent_chkTerms',  # Updated to match actual HTML
                'input#ctl00_mainContent_Terms',     # Keep old one as fallback
            ]
            
            checkbox_found = False
            for selector in checkbox_selectors:
                try:
                    checkbox = await page.wait_for_selector(selector, timeout=5000)
                    if checkbox:
                        is_checked = await checkbox.is_checked()
                        if not is_checked:
                            print("✅ Checking terms and conditions...")
                            await checkbox.check()
                        checkbox_found = True
                        break
                except:
                    continue
            
            if not checkbox_found:
                print("⚠️  Could not find terms and conditions checkbox")
            
            # Step 7: Final Book button
            print("Looking for final Book button...")
            final_book_selectors = [
                'a#ctl00_mainContent_PageNavControl_ibNext'
            ]
            
            for selector in final_book_selectors:
                try:
                    book_button = await page.wait_for_selector(selector, timeout=5000)
                    if book_button:
                        print(f"✅ Found final Book button: {selector}")
                        await book_button.click()
                        await page.wait_for_load_state('networkidle')
                        
                        # Check for success
                        success_selectors = [
                            'h1:has-text("Booking Complete")',
                            '*:has-text("booked")',
                            '*:has-text("confirmed")',
                            '*:has-text("success")'
                        ]
                        
                        for success_selector in success_selectors:
                            try:
                                success_element = await page.wait_for_selector(success_selector, timeout=5000)
                                if success_element:
                                    success_text = await success_element.text_content()
                                    print(f"🎉 Swim lane booking successful! {success_text}")
                                    return True
                            except:
                                continue
                        
                        print("✅ Final Book button clicked - likely successful")
                        return True
                except:
                    continue
            
            print("❌ Could not find final Book button")
            return False
            
        except Exception as e:
            print(f"❌ Error booking swim lane: {e}")
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
        
        # Debug output for scheduling logic
        print(f"  📅 Target date: {target_date} ({target_day_name})")
        print(f"  🕐 Current time: {current_time.strftime('%H:%M')}")
        print(f"  ⏰ Scheduled time: {scheduled_time.strftime('%H:%M')}")
        
        # Should book if current time >= scheduled time and within the same 15-minute window
        if current_time >= scheduled_time:
            # Check we're still in the same 15-minute window (to avoid re-booking)
            minutes_passed = (current_time - scheduled_time).total_seconds() / 60
            print(f"  ⏱️  Minutes passed since scheduled time: {minutes_passed:.1f}")
            if minutes_passed < 15:  # Within 15 minutes of booking time
                return True, target_date
            else:
                print(f"  ❌ Booking window closed (>15 minutes ago)")
        else:
            time_until = (scheduled_time - current_time).total_seconds() / 60
            print(f"  ⏳ Time until booking: {time_until:.1f} minutes")
        
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
                
                # Check for booking conflicts (especially critical for swim lanes)
                duplicate_entries = [e for e in schedule if 
                                   e['instructor'] == entry['instructor'] and 
                                   e['time'] == entry['time'] and 
                                   e['day_of_week'] == entry['day_of_week']]
                
                if len(duplicate_entries) > 1:
                    users_for_this_slot = [e['user'] for e in duplicate_entries]
                    is_swim_conflict = entry['instructor'].startswith('Swim(')
                    
                    if is_swim_conflict:
                        print(f"🏊 Multiple users ({', '.join(users_for_this_slot)}) booking {entry['instructor']} at {entry['time']}")
                        print(f"✅ Sequential booking should secure adjacent lanes (Lane 2, 3, 4 priority)")
                    else:
                        print(f"⚠️  Multiple users ({', '.join(users_for_this_slot)}) scheduled for {entry['instructor']} at {entry['time']}")
                        if 'Terry' in entry['instructor']:
                            print(f"✅ Terry class has 15 spots - should be OK if script runs fast")
                        else:
                            print(f"⚠️  Limited spots available - first booking will likely succeed")
                
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