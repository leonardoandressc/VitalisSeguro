#!/usr/bin/env python3
"""Entry point for running the appointment reminder job.

This script can be called by a cron job or scheduler service like Render.
It runs the daily appointment reminder process for all active accounts.

Usage:
    python run_reminder_job.py [--timezone TIMEZONE]
    
Example:
    python run_reminder_job.py --timezone America/Los_Angeles
"""
import os
import sys
import argparse
import json
from datetime import datetime
import pytz

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Initialize Firebase before importing other modules
import firebase_admin
from firebase_admin import credentials
from app.core.config import get_config

# Initialize Firebase
config = get_config()
if not firebase_admin._apps:
    cred = credentials.Certificate(config.firebase_credentials_path)
    firebase_admin.initialize_app(cred)

from scheduler.appointment_reminder import AppointmentReminderService
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


def main():
    """Main entry point for the reminder job."""
    parser = argparse.ArgumentParser(
        description="Run appointment reminder job for all active accounts"
    )
    parser.add_argument(
        "--timezone",
        type=str,
        default="America/Los_Angeles",
        help="Timezone for appointment times (default: America/Los_Angeles)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (log actions without sending messages)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    config = get_config()
    setup_logging(config)
    
    logger.info(
        "Starting appointment reminder job",
        extra={
            "timezone": args.timezone,
            "dry_run": args.dry_run,
            "start_time": datetime.now(pytz.UTC).isoformat()
        }
    )
    
    try:
        # Initialize reminder service
        reminder_service = AppointmentReminderService()
        
        # Run the reminder job
        if args.dry_run:
            logger.info("Running in dry-run mode - no messages will be sent")
            # TODO: Implement dry-run mode in the service
        
        results = reminder_service.run_daily_reminders(timezone=args.timezone)
        
        # Log results
        logger.info(
            "Reminder job completed",
            extra={
                "results": results,
                "end_time": datetime.now(pytz.UTC).isoformat()
            }
        )
        
        # Print summary for monitoring
        print(f"Reminder Job Summary:")
        print(f"  Total Accounts: {results['total_accounts']}")
        print(f"  Total Appointments: {results['total_appointments']}")
        print(f"  Reminders Sent: {results['reminders_sent']}")
        print(f"  Errors: {len(results['errors'])}")
        
        if results['errors']:
            print("\nErrors encountered:")
            for error in results['errors']:
                print(f"  - {error}")
        
        # Exit with appropriate code
        exit_code = 0 if len(results['errors']) == 0 else 1
        sys.exit(exit_code)
        
    except Exception as e:
        logger.error(
            f"Fatal error in reminder job: {e}",
            exc_info=True
        )
        print(f"FATAL ERROR: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()