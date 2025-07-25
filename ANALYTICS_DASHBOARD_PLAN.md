# Analytics Dashboard Integration Plan

## Overview
This document outlines the plan to integrate payment, reminders, and directory data into a comprehensive analytics dashboard for Vitalis Platform.

## Data Sources

### 1. Payment Data (Firestore Collection: `payments`)
- **Source Field**: `vitalis-whatsapp` or `vitalis-connect`
- **Key Metrics**:
  - Total revenue by period
  - Revenue by source
  - Payment success rate
  - Average transaction value
  - Payment trends over time
  - Top revenue-generating doctors

### 2. Booking Data (Firestore Collection: `bookings`)
- **Source Field**: `vitalis-whatsapp` or `vitalis-connect`
- **Key Metrics**:
  - Total bookings by period
  - Bookings by source
  - Booking conversion rate
  - Cancellation rate
  - No-show rate
  - Popular time slots
  - Bookings by specialty

### 3. Reminder Data (Firestore Collections: `appointment_reminders`, `reminder_job_runs`)
- **Key Metrics**:
  - Total reminders sent
  - Reminder response rate
  - Confirmation vs cancellation rates
  - Reminder effectiveness (attended vs no-show)
  - Optimal reminder timing analysis

### 4. Directory Data (Firestore Collection: `directory_profiles`, `directory_analytics`)
- **Key Metrics**:
  - Profile views
  - View-to-booking conversion rate
  - Most viewed profiles
  - Geographic distribution
  - Popular specialties

## Implementation Architecture

### Phase 1: Data Models and Repositories

#### 1.1 Create Analytics Models
```python
# app/models/analytics.py
@dataclass
class PaymentAnalytics:
    total_revenue: int
    transaction_count: int
    average_transaction: float
    success_rate: float
    revenue_by_source: Dict[str, int]
    revenue_by_period: List[Dict[str, Any]]

@dataclass
class BookingAnalytics:
    total_bookings: int
    bookings_by_source: Dict[str, int]
    conversion_rate: float
    cancellation_rate: float
    no_show_rate: float
    popular_slots: List[Dict[str, Any]]
    bookings_by_specialty: Dict[str, int]

@dataclass
class ReminderAnalytics:
    total_sent: int
    response_rate: float
    confirmation_rate: float
    cancellation_rate: float
    effectiveness_score: float

@dataclass
class DirectoryAnalytics:
    total_views: int
    conversion_rate: float
    views_by_profile: List[Dict[str, Any]]
    popular_specialties: List[str]
    geographic_distribution: Dict[str, int]
```

#### 1.2 Create Analytics Repositories
```python
# app/repositories/analytics_repository.py
class AnalyticsRepository:
    def get_payments_by_period(self, start_date, end_date, source=None)
    def get_bookings_by_period(self, start_date, end_date, source=None)
    def get_reminder_stats(self, start_date, end_date)
    def get_directory_views(self, start_date, end_date)
```

### Phase 2: Analytics Service Enhancement

#### 2.1 Extend Analytics Service
```python
# app/services/analytics_service.py (enhanced)
class AnalyticsService:
    def get_payment_analytics(self, start_date, end_date, doctor_id=None):
        # Aggregate payment data
        # Calculate revenue metrics
        # Group by source
        # Generate time series data
    
    def get_booking_analytics(self, start_date, end_date, doctor_id=None):
        # Aggregate booking data
        # Calculate conversion rates
        # Analyze popular time slots
        # Group by source and specialty
    
    def get_reminder_analytics(self, start_date, end_date, doctor_id=None):
        # Analyze reminder effectiveness
        # Calculate response rates
        # Correlate with attendance
    
    def get_directory_analytics(self, start_date, end_date):
        # Track profile views
        # Calculate conversion rates
        # Analyze search patterns
    
    def get_comprehensive_dashboard(self, start_date, end_date, doctor_id=None):
        # Combine all analytics
        # Calculate cross-domain insights
        # Generate KPIs
```

### Phase 3: API Endpoints

