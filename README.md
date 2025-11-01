# Gym Class and Swim Lane Booking Bot

Automates Hogarth gym bookings with Playwright. The bot logs in with the appropriate member account, advances to the correct booking window (eight days ahead), and submits class or swim reservations without manual intervention.

## Features

- ✅ Multi-user credentials (Peter, Adrienne, Lucy) selected per schedule entry
- ✅ CSV-driven schedule with optional S3 storage for shared automation
- ✅ Accurate class matching by instructor and start time on the target day
- ✅ Swim lane booking with duration handling and lane preference fallback
- ✅ Email notifications when a booking attempt fails (SMTP configurable)
- ✅ Time-window guard uses live timestamps instead of local state files
- ✅ Smart browser selection: local Chromium when available, bundled Playwright on Render

## Setup

1. **Install dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   playwright install
   ```

2. **Configure environment**
   ```bash
   cp .env.template .env
   ```
   Update `.env` with:
   - `GYM_URL`
   - User credentials: `PETER_USERNAME`, `PETER_PASSWORD`, etc.
   - Booking behaviour: `HEADLESS=true|false`
   - Schedule source:
     - Local file: `SCHEDULE_FILE=schedule.csv`
     - or S3: `SCHEDULE_S3_BUCKET`, `SCHEDULE_S3_KEY`, and AWS credentials
   - Email alerts: `SENDER_EMAIL`, `SENDER_PASSWORD`, `RECIPIENT_EMAIL`, plus optional SMTP host/port

3. **Prepare your schedule**
   - Copy `schedule.csv.template` to `schedule.csv`
   - Populate rows in the format:
     ```csv
     user,instructor,day_of_week,time
     peter,Mari,monday,09:00
     lucy,Swim(30),friday,09:00
     ```
   - Instructor values beginning with `Swim(` signal a swim booking and encode duration (`Swim(15)` or `Swim(30)`).

## Usage

Run the scheduled workflow locally:
```bash
python cron_booking.py
```

The script:
1. Loads the schedule (prefers S3 if configured, otherwise local CSV).
2. Evaluates whether each entry should run: eight days ahead, within a 15-minute window starting at the scheduled time.
3. Launches Playwright, logs in with the correct user, and delegates to class or swim booking flow.
4. Sends a notification email if any booking fails.

### Process Flow Overview

**Scheduled run**
- Pull schedule entries.
- For each entry whose booking window is open, instantiate `GymBookingBot` for that user.
- Launch Chromium (local executable if found, otherwise Playwright-managed browser).

**Class booking**
1. Navigate to the Classes page (via link detection or direct URL fallback).
2. Click the “Next” week control once to reach the bookable window.
3. Locate the target day column, parsing each class card for instructor/time.
4. Click the matching booking button.
5. Accept any terms checkbox and confirm the booking.

**Swim booking**
1. Navigate to the Swim page.
2. Open the date picker and advance to the target date.
3. Select duration and time-of-day dropdowns; click “Go” to load slots.
4. Evaluate available lanes (prioritising lanes 2–4) and pick the correct start time.
5. Proceed through confirmation and final booking.

## Deployment

Render.com cron job example:
- **Build command**: `pip install -r requirements.txt && playwright install`
- **Run command**: `python cron_booking.py`
- **Schedule**: `*/15 * * * *`
- Configure the same environment variables as your local `.env`. Render provides `/opt/render/project/.playwright-browsers` automatically; the bot switches to bundled Chromium in that environment.

## Troubleshooting

- Set `HEADLESS=false` to observe the browser when debugging locally.
- Check console logs for the exact selectors used while navigating.
- Confirm schedule rows use lowercase day names and HH:MM times on quarter hours.
- Verify SMTP credentials if emails are not delivered.
- When the site layout changes, update selectors inside `gym_booking_bot.py`.

## Legal Notice

This automation is intended for personal use. Ensure your gym permits automated bookings and respect cancellation policies and booking limits.
