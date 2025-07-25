"""Appointment reminder service for sending WhatsApp notifications."""
import os
import sys
from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Optional
import pytz
import requests
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import get_logger
from app.repositories.account_repository import AccountRepository
from app.models.account import AccountStatus
from app.services.ghl_service import GHLService
from app.services.whatsapp_service import WhatsAppService
from app.services.whatsapp_template_service import WhatsAppTemplateService
from app.utils.firebase import get_firestore_client
from app.utils.phone_utils import normalize_phone, format_phone_for_whatsapp
from scheduler.templates import ReminderTemplates

logger = get_logger(__name__)


@dataclass
class AppointmentReminder:
    """Represents an appointment reminder to be sent."""
    appointment_id: str
    contact_id: str
    contact_name: str
    contact_phone: str
    appointment_time: datetime
    calendar_name: str
    location_id: str
    account_id: str
    calendar_id: Optional[str] = None


class AppointmentReminderService:
    """Service for managing appointment reminders."""
    
    def __init__(self):
        """Initialize the reminder service."""
        self.account_repo = AccountRepository()
        self.ghl_service = GHLService()
        self.whatsapp_service = WhatsAppService()
        self.db = get_firestore_client()
        self.templates = ReminderTemplates()
        
    def run_daily_reminders(self, timezone: str = "America/Los_Angeles") -> Dict[str, Any]:
        """Run daily appointment reminders for all active accounts."""
        logger.info("Starting daily appointment reminder job")
        
        results = {
            "total_accounts": 0,
            "total_appointments": 0,
            "reminders_sent": 0,
            "errors": [],
            "timestamp": datetime.now(pytz.UTC).isoformat()
        }
        
        try:
            # Get all active accounts
            accounts = self.account_repo.list_all(status=AccountStatus.ACTIVE)
            results["total_accounts"] = len(accounts)
            
            logger.info(
                "Found active accounts",
                extra={
                    "account_ids": [acc.id for acc in accounts],
                    "account_names": [acc.name for acc in accounts]
                }
            )
            
            for account in accounts:
                try:
                    self._process_account_reminders(account, timezone, results)
                except Exception as e:
                    error_msg = f"Error processing account {account.id}: {str(e)}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            logger.info(
                "Reminder job completed",
                extra={
                    "accounts_processed": results["total_accounts"],
                    "reminders_sent": results["reminders_sent"],
                    "errors": len(results["errors"])
                }
            )
            
        except Exception as e:
            logger.error(f"Fatal error in reminder job: {e}")
            results["errors"].append(f"Fatal error: {str(e)}")
        
        # Store job results
        self._store_job_results(results)
        return results
    
    def _process_account_reminders(
        self, 
        account: Any, 
        timezone: str, 
        results: Dict[str, Any]
    ) -> None:
        """Process reminders for a single account."""
        logger.info(
            f"Processing reminders for account: {account.id}",
            extra={
                "account_name": account.name,
                "calendar_id": account.calendar_id,
                "location_id": account.location_id
            }
        )
        
        # Get today's appointments for this account
        appointments = self._get_todays_appointments(account, timezone)
        results["total_appointments"] += len(appointments)
        
        for appointment in appointments:
            try:
                # Check if reminder already sent
                if self._reminder_already_sent(appointment.appointment_id):
                    logger.info(
                        f"Reminder already sent for appointment {appointment.appointment_id}"
                    )
                    continue
                
                # Send reminder
                success = self._send_reminder(account, appointment)
                
                if success:
                    results["reminders_sent"] += 1
                    self._mark_reminder_sent(appointment)
                else:
                    results["errors"].append(
                        f"Failed to send reminder for appointment {appointment.appointment_id}"
                    )
                    
            except Exception as e:
                error_msg = f"Error sending reminder {appointment.appointment_id}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
    
    def _get_todays_appointments(
        self, 
        account: Any, 
        timezone_str: str
    ) -> List[AppointmentReminder]:
        """Get all appointments for today for an account."""
        tz = pytz.timezone(timezone_str)
        
        # Get start and end of today in the specified timezone
        today = datetime.now(tz).date()
        start_of_day = tz.localize(datetime.combine(today, time.min))
        end_of_day = tz.localize(datetime.combine(today, time.max))
        
        # Convert to UTC for queries
        start_utc = start_of_day.astimezone(pytz.UTC)
        end_utc = end_of_day.astimezone(pytz.UTC)
        
        reminders = []
        
        # Always fetch appointments directly from GHL API for accuracy
        logger.info(f"Fetching appointments from GHL API for account {account.id}")
        
        # Get appointments from GHL
        appointments_data = self.ghl_service.get_appointments(
            account_id=account.id,
            calendar_id=account.calendar_id,
            start_date=start_utc,
            end_date=end_utc,
            location_id=account.location_id  # Required parameter
        )
        
        # Convert to reminder objects
        for event in appointments_data.get("events", []):
            # Skip if not an appointment (no appointmentStatus)
            if not event.get("appointmentStatus"):
                continue
                
            # Skip cancelled appointments
            if event.get("appointmentStatus") == "cancelled":
                continue
            
            # Get contact details using contactId
            contact_id = event.get("contactId")
            if not contact_id:
                logger.warning(
                    f"No contactId for appointment {event['id']}, skipping reminder"
                )
                continue
                
            # Fetch contact details from GHL
            contact = self.ghl_service.get_contact(account.id, contact_id)
            if not contact:
                logger.warning(
                    f"Could not fetch contact {contact_id} for appointment {event['id']}, skipping reminder"
                )
                continue
                
            # Extract phone number
            contact_phone = contact.get("phone") or contact.get("phoneNumber")
            if not contact_phone:
                logger.warning(
                    f"No phone number for contact {contact_id}, appointment {event['id']}, skipping reminder"
                )
                continue
            
            # Parse appointment time from startTime
            start_time_str = event.get("startTime")
            if not start_time_str:
                logger.warning(
                    f"No startTime for appointment {event['id']}, skipping reminder"
                )
                continue
                
            try:
                # Handle various datetime formats
                if start_time_str.endswith('Z'):
                    apt_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                else:
                    apt_time = datetime.fromisoformat(start_time_str)
            except ValueError as e:
                logger.error(
                    f"Invalid startTime format for appointment {event['id']}: {start_time_str}, error: {e}"
                )
                continue
            
            reminder = AppointmentReminder(
                appointment_id=event["id"],
                contact_id=contact_id,
                contact_name=contact.get("name") or contact.get("firstName", "Cliente"),
                contact_phone=contact_phone,
                appointment_time=apt_time,
                calendar_name=event.get("title", ""),
                location_id=account.location_id,
                account_id=account.id,
                calendar_id=event.get("calendarId", account.calendar_id)
            )
            
            reminders.append(reminder)
        
        return reminders
    
    def _send_reminder(
        self, 
        account: Any, 
        reminder: AppointmentReminder
    ) -> bool:
        """Send a WhatsApp reminder for an appointment."""
        try:
            # Format appointment time in local timezone
            local_time = reminder.appointment_time.strftime("%I:%M %p")
            
            # Send WhatsApp template reminder
            template_service = WhatsAppTemplateService()
            response = template_service.send_appointment_reminder_template(
                phone_number_id=account.phone_number_id,
                to_number=reminder.contact_phone,
                patient_name=reminder.contact_name,
                appointment_time=local_time,
                calendar_name=reminder.calendar_name
            )
            
            if response and response.get("messages"):
                logger.info(
                    f"Reminder sent successfully",
                    extra={
                        "appointment_id": reminder.appointment_id,
                        "contact_phone": reminder.contact_phone,
                        "message_id": response["messages"][0]["id"]
                    }
                )
                return True
            else:
                logger.error(
                    f"Failed to send reminder",
                    extra={
                        "appointment_id": reminder.appointment_id,
                        "response": response
                    }
                )
                return False
                
        except Exception as e:
            logger.error(
                f"Error sending reminder: {e}",
                extra={"appointment_id": reminder.appointment_id}
            )
            return False
    
    def _reminder_already_sent(self, appointment_id: str) -> bool:
        """Check if a reminder has already been sent for an appointment."""
        doc_ref = self.db.collection("appointment_reminders").document(appointment_id)
        doc = doc_ref.get()
        return doc.exists
    
    def _mark_reminder_sent(self, reminder: AppointmentReminder) -> None:
        """Mark that a reminder has been sent."""
        doc_ref = self.db.collection("appointment_reminders").document(
            reminder.appointment_id
        )
        doc_ref.set({
            "appointment_id": reminder.appointment_id,
            "contact_id": reminder.contact_id,
            "contact_phone": reminder.contact_phone,
            "appointment_time": reminder.appointment_time.isoformat(),
            "sent_at": datetime.now(pytz.UTC).isoformat(),
            "account_id": reminder.account_id,
            "location_id": reminder.location_id,
            "calendar_id": reminder.calendar_id if hasattr(reminder, 'calendar_id') else None
        })
        
        # Also create active reminder context for message handling
        # Normalize phone for consistent storage
        normalized_phone = normalize_phone(reminder.contact_phone)
        
        context_ref = self.db.collection("active_reminder_contexts").document()
        context_data = {
            "phone_number": normalized_phone,  # Store normalized phone
            "appointment_id": reminder.appointment_id,
            "account_id": reminder.account_id,
            "location_id": reminder.location_id,
            "created_at": datetime.now(pytz.UTC).isoformat(),
            "expires_at": (datetime.now(pytz.UTC) + timedelta(hours=24)).isoformat()
        }
        context_ref.set(context_data)
        
        logger.info(
            "Created active reminder context",
            extra={
                "context_id": context_ref.id,
                "phone_number": reminder.contact_phone,
                "normalized_phone": normalized_phone,
                "appointment_id": reminder.appointment_id,
                "expires_at": context_data["expires_at"]
            }
        )
    
    def _store_job_results(self, results: Dict[str, Any]) -> None:
        """Store job execution results in Firestore."""
        doc_ref = self.db.collection("reminder_job_runs").document()
        doc_ref.set(results)