from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class Booking:
    """Represents a booking/appointment record for tracking across both platforms"""
    id: str
    doctor_id: str  # WhatsApp bot account ID or directory profile ID
    patient_info: Dict[str, Any]  # name, phone, email, etc.
    appointment_datetime: datetime
    appointment_time: str  # Display format (e.g., "10:00 AM")
    appointment_date: str  # Display format (e.g., "Lunes, 25 de Julio")
    source: str  # "vitalis-whatsapp" or "vitalis-connect"
    status: str  # "pending", "confirmed", "cancelled", "completed", "no-show"
    payment_required: bool
    payment_id: Optional[str] = None
    payment_status: Optional[str] = None  # "pending", "completed", "failed"
    appointment_id: Optional[str] = None  # GHL appointment ID
    calendar_id: Optional[str] = None  # GHL calendar ID
    doctor_name: Optional[str] = None
    location: Optional[str] = None
    specialty: Optional[str] = None
    consultation_price: Optional[int] = None  # in cents
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None  # Additional platform-specific data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert booking to dictionary for Firestore"""
        data = {
            'id': self.id,
            'doctor_id': self.doctor_id,
            'patient_info': self.patient_info,
            'appointment_datetime': self.appointment_datetime,
            'appointment_time': self.appointment_time,
            'appointment_date': self.appointment_date,
            'source': self.source,
            'status': self.status,
            'payment_required': self.payment_required,
            'payment_id': self.payment_id,
            'payment_status': self.payment_status,
            'appointment_id': self.appointment_id,
            'calendar_id': self.calendar_id,
            'doctor_name': self.doctor_name,
            'location': self.location,
            'specialty': self.specialty,
            'consultation_price': self.consultation_price,
            'created_at': self.created_at or datetime.utcnow(),
            'updated_at': self.updated_at or datetime.utcnow(),
            'metadata': self.metadata or {}
        }
        
        # Remove None values
        return {k: v for k, v in data.items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Booking':
        """Create Booking from Firestore document"""
        # Handle datetime conversion
        if isinstance(data.get('appointment_datetime'), str):
            data['appointment_datetime'] = datetime.fromisoformat(data['appointment_datetime'])
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('updated_at'), str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
            
        return cls(**data)