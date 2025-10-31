"""
Gym Class and Swim Lane Booking Automation Bot using Playwright

This script automates the process of logging into a gym website and booking classes
or swim lanes 8 days ahead of the current date.

Simplified version without state management - relies on 15-minute booking windows
to prevent duplicates naturally.
"""

import os
import re
import pytz
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page

# Load environment variables
load_dotenv()

# Ensure Playwright finds browsers in Render environment  
if not os.getenv('PLAYWRIGHT_BROWSERS_PATH'):
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/opt/render/project/.playwright-browsers'

class GymBookingBot:
    def __init__(self, user_name: str = "peter"):
        gym_url = os.getenv('GYM_URL')
        if not gym_url:
            raise ValueError("Please set GYM_URL in your .env file")
        self.gym_url: str = gym_url
        self.user_name = user_name.upper()
        
        # Load credentials for the specified user
        username = os.getenv(f'{self.user_name}_USERNAME')
        password = os.getenv(f'{self.user_name}_PASSWORD')
        if not username or not password:
            raise ValueError(f"Please set {self.user_name}_USERNAME and {self.user_name}_PASSWORD in your .env file")
        self.username: str = username
        self.password: str = password
        self.headless = os.getenv('HEADLESS', 'false').lower() == 'true'

    def _detect_browser_environment(self):
        """Detect if running locally and find available browser"""
        import platform
        
        is_local = (
            os.getenv('RENDER') is None and  # Not on Render
            platform.system() == 'Darwin'   # macOS (local machine)
        )
        
        if is_local:
            print("🏠 Running locally - using local Chromium installation")
            local_chromium_paths = [
                '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                '/usr/local/bin/chromium',
                '/opt/homebrew/bin/chromium',
                '/Applications/Chromium.app/Contents/MacOS/Chromium'
            ]
            
            for path in local_chromium_paths:
                if os.path.exists(path):
                    print(f"✅ Found browser at: {path}")
                    return True, path
            
            print("⚠️  No local browser found, trying default Playwright installation")
            return True, None
        else:
            print("☁️  Running on Render - using Playwright's bundled Chromium")
            return False, None

    async def _navigate_datepicker_to_date(self, page: Page, calendar_selector: str, target_date: datetime) -> bool:
        """Navigate the UIkit datepicker to the desired month and click the target day."""
        target_month_start = target_date.replace(day=1)
        target_month_key = (target_month_start.year, target_month_start.month)

        for attempt in range(12):  # Prevent infinite loops
            calendars = await page.query_selector_all(calendar_selector)
            if not calendars:
                return False

            calendar = calendars[-1]  # Use the most recent calendar instance
            title_text = await self._get_datepicker_title(calendar)
            displayed_month = self._parse_month_year_title(title_text)
            displayed_month_key = (
                (displayed_month.year, displayed_month.month)
                if displayed_month is not None else None
            )
            if title_text:
                print(f"📆 Datepicker shows: '{title_text}' (attempt {attempt + 1})")
            else:
                print(f"📆 Datepicker title not found (attempt {attempt + 1})")

            if displayed_month_key is None:
                # Try clicking the day directly as a fallback
                return await self._click_datepicker_day(calendar, target_date)

            if displayed_month_key == target_month_key:
                return await self._click_datepicker_day(calendar, target_date)

            if displayed_month_key < target_month_key:
                print("➡️  Navigating forward a month...")
                if not await self._click_datepicker_nav(calendar, ['.uk-datepicker-next', '.ui-datepicker-next', '[data-uk-datepicker-next]']):
                    return False
            else:
                print("⬅️  Navigating back a month...")
                if not await self._click_datepicker_nav(calendar, ['.uk-datepicker-prev', '.ui-datepicker-prev', '[data-uk-datepicker-previous]', '.uk-datepicker-previous']):
                    return False

            await page.wait_for_timeout(400)

        return False

    async def _container_matches_day(self, container, target_texts: list[str]) -> tuple[bool, str]:
        """Check whether a class container belongs to the requested day using lightweight DOM inspection."""
        if not container:
            return False, ""

        script = """(node, targets) => {
            const response = { match: false, label: '' };
            if (!node) {
                return response;
            }

            const dayWrapper = node.closest('.classCalendarDay, .classDayWrapper, .classWeekDay, .dayWrap, .uk-accordion-content, .uk-panel, .day-wrapper, .classDay');
            const labelSelectors = [
                '.classDayTitle',
                '.classDayHeader',
                '.classDayName',
                '.dayTitle',
                '.uk-accordion-title',
                'header',
                'h1',
                'h2',
                'h3'
            ];
            const attrCandidates = [
                'data-date',
                'data-day',
                'data-classdate',
                'data-class-date',
                'data-class-date-iso'
            ];

            const wrapper = dayWrapper || node;
            let label = '';

            for (const selector of labelSelectors) {
                const headerEl = wrapper.querySelector(selector);
                if (headerEl && headerEl.textContent) {
                    label = headerEl.textContent;
                    break;
                }
            }

            if (!label) {
                for (const attr of attrCandidates) {
                    const value = wrapper.getAttribute(attr) || node.getAttribute(attr);
                    if (value) {
                        label = value;
                        break;
                    }
                }
            }

            if (!label && wrapper.textContent) {
                label = wrapper.textContent;
            }

            const normalizedLabel = (label || '').replace(/\\s+/g, ' ').trim().toLowerCase();

            for (const target of targets || []) {
                const normalizedTarget = String(target || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                if (normalizedTarget && normalizedLabel.includes(normalizedTarget)) {
                    response.match = true;
                    response.label = label ? label.trim() : '';
                    return response;
                }
            }

            response.label = label ? label.trim() : '';
            return response;
        }"""

        try:
            result = await container.evaluate(script, target_texts)
        except Exception:
            return False, ""

        if not isinstance(result, dict):
            return False, ""

        matches = bool(result.get('match'))
        label = (result.get('label') or "").strip()
        return matches, label

    async def _get_datepicker_title(self, calendar) -> str:
        """Extract the month/year title text from the datepicker."""
        title_selectors = [
            '.uk-datepicker-nav .uk-datepicker-title',
            '.uk-datepicker-title',
            '.ui-datepicker-title',
            '.uk-datepicker-heading'
        ]
        for selector in title_selectors:
            try:
                element = await calendar.query_selector(selector)
                if element:
                    text = await element.text_content()
                    if text:
                        return text.strip()
            except Exception:
                continue
        return ""

    def _parse_month_year_title(self, text: str):
        """Parse strings like 'November 2025' into a datetime at the first of the month."""
        if not text:
            return None

        cleaned = re.sub(r'\s+', ' ', text.strip())
        for fmt in ("%B %Y", "%b %Y"):
            try:
                parsed = datetime.strptime(cleaned, fmt)
                return parsed.replace(day=1)
            except ValueError:
                continue
        return None

    async def _click_datepicker_nav(self, calendar, selectors: list[str]) -> bool:
        """Click the next/previous navigation button."""
        for selector in selectors:
            try:
                button = await calendar.query_selector(selector)
                if button:
                    try:
                        await button.scroll_into_view_if_needed()
                    except Exception:
                        pass
                    try:
                        await button.click(force=True)
                    except Exception:
                        await button.click()
                    return True
            except Exception:
                continue
        return False

    async def _click_datepicker_day(self, calendar, target_date: datetime) -> bool:
        """Click the day cell matching the target date."""
        iso_target = target_date.strftime('%Y-%m-%d')
        day_strings = {str(target_date.day), target_date.strftime('%d')}
        class_blocklist = ('disabled', 'empty', 'off', 'out', 'outside', 'muted')

        # Prefer exact data-date matches if available
        data_selectors = [
            f'[data-date="{iso_target}"]',
            f'[data-date="{iso_target} 00:00:00"]',
            f'[data-date="{iso_target}T00:00:00"]',
            f'[data-date^="{iso_target}T"]',
            f'[data-date^="{iso_target} "]',
            f'[data-date^="{iso_target}"]',
        ]
        for selector in data_selectors:
            try:
                elements = await calendar.query_selector_all(selector)
                for element in elements:
                    if not element:
                        continue
                    classes = (await element.get_attribute('class') or '').lower()
                    if any(token in classes for token in class_blocklist):
                        continue
                    try:
                        await element.scroll_into_view_if_needed()
                    except Exception:
                        pass
                    try:
                        data_value = await element.get_attribute('data-date')
                    except Exception:
                        data_value = None
                    print(f"🗓️  Selecting day using data-date match: {data_value or 'unknown'}")
                    try:
                        await element.click(force=True)
                    except Exception:
                        await element.click()
                    return True
            except Exception:
                continue

        # Fallback: match by visible text while avoiding disabled/off-month cells
        try:
            cells = await calendar.query_selector_all('td')
        except Exception:
            cells = []

        for cell in cells:
            try:
                cell_classes = (await cell.get_attribute('class') or '').lower()
                clickable = await cell.query_selector('a, button')
                clickable_classes = (await clickable.get_attribute('class') or '').lower() if clickable else ''
                combined_classes = f"{cell_classes} {clickable_classes}"
                if any(token in combined_classes for token in class_blocklist):
                    continue

                data_date = ''
                if clickable:
                    data_date = (await clickable.get_attribute('data-date')) or ''
                if not data_date:
                    data_date = (await cell.get_attribute('data-date')) or ''

                if data_date and not data_date.startswith(iso_target):
                    continue

                text_source = clickable if clickable else cell
                text = (await text_source.text_content() or '').strip()
                if text in day_strings:
                    if clickable:
                        try:
                            await clickable.scroll_into_view_if_needed()
                        except Exception:
                            pass
                        print(f"🗓️  Selecting day by visible text: {text}")
                        try:
                            await clickable.click(force=True)
                        except Exception:
                            await clickable.click()
                    else:
                        try:
                            await cell.scroll_into_view_if_needed()
                        except Exception:
                            pass
                        print(f"🗓️  Selecting day by cell text: {text}")
                        try:
                            await cell.click(force=True)
                        except Exception:
                            await cell.click()
                    return True
            except Exception:
                continue

        return False

    async def _get_input_value(self, element) -> str:
        """Safely get the live value of an input element."""
        if not element:
            return ""
        try:
            return await element.input_value()
        except Exception:
            try:
                return await element.evaluate("(el) => el.value")
            except Exception:
                try:
                    return await element.get_attribute('value') or ""
                except Exception:
                    return ""

    def _send_booking_failure_email(self, booking_details: dict, failure_reason: str, error_details: str = ""):
        """Send email notification when a booking fails"""
        try:
            # Get email configuration from environment variables
            smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_user = os.getenv('SENDER_EMAIL')
            smtp_password = os.getenv('SENDER_PASSWORD')
            notification_email = os.getenv('RECIPIENT_EMAIL')
            
            if not smtp_user or not smtp_password or not notification_email:
                print("⚠️  Email notification skipped - SMTP credentials not configured")
                print(f"   SENDER_EMAIL: {'✓' if smtp_user else '✗'}")
                print(f"   SENDER_PASSWORD: {'✓' if smtp_password else '✗'}")
                print(f"   RECIPIENT_EMAIL: {'✓' if notification_email else '✗'}")
                return
            
            # Format booking details
            booking_type = "Swim Lane" if booking_details.get('is_swim') else "Class"
            duration_text = f" ({booking_details.get('duration')}min)" if booking_details.get('is_swim') else ""
            instructor_text = booking_details.get('instructor', 'Unknown')
            
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = notification_email
            msg['Subject'] = f"🚨 Hogarth Booking Failed - {booking_details.get('user', 'Unknown')} - {instructor_text}"
            
            # Email body
            body = f"""
Hogarth Gym Booking Failure Alert

❌ BOOKING FAILED ❌

User: {booking_details.get('user', 'Unknown')}
Type: {booking_type}{duration_text}
Instructor/Activity: {instructor_text}
Time: {booking_details.get('time', 'Unknown')}
Target Date: {booking_details.get('target_date', 'Unknown')}

Failure Reason: {failure_reason}

{f'Technical Details: {error_details}' if error_details else ''}

This booking was scheduled to occur automatically but failed to complete.
You may need to book manually or check the system configuration.

Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """.strip()
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_password)
            text = msg.as_string()
            server.sendmail(smtp_user, notification_email, text)
            server.quit()
            
            print(f"📧 Failure notification email sent to {notification_email}")
            
        except Exception as e:
            print(f"⚠️  Failed to send email notification: {e}")

    async def login(self, page: Page) -> bool:
        """
        Log into the Hogarth gym website
        
        Args:
            page: Playwright page object
            
        Returns:
            True if login successful, False otherwise
        """
        try:
            print(f"🌐 Navigating to {self.gym_url}...")
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
            
            # Check if login was successful by looking for a known post-login element
            success_selector = 'h1:has-text("Members Area")'
            try:
                element = await page.wait_for_selector(success_selector, timeout=5000)
                if element:
                    print(f"✅ Login successful for {self.user_name}")
                    return True
            except Exception:
                pass
            
            print(f"⚠️  Login success indicator not found for {self.user_name}, assuming success")
            return True  # Return True to keep behaviour compatible with existing callers
                
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
            print(f"🎯 [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Looking for {instructor} class at {time} on {target_date.strftime('%Y-%m-%d %A')}...")
            
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
            
            # Prepare selectors for locating the target day
            day_name = target_date.strftime('%A')  # e.g., "Friday"
            day_header = target_date.strftime('%a %d %b')  # e.g., "Fri 24 Oct"
            day_selectors = [
                f'*:has-text("{day_header}")',  # Full format first: "Fri 24 Oct"
                f'h2:has-text("{day_header}")',
                f'h3:has-text("{day_header}")',
                f'h1:has-text("{day_header}")',
                f'td:has-text("{day_header}")',
                f'th:has-text("{day_header}")',
                f'div:has-text("{day_header}")',
                f'*:has-text("{day_name[:3]}")',  # Fallback "Fri"
                f'*:has-text("{day_name}")',  # Fallback "Friday"
            ]
            
            # Step 2: Click "Next" to advance to the bookable week if needed
            day_section = None
            for selector in day_selectors:
                try:
                    candidate = await page.query_selector(selector)
                    if candidate:
                        day_section = candidate
                        print(f"✅ Target day already visible on current calendar with selector: {selector}")
                        break
                except Exception:
                    continue
            
            if not day_section:
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
            if day_section:
                print(f"➡️  Reusing existing handle for {day_header}")
            else:
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
                print(f"❌ Could not find {day_name} section")
                return False
                
            # Step 4: Look for class with matching instructor and time
            print(f"Looking for {instructor} at {time}...")
            
            # Find class containers that have both instructor and time, scoped to the located day section
            class_containers = []
            day_container_handle = None
            try:
                day_container_handle = await day_section.evaluate_handle(
                    """(node) => {
                        const scopes = [
                            '.classCalendarDay',
                            '.classDayWrapper',
                            '.classWeekDay',
                            '.dayWrap',
                            '.uk-accordion-content',
                            '.uk-panel',
                            '.day-wrapper',
                            '.classDay'
                        ];
                        for (const selector of scopes) {
                            const match = node.closest(selector);
                            if (match) {
                                return match;
                            }
                        }
                        return node;
                    }"""
                )
            except Exception:
                day_container_handle = None

            day_container = day_container_handle.as_element() if day_container_handle else None
            if day_container:
                class_containers = await day_container.query_selector_all('div.classDesktopWrapper')

            if not class_containers:
                # Fallback to global search if we couldn't scope the day section
                print("⚠️  Could not scope class search to day section, falling back to full page scan")
                class_containers = await page.query_selector_all('div.classDesktopWrapper')

            # Collect metadata to filter class containers down to the requested day
            container_contexts = []
            filtered_contexts = []
            skipped_contexts = []

            day_tokens = [
                day_header,
                target_date.strftime('%Y-%m-%d'),
                target_date.strftime('%d %b'),
                target_date.strftime('%d %B'),
                target_date.strftime('%d/%m'),
                target_date.strftime('%m/%d'),
                day_name,
                day_name[:3],
                str(target_date.day)
            ]

            for original_index, container in enumerate(class_containers, 1):
                matches_day, label = await self._container_matches_day(container, day_tokens)
                context_entry = (original_index, container, label, matches_day)
                container_contexts.append(context_entry)
                if matches_day:
                    filtered_contexts.append(context_entry)
                else:
                    skipped_contexts.append(context_entry)

            if filtered_contexts:
                class_contexts = filtered_contexts
                print(f"✅ Scoped search to {len(filtered_contexts)} class container(s) matching {day_header}")
            else:
                class_contexts = container_contexts
                if skipped_contexts:
                    print("⚠️  Day-level filtering did not match any containers; continuing with unfiltered list")

            class_booked = False
            matching_containers = 0
            for original_index, container, label, _ in class_contexts:
                try:
                    # Get all text content from this class container
                    container_text = await container.text_content()
                    if not container_text:
                        continue
                    
                    # Check if this container has both the instructor and time
                    has_instructor = instructor in container_text
                    has_time = time in container_text or time.replace(':', '') in container_text
                    
                    if has_instructor and has_time:
                        matching_containers += 1
                        extra_context = label or ''
                        context_blurb = f" ({extra_context})" if extra_context else ''
                        print(f"✅ Found {instructor} class at {time} (container #{original_index}){context_blurb}")
                        print(f"   Container text preview: {container_text[:100]}...")
                        
                        # If this is not the first matching container, log it
                        if matching_containers > 1:
                            print(f"⚠️  Multiple matching classes found! This is container #{matching_containers}")
                            print(f"   You may need to be more specific in your schedule (e.g., add level/type)")
                        
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
                        
                        # Wait for overlay to fully load and DOM to stabilize
                        print("⏳ Waiting for overlay to load completely...")
                        await page.wait_for_timeout(2000)  # Wait longer for DOM changes
                        
                        # Now look for the booking button within this specific class container
                        # Re-find the container since DOM may have changed after clicking
                        updated_containers = await page.query_selector_all('div.classDesktopWrapper')
                        
                        for updated_container in updated_containers:
                            try:
                                # Check if this is still our class
                                container_text = await updated_container.text_content()
                                if container_text and instructor in container_text and time in container_text:
                                    print(f"✅ Found updated container for {instructor} at {time}")
                                    
                                    # Look for booking button within this specific container
                                    booking_button = None
                                    try:
                                        booking_button = await updated_container.wait_for_selector(
                                            'a.bookClassButton',
                                            state='visible',
                                            timeout=5000
                                        )
                                    except Exception:
                                        booking_button = await updated_container.query_selector('a.bookClassButton')

                                    if booking_button:
                                        try:
                                            await booking_button.scroll_into_view_if_needed()
                                        except Exception:
                                            pass

                                        button_text = await booking_button.text_content()
                                        display_text = button_text.strip() if button_text else "Unknown"

                                        
                                        # Check what type of button it is
                                        if button_text:
                                            button_lower = button_text.lower()
                                            if "waiting" in button_lower:
                                                print(f"❌ Class is full - only waiting list available")
                                                return False
                                            elif "full" in button_lower:
                                                print(f"❌ Class is full")
                                                return False
                                            elif "book" in button_lower:
                                                is_visible = await booking_button.is_visible()
                                                if is_visible:
                                                    print(f"✅ Clicking booking button for {instructor} class")
                                                    await booking_button.click()
                                                    await page.wait_for_load_state('networkidle')
                                                    class_booked = True
                                                    break
                                                else:
                                                    print(f"⚠️  Booking button not visible")
                                            else:
                                                print(f"⚠️  Unknown button type: '{button_text.strip()}'")
                                    else:
                                        print(f"❌ No booking button found in {instructor} class container")
                                    break
                            except Exception as e:
                                print(f"⚠️  Error checking container: {e}")
                                continue
                        
                        if class_booked:
                            break
                    else:
                        # Class doesn't match - continue searching
                        pass
                            
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
                        
                        success_found = False
                        for success_selector in success_selectors:
                            try:
                                success_element = await page.wait_for_selector(success_selector, timeout=5000)
                                if success_element:
                                    success_text = await success_element.text_content()
                                    print(f"🎉 Class booking successful! {success_text}")
                                    success_found = True
                                    break
                            except:
                                continue
                        
                        if success_found:
                            return True
                        else:
                            print(f"⚠️  No booking success confirmation found for {instructor} at {time}")
                            # Check if we're outside booking window
                            page_content = await page.content()
                            if "not available" in page_content.lower() or "fully booked" in page_content.lower():
                                print("❌ Class not available or fully booked")
                                return False
                            else:
                                print("❌ Booking may have failed - no success confirmation")
                                return False
                except:
                    continue
            
            print(f"❌ Could not find or book class: {instructor} at {time} on {target_date.strftime('%Y-%m-%d')}")
            print("   This class may not exist on this date or is outside the bookable window")
            return False
                
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
            target_date_str = target_date.strftime('%d/%m/%Y')  # Format: 25/10/2025
            date_selected = False
            
            try:
                date_input = await page.wait_for_selector('input#ctl00_mainContent_SessionDatePicker', timeout=5000)
                if date_input:
                    # Check current value
                    current_value = await self._get_input_value(date_input)
                    print(f"📅 Current date value: {current_value}, Target: {target_date_str}")
                    
                    if current_value == target_date_str:
                        print(f"✅ Date already set correctly: {current_value}")
                        date_selected = True
                    else:
                        print("🗓️  Attempting to set date using datepicker widget...")
                        
                        # Method 1: Use the datepicker controls to navigate to the target month/day
                        try:
                            await date_input.click()
                            await page.wait_for_timeout(1000)  # Wait for datepicker to open
                            
                            # Look for datepicker calendar
                            calendar_selectors = [
                                '.uk-datepicker',
                                '[data-uk-datepicker]',
                                '.datepicker',
                                '.uk-dropdown'
                            ]
                            
                            calendar_found = False
                            for cal_selector in calendar_selectors:
                                try:
                                    calendars = await page.query_selector_all(cal_selector)
                                    if calendars:
                                        print(f"✅ Found datepicker calendar: {cal_selector}")
                                        calendar_found = True
                                        navigation_success = await self._navigate_datepicker_to_date(page, cal_selector, target_date)
                                        if navigation_success:
                                            # Wait for the input value to update
                                            last_value = current_value
                                            for _ in range(12):
                                                new_value = await self._get_input_value(date_input)
                                                if new_value == target_date_str:
                                                    print(f"✅ Date selected via datepicker: {new_value}")
                                                    date_selected = True
                                                    break
                                                last_value = new_value
                                                await page.wait_for_timeout(250)
                                            if not date_selected:
                                                print(f"⚠️  Datepicker navigation completed but value is '{last_value}'")
                                        else:
                                            print("⚠️  Could not navigate datepicker to target month/day")
                                        break
                                except Exception as nav_error:
                                    print(f"⚠️  Datepicker selector error for {cal_selector}: {nav_error}")
                                    continue
                            
                            if not calendar_found:
                                print("⚠️  Could not find datepicker calendar")
                        except Exception as e:
                            print(f"⚠️  Could not open datepicker: {e}")
                        
            except Exception as e:
                print(f"⚠️  Date selector error: {e}")
            
            if not date_selected:
                print("❌ Unable to set swim booking date to target day. Aborting booking attempt.")
                return False

            
            # Select duration
            print(f"Selecting duration: {duration} minutes...")
            duration_selectors = [
                'select#ctl00_mainContent_minutes'
            ]
            
            duration_selected = False
            for selector in duration_selectors:
                try:
                    duration_locator = page.locator(selector)
                    await duration_locator.wait_for(state="visible", timeout=3000)
                except Exception as e:
                    print(f"⚠️  Duration dropdown not ready for {selector}: {e}")
                    continue

                try:
                    options = await duration_locator.evaluate(
                        """(el) => Array.from(el.options).map(opt => ({
                            text: (opt.textContent || '').trim(),
                            value: (opt.value || '').trim()
                        }))"""
                    )
                except Exception as e:
                    print(f"⚠️  Could not read duration options for {selector}: {e}")
                    continue

                target_token = f"{duration} min"
                for option in options:
                    option_text = option.get("text", "")
                    if not option_text:
                        continue

                    text_normalised = option_text.lower().replace("mins", "min")
                    if target_token not in text_normalised:
                        continue

                    option_value = option.get("value", "")
                    print(f"✅ Selecting duration: {option_text}")

                    selection_applied = False
                    # Try selecting by value first to avoid stale element handles
                    if option_value:
                        try:
                            await duration_locator.select_option(value=option_value)
                            selection_applied = True
                        except Exception as value_err:
                            print(f"⚠️  select_option(value=...) failed: {value_err}")
                    if not selection_applied:
                        try:
                            await duration_locator.select_option(label=option_text)
                            selection_applied = True
                        except Exception as label_err:
                            print(f"⚠️  select_option(label=...) failed: {label_err}")

                    if not selection_applied and option_value:
                        try:
                            # Use page-level selection as a last resort
                            await page.select_option(selector, option_value)
                            selection_applied = True
                        except Exception as page_err:
                            print(f"⚠️  page.select_option fallback failed: {page_err}")

                    if selection_applied:
                        await page.wait_for_timeout(300)
                        try:
                            selected_label = (await duration_locator.evaluate("(el) => el.options[el.selectedIndex]?.textContent || ''") or '').strip()
                        except Exception as verify_err:
                            print(f"⚠️  Could not verify duration selection: {verify_err}")
                            selected_label = ''
                        if selected_label and target_token in selected_label.lower().replace("mins", "min"):
                            duration_selected = True
                            break

                if duration_selected:
                    break
            
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
                            if option_text and any(keyword in option_text for keyword in time_period_keywords.get(time_period, [])):
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
            
            # Wait for time slots to fully load - they may load dynamically
            print("⏳ Waiting for time slots to load...")
            await page.wait_for_timeout(5000)  # Increased: Wait 5 seconds for dynamic loading
            
            # Wait for the timeSlots containers to have the 'loaded' class
            try:
                await page.wait_for_selector('.timeSlots.loaded', timeout=12000)  # Increased: 12 seconds
                print("✅ Time slots marked as loaded")
            except:
                print("⚠️  Time slots 'loaded' class not found, waiting additional time...")
                # If 'loaded' class not found, wait longer before continuing
                await page.wait_for_timeout(5000)  # Increased: 5 more seconds
                
            # Additional wait for CSS transitions and final rendering
            await page.wait_for_timeout(3000)  # Increased: 3 seconds for transitions
            
            # Priority order: Lane 2, Lane 3, Lane 4, Lane 1
            lane_priority = [2, 3, 4, 1]
            slot_booked = False
            

            # Get lane containers for booking
            time_slot_inners = await page.query_selector_all('div.timeSlotInner')
            
            for lane_num in lane_priority:
                if slot_booked:
                    break
                    
                print(f"Checking Lane {lane_num} for {time}...")
                
                if len(time_slot_inners) >= lane_num:
                    # Get the timeSlotInner for this specific lane (0-indexed)
                    lane_div = time_slot_inners[lane_num - 1]
                    print(f"✅ Found Lane {lane_num} container")
                    
                    # Find all timeSlot divs within this lane
                    time_slots = await lane_div.query_selector_all('div.timeSlot')
                    
                    # Always try the booking button approach as it seems more reliable
                    booking_buttons = await lane_div.query_selector_all('a.bookButton')
                    # Use booking buttons approach if we have them
                    if len(booking_buttons) > 0:
                        for button in booking_buttons:
                            try:
                                # Get the button text content directly
                                link_text = await button.text_content()
                                
                                # Extract time pattern
                                if not link_text:
                                    continue
                                clean_text = re.sub(r'\s+', ' ', link_text).strip()
                                time_match_obj = re.search(r'\b(\d{1,2}:\d{2})\b', clean_text)
                                
                                if time_match_obj:
                                    extracted_time = time_match_obj.group(1)
                                    
                                    if extracted_time == time:
                                        print(f"✅ Found {time} slot in Lane {lane_num}")
                                        await button.click()
                                        slot_booked = True
                                        break
                            except Exception as e:
                                print(f"⚠️  Error checking button: {e}")
                                continue
                                
                        if slot_booked:
                            break
                            
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
                                    print(f"🎉 Swim lane booking successful!")
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
        target_date_obj = current_time.date() + timedelta(days=8)
        # Convert to datetime for consistent return type
        target_datetime = datetime.combine(target_date_obj, datetime.min.time()).replace(tzinfo=current_time.tzinfo)
        
        # Check if target date matches the scheduled day of week
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        target_day_name = day_names[target_date_obj.weekday()]
        
        if target_day_name != schedule_entry['day_of_week']:
            return False, target_datetime
        
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
                return True, target_datetime
            else:
                print(f"  ❌ Booking window closed (>15 minutes ago)")
        else:
            time_until = (scheduled_time - current_time).total_seconds() / 60
            print(f"  ⏳ Time until booking: {time_until:.1f} minutes")
        
        return False, target_datetime

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
        if pytz:
            uk_tz = pytz.timezone('Europe/London')
            current_time = datetime.now(uk_tz)
        else:
            # Fallback to system timezone if pytz not available
            current_time = datetime.now()
        
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
                    # Use centralized browser detection
                    is_local, browser_path = user_bot._detect_browser_environment()
                    
                    if is_local and browser_path:
                        browser = await p.chromium.launch(
                            headless=self.headless,
                            executable_path=browser_path
                        )
                    else:
                        browser = await p.chromium.launch(headless=self.headless)
                    
                    # Create context with realistic user agent to avoid bot detection
                    context = await browser.new_context(
                        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
                    )
                    page = await context.new_page()
                    
                    try:
                        # Login
                        if not await user_bot.login(page):
                            print(f"❌ Login failed for {entry['user']}")
                            # Send email notification for login failure
                            self._send_booking_failure_email(
                                {
                                    'user': entry['user'],
                                    'instructor': entry['instructor'],
                                    'time': entry['time'],
                                    'target_date': target_date.strftime('%Y-%m-%d (%A)'),
                                    'is_swim': is_swim,
                                    'duration': duration if is_swim else None
                                },
                                "Login Authentication Failed",
                                "Could not log into the gym website with provided credentials"
                            )
                            continue
                        
                        if is_swim:
                            # Make swim booking
                            success = await user_bot.book_swim_lane(page, target_date, duration, entry['time'])
                            if success:
                                print(f"🏊 Swim booking successful: {entry['user']} - {duration}min at {entry['time']}")
                                bookings_made += 1
                            else:
                                print(f"❌ Swim booking failed: {entry['user']} - {duration}min at {entry['time']}")
                                # Send email notification for swim booking failure
                                self._send_booking_failure_email(
                                    {
                                        'user': entry['user'],
                                        'instructor': entry['instructor'],
                                        'time': entry['time'],
                                        'target_date': target_date.strftime('%Y-%m-%d (%A)'),
                                        'is_swim': True,
                                        'duration': duration
                                    },
                                    "Swim Lane Booking Failed",
                                    "Could not secure swim lane - may be fully booked or page loading issues"
                                )
                        else:
                            # Make class booking
                            success = await user_bot.book_class(page, target_date, entry['instructor'], entry['time'])
                            if success:
                                print(f"🏃 Class booking successful: {entry['user']} - {entry['instructor']} at {entry['time']}")
                                bookings_made += 1
                            else:
                                print(f"❌ Class booking failed: {entry['user']} - {entry['instructor']} at {entry['time']}")
                                # Send email notification for class booking failure
                                self._send_booking_failure_email(
                                    {
                                        'user': entry['user'],
                                        'instructor': entry['instructor'],
                                        'time': entry['time'],
                                        'target_date': target_date.strftime('%Y-%m-%d (%A)'),
                                        'is_swim': False,
                                        'duration': None
                                    },
                                    "Class Booking Failed",
                                    f"Could not book {entry['instructor']} class - may be full, cancelled, or not available on this date"
                                )
                        
                    except Exception as e:
                        print(f"❌ Error processing booking for {entry['user']}: {e}")
                        # Send email notification for unexpected errors
                        self._send_booking_failure_email(
                            {
                                'user': entry['user'],
                                'instructor': entry['instructor'],
                                'time': entry['time'],
                                'target_date': target_date.strftime('%Y-%m-%d (%A)'),
                                'is_swim': is_swim,
                                'duration': duration if is_swim else None
                            },
                            "Booking System Error",
                            f"Unexpected error during booking process: {str(e)}"
                        )
                    finally:
                        await browser.close()
                
            except Exception as e:
                print(f"❌ Error processing schedule entry {entry}: {e}")
                continue
        
        print(f"✅ Schedule processing complete. Bookings made: {bookings_made}")
        return True
