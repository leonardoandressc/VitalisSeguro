"""Analytics service for processing conversation and appointment data."""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
import calendar

from app.core.logging import get_logger
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.account_repository import AccountRepository
from app.models.conversation import ConversationStatus
from app.models.analytics import (
    PaymentAnalytics, BookingAnalytics, ReminderAnalytics, 
    DirectoryAnalytics, DashboardMetrics, TimeSeriesData
)
from app.services.ghl_service import GHLService

logger = get_logger(__name__)


class AnalyticsService:
    """Service for analytics data processing."""
    
    def __init__(self):
        """Initialize analytics service."""
        self.conversation_repo = ConversationRepository()
        self.analytics_repo = AnalyticsRepository()
        self.account_repo = AccountRepository()
        self.ghl_service = GHLService()
    
    def get_account_stats(self, account_id: str) -> Dict[str, Any]:
        """Get overview statistics for an account."""
        try:
            # Get all conversations for the account
            conversations = self.conversation_repo.get_by_account_id(account_id)
            
            # Calculate statistics
            total_conversations = len(conversations)
            total_appointments = 0
            active_users = set()
            
            for conv in conversations:
                # Check if conversation has appointment
                if conv.context and hasattr(conv.context, 'appointment_info') and conv.context.appointment_info:
                    total_appointments += 1
                
                # Count unique users
                active_users.add(conv.phone_number)
            
            # Calculate conversion rate
            conversion_rate = (total_appointments / total_conversations * 100) if total_conversations > 0 else 0
            
            return {
                "totalConversations": total_conversations,
                "totalAppointments": total_appointments,
                "conversionRate": round(conversion_rate, 1),
                "activeUsers": len(active_users)
            }
            
        except Exception as e:
            logger.error(f"Error calculating account stats: {e}")
            raise
    
    def get_chart_data(self, account_id: str, period: str = "monthly") -> List[Dict[str, Any]]:
        """Get chart data for conversations and appointments over time."""
        try:
            # Get conversations from the last 6 months
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=180)
            
            conversations = self.conversation_repo.get_by_date_range(
                account_id=account_id,
                start_date=start_date,
                end_date=end_date
            )
            
            # Group by month
            monthly_data = defaultdict(lambda: {"conversations": 0, "appointments": 0})
            
            for conv in conversations:
                # Get month key
                month_key = conv.created_at.strftime("%b")
                
                # Count conversation
                monthly_data[month_key]["conversations"] += 1
                
                # Count appointment if exists
                if conv.context and hasattr(conv.context, 'appointment_info') and conv.context.appointment_info:
                    monthly_data[month_key]["appointments"] += 1
            
            # Create ordered list of last 6 months
            chart_data = []
            current_date = end_date
            
            for _ in range(6):
                month_name = current_date.strftime("%b")
                data = monthly_data.get(month_name, {"conversations": 0, "appointments": 0})
                
                chart_data.append({
                    "month": month_name,
                    "conversations": data["conversations"],
                    "appointments": data["appointments"]
                })
                
                # Move to previous month
                current_date = current_date.replace(day=1) - timedelta(days=1)
            
            # Reverse to show oldest to newest
            chart_data.reverse()
            
            return chart_data
            
        except Exception as e:
            logger.error(f"Error generating chart data: {e}")
            raise
    
    def get_conversations_detailed(
        self,
        account_id: str,
        limit: int = 20,
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get detailed conversation list with messages."""
        try:
            # Get conversations with pagination
            if start_date and end_date:
                conversations = self.conversation_repo.get_by_date_range(
                    account_id=account_id,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                conversations = self.conversation_repo.get_by_account_id(account_id)
            
            # Sort by created_at descending
            conversations.sort(key=lambda x: x.created_at, reverse=True)
            
            # Apply pagination
            paginated_conversations = conversations[offset:offset + limit]
            
            # Format for frontend
            formatted_conversations = []
            
            for conv in paginated_conversations:
                # Extract appointment info
                has_appointment = bool(conv.context and hasattr(conv.context, 'appointment_info') and conv.context.appointment_info)
                appointment_date = None
                
                if has_appointment and conv.context.appointment_info:
                    appointment_info = conv.context.appointment_info
                    # Try to parse appointment date
                    if isinstance(appointment_info, dict) and "datetime_str" in appointment_info:
                        try:
                            appointment_date = appointment_info["datetime_str"]
                        except:
                            pass
                
                # Format messages
                formatted_messages = []
                for msg in conv.messages:
                    # Check if msg is a Message object or dict
                    if hasattr(msg, 'role'):
                        # It's a Message object
                        formatted_messages.append({
                            "id": f"msg_{conv.id}_{len(formatted_messages)}",
                            "sender": msg.role.value if hasattr(msg.role, 'value') else msg.role,
                            "content": msg.content,
                            "timestamp": msg.timestamp.isoformat() if hasattr(msg.timestamp, 'isoformat') else str(msg.timestamp)
                        })
                    else:
                        # It's a dictionary
                        formatted_messages.append({
                            "id": f"msg_{conv.id}_{len(formatted_messages)}",
                            "sender": msg["role"],
                            "content": msg["content"],
                            "timestamp": msg.get("timestamp", conv.created_at.isoformat())
                        })
                
                # Get user name from messages or phone number
                user_name = conv.phone_number
                if conv.context and conv.context.appointment_info and isinstance(conv.context.appointment_info, dict):
                    user_name = conv.context.appointment_info.get("name", conv.phone_number)
                
                formatted_conversations.append({
                    "id": conv.id,
                    "userId": conv.phone_number,
                    "userName": user_name,
                    "startTime": conv.created_at.isoformat(),
                    "endTime": conv.updated_at.isoformat() if conv.updated_at else None,
                    "messages": formatted_messages,
                    "hasAppointment": has_appointment,
                    "appointmentDate": appointment_date
                })
            
            return formatted_conversations
            
        except Exception as e:
            logger.error(f"Error getting detailed conversations: {e}")
            raise
    
    def get_payment_analytics(
        self,
        location_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> PaymentAnalytics:
        """Get payment analytics for a location."""
        try:
            # Get all payments for the period
            payments = self.analytics_repo.get_payments_by_period(location_id, start_date, end_date)
            
            # Log payment details for debugging
            logger.info(f"Found {len(payments)} payments for location {location_id}")
            if payments:
                # Log unique statuses
                statuses = set(p.get('status', 'unknown') for p in payments)
                logger.info(f"Payment statuses found: {statuses}")
                # Log sample payment
                sample = payments[0]
                logger.info(f"Sample payment: status={sample.get('status')}, amount={sample.get('amount')}")
            
            # Calculate metrics - check for 'paid' or 'completed' status
            total_revenue = sum(p.get('amount', 0) for p in payments if p.get('status') in ['completed', 'paid', 'succeeded'])
            transaction_count = len(payments)
            completed_count = sum(1 for p in payments if p.get('status') in ['completed', 'paid', 'succeeded'])
            success_rate = (completed_count / transaction_count * 100) if transaction_count > 0 else 0
            average_transaction = total_revenue / completed_count if completed_count > 0 else 0
            
            # Revenue by source
            revenue_by_source = defaultdict(int)
            for payment in payments:
                if payment.get('status') in ['completed', 'paid', 'succeeded']:
                    source = payment.get('source', 'vitalis-whatsapp')
                    revenue_by_source[source] += payment.get('amount', 0)
            
            # Revenue by period (monthly)
            revenue_by_period_raw = self.analytics_repo.aggregate_by_period(
                [p for p in payments if p.get('status') in ['completed', 'paid', 'succeeded']],
                'created_at',
                'amount',
                'month'
            )
            
            # Transform to match expected structure
            revenue_by_period = [
                {'period': item['period'], 'revenue': item['value']}
                for item in revenue_by_period_raw
            ]
            
            # Payment methods (placeholder - would need to extract from payment metadata)
            payment_methods = {'card': completed_count}  # Default for now
            
            return PaymentAnalytics(
                total_revenue=total_revenue,
                transaction_count=transaction_count,
                average_transaction=average_transaction,
                success_rate=success_rate,
                revenue_by_source=dict(revenue_by_source),
                revenue_by_period=revenue_by_period,
                top_revenue_doctors=[],  # Would need doctor mapping
                payment_methods=payment_methods
            )
            
        except Exception as e:
            logger.error(f"Error calculating payment analytics: {e}")
            raise
    
    def get_booking_analytics(
        self,
        location_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> BookingAnalytics:
        """Get booking analytics for a location."""
        try:
            # Get all bookings for the period
            bookings = self.analytics_repo.get_bookings_by_period(location_id, start_date, end_date)
            
            # Calculate metrics
            total_bookings = len(bookings)
            
            # Bookings by source
            bookings_by_source = defaultdict(int)
            for booking in bookings:
                source = booking.get('source', 'vitalis-whatsapp')
                bookings_by_source[source] += 1
            
            # Get booking status counts from existing booking data
            bookings_by_status = defaultdict(int)
            
            # Use booking status from our database instead of calling GHL API
            # This is much faster and avoids external API calls
            for booking in bookings:
                status = booking.get('status', 'pending')
                # Map our internal statuses
                if status == 'confirmed':
                    bookings_by_status['confirmed'] += 1
                elif status == 'completed':
                    bookings_by_status['showed'] += 1
                elif status == 'cancelled':
                    bookings_by_status['cancelled'] += 1
                elif status == 'no_show':
                    bookings_by_status['noshow'] += 1
                else:
                    bookings_by_status[status] += 1
            
            # Log booking status distribution
            logger.info(
                "Booking status distribution",
                extra={
                    "total_bookings": total_bookings,
                    "status_counts": dict(bookings_by_status)
                }
            )
            
            # Calculate rates
            confirmed_count = bookings_by_status.get('confirmed', 0)
            cancelled_count = bookings_by_status.get('cancelled', 0)
            no_show_count = bookings_by_status.get('no-show', 0)
            
            cancellation_rate = (cancelled_count / total_bookings * 100) if total_bookings > 0 else 0
            no_show_rate = (no_show_count / total_bookings * 100) if total_bookings > 0 else 0
            confirmed_rate = (confirmed_count / total_bookings * 100) if total_bookings > 0 else 0
            
            # Popular time slots
            slot_counts = defaultdict(int)
            for booking in bookings:
                if booking.get('appointment_datetime'):
                    dt = booking['appointment_datetime']
                    if isinstance(dt, str):
                        dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
                    time_slot = dt.strftime('%H:00')
                    slot_counts[time_slot] += 1
            
            popular_slots = [
                {'time': time, 'count': count}
                for time, count in sorted(slot_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            ]
            
            # Bookings by specialty (from metadata)
            bookings_by_specialty = defaultdict(int)
            for booking in bookings:
                specialty = booking.get('specialty', 'General')
                bookings_by_specialty[specialty] += 1
            
            # Average lead time (hours between booking creation and appointment)
            lead_times = []
            for booking in bookings:
                try:
                    if booking.get('created_at') and booking.get('appointment_datetime'):
                        created = booking['created_at']
                        appointment = booking['appointment_datetime']
                        
                        # Convert to datetime if string
                        if isinstance(created, str):
                            created = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        if isinstance(appointment, str):
                            appointment = datetime.fromisoformat(appointment.replace('Z', '+00:00'))
                        
                        # Ensure both are timezone-naive for comparison
                        if created.tzinfo is not None:
                            created = created.replace(tzinfo=None)
                        if appointment.tzinfo is not None:
                            appointment = appointment.replace(tzinfo=None)
                        
                        lead_time = (appointment - created).total_seconds() / 3600  # Hours
                        if lead_time > 0:  # Only positive lead times
                            lead_times.append(lead_time)
                except Exception as e:
                    logger.debug(f"Error calculating lead time for booking: {e}")
                    continue
            
            average_lead_time = sum(lead_times) / len(lead_times) if lead_times else 0
            
            # Conversion rate (would need total attempts, using confirmed/total for now)
            conversion_rate = confirmed_rate
            
            return BookingAnalytics(
                total_bookings=total_bookings,
                bookings_by_source=dict(bookings_by_source),
                conversion_rate=conversion_rate,
                cancellation_rate=cancellation_rate,
                no_show_rate=no_show_rate,
                confirmed_rate=confirmed_rate,
                popular_slots=popular_slots,
                bookings_by_specialty=dict(bookings_by_specialty),
                bookings_by_status=dict(bookings_by_status),
                average_lead_time=average_lead_time
            )
            
        except Exception as e:
            logger.error(f"Error calculating booking analytics: {e}")
            raise
    
    def get_reminder_analytics(
        self,
        location_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> ReminderAnalytics:
        """Get reminder analytics for a location."""
        try:
            # Get reminder statistics
            stats = self.analytics_repo.get_reminder_stats(location_id, start_date, end_date)
            
            total_sent = stats.get('total_sent', 0)
            total_responses = stats.get('total_responses', 0)
            total_confirmations = stats.get('total_confirmations', 0)
            total_cancellations = stats.get('total_cancellations', 0)
            avg_response_time = stats.get('avg_response_time', 0)
            
            # Calculate rates
            response_rate = (total_responses / total_sent * 100) if total_sent > 0 else 0
            confirmation_rate = (total_confirmations / total_responses * 100) if total_responses > 0 else 0
            cancellation_rate = (total_cancellations / total_responses * 100) if total_responses > 0 else 0
            
            # Effectiveness score (simplified - would need appointment attendance data)
            effectiveness_score = confirmation_rate * 0.8  # Placeholder
            
            # Reminders by type (placeholder)
            reminders_by_type = {
                '24h': int(total_sent * 0.6),
                '2h': int(total_sent * 0.4)
            }
            
            return ReminderAnalytics(
                total_sent=total_sent,
                total_delivered=total_sent,  # Assuming all sent are delivered
                response_rate=response_rate,
                confirmation_rate=confirmation_rate,
                cancellation_rate=cancellation_rate,
                effectiveness_score=effectiveness_score,
                average_response_time=avg_response_time,
                reminders_by_type=reminders_by_type
            )
            
        except Exception as e:
            logger.error(f"Error calculating reminder analytics: {e}")
            raise
    
    def get_directory_analytics(
        self,
        location_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> DirectoryAnalytics:
        """Get directory analytics for a location."""
        try:
            # Get directory analytics events
            events = self.analytics_repo.get_directory_analytics(location_id, start_date, end_date)
            
            # Calculate metrics
            view_events = [e for e in events if e.get('type') == 'profile_view']
            booking_events = [e for e in events if e.get('type') == 'booking_started']
            search_events = [e for e in events if e.get('type') == 'search']
            
            total_views = len(view_events)
            unique_visitors = len(set(e.get('data', {}).get('sessionId') for e in events if e.get('data', {}).get('sessionId')))
            
            # Conversion rate (bookings started / views)
            conversion_rate = (len(booking_events) / total_views * 100) if total_views > 0 else 0
            
            # Views by profile
            profile_views = defaultdict(int)
            for event in view_events:
                profile_id = event.get('data', {}).get('profileId')
                if profile_id:
                    profile_views[profile_id] += 1
            
            views_by_profile = [
                {'profile_id': pid, 'views': count}
                for pid, count in sorted(profile_views.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
            
            # Popular specialties (from search or view data)
            specialty_counts = defaultdict(int)
            for event in events:
                specialty = event.get('data', {}).get('specialty')
                if specialty:
                    specialty_counts[specialty] += 1
            
            popular_specialties = [
                spec for spec, _ in sorted(specialty_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            ]
            
            # Search terms
            search_term_counts = defaultdict(int)
            for event in search_events:
                term = event.get('data', {}).get('searchTerm')
                if term:
                    search_term_counts[term.lower()] += 1
            
            search_terms = [
                {'term': term, 'count': count}
                for term, count in sorted(search_term_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
            
            # Geographic distribution (placeholder)
            geographic_distribution = {'CDMX': total_views}  # Would need location data
            
            # Average session duration and bounce rate (placeholders)
            average_session_duration = 180  # 3 minutes
            bounce_rate = 35.0  # 35%
            
            return DirectoryAnalytics(
                total_views=total_views,
                unique_visitors=unique_visitors,
                conversion_rate=conversion_rate,
                views_by_profile=views_by_profile,
                popular_specialties=popular_specialties,
                search_terms=search_terms,
                geographic_distribution=geographic_distribution,
                average_session_duration=average_session_duration,
                bounce_rate=bounce_rate
            )
            
        except Exception as e:
            logger.error(f"Error calculating directory analytics: {e}")
            raise
    
    def get_comprehensive_dashboard(
        self,
        location_id: str,
        start_date: datetime,
        end_date: datetime,
        source: Optional[str] = None
    ) -> DashboardMetrics:
        """Get comprehensive dashboard metrics for a location."""
        try:
            # Get conversations count from actual conversations collection
            conversations_count = self.analytics_repo.get_conversations_count(location_id, start_date, end_date)
            conversations_data = self.analytics_repo.get_conversations_by_period(location_id, start_date, end_date, source)
            
            # Get all analytics with optional source filter
            payment_analytics = self.get_payment_analytics(location_id, start_date, end_date)
            booking_analytics = self.get_booking_analytics(location_id, start_date, end_date)
            reminder_analytics = self.get_reminder_analytics(location_id, start_date, end_date)
            directory_analytics = self.get_directory_analytics(location_id, start_date, end_date)
            
            # Get patient counts
            active_patients, new_patients = self.analytics_repo.get_unique_patients(
                location_id, start_date, end_date
            )
            
            # Calculate platform-specific metrics
            whatsapp_bookings = booking_analytics.bookings_by_source.get('vitalis-whatsapp', 0)
            connect_bookings = booking_analytics.bookings_by_source.get('vitalis-connect', 0)
            whatsapp_revenue = payment_analytics.revenue_by_source.get('vitalis-whatsapp', 0)
            connect_revenue = payment_analytics.revenue_by_source.get('vitalis-connect', 0)
            
            # Get appointment reminders count
            reminders = self.analytics_repo.get_appointment_reminders_by_period(location_id, start_date, end_date)
            reminders_count = len(reminders)
            
            # Count successful appointments (showed status)
            showed_appointments = booking_analytics.bookings_by_status.get('showed', 0)
            
            whatsapp_metrics = {
                'bookings': whatsapp_bookings,
                'revenue': whatsapp_revenue,
                'conversionRate': booking_analytics.conversion_rate if whatsapp_bookings > connect_bookings else 0,
                'totalConversations': conversations_count,  # Add conversations count
                'remindersSent': reminders_count,  # Add reminders count
                'showedAppointments': showed_appointments  # Add successful appointments
            }
            
            connect_metrics = {
                'bookings': connect_bookings,
                'revenue': connect_revenue,
                'conversionRate': directory_analytics.conversion_rate,
                'totalConversations': 0  # Connect doesn't have conversations
            }
            
            # Calculate growth (would need previous period data)
            revenue_growth = 0  # Placeholder
            appointment_growth = 0  # Placeholder
            patient_growth = 0  # Placeholder
            
            return DashboardMetrics(
                total_revenue=payment_analytics.total_revenue,
                total_appointments=booking_analytics.total_bookings,
                active_patients=active_patients,
                new_patients=new_patients,
                overall_conversion_rate=booking_analytics.conversion_rate,
                appointment_completion_rate=booking_analytics.confirmed_rate,
                payment_success_rate=payment_analytics.success_rate,
                patient_retention_rate=0,  # Would need historical data
                revenue_growth=revenue_growth,
                appointment_growth=appointment_growth,
                patient_growth=patient_growth,
                whatsapp_metrics=whatsapp_metrics,
                connect_metrics=connect_metrics,
                period_start=start_date,
                period_end=end_date,
                payment_analytics=payment_analytics,
                booking_analytics=booking_analytics,
                reminder_analytics=reminder_analytics,
                directory_analytics=directory_analytics
            )
            
        except Exception as e:
            logger.error(f"Error calculating comprehensive dashboard: {e}")
            raise
    
    def get_calendar_events(
        self,
        location_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get calendar events from GHL for analytics."""
        try:
            # Get account for this location
            account = self.account_repo.get_by_location_id(location_id)
            if not account:
                logger.warning(f"No account found for location_id: {location_id}")
                return []
            
            # Get calendar events from GHL
            events_data = self.ghl_service.get_appointments(
                account_id=account.id,
                calendar_id=account.calendar_id,
                start_date=start_date,
                end_date=end_date,
                location_id=location_id
            )
            
            events = events_data.get("events", [])
            
            # Process events for analytics
            processed_events = []
            for event in events:
                processed_events.append({
                    "id": event.get("id"),
                    "title": event.get("title"),
                    "startTime": event.get("startTime"),
                    "endTime": event.get("endTime"),
                    "status": event.get("appointmentStatus", "unknown"),
                    "contactId": event.get("contactId"),
                    "calendarId": event.get("calendarId")
                })
            
            return processed_events
            
        except Exception as e:
            logger.error(f"Error fetching calendar events: {e}")
            return []