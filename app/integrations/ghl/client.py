"""GoHighLevel API client."""
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.core.exceptions import ExternalServiceError, TokenError
from app.core.logging import get_logger
from app.core.config import get_config
from app.repositories.token_repository import TokenRepository
from app.utils.phone_utils import normalize_phone, format_phone_for_ghl, phones_match

logger = get_logger(__name__)


class GoHighLevelClient:
    """Client for GoHighLevel API."""
    
    def __init__(self):
        self.config = get_config()
        self.base_url = self.config.ghl_api_base_url
        self.token_repository = TokenRepository()
        self.oauth_base_url = "https://services.leadconnectorhq.com"
    
    def _get_headers(self, account_id: str) -> Dict[str, str]:
        """Get headers with valid access token."""
        tokens = self.token_repository.get_tokens(account_id)
        if not tokens:
            raise TokenError("No tokens found for account", account_id=account_id)
        
        # Check if token is expired and refresh if needed
        if self.token_repository.is_token_expired(account_id):
            logger.info(f"Token expired for account {account_id}, refreshing...")
            self.refresh_token(account_id)
            tokens = self.token_repository.get_tokens(account_id)
        
        return {
            "Authorization": f"Bearer {tokens['access_token']}",
            "Content-Type": "application/json",
            "Version": "2021-07-28"
        }
    
    def refresh_token(self, account_id: str) -> Dict[str, Any]:
        """Refresh access token using refresh token."""
        try:
            tokens = self.token_repository.get_tokens(account_id)
            if not tokens or not tokens.get("refresh_token"):
                raise TokenError("No refresh token available", account_id=account_id)
            
            response = requests.post(
                f"{self.oauth_base_url}/oauth/token",
                data={
                    "client_id": self.config.ghl_client_id,
                    "client_secret": self.config.ghl_client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": tokens["refresh_token"]
                }
            )
            
            # Log response details for debugging refresh failures
            if response.status_code != 200:
                logger.error(
                    f"Token refresh failed with status {response.status_code}",
                    extra={
                        "status_code": response.status_code,
                        "response_text": response.text,
                        "response_headers": dict(response.headers),
                        "has_refresh_token": bool(tokens.get("refresh_token")),
                        "refresh_token_preview": tokens.get("refresh_token", "")[:20] + "..." if tokens.get("refresh_token") else None
                    }
                )
            
            response.raise_for_status()
            new_tokens = response.json()
            
            # Check if a new refresh token was provided (token rotation)
            if new_tokens.get("refresh_token"):
                logger.info(f"New refresh token provided for account {account_id}, updating all tokens")
                # Save all tokens including the new refresh token
                self.token_repository.save_tokens(account_id, new_tokens)
            else:
                # Update only the access token
                self.token_repository.update_access_token(
                    account_id,
                    new_tokens["access_token"],
                    new_tokens.get("expires_in", 3600)
                )
            
            logger.info(f"Successfully refreshed token for account {account_id}")
            return new_tokens
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to refresh token: {e}")
            raise ExternalServiceError(
                "GoHighLevel",
                f"Token refresh failed: {str(e)}",
                {"account_id": account_id}
            )
    
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
        """Create or update a contact in GoHighLevel."""
        try:
            # Normalize and format phone for GHL
            normalized_phone = normalize_phone(phone)
            ghl_phone = format_phone_for_ghl(normalized_phone)
            
            # Search for existing contact by phone
            existing_contact = self.search_contact_by_phone(account_id, location_id, ghl_phone)
            
            if existing_contact:
                logger.info(f"Contact already exists with ID: {existing_contact['id']}")
                return existing_contact
            
            # Create new contact
            headers = self._get_headers(account_id)
            
            # Use the already formatted phone for GHL
            contact_data = {
                "locationId": location_id,
                "name": name,
                "phone": ghl_phone,
                "source": source
            }
            
            if email:
                contact_data["email"] = email
            
            # Add custom fields like working version
            if reason:
                contact_data["customFields"] = [
                    {"key": "reason_of_appointment", "value": reason}
                ]
            
            logger.info(f"Creating GHL contact with data: {contact_data}")
            
            response = requests.post(
                f"{self.base_url}/contacts/",
                headers=headers,
                json=contact_data
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"GHL contact creation failed. Status: {response.status_code}, Response: {response.text}")
                
                # Check if it's a duplicate contact error
                if response.status_code == 400:
                    try:
                        error_data = response.json()
                        if "duplicated contacts" in error_data.get("message", ""):
                            # Extract existing contact ID from error response
                            existing_contact_id = error_data.get("meta", {}).get("contactId")
                            if existing_contact_id:
                                logger.info(f"Found existing contact ID from error response: {existing_contact_id}")
                                # Return a minimal contact object with the ID
                                return {"id": existing_contact_id, "name": name, "phone": phone}
                    except:
                        pass
            
            response.raise_for_status()
            contact = response.json()["contact"]
            
            logger.info(
                "Created contact in GoHighLevel",
                extra={
                    "contact_id": contact["id"],
                    "contact_name": name,
                    "contact_phone": phone
                }
            )
            
            return contact
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create contact: {e}")
            raise ExternalServiceError(
                "GoHighLevel",
                f"Contact creation failed: {str(e)}",
                {"contact_name": name, "contact_phone": phone}
            )
    
    def update_contact(
        self,
        account_id: str,
        contact_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing contact in GoHighLevel."""
        try:
            headers = self._get_headers(account_id)
            
            # Build update data with only provided fields
            update_data = {}
            if name:
                update_data["name"] = name
            if email:
                update_data["email"] = email
            
            # Add reason to custom fields or tags if provided
            if reason:
                update_data["tags"] = [reason]
            
            response = requests.put(
                f"{self.base_url}/contacts/{contact_id}",
                headers=headers,
                json=update_data
            )
            
            response.raise_for_status()
            contact = response.json()["contact"]
            
            logger.info(
                "Updated contact in GHL",
                extra={
                    "contact_id": contact_id,
                    "updated_fields": list(update_data.keys())
                }
            )
            
            return contact
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update contact: {e}")
            raise ExternalServiceError(
                "GoHighLevel",
                f"Contact update failed: {str(e)}",
                {"contact_id": contact_id}
            )
    
    def search_contact_by_phone(
        self,
        account_id: str,
        location_id: str,
        phone: str
    ) -> Optional[Dict[str, Any]]:
        """Search for a contact by phone number."""
        try:
            headers = self._get_headers(account_id)
            
            response = requests.get(
                f"{self.base_url}/contacts/",
                headers=headers,
                params={
                    "locationId": location_id,
                    "query": phone
                }
            )
            
            response.raise_for_status()
            contacts = response.json()["contacts"]
            
            # Find phone match using normalization
            for contact in contacts:
                if phones_match(contact.get("phone"), phone):
                    return contact
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to search contact: {e}")
            return None
    
    def get_contact(self, account_id: str, contact_id: str) -> Optional[Dict[str, Any]]:
        """Get a contact by ID from GoHighLevel."""
        try:
            headers = self._get_headers(account_id)
            
            response = requests.get(
                f"{self.base_url}/contacts/{contact_id}",
                headers=headers
            )
            
            response.raise_for_status()
            contact = response.json().get("contact", response.json())
            
            logger.info(
                "Retrieved contact from GoHighLevel",
                extra={
                    "contact_id": contact_id,
                    "contact_name": contact.get("name") or contact.get("firstName"),
                    "contact_phone": contact.get("phone") or contact.get("phoneNumber")
                }
            )
            
            return contact
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get contact {contact_id}: {e}")
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
        """Create an appointment in GoHighLevel."""
        try:
            headers = self._get_headers(account_id)
            
            appointment_data = {
                "calendarId": calendar_id,
                "locationId": location_id,
                "contactId": contact_id,
                "startTime": start_time,
                "endTime": end_time,
                "title": title,
                "appointmentStatus": appointment_status,
                "assignedUserId": assigned_user_id,
                "ignoreFreeSlotValidation": False  # Respect calendar availability
            }
            
            logger.info(f"Creating GHL appointment with data: {appointment_data}")
            
            response = requests.post(
                f"{self.base_url}/calendars/events/appointments",  # Use working version URL
                headers=headers,
                json=appointment_data
            )
            
            if not response.ok:  # Checks for any 2xx status code
                logger.error(f"GHL appointment creation failed. Status: {response.status_code}, Response: {response.text}")
            else:
                logger.info(f"GHL appointment creation successful. Status: {response.status_code}, Response: {response.text}")
            
            response.raise_for_status()
            appointment = response.json()
            
            logger.info(
                "Created appointment in GoHighLevel",
                extra={
                    "appointment_id": appointment.get("id"),
                    "contact_id": contact_id,
                    "start_time": start_time
                }
            )
            
            return appointment
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create appointment: {e}")
            raise ExternalServiceError(
                "GoHighLevel",
                f"Appointment creation failed: {str(e)}",
                {
                    "contact_id": contact_id,
                    "start_time": start_time
                }
            )
    
    def get_calendar_events(
        self,
        account_id: str,
        location_id: str,
        start_date: int,
        end_date: int
    ) -> Dict[str, Any]:
        """Get calendar events for a date range."""
        try:
            headers = self._get_headers(account_id)
            
            params = {
                "locationId": location_id,
                "startTime": start_date,
                "endTime": end_date
            }
            
            response = requests.get(
                f"{self.base_url}/calendars/events",
                headers=headers,
                params=params
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Failed to get calendar events: {e}",
                extra={
                    "account_id": account_id,
                    "location_id": location_id
                }
            )
            raise ExternalServiceError("GoHighLevel", f"Failed to get calendar events: {str(e)}")
    
    def get_free_slots(
        self,
        account_id: str,
        calendar_id: str,
        start_date: int,
        end_date: int,
        timezone: str = "America/Mexico_City",
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get free slots for a calendar between a date range."""
        try:
            headers = self._get_headers(account_id)
            
            params = {
                "startDate": start_date,
                "endDate": end_date,
                "timezone": timezone,
                "enableLookBusy": False
            }
            
            if user_id:
                params["userId"] = user_id
            
            response = requests.get(
                f"{self.base_url}/calendars/{calendar_id}/free-slots",
                headers=headers,
                params=params
            )
            
            response.raise_for_status()
            slots_data = response.json()
            
            # Parse the GHL free slots response format: {"date": {"slots": ["time1", "time2"]}}
            all_slots = []
            total_slot_count = 0
            
            for date_key, date_data in slots_data.items():
                if isinstance(date_data, dict) and "slots" in date_data:
                    date_slots = date_data["slots"]
                    total_slot_count += len(date_slots)
                    
                    # Convert each slot to a full datetime string
                    for time_slot in date_slots:
                        # Check if time_slot is already a full datetime or just time
                        if "T" in time_slot:
                            # Already a full datetime, use as-is
                            datetime_str = time_slot
                            # Extract just the time part for comparison
                            time_part = time_slot.split("T")[1].split(":")[0] + ":" + time_slot.split("T")[1].split(":")[1]
                        else:
                            # Just a time, combine with date
                            datetime_str = f"{date_key}T{time_slot}:00"
                            time_part = time_slot
                        
                        all_slots.append({
                            "date": date_key,
                            "time": time_part,
                            "datetime": datetime_str
                        })
            
            logger.info(
                "Retrieved free slots from GoHighLevel",
                extra={
                    "calendar_id": calendar_id,
                    "slot_count": total_slot_count,
                    "date_range": f"{start_date} to {end_date}",
                    "dates_with_slots": list(slots_data.keys())
                }
            )
            
            return all_slots
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get free slots: {e}")
            raise ExternalServiceError(
                "GoHighLevel",
                f"Failed to get free slots: {str(e)}",
                {"calendar_id": calendar_id}
            )
    
    def get_appointment(
        self,
        account_id: str,
        appointment_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get appointment details from GoHighLevel."""
        try:
            headers = self._get_headers(account_id)
            
            response = requests.get(
                f"{self.base_url}/calendars/events/appointments/{appointment_id}",
                headers=headers
            )
            
            if response.status_code == 404:
                logger.warning(f"Appointment {appointment_id} not found")
                return None
            
            response.raise_for_status()
            appointment = response.json()
            
            logger.info(
                "Retrieved appointment from GoHighLevel",
                extra={
                    "appointment_id": appointment_id,
                    "status": appointment.get("status")
                }
            )
            
            return appointment
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get appointment: {e}")
            return None
    
    def update_appointment(
        self,
        account_id: str,
        appointment_id: str,
        start_time: str,
        end_time: str,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update/reschedule an appointment in GoHighLevel."""
        try:
            headers = self._get_headers(account_id)
            
            update_data = {
                "startTime": start_time,
                "endTime": end_time
            }
            
            if title:
                update_data["title"] = title
            
            logger.info(f"Updating GHL appointment {appointment_id} with data: {update_data}")
            
            response = requests.put(
                f"{self.base_url}/calendars/events/appointments/{appointment_id}",
                headers=headers,
                json=update_data
            )
            
            if response.status_code != 200:
                logger.error(f"GHL appointment update failed. Status: {response.status_code}, Response: {response.text}")
            
            response.raise_for_status()
            appointment = response.json()
            
            logger.info(
                "Updated appointment in GoHighLevel",
                extra={
                    "appointment_id": appointment_id,
                    "new_start_time": start_time
                }
            )
            
            return appointment
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update appointment: {e}")
            raise ExternalServiceError(
                "GoHighLevel",
                f"Appointment update failed: {str(e)}",
                {"appointment_id": appointment_id}
            )
    
    def cancel_appointment(
        self,
        account_id: str,
        appointment_id: str
    ) -> bool:
        """Cancel an appointment in GoHighLevel."""
        try:
            headers = self._get_headers(account_id)
            
            # Update appointment status to cancelled
            update_data = {
                "appointmentStatus": "cancelled"
            }
            
            logger.info(f"Cancelling GHL appointment {appointment_id}")
            
            response = requests.put(
                f"{self.base_url}/calendars/events/appointments/{appointment_id}",
                headers=headers,
                json=update_data
            )
            
            if response.status_code != 200:
                logger.error(f"GHL appointment cancellation failed. Status: {response.status_code}, Response: {response.text}")
                return False
            
            response.raise_for_status()
            
            logger.info(
                "Cancelled appointment in GoHighLevel",
                extra={"appointment_id": appointment_id}
            )
            
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to cancel appointment: {e}")
            return False
    
    def get_blocked_slots(
        self,
        account_id: str,
        calendar_id: str,
        start_time: int,
        end_time: int,
        location_id: str,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get blocked slots for a calendar between a date range."""
        try:
            headers = self._get_headers(account_id)
            headers["Version"] = "2021-04-15"  # Required API version for blocked slots
            
            # Try appointments endpoint first
            events_params = {
                "startTime": start_time,
                "endTime": end_time,
                "locationId": location_id,
                "calendarId": calendar_id
            }
            
            # Log the request for debugging
            events_url = f"{self.base_url}/calendars/events/appointments"
            logger.info(f"[DEBUG] Trying appointments endpoint: {events_url}")
            logger.info(f"[DEBUG] With params: {events_params}")
            
            try:
                response = requests.get(
                    events_url,
                    headers=headers,
                    params=events_params
                )
                response.raise_for_status()
                appointments_data = response.json()
                logger.info(f"[DEBUG] Appointments response: {appointments_data}")
                
                # If we got appointments, return them
                if appointments_data and "appointments" in appointments_data:
                    return appointments_data["appointments"]
            except Exception as e:
                logger.warning(f"Appointments endpoint failed, trying blocked-slots: {e}")
            
            # Fallback to blocked-slots endpoint
            # Only pass calendarId OR userId, not both
            params = {
                "startTime": start_time,
                "endTime": end_time,
                "locationId": location_id
            }
            
            # Prefer calendar_id if available, otherwise use user_id
            if calendar_id:
                params["calendarId"] = calendar_id
            elif user_id:
                params["userId"] = user_id
            else:
                raise ValueError("Either calendar_id or user_id must be provided")
            
            # Log the request for debugging
            url = f"{self.base_url}/calendars/blocked-slots"
            logger.info(f"[DEBUG] Requesting blocked slots from: {url}")
            logger.info(f"[DEBUG] With params: {params}")
            
            response = requests.get(
                url,
                headers=headers,
                params=params
            )
            
            response.raise_for_status()
            blocked_data = response.json()
            
            # Log raw response for debugging
            logger.info(f"[DEBUG] Raw blocked slots response: {blocked_data}")
            
            # Extract events from response
            events = blocked_data.get("events", [])
            
            # Log each event for debugging
            for i, event in enumerate(events):
                logger.info(f"[DEBUG] Blocked slot {i}: startTime={event.get('startTime')}, endTime={event.get('endTime')}, title={event.get('title')}, status={event.get('appointmentStatus')}")
            
            logger.info(
                "Retrieved blocked slots from GoHighLevel",
                extra={
                    "calendar_id": calendar_id,
                    "blocked_count": len(events),
                    "date_range": f"{start_time} to {end_time}",
                    "location_id": location_id,
                    "user_id": user_id
                }
            )
            
            return events
            
        except requests.exceptions.RequestException as e:
            # Log more details about the error
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Failed to get blocked slots: {e}")
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            else:
                logger.error(f"Failed to get blocked slots: {e}")
            # Return empty list on error to allow graceful degradation
            return []