#### 3.1 Create Analytics Routes
```python
# app/api/routes/analytics.py
@analytics_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    # Return comprehensive dashboard data
    # Support date range filtering
    # Support doctor-specific views

@analytics_bp.route('/payments', methods=['GET'])
def get_payment_analytics():
    # Detailed payment analytics
    # Support grouping by source

@analytics_bp.route('/bookings', methods=['GET'])
def get_booking_analytics():
    # Detailed booking analytics
    # Support filtering by source

@analytics_bp.route('/reminders', methods=['GET'])
def get_reminder_analytics():
    # Reminder effectiveness metrics

@analytics_bp.route('/directory', methods=['GET'])
def get_directory_analytics():
    # Directory performance metrics

@analytics_bp.route('/export', methods=['POST'])
def export_analytics():
    # Export data as CSV/PDF
    # Support custom date ranges
```

### Phase 4: Admin Hub Integration

#### 4.1 Analytics Dashboard UI Components
```typescript
// Frontend components for Admin Hub
- DashboardOverview: KPI cards and summary metrics
- RevenueChart: Time series revenue visualization
- BookingHeatmap: Popular time slots visualization
- ConversionFunnel: View → Booking → Payment → Attendance
- SourceComparison: WhatsApp vs Connect metrics
- DoctorPerformance: Individual doctor analytics
```

#### 4.2 Real-time Updates
- Use Firebase listeners for real-time data
- Implement caching for performance
- Progressive loading for large datasets

### Phase 5: Advanced Features

#### 5.1 Predictive Analytics
- No-show prediction based on historical data
- Revenue forecasting
- Optimal pricing recommendations
- Best reminder timing suggestions

#### 5.2 Automated Reporting
- Daily/Weekly/Monthly email reports
- WhatsApp business metrics
- Custom alerts for anomalies
- Performance benchmarking

#### 5.3 Data Export and Integration
- CSV/Excel export functionality
- API for third-party integrations
- Webhook notifications for key events
- Integration with accounting software

## Key Performance Indicators (KPIs)

### Financial KPIs
1. **Monthly Recurring Revenue (MRR)**
   - Total revenue per month
   - Growth rate
   - Revenue per doctor

2. **Average Revenue Per User (ARPU)**
   - Revenue / Active patients
   - By source (WhatsApp vs Connect)

3. **Payment Success Rate**
   - Completed / Total payment attempts
   - By payment method

### Operational KPIs
1. **Booking Conversion Rate**
   - Bookings / Profile views (Connect)
   - Appointments / Conversations (WhatsApp)

2. **Appointment Attendance Rate**
   - Attended / Total scheduled
   - Impact of reminders

3. **Platform Utilization**
   - Active doctors
   - Bookings per doctor
   - Geographic coverage

### Growth KPIs
1. **User Acquisition**
   - New patients per period
   - Acquisition by source

2. **Retention Rate**
   - Repeat bookings
   - Patient lifetime value

3. **Platform Expansion**
   - New doctor signups
   - New specialties added
   - Geographic expansion

## Implementation Timeline

### Week 1-2: Foundation
- Create analytics models
- Implement analytics repositories
- Set up data aggregation jobs

### Week 3-4: Service Layer
- Enhance analytics service
- Implement calculation logic
- Add caching layer

### Week 5-6: API Development
- Create analytics endpoints
- Implement authentication
- Add export functionality

### Week 7-8: Frontend Integration
- Build dashboard components
- Implement real-time updates
- Create visualizations

### Week 9-10: Testing and Optimization
- Performance testing
- Data accuracy validation
- UI/UX refinements

### Week 11-12: Advanced Features
- Predictive analytics
- Automated reporting
- Third-party integrations

## Technical Considerations

### Performance
- Implement data aggregation jobs (daily/hourly)
- Use materialized views for common queries
- Cache frequently accessed data
- Paginate large result sets

### Security
- Role-based access control
- Data anonymization for analytics
- Audit logging for data access
- HIPAA compliance for health data

### Scalability
- Design for multi-tenant architecture
- Implement data partitioning
- Use time-series optimized storage
- Plan for data archival

## Success Metrics
1. Dashboard load time < 2 seconds
2. Real-time data delay < 1 minute
3. 95% data accuracy
4. Support for 10,000+ appointments/month
5. Export generation < 30 seconds

## Next Steps
1. Review and approve plan
2. Set up development environment
3. Create initial data models
4. Begin implementation of Phase 1