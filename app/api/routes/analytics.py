"""Analytics API routes."""
from flask import Blueprint, jsonify, request, Response
from datetime import datetime, timedelta
import calendar
import csv
import io
from collections import defaultdict
from typing import Dict, List, Any

from app.core.logging import get_logger
from app.api.middleware.rate_limit import rate_limit
from app.services.analytics_service import AnalyticsService
from app.repositories.account_repository import AccountRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.directory_repository import DirectoryRepository

logger = get_logger(__name__)
bp = Blueprint("analytics", __name__)

# Services will be initialized in route handlers to ensure Firebase is ready


@bp.route("/analytics/stats", methods=["GET"])
@rate_limit(requests_per_minute=100)
def get_analytics_stats():
    """Get overview statistics for a location."""
    try:
        # Initialize services
        analytics_service = AnalyticsService()
        account_repo = AccountRepository()
        location_id = request.args.get("location_id")
        if not location_id:
            return jsonify({
                "error": {
                    "code": "MISSING_PARAMETER",
                    "message": "location_id parameter is required"
                }
            }), 400
        
        # Get account by location_id
        account = account_repo.get_by_location_id(location_id)
        if not account:
            return jsonify({
                "error": {
                    "code": "ACCOUNT_NOT_FOUND",
                    "message": f"No account found for location_id: {location_id}"
                }
            }), 404
        
        # Get statistics
        stats = analytics_service.get_account_stats(account.id)
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Error getting analytics stats: {e}")
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Failed to retrieve analytics stats"
            }
        }), 500


@bp.route("/analytics/chart-data", methods=["GET"])
@rate_limit(requests_per_minute=100)
def get_chart_data():
    """Get monthly chart data for conversations and appointments."""
    try:
        # Initialize services
        analytics_service = AnalyticsService()
        account_repo = AccountRepository()
        location_id = request.args.get("location_id")
        period = request.args.get("period", "monthly")
        
        if not location_id:
            return jsonify({
                "error": {
                    "code": "MISSING_PARAMETER",
                    "message": "location_id parameter is required"
                }
            }), 400
        
        # Get account by location_id
        account = account_repo.get_by_location_id(location_id)
        if not account:
            return jsonify({
                "error": {
                    "code": "ACCOUNT_NOT_FOUND",
                    "message": f"No account found for location_id: {location_id}"
                }
            }), 404
        
        # Get chart data
        chart_data = analytics_service.get_chart_data(account.id, period)
        
        return jsonify(chart_data), 200
        
    except Exception as e:
        logger.error(f"Error getting chart data: {e}")
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Failed to retrieve chart data"
            }
        }), 500


@bp.route("/analytics/conversations", methods=["GET"])
@rate_limit(requests_per_minute=100)
def get_conversations():
    """Get detailed conversation list with messages."""
    try:
        # Initialize services
        analytics_service = AnalyticsService()
        account_repo = AccountRepository()
        location_id = request.args.get("location_id")
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        
        if not location_id:
            return jsonify({
                "error": {
                    "code": "MISSING_PARAMETER",
                    "message": "location_id parameter is required"
                }
            }), 400
        
        # Get account by location_id
        account = account_repo.get_by_location_id(location_id)
        if not account:
            return jsonify({
                "error": {
                    "code": "ACCOUNT_NOT_FOUND",
                    "message": f"No account found for location_id: {location_id}"
                }
            }), 404
        
        # Parse dates if provided
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if start_date else None
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if end_date else None
        
        # Get conversations
        conversations = analytics_service.get_conversations_detailed(
            account_id=account.id,
            limit=limit,
            offset=offset,
            start_date=start_dt,
            end_date=end_dt
        )
        
        return jsonify(conversations), 200
        
    except ValueError as e:
        return jsonify({
            "error": {
                "code": "INVALID_PARAMETER",
                "message": f"Invalid parameter value: {str(e)}"
            }
        }), 400
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Failed to retrieve conversations"
            }
        }), 500


