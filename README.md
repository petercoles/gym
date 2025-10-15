# Gym Class and Swim Lane Booking Bot

Automate booking gym classes and swim lanes using Playwright. This bot can log into your gym's website, navigate to schedules, and book classes or swim sessions 8 days in advance.

## Features

- ✅ **Multi-User Support**: Separate credentials for Peter, Adrienne, and Lucy
- ✅ **Instructor + Time Booking**: Book classes by instructor name and time (handles duplicate class names)
- ✅ **CSV Schedule Automation**: Manage all bookings in a simple CSV file
- ✅ **Smart State Tracking**: Prevents duplicate bookings with automatic state management
- ✅ **Swim Lane Booking**: Book swim sessions with specific time slots and lane priority
- ✅ **Robust Error Handling**: Graceful handling of failures with detailed logging
- ✅ **Single Cron Job**: Replace multiple cron entries with one scheduled check
- ✅ **Quarter-Hour Precision**: Optimized for gym's 15-minute booking intervals

## Setup

1. **Install dependencies**:
   ```bash
   pip install playwright
   playwright install
   ```

2. **Configure your credentials** by creating a `.env` file from the template:
   ```bash
   cp .env.template .env
   # Edit .env with your actual credentials
   ```
   
   ```
   # Multi-user configuration
   PETER_USERNAME=peters_username_or_email
   PETER_PASSWORD=peters_password
   ADRIENNE_USERNAME=adriennes_username_or_email
   ADRIENNE_PASSWORD=adriennes_password
   LUCY_USERNAME=lucys_username_or_email
   LUCY_PASSWORD=lucys_password
   HEADLESS=false
   ```

3. **Set up your S3 bucket** and upload your schedule:
   ```bash
   # Create schedule.csv with your bookings and upload to S3
   # Update .env with your S3 bucket details
   ```

## Usage

The bot is designed for automated cron-based execution. It loads your booking schedule from an S3 bucket and processes any bookings that are due.

### Local Testing
```bash
python cron_booking.py
```

### Deployment
Deploy to Render.com as a cron job that runs every 15 minutes. The bot will automatically:
1. Load your schedule from S3
2. Check if any bookings are due (8 days in advance)
3. Make the bookings using the appropriate user credentials
4. Exit cleanly

## How It Works

### Class Booking Flow (Instructor + Time Matching)
1. **Login** to gym website using specified user credentials
2. **Navigate** to class calendar via menu
3. **Click "Next"** once to advance to bookable week (8 days ahead)
4. **Parse all class elements** in the target date section
5. **Extract instructor names** and start times from each class
6. **Match target instructor + time** with available classes
7. **Click booking icon** for the matched class
6. **Handle modal** and click "Book" button
7. **Accept terms** and conditions
8. **Confirm booking** with final button

### Swim Lane Booking Flow  
1. **Login** to gym website
2. **Navigate** to swim booking via menu
3. **Select date** (8 days ahead) using date picker
4. **Choose duration** (15 or 30 minutes)
5. **Select specific time** (e.g. "09:00")
6. **Click "Go"** to see availability
7. **Select available lane** (prioritizes lanes 2-3)
8. **Complete booking** through modal flow

## S3 Schedule Configuration

Create a `schedule.csv` file with your regular bookings and upload it to your S3 bucket:

```csv
user,instructor,day_of_week,time
peter,Mari,monday,09:00
adrienne,Sarah,wednesday,18:30
lucy,Swim(30),friday,09:00
peter,Swim(15),tuesday,07:00
```

Configure your `.env` file with S3 details:
```bash
SCHEDULE_S3_BUCKET=your-gym-schedules
SCHEDULE_S3_KEY=schedule.csv
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_DEFAULT_REGION=eu-west-2
```

## Render.com Deployment

