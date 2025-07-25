"""Repository for analytics data aggregation."""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter, aggregation

from app.core.logging import get_logger
from app.core.exceptions import VitalisException
from app.utils.firebase import get_firestore_client

logger = get_logger(__name__)


class AnalyticsRepository:
    """Repository for aggregating analytics data from multiple collections."""
    
    def __init__(self):
        self.db = get_firestore_client()
        
    def get_payments_by_period(
        self,
        location_id: str,
        start_date: datetime,
        end_date: datetime,
        source: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get payments within a date range, optionally filtered by source."""
        try:
            # First get the account ID for this location
            account_ref = self.db.collection('accounts').where('location_id', '==', location_id).limit(1).get()
            if not account_ref:
                return []
            
            account_id = account_ref[0].id
            
            # Query payments
            query = self.db.collection('payments').where('account_id', '==', account_id)
            
            # Add date filters
            query = query.where('created_at', '>=', start_date.isoformat())
            query = query.where('created_at', '<=', end_date.isoformat())
            
            # Add source filter if specified
            if source:
                query = query.where('source', '==', source)
            
            # Execute query
            payments = []
            for doc in query.stream():
                payment_data = doc.to_dict()
                payment_data['id'] = doc.id
                payments.append(payment_data)
            
            return payments
            
        except Exception as e:
            logger.error(f"Error getting payments by period: {e}")
            return []
    
    def get_bookings_by_period(
        self,
        location_id: str,
        start_date: datetime,
        end_date: datetime,
        source: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get bookings within a date range, optionally filtered by source."""
        try:
            # Get account ID for location
            account_ref = self.db.collection('accounts').where('location_id', '==', location_id).limit(1).get()
            if not account_ref:
                return []
            
            account = account_ref[0].to_dict()
            account_id = account_ref[0].id
            
            # Query bookings - need to handle both WhatsApp (doctor_id = account_id) 
            # and Connect (doctor_id = directory_profile_id)
            bookings = []
            
            # Get WhatsApp bookings (doctor_id = account_id)
            query = self.db.collection('bookings').where('doctor_id', '==', account_id)
            query = query.where('created_at', '>=', start_date.isoformat())
            query = query.where('created_at', '<=', end_date.isoformat())
            
            if source:
                query = query.where('source', '==', source)
            
            for doc in query.stream():
                booking_data = doc.to_dict()
                booking_data['id'] = doc.id
                bookings.append(booking_data)
            
            # Get Connect bookings (through directory profiles)
            if not source or source == 'vitalis-connect':
                # Get directory profiles for this account
                profiles = self.db.collection('directory_profiles').where('account_id', '==', account_id).stream()
                profile_ids = [prof.id for prof in profiles]
                
                # Query bookings for these profiles
                for profile_id in profile_ids:
                    query = self.db.collection('bookings').where('doctor_id', '==', profile_id)
                    query = query.where('created_at', '>=', start_date.isoformat())
                    query = query.where('created_at', '<=', end_date.isoformat())
                    
                    if source:
                        query = query.where('source', '==', source)
                    
                    for doc in query.stream():
                        booking_data = doc.to_dict()
                        booking_data['id'] = doc.id
                        bookings.append(booking_data)
            
            return bookings
            
        except Exception as e:
            logger.error(f"Error getting bookings by period: {e}")
            return []
    
    def get_reminder_stats(
        self,
        location_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get reminder statistics for a period."""
        try:
            # Get account ID
            account_ref = self.db.collection('accounts').where('location_id', '==', location_id).limit(1).get()
            if not account_ref:
                return {}
            
            account_id = account_ref[0].id
            
            # Query reminders
            query = self.db.collection('appointment_reminders')
            query = query.where('account_id', '==', account_id)
            query = query.where('sent_at', '>=', start_date.isoformat())
            query = query.where('sent_at', '<=', end_date.isoformat())
            
            reminders = []
            for doc in query.stream():
                reminder_data = doc.to_dict()
                reminder_data['id'] = doc.id
                reminders.append(reminder_data)
            
            # Calculate statistics
            total_sent = len(reminders)
            total_responses = sum(1 for r in reminders if r.get('response_received'))
            total_confirmations = sum(1 for r in reminders if r.get('response_type') == 'confirm')
            total_cancellations = sum(1 for r in reminders if r.get('response_type') == 'cancel')
            
            # Calculate response times
            response_times = []
            for reminder in reminders:
                if reminder.get('response_received') and reminder.get('response_time'):
                    sent_at = reminder.get('sent_at')
                    response_time = reminder.get('response_time')
                    if isinstance(sent_at, datetime) and isinstance(response_time, datetime):
                        diff = (response_time - sent_at).total_seconds() / 60  # Minutes
                        response_times.append(diff)
            
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            return {
                'total_sent': total_sent,
                'total_responses': total_responses,
                'total_confirmations': total_confirmations,
                'total_cancellations': total_cancellations,
                'response_times': response_times,
                'avg_response_time': avg_response_time,
                'reminders': reminders
            }
            
        except Exception as e:
            logger.error(f"Error getting reminder stats: {e}")
            return {}
    
    def get_directory_analytics(
        self,
        location_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get directory analytics events."""
        try:
            # Query directory analytics
            query = self.db.collection('directory_analytics')
            query = query.where('timestamp', '>=', start_date.isoformat())
            query = query.where('timestamp', '<=', end_date.isoformat())
            
            # Get account to filter by its directory profiles
            account_ref = self.db.collection('accounts').where('location_id', '==', location_id).limit(1).get()
            if not account_ref:
                return []
            
            account_id = account_ref[0].id
            
            # Get directory profiles for this account
            profiles = self.db.collection('directory_profiles').where('account_id', '==', account_id).stream()
            profile_ids = [prof.id for prof in profiles]
            
            # Filter analytics by profile IDs
            events = []
            for doc in query.stream():
                event_data = doc.to_dict()
                # Check if event is related to one of our profiles
                if event_data.get('data', {}).get('profileId') in profile_ids:
                    event_data['id'] = doc.id
                    events.append(event_data)
            
            return events
            
        except Exception as e:
            logger.error(f"Error getting directory analytics: {e}")
            return []
    
    def get_conversations_count(
        self,
        location_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> int:
        """Get count of conversations for a period."""
        try:
            # Get account ID
            account_ref = self.db.collection('accounts').where('location_id', '==', location_id).limit(1).get()
            if not account_ref:
                return 0
            
            account_id = account_ref[0].id
            
            # Count conversations
            query = self.db.collection('conversations')
            query = query.where('account_id', '==', account_id)
            query = query.where('created_at', '>=', start_date.isoformat())
            query = query.where('created_at', '<=', end_date.isoformat())
            
            # Count using aggregation query
            count_query = query.count()
            result = count_query.get()
            
            # The result is a list of aggregation results
            if result and len(result) > 0:
                return result[0][0].value
            
            return 0
            
        except Exception as e:
            logger.error(f"Error counting conversations: {e}")
            # Fallback to manual count
            try:
                query = self.db.collection('conversations')
                query = query.where('account_id', '==', account_id)
                query = query.where('created_at', '>=', start_date.isoformat())
                query = query.where('created_at', '<=', end_date.isoformat())
                
                count = 0
                for _ in query.stream():
                    count += 1
                
                return count
            except:
                return 0
    
    def get_conversations_by_period(
        self,
        location_id: str,
        start_date: datetime,
        end_date: datetime,
        source: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get conversations within a date range."""
        try:
            # Get account ID for location
            account_ref = self.db.collection('accounts').where('location_id', '==', location_id).limit(1).get()
            if not account_ref:
                return []
            
            account_id = account_ref[0].id
            
            # Query conversations
            query = self.db.collection('conversations').where('account_id', '==', account_id)
            query = query.where('created_at', '>=', start_date.isoformat())
            query = query.where('created_at', '<=', end_date.isoformat())
            
            conversations = []
            for doc in query.stream():
                conv_data = doc.to_dict()
                conv_data['id'] = doc.id
                
                # Filter by source if specified (WhatsApp conversations only for now)
                if not source or source == 'vitalis-whatsapp':
                    conversations.append(conv_data)
            
            return conversations
            
        except Exception as e:
            logger.error(f"Error getting conversations by period: {e}")
            return []
    
    def get_appointment_reminders_by_period(
        self,
        location_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get appointment reminders within a date range."""
        try:
            # Get account ID for location
            account_ref = self.db.collection('accounts').where('location_id', '==', location_id).limit(1).get()
            if not account_ref:
                logger.warning(f"No account found for location_id: {location_id}")
                return []
            
            account_id = account_ref[0].id
            
            logger.info(
                "Querying appointment reminders",
                extra={
                    "account_id": account_id,
                    "location_id": location_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
            )
            
            # Query appointment reminders - try without date filter first to debug
            base_query = self.db.collection('appointment_reminders').where('account_id', '==', account_id)
            
            # Count total reminders for this account
            total_reminders = 0
            for doc in base_query.stream():
                total_reminders += 1
            
            logger.info(f"Total reminders for account {account_id}: {total_reminders}")
            
            # Now query with date filter
            query = self.db.collection('appointment_reminders').where('account_id', '==', account_id)
            query = query.where('sent_at', '>=', start_date.isoformat())
            query = query.where('sent_at', '<=', end_date.isoformat())
            
            reminders = []
            for doc in query.stream():
                reminder_data = doc.to_dict()
                reminder_data['id'] = doc.id
                reminders.append(reminder_data)
                
                # Log sample reminder
                if len(reminders) == 1:
                    logger.info(
                        "Sample reminder data",
                        extra={
                            "reminder_id": doc.id,
                            "sent_at": reminder_data.get('sent_at'),
                            "fields": list(reminder_data.keys())
                        }
                    )
            
            logger.info(f"Found {len(reminders)} reminders in date range for account {account_id}")
            
            return reminders
            
        except Exception as e:
            logger.error(f"Error getting appointment reminders by period: {e}", exc_info=True)
            return []
    
    def get_unique_patients(
        self,
        location_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Tuple[int, int]:
        """Get count of unique patients (total and new)."""
        try:
            # Get account ID
            account_ref = self.db.collection('accounts').where('location_id', '==', location_id).limit(1).get()
            if not account_ref:
                return 0, 0
            
            account_id = account_ref[0].id
            
            # Get all bookings for the period
            bookings = self.get_bookings_by_period(location_id, start_date, end_date)
            
            # Extract unique patient phones
            current_patients = set()
            for booking in bookings:
                patient_info = booking.get('patient_info', {})
                if patient_info.get('phone'):
                    current_patients.add(patient_info['phone'])
            
            # Get bookings before the period to identify new patients
            previous_bookings = self.get_bookings_by_period(
                location_id, 
                start_date - timedelta(days=365),  # Look back 1 year
                start_date - timedelta(seconds=1)
            )
            
            previous_patients = set()
            for booking in previous_bookings:
                patient_info = booking.get('patient_info', {})
                if patient_info.get('phone'):
                    previous_patients.add(patient_info['phone'])
            
            # Calculate new patients
            new_patients = current_patients - previous_patients
            
            return len(current_patients), len(new_patients)
            
        except Exception as e:
            logger.error(f"Error getting unique patients: {e}")
            return 0, 0
    
    def aggregate_by_period(
        self,
        data: List[Dict[str, Any]],
        date_field: str,
        value_field: str,
        period: str = 'day'
    ) -> List[Dict[str, Any]]:
        """Aggregate data by time period (day, week, month)."""
        aggregated = defaultdict(float)
        
        for item in data:
            date_value = item.get(date_field)
            if not date_value:
                continue
            
            # Convert to datetime if string
            if isinstance(date_value, str):
                date_value = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            
            # Determine period key
            if period == 'day':
                key = date_value.strftime('%Y-%m-%d')
            elif period == 'week':
                # Get week start (Monday)
                week_start = date_value - timedelta(days=date_value.weekday())
                key = week_start.strftime('%Y-%m-%d')
            elif period == 'month':
                key = date_value.strftime('%Y-%m')
            else:
                key = date_value.strftime('%Y-%m-%d')
            
            # Aggregate value
            value = item.get(value_field, 0)
            if isinstance(value, (int, float)):
                aggregated[key] += value
            else:
                aggregated[key] += 1
        
        # Convert to list
        result = []
        for key, value in sorted(aggregated.items()):
            result.append({
                'period': key,
                'value': value
            })
        
        return result