@bp.route("/analytics/dashboard", methods=["GET"])
@rate_limit(requests_per_minute=60)
def get_dashboard():
    """Get comprehensive dashboard data."""
    try:
        # Initialize services
        analytics_service = AnalyticsService()
        account_repo = AccountRepository()
        directory_repo = DirectoryRepository()
        
        # Get parameters
        location_id = request.args.get("location_id")
        if not location_id:
            return jsonify({
                "error": {
                    "code": "MISSING_PARAMETER",
                    "message": "location_id parameter is required"
                }
            }), 400
        
        # Get date range (default to last 30 days)
        end_date = datetime.utcnow()
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        source = request.args.get("source")  # Optional source filter
        
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        else:
            start_date = end_date - timedelta(days=30)
        
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # Get account by location_id
        account = account_repo.get_by_location_id(location_id)
        if not account:
            return jsonify({
                "error": {
                    "code": "ACCOUNT_NOT_FOUND",
                    "message": f"No account found for location_id: {location_id}"
                }
            }), 404
        
        # Debug logging for feature detection
        logger.info(
            "Loading account for feature detection",
            extra={
                "account_id": account.id,
                "location_id": location_id,
                "stripe_enabled": account.stripe_enabled,
                "stripe_connect_account_id": account.stripe_connect_account_id,
                "stripe_onboarding_completed": account.stripe_onboarding_completed,
                "account_name": account.name
            }
        )
        
        # Get comprehensive dashboard metrics
        try:
            dashboard_metrics = analytics_service.get_comprehensive_dashboard(
                location_id=location_id,
                start_date=start_date,
                end_date=end_date,
                source=source
            )
            
            # Convert to dict and add features based on account settings
            dashboard_data = dashboard_metrics.to_dict()
        except Exception as e:
            logger.error(f"Error getting comprehensive dashboard: {e}", exc_info=True)
            # Return minimal dashboard data with features
            dashboard_data = {
                "overview": {"totalRevenue": 0, "totalAppointments": 0, "activePatients": 0, "newPatients": 0},
                "performance": {"conversionRate": 0, "completionRate": 0, "paymentSuccessRate": 0, "retentionRate": 0},
                "growth": {"revenueGrowth": 0, "appointmentGrowth": 0, "patientGrowth": 0},
                "platformComparison": {"whatsapp": {}, "connect": {}},
                "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "details": {"payments": None, "bookings": None, "reminders": None, "directory": None}
            }
        
        # Always add features, even if dashboard metrics fail
        try:
            # Check if directory is enabled for this account
            directory_profile = directory_repo.get_by_account_id(account.id)
            has_directory_enabled = directory_profile is not None and directory_profile.enabled
            
            # Debug logging for directory detection
            logger.info(
                "Directory profile check",
                extra={
                    "account_id": account.id,
                    "has_profile": directory_profile is not None,
                    "profile_enabled": directory_profile.enabled if directory_profile else False,
                    "profile_id": directory_profile.id if directory_profile else None
                }
            )
        except Exception as e:
            logger.error(f"Error checking directory profile: {e}")
            has_directory_enabled = False
        
        # Add features object based on what's enabled for the account
        dashboard_data["features"] = {
            "payments": account.stripe_enabled,
            "directory": has_directory_enabled,
            "reminders": True   # Assuming all accounts have reminders for now
        }
        
        logger.info(
            "Feature flags set",
            extra={
                "features": dashboard_data["features"],
                "account_id": account.id,
                "stripe_enabled": account.stripe_enabled
            }
        )
        
        return jsonify(dashboard_data), 200
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Failed to retrieve dashboard data"
            }
        }), 500


@bp.route("/analytics/payments", methods=["GET"])
@rate_limit(requests_per_minute=100)
def get_payment_analytics():
    """Get detailed payment analytics."""
    try:
        # Initialize services
        analytics_service = AnalyticsService()
        account_repo = AccountRepository()
        
        # Get parameters
        location_id = request.args.get("location_id")
        if not location_id:
            return jsonify({
                "error": {
                    "code": "MISSING_PARAMETER",
                    "message": "location_id parameter is required"
                }
            }), 400
        
        # Get date range
        end_date = datetime.utcnow()
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        else:
            start_date = end_date - timedelta(days=30)
        
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # Get account
        account = account_repo.get_by_location_id(location_id)
        if not account:
            return jsonify({
                "error": {
                    "code": "ACCOUNT_NOT_FOUND",
                    "message": f"No account found for location_id: {location_id}"
                }
            }), 404
        
        # Get payment analytics
        payment_analytics = analytics_service.get_payment_analytics(
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify(payment_analytics.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Error getting payment analytics: {e}")
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Failed to retrieve payment analytics"
            }
        }), 500