Deploy as a cron job on Render.com that runs every 15 minutes. The bot automatically loads the schedule from S3 and makes any due bookings.
2 7 * * * cd /path/to/hogarth && /path/to/hogarth/.venv/bin/python gym_booking_bot.py class adrienne Sarah 18:30
4 7 * * * cd /path/to/hogarth && /path/to/hogarth/.venv/bin/python gym_booking_bot.py class lucy Emma 07:00
```

### CSV Schedule Format

The `schedule.csv` file supports the following columns:

| Column | Description | Examples |
|--------|-------------|----------|
| `user` | User name | `peter`, `adrienne`, `lucy` |
| `instructor` | Instructor name OR swim booking | `Mari`, `Sarah`, `Swim(30)`, `Swim(15)` |
| `day_of_week` | Day of the week | `monday`, `tuesday`, `wednesday`, etc. |
| `time` | Class/swim time | `09:00`, `18:30`, `07:15` |

**Swim Bookings**: Use `Swim(duration)` format where duration is 15 or 30 minutes.

**Timing**: Bookings are made exactly 8 days in advance when the scheduled time arrives. The system checks every 15 minutes and prevents duplicate bookings.

### Benefits of CSV Scheduling

✅ **Single Cron Job**: Replace multiple cron entries with one check every 15 minutes  
✅ **Easy Management**: Edit schedule.csv instead of modifying crontab  
✅ **No Duplicates**: Automatic state tracking prevents re-booking  
✅ **Graceful Handling**: Continues processing if individual bookings fail  
✅ **Visual Schedule**: Clear overview of all recurring bookings in one file

### Files Created Automatically

- **`booking_state.json`**: Tracks completed bookings to prevent duplicates
- **Template files**: `.env.template` and `schedule.csv.template` for easy setup

## Troubleshooting

### General Issues
1. **Set `HEADLESS=false`** to watch the browser and debug
2. **Check console output** for detailed step-by-step logs
3. **Test login credentials** for each user in `.env` file

### Class Booking Issues
4. **Use instructor names only** (e.g., "Mari" not "Group Cycle- Mari")
5. **Verify instructor spelling** matches exactly what's shown on website
6. **Check time format** is HH:MM (e.g., "09:00" not "9am")

### Schedule Issues
7. **Validate CSV format** - check for proper columns and data types
8. **Use correct day names** (monday, tuesday, etc. - all lowercase)
9. **Check `booking_state.json`** if bookings seem to be skipped
10. **Clear old state** by deleting `booking_state.json` if needed

### Swim Booking Issues
11. **Use Swim(duration) format** exactly (e.g., "Swim(30)" not "Swim 30")
12. **Valid durations** are 15 or 30 minutes only

## Deployment

The bot automatically handles backend initialization and fallback logic.

### Render.com Cron Deployment

Simple cron-based deployment for reliable booking automation:

#### Quick Setup
1. **Push to GitHub**: Ensure all files are committed to your repository
2. **Create Cron Job**: Connect your GitHub repo to Render.com
3. **Configure Service**:
   - **Service Type**: Cron Job
   - **Build Command**: `pip install -r requirements.txt`
   - **Run Command**: `python cron_booking.py`
   - **Schedule**: `*/15 * * * *` (every 15 minutes)
4. **Set Environment Variables**: Add user credentials and configuration

#### Environment Variables
```bash
# Required: User credentials (set for users you want to book for)
GYM_URL=your_gym_website_url
PETER_USERNAME=your_username
PETER_PASSWORD=your_password
ADRIENNE_USERNAME=adrienne_username
ADRIENNE_PASSWORD=adrienne_password
LUCY_USERNAME=lucy_username
LUCY_PASSWORD=lucy_password

# Schedule Configuration (choose one)
SCHEDULE_S3_BUCKET=your-s3-bucket          # S3 approach (recommended)
SCHEDULE_S3_KEY=schedule.csv
# OR
SCHEDULE_FILE=schedule.csv                 # Local file approach

# AWS credentials (if using S3)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
```

#### S3 Schedule Privacy Setup

For enhanced privacy, store your schedule in S3 instead of committing it to your repository:

1. **Upload schedule to S3**: `aws s3 cp schedule.csv s3://your-bucket/schedule.csv`
2. **Set environment variables**: `SCHEDULE_S3_BUCKET=your-bucket`, `SCHEDULE_S3_KEY=schedule.csv`
3. **Exclude from git**: Schedule is already excluded in `.gitignore`

The bot automatically detects S3 configuration and loads schedules from S3 when `SCHEDULE_S3_BUCKET` is set.

## Environment Variables

Configuration files:

### `.env` file:

**User Credentials:**
- `PETER_USERNAME`, `PETER_PASSWORD` - Peter's credentials
- `ADRIENNE_USERNAME`, `ADRIENNE_PASSWORD` - Adrienne's credentials  
- `LUCY_USERNAME`, `LUCY_PASSWORD` - Lucy's credentials

**General Settings:**
- `GYM_URL` - Gym website URL (required)
- `HEADLESS` - Set to `false` for debugging, `true` for automated runs
- `SCHEDULE_FILE` - Path to CSV schedule file (default: schedule.csv)

**S3 Schedule (optional, for privacy):**
- `SCHEDULE_S3_BUCKET` - S3 bucket name for schedule storage
- `SCHEDULE_S3_KEY` - S3 object key (default: schedule.csv)
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`

### `schedule.csv` file:
- `user` - peter, adrienne, or lucy
- `instructor` - Instructor name or Swim(duration)
- `day_of_week` - monday through sunday
- `time` - HH:MM format (e.g., 09:00, 18:30)

## Legal Notice

This tool is for personal use only. Ensure you comply with your gym's terms of service and booking policies. Always respect booking limits and cancellation policies.
