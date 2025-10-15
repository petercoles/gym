#!/usr/bin/env python3
"""Simple cron entry point for gym booking bot"""

import asyncio
import sys

async def main():
    try:
        from gym_booking_bot import GymBookingBot
        bot = GymBookingBot()
        await bot.run_scheduled_bookings()
    except Exception as e:
        print(f"Error: {e}")
        # Exit cleanly - booking likely failed due to full class
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())