@bp.route("/analytics/bookings", methods=["GET"])
@rate_limit(requests_per_minute=100)
def get_booking_analytics():
    """Get detailed booking analytics."""
    try:
        # Initialize services
        analytics_service = AnalyticsService()
        account_repo = AccountRepository()
        
        # Get parameters
        location_id = request.args.get("location_id")
        source = request.args.get("source")  # Optional filter
        
        if not location_id:
            return jsonify({
                "error": {
                    "code": "MISSING_PARAMETER",
                    "message": "location_id parameter is required"
                }
            }), 400
        
        # Get date range
        end_date = datetime.utcnow()
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        else:
            start_date = end_date - timedelta(days=30)
        
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # Get account
        account = account_repo.get_by_location_id(location_id)
        if not account:
            return jsonify({
                "error": {
                    "code": "ACCOUNT_NOT_FOUND",
                    "message": f"No account found for location_id: {location_id}"
                }
            }), 404
        
        # Get booking analytics
        booking_analytics = analytics_service.get_booking_analytics(
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Filter by source if specified
        if source and source in ['vitalis-whatsapp', 'vitalis-connect']:
            # Filter the results (simplified - would be better done in the query)
            result = booking_analytics.to_dict()
            # Add source filter indicator
            result['filteredBySource'] = source
        else:
            result = booking_analytics.to_dict()
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error getting booking analytics: {e}")
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Failed to retrieve booking analytics"
            }
        }), 500


@bp.route("/analytics/reminders", methods=["GET"])
@rate_limit(requests_per_minute=100)
def get_reminder_analytics():
    """Get reminder effectiveness metrics."""
    try:
        # Initialize services
        analytics_service = AnalyticsService()
        account_repo = AccountRepository()
        
        # Get parameters
        location_id = request.args.get("location_id")
        if not location_id:
            return jsonify({
                "error": {
                    "code": "MISSING_PARAMETER",
                    "message": "location_id parameter is required"
                }
            }), 400
        
        # Get date range
        end_date = datetime.utcnow()
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        else:
            start_date = end_date - timedelta(days=30)
        
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # Get account
        account = account_repo.get_by_location_id(location_id)
        if not account:
            return jsonify({
                "error": {
                    "code": "ACCOUNT_NOT_FOUND",
                    "message": f"No account found for location_id: {location_id}"
                }
            }), 404
        
        # Get reminder analytics
        reminder_analytics = analytics_service.get_reminder_analytics(
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify(reminder_analytics.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Error getting reminder analytics: {e}")
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Failed to retrieve reminder analytics"
            }
        }), 500


@bp.route("/analytics/directory", methods=["GET"])
@rate_limit(requests_per_minute=100)
def get_directory_analytics():
    """Get directory performance metrics."""
    try:
        # Initialize services
        analytics_service = AnalyticsService()
        account_repo = AccountRepository()
        
        # Get parameters
        location_id = request.args.get("location_id")
        if not location_id:
            return jsonify({
                "error": {
                    "code": "MISSING_PARAMETER",
                    "message": "location_id parameter is required"
                }
            }), 400
        
        # Get date range
        end_date = datetime.utcnow()
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        else:
            start_date = end_date - timedelta(days=30)
        
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # Get account
        account = account_repo.get_by_location_id(location_id)
        if not account:
            return jsonify({
                "error": {
                    "code": "ACCOUNT_NOT_FOUND",
                    "message": f"No account found for location_id: {location_id}"
                }
            }), 404
        
        # Get directory analytics
        directory_analytics = analytics_service.get_directory_analytics(
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify(directory_analytics.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Error getting directory analytics: {e}")
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Failed to retrieve directory analytics"
            }
        }), 500


