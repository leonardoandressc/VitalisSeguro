from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

from app.models.booking import Booking
from app.core.logging import get_logger
from app.utils.firebase import get_firestore_client

logger = get_logger(__name__)


class BookingService:
    """Service for managing bookings across both WhatsApp and Vitalis Connect platforms"""
    
    def __init__(self):
        self.db = get_firestore_client()
        self.bookings_collection = self.db.collection('bookings')
    
    def create_booking(
        self,
        doctor_id: str,
        patient_info: Dict[str, Any],
        appointment_datetime: datetime,
        appointment_time: str,
        appointment_date: str,
        source: str,
        payment_required: bool,
        calendar_id: Optional[str] = None,
        doctor_name: Optional[str] = None,
        location: Optional[str] = None,
        specialty: Optional[str] = None,
        consultation_price: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Booking:
        """Create a new booking record"""
        booking_id = str(uuid.uuid4())
        
        booking = Booking(
            id=booking_id,
            doctor_id=doctor_id,
            patient_info=patient_info,
            appointment_datetime=appointment_datetime,
            appointment_time=appointment_time,
            appointment_date=appointment_date,
            source=source,
            status="pending",
            payment_required=payment_required,
            payment_status="pending" if payment_required else None,
            calendar_id=calendar_id,
            doctor_name=doctor_name,
            location=location,
            specialty=specialty,
            consultation_price=consultation_price,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata=metadata
        )
        
        try:
            # Save to Firestore
            self.bookings_collection.document(booking_id).set(booking.to_dict())
            logger.info(f"Created booking {booking_id} from source: {source}")
            return booking
        except Exception as e:
            logger.error(f"Error creating booking: {str(e)}")
            raise
    
    def update_booking(
        self,
        booking_id: str,
        status: Optional[str] = None,
        payment_id: Optional[str] = None,
        payment_status: Optional[str] = None,
        appointment_id: Optional[str] = None,
        **kwargs
    ) -> bool:
        """Update booking record"""
        try:
            update_data = {
                'updated_at': datetime.utcnow()
            }
            
            if status:
                update_data['status'] = status
            if payment_id:
                update_data['payment_id'] = payment_id
            if payment_status:
                update_data['payment_status'] = payment_status
            if appointment_id:
                update_data['appointment_id'] = appointment_id
                
            # Add any additional fields from kwargs
            update_data.update(kwargs)
            
            self.bookings_collection.document(booking_id).update(update_data)
            logger.info(f"Updated booking {booking_id}: {update_data}")
            return True
        except Exception as e:
            logger.error(f"Error updating booking {booking_id}: {str(e)}")
            return False
    
    def get_booking(self, booking_id: str) -> Optional[Booking]:
        """Get booking by ID"""
        try:
            doc = self.bookings_collection.document(booking_id).get()
            if doc.exists:
                return Booking.from_dict(doc.to_dict())
            return None
        except Exception as e:
            logger.error(f"Error getting booking {booking_id}: {str(e)}")
            return None
    
    def get_bookings_by_phone(self, phone: str, limit: int = 10) -> List[Booking]:
        """Get bookings by patient phone number"""
        try:
            query = (self.bookings_collection
                    .where('patient_info.phone', '==', phone)
                    .order_by('created_at', direction=firestore.Query.DESCENDING)
                    .limit(limit))
            
            bookings = []
            for doc in query.stream():
                bookings.append(Booking.from_dict(doc.to_dict()))
            
            return bookings
        except Exception as e:
            logger.error(f"Error getting bookings for phone {phone}: {str(e)}")
            return []
    
    def get_bookings_by_doctor(
        self,
        doctor_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        source: Optional[str] = None
    ) -> List[Booking]:
        """Get bookings by doctor with optional filters"""
        try:
            query = self.bookings_collection.where('doctor_id', '==', doctor_id)
            
            if source:
                query = query.where('source', '==', source)
            
            if start_date:
                query = query.where('appointment_datetime', '>=', start_date)
            
            if end_date:
                query = query.where('appointment_datetime', '<=', end_date)
            
            query = query.order_by('appointment_datetime')
            
            bookings = []
            for doc in query.stream():
                bookings.append(Booking.from_dict(doc.to_dict()))
            
            return bookings
        except Exception as e:
            logger.error(f"Error getting bookings for doctor {doctor_id}: {str(e)}")
            return []
    
    def cancel_booking(self, booking_id: str, reason: Optional[str] = None) -> bool:
        """Cancel a booking"""
        metadata = {'cancellation_reason': reason} if reason else {}
        return self.update_booking(
            booking_id,
            status='cancelled',
            **({'metadata': metadata} if metadata else {})
        )
    
    def complete_booking(self, booking_id: str) -> bool:
        """Mark booking as completed"""
        return self.update_booking(booking_id, status='completed')
    
    def mark_no_show(self, booking_id: str) -> bool:
        """Mark booking as no-show"""
        return self.update_booking(booking_id, status='no-show')
    
    def link_payment_to_booking(self, booking_id: str, payment_id: str, payment_status: str) -> bool:
        """Link a payment to a booking"""
        return self.update_booking(
            booking_id,
            payment_id=payment_id,
            payment_status=payment_status
        )
    
    def link_appointment_to_booking(self, booking_id: str, appointment_id: str) -> bool:
        """Link a GHL appointment to a booking"""
        return self.update_booking(
            booking_id,
            appointment_id=appointment_id,
            status='confirmed'
        )