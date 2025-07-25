"""Analytics data models for dashboard metrics."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional


@dataclass
class PaymentAnalytics:
    """Payment analytics metrics."""
    total_revenue: int  # Total revenue in cents
    transaction_count: int
    average_transaction: float
    success_rate: float
    revenue_by_source: Dict[str, int]  # {"vitalis-whatsapp": 150000, "vitalis-connect": 200000}
    revenue_by_period: List[Dict[str, Any]]  # [{"period": "2024-01", "revenue": 50000}]
    top_revenue_doctors: List[Dict[str, Any]]  # [{"doctor_id": "123", "name": "Dr. Smith", "revenue": 100000}]
    payment_methods: Dict[str, int]  # {"card": 45, "oxxo": 10}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "totalRevenue": self.total_revenue,
            "transactionCount": self.transaction_count,
            "averageTransaction": self.average_transaction,
            "successRate": self.success_rate,
            "revenueBySource": self.revenue_by_source,
            "revenueByPeriod": self.revenue_by_period,
            "topRevenueDoctors": self.top_revenue_doctors,
            "paymentMethods": self.payment_methods
        }


@dataclass
class BookingAnalytics:
    """Booking analytics metrics."""
    total_bookings: int
    bookings_by_source: Dict[str, int]  # {"vitalis-whatsapp": 45, "vitalis-connect": 30}
    conversion_rate: float  # Bookings / Total attempts
    cancellation_rate: float
    no_show_rate: float
    confirmed_rate: float
    popular_slots: List[Dict[str, Any]]  # [{"time": "10:00", "count": 15}]
    bookings_by_specialty: Dict[str, int]  # {"General": 30, "Cardiology": 20}
    bookings_by_status: Dict[str, int]  # {"confirmed": 50, "cancelled": 10, "no-show": 5}
    average_lead_time: float  # Hours between booking and appointment
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "totalBookings": self.total_bookings,
            "bookingsBySource": self.bookings_by_source,
            "conversionRate": self.conversion_rate,
            "cancellationRate": self.cancellation_rate,
            "noShowRate": self.no_show_rate,
            "confirmedRate": self.confirmed_rate,
            "popularSlots": self.popular_slots,
            "bookingsBySpecialty": self.bookings_by_specialty,
            "bookingsByStatus": self.bookings_by_status,
            "averageLeadTime": self.average_lead_time
        }


@dataclass
class ReminderAnalytics:
    """Reminder analytics metrics."""
    total_sent: int
    total_delivered: int
    response_rate: float  # Responses / Delivered
    confirmation_rate: float  # Confirmations / Responses
    cancellation_rate: float  # Cancellations / Responses
    effectiveness_score: float  # Attended appointments / Reminders sent
    average_response_time: float  # Minutes between reminder and response
    reminders_by_type: Dict[str, int]  # {"24h": 100, "2h": 150}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "totalSent": self.total_sent,
            "totalDelivered": self.total_delivered,
            "responseRate": self.response_rate,
            "confirmationRate": self.confirmation_rate,
            "cancellationRate": self.cancellation_rate,
            "effectivenessScore": self.effectiveness_score,
            "averageResponseTime": self.average_response_time,
            "remindersByType": self.reminders_by_type
        }


@dataclass
class DirectoryAnalytics:
    """Directory analytics metrics."""
    total_views: int
    unique_visitors: int
    conversion_rate: float  # Bookings / Views
    views_by_profile: List[Dict[str, Any]]  # [{"profile_id": "123", "doctor_name": "Dr. Smith", "views": 150}]
    popular_specialties: List[str]
    search_terms: List[Dict[str, Any]]  # [{"term": "cardiologo", "count": 45}]
    geographic_distribution: Dict[str, int]  # {"CDMX": 100, "Guadalajara": 50}
    average_session_duration: float  # Seconds
    bounce_rate: float  # Single page visits / Total visits
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "totalViews": self.total_views,
            "uniqueVisitors": self.unique_visitors,
            "conversionRate": self.conversion_rate,
            "viewsByProfile": self.views_by_profile,
            "popularSpecialties": self.popular_specialties,
            "searchTerms": self.search_terms,
            "geographicDistribution": self.geographic_distribution,
            "averageSessionDuration": self.average_session_duration,
            "bounceRate": self.bounce_rate
        }


@dataclass
class DashboardMetrics:
    """Combined dashboard metrics and KPIs."""
    # Overview metrics
    total_revenue: int
    total_appointments: int
    active_patients: int
    new_patients: int
    
    # Performance metrics
    overall_conversion_rate: float
    appointment_completion_rate: float
    payment_success_rate: float
    patient_retention_rate: float
    
    # Growth metrics
    revenue_growth: float  # Percentage vs previous period
    appointment_growth: float
    patient_growth: float
    
    # Platform comparison
    whatsapp_metrics: Dict[str, Any]
    connect_metrics: Dict[str, Any]
    
    # Time period
    period_start: datetime
    period_end: datetime
    
    # Detailed analytics
    payment_analytics: Optional[PaymentAnalytics] = None
    booking_analytics: Optional[BookingAnalytics] = None
    reminder_analytics: Optional[ReminderAnalytics] = None
    directory_analytics: Optional[DirectoryAnalytics] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "overview": {
                "totalRevenue": self.total_revenue,
                "totalAppointments": self.total_appointments,
                "activePatients": self.active_patients,
                "newPatients": self.new_patients
            },
            "performance": {
                "conversionRate": self.overall_conversion_rate,
                "completionRate": self.appointment_completion_rate,
                "paymentSuccessRate": self.payment_success_rate,
                "retentionRate": self.patient_retention_rate
            },
            "growth": {
                "revenueGrowth": self.revenue_growth,
                "appointmentGrowth": self.appointment_growth,
                "patientGrowth": self.patient_growth
            },
            "platformComparison": {
                "whatsapp": self.whatsapp_metrics,
                "connect": self.connect_metrics
            },
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat()
            },
            "details": {
                "payments": self.payment_analytics.to_dict() if self.payment_analytics else None,
                "bookings": self.booking_analytics.to_dict() if self.booking_analytics else None,
                "reminders": self.reminder_analytics.to_dict() if self.reminder_analytics else None,
                "directory": self.directory_analytics.to_dict() if self.directory_analytics else None
            }
        }


@dataclass 
class TimeSeriesData:
    """Time series data point for charts."""
    timestamp: datetime
    value: float
    label: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "label": self.label,
            "metadata": self.metadata
        }