@bp.route("/analytics/export", methods=["POST"])
@rate_limit(requests_per_minute=10)
def export_analytics():
    """Export analytics data as CSV."""
    try:
        # Get parameters
        data = request.get_json()
        location_id = data.get("location_id")
        export_type = data.get("type", "dashboard")  # dashboard, payments, bookings, etc.
        format = data.get("format", "csv")  # csv for now
        
        if not location_id:
            return jsonify({
                "error": {
                    "code": "MISSING_PARAMETER",
                    "message": "location_id parameter is required"
                }
            }), 400
        
        # Get date range
        end_date = datetime.utcnow()
        start_date_str = data.get("start_date")
        end_date_str = data.get("end_date")
        
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        else:
            start_date = end_date - timedelta(days=30)
        
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # Initialize services
        analytics_service = AnalyticsService()
        account_repo = AccountRepository()
        
        # Get account
        account = account_repo.get_by_location_id(location_id)
        if not account:
            return jsonify({
                "error": {
                    "code": "ACCOUNT_NOT_FOUND",
                    "message": f"No account found for location_id: {location_id}"
                }
            }), 404
        
        # Generate CSV based on type
        output = io.StringIO()
        writer = csv.writer(output)
        
        if export_type == "payments":
            # Export payment data
            analytics = analytics_service.get_payment_analytics(location_id, start_date, end_date)
            
            # Write headers
            writer.writerow([
                "Period", "Total Revenue", "Transactions", "Success Rate",
                "WhatsApp Revenue", "Connect Revenue"
            ])
            
            # Write summary row
            writer.writerow([
                f"{start_date.date()} to {end_date.date()}",
                f"${analytics.total_revenue / 100:.2f}",
                analytics.transaction_count,
                f"{analytics.success_rate:.1f}%",
                f"${analytics.revenue_by_source.get('vitalis-whatsapp', 0) / 100:.2f}",
                f"${analytics.revenue_by_source.get('vitalis-connect', 0) / 100:.2f}"
            ])
            
        elif export_type == "bookings":
            # Export booking data
            analytics = analytics_service.get_booking_analytics(location_id, start_date, end_date)
            
            # Write headers
            writer.writerow([
                "Period", "Total Bookings", "Confirmed", "Cancelled", "No-Shows",
                "WhatsApp Bookings", "Connect Bookings", "Conversion Rate"
            ])
            
            # Write summary row
            writer.writerow([
                f"{start_date.date()} to {end_date.date()}",
                analytics.total_bookings,
                analytics.bookings_by_status.get('confirmed', 0),
                analytics.bookings_by_status.get('cancelled', 0),
                analytics.bookings_by_status.get('no-show', 0),
                analytics.bookings_by_source.get('vitalis-whatsapp', 0),
                analytics.bookings_by_source.get('vitalis-connect', 0),
                f"{analytics.conversion_rate:.1f}%"
            ])
            
        else:
            # Default to dashboard summary
            dashboard = analytics_service.get_comprehensive_dashboard(location_id, start_date, end_date)
            
            # Write headers
            writer.writerow([
                "Metric", "Value"
            ])
            
            # Write metrics
            writer.writerow(["Total Revenue", f"${dashboard.total_revenue / 100:.2f}"])
            writer.writerow(["Total Appointments", dashboard.total_appointments])
            writer.writerow(["Active Patients", dashboard.active_patients])
            writer.writerow(["New Patients", dashboard.new_patients])
            writer.writerow(["Conversion Rate", f"{dashboard.overall_conversion_rate:.1f}%"])
            writer.writerow(["Payment Success Rate", f"{dashboard.payment_success_rate:.1f}%"])
        
        # Get CSV content
        csv_content = output.getvalue()
        output.close()
        
        # Return CSV file
        response = Response(
            csv_content,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=analytics_{export_type}_{start_date.date()}_{end_date.date()}.csv"
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error exporting analytics: {e}")
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Failed to export analytics"
            }
        }), 500


@bp.route("/analytics/calendar-events", methods=["GET"])
@rate_limit(requests_per_minute=100)
def get_calendar_events():
    """Get calendar events from GHL for appointment analytics."""
    try:
        # Initialize services
        analytics_service = AnalyticsService()
        
        # Get parameters
        location_id = request.args.get("location_id")
        if not location_id:
            return jsonify({
                "error": {
                    "code": "MISSING_PARAMETER",
                    "message": "location_id parameter is required"
                }
            }), 400
        
        # Get date range
        end_date = datetime.utcnow()
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")
        
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        else:
            start_date = end_date - timedelta(days=30)
        
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # Get calendar events
        events = analytics_service.get_calendar_events(
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({"events": events}), 200
        
    except Exception as e:
        logger.error(f"Error getting calendar events: {e}")
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Failed to retrieve calendar events"
            }
        }), 500

