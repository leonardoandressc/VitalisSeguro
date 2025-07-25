"""Appointment domain model."""
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class AppointmentInfo:
    """Information extracted for an appointment."""
    name: str
    reason: str
    datetime_str: str
    phone_number: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    raw_datetime: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "reason": self.reason,
            "datetime": self.datetime_str,
            "phone_number": self.phone_number,
            "email": self.email,
            "notes": self.notes,
            "raw_datetime": self.raw_datetime
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppointmentInfo":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            reason=data["reason"],
            datetime_str=data.get("datetime", data.get("datetime_str", "")),
            phone_number=data.get("phone_number"),
            email=data.get("email"),
            notes=data.get("notes"),
            raw_datetime=data.get("raw_datetime")
        )
    
    def format_for_confirmation(self) -> str:
        """Format appointment info for user confirmation."""
        lines = [
            f"📋 *Datos de la cita:*",
            f"👤 Nombre: {self.name}",
            f"📝 Motivo: {self.reason}",
            f"📅 Fecha y hora: {self.datetime_str}"
        ]
        
        if self.phone_number:
            lines.append(f"📱 Teléfono: {self.phone_number}")
        
        if self.email:
            lines.append(f"✉️ Email: {self.email}")
        
        if self.notes:
            lines.append(f"📌 Notas: {self.notes}")
        
        return "\n".join(lines)


@dataclass
class GHLAppointmentResponse:
    """Response from GoHighLevel appointment creation."""
    appointment_id: str
    contact_id: str
    calendar_id: str
    status: str
    start_time: datetime
    end_time: datetime
    created_at: datetime
    
    @classmethod
    def from_ghl_response(cls, data: Dict[str, Any]) -> "GHLAppointmentResponse":
        """Create from GHL API response."""
        return cls(
            appointment_id=data["id"],
            contact_id=data["contactId"],
            calendar_id=data["calendarId"],
            status=data["status"],
            start_time=datetime.fromisoformat(data["startTime"].replace("Z", "+00:00")),
            end_time=datetime.fromisoformat(data["endTime"].replace("Z", "+00:00")),
            created_at=datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
        )