"""GoHighLevel data models."""
from typing import Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class GHLContact:
    """GoHighLevel contact model."""
    id: str
    location_id: str
    name: str
    phone: str
    email: Optional[str] = None
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_api_response(cls, data: dict) -> "GHLContact":
        """Create from API response."""
        return cls(
            id=data["id"],
            location_id=data["locationId"],
            name=data.get("name", ""),
            phone=data.get("phone", ""),
            email=data.get("email"),
            created_at=datetime.fromisoformat(data["dateAdded"].replace("Z", "+00:00")) if data.get("dateAdded") else None
        )


@dataclass
class GHLAppointment:
    """GoHighLevel appointment model."""
    id: str
    calendar_id: str
    location_id: str
    contact_id: str
    assigned_user_id: str
    title: str
    start_time: datetime
    end_time: datetime
    status: str
    
    @classmethod
    def from_api_response(cls, data: dict) -> "GHLAppointment":
        """Create from API response."""
        return cls(
            id=data["id"],
            calendar_id=data["calendarId"],
            location_id=data["locationId"],
            contact_id=data["contactId"],
            assigned_user_id=data["assignedUserId"],
            title=data["title"],
            start_time=datetime.fromisoformat(data["startTime"].replace("Z", "+00:00")),
            end_time=datetime.fromisoformat(data["endTime"].replace("Z", "+00:00")),
            status=data["appointmentStatus"]
        )