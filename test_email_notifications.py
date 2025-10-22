#!/usr/bin/env python3
"""
Test script for email notification functionality
"""

import os
from datetime import datetime
from gym_booking_bot import GymBookingBot
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_email_notification():
    """Test the email notification system with a simulated booking failure"""
    
    print("🧪 Testing Email Notification System")
    print("=" * 50)
    
    # Check if email credentials are configured
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    notification_email = os.getenv('NOTIFICATION_EMAIL')
    
    print(f"📧 SMTP_USER: {'✅ Configured' if smtp_user else '❌ Not configured'}")
    print(f"🔐 SMTP_PASSWORD: {'✅ Configured' if smtp_password else '❌ Not configured'}")
    print(f"📮 NOTIFICATION_EMAIL: {'✅ Configured' if notification_email else '❌ Not configured'}")
    
    if smtp_user:
        print(f"📨 Email will be sent from: {smtp_user}")
    if notification_email:
        print(f"📬 Email will be sent to: {notification_email}")
    
    print("\n🎯 Simulating a booking failure...")
    
    # Create a bot instance
    try:
        bot = GymBookingBot(user_name="peter")
    except Exception as e:
        print(f"❌ Could not create bot (likely missing gym credentials): {e}")
        print("💡 Add GYM_URL, PETER_USERNAME, PETER_PASSWORD to .env file")
        return False
    
    # Simulate a booking failure
    test_booking_details = {
        'user': 'peter',
        'instructor': 'Mari',
        'time': '08:15',
        'target_date': datetime.now().strftime('%Y-%m-%d (%A)'),
        'is_swim': False,
        'duration': None
    }
    
    failure_reason = "TEST: Class Booking Failed"
    error_details = "This is a test email to verify the notification system is working correctly."
    
    print(f"📋 Test booking details:")
    print(f"   User: {test_booking_details['user']}")
    print(f"   Class: {test_booking_details['instructor']}")
    print(f"   Time: {test_booking_details['time']}")
    print(f"   Date: {test_booking_details['target_date']}")
    print(f"   Reason: {failure_reason}")
    
    print("\n📤 Attempting to send test notification email...")
    
    # Test the email notification
    bot._send_booking_failure_email(test_booking_details, failure_reason, error_details)
    
    print("\n✅ Test completed!")
    
    if not smtp_user or not smtp_password:
        print("\n💡 To enable email notifications:")
        print("1. Add these to your .env file:")
        print("   SMTP_SERVER=smtp.gmail.com")
        print("   SMTP_PORT=587")
        print("   SMTP_USER=your-email@gmail.com")
        print("   SMTP_PASSWORD=your-gmail-app-password")
        print("   NOTIFICATION_EMAIL=your-email@gmail.com")
        print("\n2. For Gmail users:")
        print("   - Enable 2FA on your Gmail account")
        print("   - Generate an App Password (not your regular password)")
        print("   - Use the App Password as SMTP_PASSWORD")
        print("\n3. Run this test again to verify email delivery")
    
    return True

if __name__ == "__main__":
    test_email_notification()