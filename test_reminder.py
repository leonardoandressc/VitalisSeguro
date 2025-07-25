#!/usr/bin/env python3
"""Test script for sending appointment reminder messages.

This script allows testing the WhatsApp reminder functionality
without waiting for the cron job to run.

Usage:
    python test_reminder.py --phone +521234567890
    python test_reminder.py --phone +521234567890 --name "Juan Pérez"
    python test_reminder.py --phone +521234567890 --preview
"""
import os
import sys
import argparse
from datetime import datetime, timedelta
import pytz

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Initialize Firebase before importing other modules
import firebase_admin
from firebase_admin import credentials
from app.core.config import get_config

# Initialize Firebase
config = get_config()
if not firebase_admin._apps:
    cred = credentials.Certificate(config.firebase_credentials_path)
    firebase_admin.initialize_app(cred)

from app.services.whatsapp_service import WhatsAppService
from app.repositories.account_repository import AccountRepository
from app.models.account import AccountStatus
from scheduler.templates import ReminderTemplates
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


def main():
    """Main entry point for test reminder script."""
    parser = argparse.ArgumentParser(
        description="Test appointment reminder messages"
    )
    parser.add_argument(
        "--phone",
        type=str,
        required=False,
        help="Phone number to send test message to (with country code, e.g. +521234567890)"
    )
    parser.add_argument(
        "--name",
        type=str,
        default="Cliente de Prueba",
        help="Customer name for the test message"
    )
    parser.add_argument(
        "--time",
        type=str,
        default=None,
        help="Appointment time (e.g. '2:30 PM'). If not provided, uses 2 hours from now"
    )
    parser.add_argument(
        "--calendar",
        type=str,
        default="Consulta General",
        help="Calendar/appointment type name"
    )
    parser.add_argument(
        "--account-id",
        type=str,
        default=None,
        help="Account ID to use for sending. If not provided, uses first active account"
    )
    parser.add_argument(
        "--account-name",
        type=str,
        default=None,
        help="Account name to use for sending (alternative to --account-id)"
    )
    parser.add_argument(
        "--list-accounts",
        action="store_true",
        help="List all available accounts and exit"
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview the message without sending"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Send interactive reminder with buttons (like production)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(config)
    
    # Handle list accounts option
    if args.list_accounts:
        account_repo = AccountRepository()
        accounts = account_repo.list_all(status=AccountStatus.ACTIVE)
        
        print("\n" + "="*60)
        print("AVAILABLE ACCOUNTS")
        print("="*60)
        
        if not accounts:
            print("No active accounts found.")
        else:
            for i, account in enumerate(accounts, 1):
                print(f"\n{i}. {account.name}")
                print(f"   ID: {account.id}")
                print(f"   Phone Number ID: {account.phone_number_id}")
                print(f"   Location ID: {account.location_id}")
                print(f"   Status: {account.status.value}")
        
        print("="*60 + "\n")
        print("To use a specific account, run with:")
        print("  --account-id <ID>")
        print("  --account-name <NAME>")
        sys.exit(0)
    
    # Check required arguments when not listing
    if not args.phone:
        print("❌ Error: --phone is required")
        parser.print_help()
        sys.exit(1)
    
    logger.info(
        "Starting test reminder",
        extra={
            "phone": args.phone,
            "customer_name": args.name,
            "preview_only": args.preview
        }
    )
    
    try:
        # Get appointment time
        if args.time:
            # Parse provided time
            appointment_time = args.time
        else:
            # Use 2 hours from now
            tz = pytz.timezone("America/Los_Angeles")
            future_time = datetime.now(tz) + timedelta(hours=2)
            appointment_time = future_time.strftime("%I:%M %p")
        
        # Generate message
        templates = ReminderTemplates()
        
        if args.interactive:
            # Generate interactive message
            interactive_data = templates.get_interactive_reminder_message(
                customer_name=args.name,
                appointment_time=appointment_time,
                calendar_name=args.calendar
            )
            interactive = interactive_data["interactive"]
            
            print("\n" + "="*50)
            print("TEST INTERACTIVE REMINDER MESSAGE")
            print("="*50)
            print(f"To: {args.phone}")
            print(f"Customer: {args.name}")
            print(f"Time: {appointment_time}")
            print(f"Calendar: {args.calendar}")
            print("-"*50)
            print("Message Content:")
            print("-"*50)
            print(interactive.body_text)
            print("\nButtons:")
            for button in interactive.buttons:
                print(f"  [{button.title}]")
            if interactive.footer_text:
                print(f"\nFooter: {interactive.footer_text}")
            print("="*50 + "\n")
        else:
            # Generate text message
            message = templates.get_reminder_message(
                customer_name=args.name,
                appointment_time=appointment_time,
                calendar_name=args.calendar
            )
            
            print("\n" + "="*50)
            print("TEST REMINDER MESSAGE")
            print("="*50)
            print(f"To: {args.phone}")
            print(f"Customer: {args.name}")
            print(f"Time: {appointment_time}")
            print(f"Calendar: {args.calendar}")
            print("-"*50)
            print("Message Content:")
            print("-"*50)
            print(message)
            print("="*50 + "\n")
        
        if args.preview:
            print("✓ Preview mode - message not sent")
            return
        
        # Get account for sending
        account_repo = AccountRepository()
        account = None
        
        if args.account_id:
            # Use specific account by ID
            account = account_repo.get(args.account_id)
            if not account:
                print(f"❌ Account with ID '{args.account_id}' not found")
                print("\nRun with --list-accounts to see available accounts")
                sys.exit(1)
            account_id = account.id
            
        elif args.account_name:
            # Find account by name
            accounts = account_repo.list_all(status=AccountStatus.ACTIVE)
            matching_accounts = [a for a in accounts if a.name.lower() == args.account_name.lower()]
            
            if not matching_accounts:
                print(f"❌ No active account found with name '{args.account_name}'")
                print("\nAvailable accounts:")
                for a in accounts:
                    print(f"  - {a.name}")
                sys.exit(1)
            
            account = matching_accounts[0]
            account_id = account.id
            
        else:
            # Get first active account
            accounts = account_repo.list_all(status=AccountStatus.ACTIVE)
            if not accounts:
                print("❌ No active accounts found")
                print("\nPlease create an account first or check account status")
                sys.exit(1)
            account = accounts[0]  # Take the first active account
            account_id = account.id
        
        print(f"\n✓ Using account: {account.name}")
        print(f"  ID: {account_id}")
        print(f"  Phone Number ID: {account.phone_number_id}")
        
        # Send test message
        whatsapp_service = WhatsAppService()
        phone_number_id = account.phone_number_id
        
        print("\nSending message...")
        
        if args.interactive:
            # Send interactive message
            response = whatsapp_service.send_interactive_reminder(
                phone_number_id=phone_number_id,
                to_number=args.phone,
                interactive=interactive
            )
        else:
            # Send text message
            response = whatsapp_service.send_text_message(
                phone_number_id=phone_number_id,
                to_number=args.phone,
                message=message
            )
        
        if response and response.get("messages"):
            message_id = response["messages"][0]["id"]
            print(f"✅ Message sent successfully!")
            print(f"Message ID: {message_id}")
            print(f"\nCheck WhatsApp on {args.phone} to see the reminder")
        else:
            print("❌ Failed to send message")
            if response:
                print(f"Response: {response}")
        
    except Exception as e:
        logger.error(f"Error in test reminder: {e}", exc_info=True)
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()