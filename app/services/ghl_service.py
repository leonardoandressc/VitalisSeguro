"""GoHighLevel service for appointments and contacts."""
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.integrations.ghl.client import GoHighLevelClient
from app.core.logging import get_logger
from app.core.exceptions import ExternalServiceError

logger = get_logger(__name__)


class GHLService:
    """Service for GoHighLevel operations."""
    
    def __init__(self):
        """Initialize GHL service."""
        self.client = GoHighLevelClient()
        # Import here to avoid circular dependencies
        from app.services.account_service import AccountService
        self.account_service = AccountService()
    
    def get_appointments(
        self,
        account_id: str,
        calendar_id: str,
        start_date: datetime,
        end_date: datetime,
        location_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get appointments from GoHighLevel for a date range.
        
        Args:
            account_id: Account ID for auth
            calendar_id: Calendar ID to fetch appointments from
            start_date: Start date for appointment search
            end_date: End date for appointment search
            location_id: Optional location ID filter
            
        Returns:
            Dictionary with appointments list
        """
        try:
            headers = self.client._get_headers(account_id)
            
            # Format dates for API
            start_str = start_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            end_str = end_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            
            params = {
                "calendarId": calendar_id,
                "startTime": int(start_date.timestamp() * 1000),  # Convert to milliseconds
                "endTime": int(end_date.timestamp() * 1000)
            }
            
            # locationId is required by the API
            if location_id:
                params["locationId"] = location_id
            else:
                logger.error("No location_id provided for appointment query")
                return {"appointments": []}
            
            logger.info(
                "Fetching appointments from GoHighLevel",
                extra={
                    "calendar_id": calendar_id,
                    "start_date": start_str,
                    "end_date": end_str
                }
            )
            
            # Log the exact query parameters
            logger.info(
                "Querying GHL appointments API",
                extra={
                    "params": params,
                    "start_timestamp": params["startTime"],
                    "end_timestamp": params["endTime"],
                    "calendar_id": calendar_id
                }
            )
            
            # Using the calendars events endpoint
            response = requests.get(
                f"{self.client.base_url}/calendars/events",
                headers=headers,
                params=params
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Log raw response for debugging
            events = data.get("events", [])
            logger.info(
                "GHL appointments API response",
                extra={
                    "response_keys": list(data.keys()) if isinstance(data, dict) else "not a dict",
                    "events_count": len(events),
                    "first_event": events[0] if events else "No events"
                }
            )
            
            # Filter for appointments only (not other event types)
            # The API returns events array with appointmentStatus field
            appointments = [
                event for event in events
                if event.get("appointmentStatus") is not None  # Has appointmentStatus = it's an appointment
            ]
            
            logger.info(
                f"Retrieved {len(appointments)} appointments",
                extra={
                    "calendar_id": calendar_id,
                    "date_range": f"{start_str} to {end_str}",
                    "appointments": [
                        {
                            "id": apt.get("id"),
                            "title": apt.get("title"),
                            "startTime": apt.get("startTime"),
                            "appointmentStatus": apt.get("appointmentStatus"),
                            "contactId": apt.get("contactId")
                        }
                        for apt in appointments[:5]  # Log first 5 appointments
                    ] if appointments else "No appointments found"
                }
            )
            
            # Return the raw events for now, we'll filter in the reminder service
            return {"events": events}
            
        except Exception as e:
            logger.error(
                f"Failed to get appointments: {e}",
                extra={
                    "calendar_id": calendar_id,
                    "error": str(e)
                }
            )
            # Return empty list on error to allow reminder job to continue
            return {"appointments": []}
    
    def create_contact(
        self,
        account_id: str,
        location_id: str,
        name: str,
        phone: str,
        email: Optional[str] = None,
        reason: Optional[str] = None,
        source: str = "WhatsApp Bot"
    ) -> Dict[str, Any]:
        """Create or update a contact in GoHighLevel.
        
        Args:
            account_id: Account ID for auth
            location_id: Location ID for the contact
            name: Contact name
            phone: Contact phone number
            email: Optional email address
            reason: Optional reason for appointment
            source: Source of the contact
            
        Returns:
            Created/found contact data
        """
        return self.client.create_contact(
            account_id=account_id,
            location_id=location_id,
            name=name,
            phone=phone,
            email=email,
            reason=reason,
            source=source
        )
    
    def get_contact(self, account_id: str, contact_id: str) -> Optional[Dict[str, Any]]:
        """Get contact details from GoHighLevel.
        
        Args:
            account_id: Account ID for auth
            contact_id: Contact ID
            
        Returns:
            Contact data or None if not found
        """
        try:
            contact = self.client.get_contact(account_id, contact_id)
            return contact
        except Exception as e:
            logger.error(
                f"Failed to get contact {contact_id}: {e}",
                extra={"contact_id": contact_id}
            )
            return None
    
    def create_appointment(
        self,
        account_id: str,
        calendar_id: str,
        location_id: str,
        contact_id: str,
        assigned_user_id: str,
        start_time: str,
        end_time: str,
        title: str,
        appointment_status: str = "confirmed"
    ) -> Dict[str, Any]:
        """Create an appointment in GoHighLevel.
        
        Args:
            account_id: Account ID for auth
            calendar_id: Calendar ID
            location_id: Location ID
            contact_id: Contact ID
            assigned_user_id: Assigned user ID
            start_time: Appointment start time
            end_time: Appointment end time
            title: Appointment title
            appointment_status: Status of the appointment
            
        Returns:
            Created appointment data
        """
        return self.client.create_appointment(
            account_id=account_id,
            calendar_id=calendar_id,
            location_id=location_id,
            contact_id=contact_id,
            assigned_user_id=assigned_user_id,
            start_time=start_time,
            end_time=end_time,
            title=title,
            appointment_status=appointment_status
        )
    
    def get_calendar_events(
        self,
        account_id: str,
        start_date: datetime,
        end_date: datetime,
        location_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get calendar events for a date range.
        
        Args:
            account_id: Account ID for auth
            start_date: Start date
            end_date: End date
            location_id: Optional location ID to filter by
            
        Returns:
            Dictionary containing events list
        """
        try:
            # Convert dates to timestamps
            start_timestamp = int(start_date.timestamp() * 1000)
            end_timestamp = int(end_date.timestamp() * 1000)
            
            # Get location ID from account if not provided
            if not location_id:
                account = self.account_service.get_account(account_id)
                if account:
                    location_id = account.location_id
            
            # Use GHL client to get calendar events
            return self.client.get_calendar_events(
                account_id=account_id,
                location_id=location_id,
                start_date=start_timestamp,
                end_date=end_timestamp
            )
        except Exception as e:
            logger.error(f"Failed to get calendar events: {e}")
            return {}
    
    def get_free_slots(
        self,
        account_id: str,
        calendar_id: str,
        start_date: int,
        end_date: int,
        timezone: str = "America/Mexico_City",
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get free slots for a calendar.
        
        Args:
            account_id: Account ID for auth
            calendar_id: Calendar ID
            start_date: Start date timestamp
            end_date: End date timestamp  
            timezone: Timezone for slots
            user_id: Optional user ID filter
            
        Returns:
            List of available time slots
        """
        return self.client.get_free_slots(
            account_id=account_id,
            calendar_id=calendar_id,
            start_date=start_date,
            end_date=end_date,
            timezone=timezone,
            user_id=user_id
        )
    
    def get_appointment(
        self,
        account_id: str,
        appointment_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get appointment details from GoHighLevel.
        
        Args:
            account_id: Account ID for auth
            appointment_id: Appointment ID to retrieve
            
        Returns:
            Appointment data or None if not found
        """
        return self.client.get_appointment(
            account_id=account_id,
            appointment_id=appointment_id
        )
    
    def update_appointment(
        self,
        account_id: str,
        appointment_id: str,
        start_time: str,
        end_time: str,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update/reschedule an appointment in GoHighLevel.
        
        Args:
            account_id: Account ID for auth
            appointment_id: Appointment ID to update
            start_time: New start time
            end_time: New end time
            title: Optional new title
            
        Returns:
            Updated appointment data
        """
        return self.client.update_appointment(
            account_id=account_id,
            appointment_id=appointment_id,
            start_time=start_time,
            end_time=end_time,
            title=title
        )
    
    def cancel_appointment(
        self,
        account_id: str,
        appointment_id: str
    ) -> bool:
        """Cancel an appointment in GoHighLevel.
        
        Args:
            account_id: Account ID for auth
            appointment_id: Appointment ID to cancel
            
        Returns:
            True if successfully cancelled
        """
        return self.client.cancel_appointment(
            account_id=account_id,
            appointment_id=appointment_id
        )