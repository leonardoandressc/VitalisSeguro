"""
Directory API routes for Vitalis Connect
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import math
import os
import uuid
import pytz
from typing import List, Dict, Any, Optional

import firebase_admin
from firebase_admin import firestore
from app.core.logging import get_logger
from app.core.exceptions import ResourceNotFoundError
from app.services.account_service import AccountService
from app.services.ghl_service import GHLService
from app.services.directory_service import DirectoryService
from app.services.whatsapp_service import WhatsAppService
from app.services.whatsapp_template_service import WhatsAppTemplateService
from app.utils.firebase import get_firestore_client
from app.services.booking_service import BookingService
from app.api.middleware.auth import require_api_key
from app.utils.validators import validate_email, validate_phone
from app.utils.phone_utils import normalize_phone, format_phone_for_whatsapp

logger = get_logger(__name__)

directory_bp = Blueprint('directory', __name__)

# Helper function to calculate distance between two coordinates
def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers using Haversine formula"""
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

@directory_bp.route('/doctors', methods=['GET'])
def get_doctors():
    """
    Get list of doctors with optional filters
    Query params:
    - specialty: Filter by specialty
    - lat/lng: User location for distance calculation
    - radius: Maximum distance in km (default 50)
    - page: Page number (default 1)
    - limit: Results per page (default 20)
    """
    try:
        # Get query parameters
        specialty = request.args.get('specialty')
        lat = request.args.get('lat', type=float)
        lng = request.args.get('lng', type=float)
        radius = request.args.get('radius', type=float, default=50)
        page = request.args.get('page', type=int, default=1)
        limit = request.args.get('limit', type=int, default=20)
        
        # Use directory service
        directory_service = DirectoryService()
        result = directory_service.search_doctors(
            lat=lat,
            lng=lng,
            specialty=specialty,
            radius_km=radius,
            page=page,
            limit=limit
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error fetching doctors: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Error fetching doctors',
            'error': str(e) if os.getenv('FLASK_ENV') == 'development' else None
        }), 500

@directory_bp.route('/doctors/<doctor_id>', methods=['GET'])
def get_doctor(doctor_id):
    """Get single doctor details"""
    try:
        directory_service = DirectoryService()
        doctor = directory_service.get_doctor_details(doctor_id)
        
        return jsonify({
            'success': True,
            'data': doctor
        })
        
    except ResourceNotFoundError:
        return jsonify({
            'success': False,
            'message': 'Doctor not found'
        }), 404
    except Exception as e:
        logger.error(f"Error fetching doctor {doctor_id}: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error fetching doctor details'
        }), 500

@directory_bp.route('/specialties', methods=['GET'])
def get_specialties():
    """Get list of available specialties with doctor count"""
    try:
        directory_service = DirectoryService()
        specialties = directory_service.get_specialties_list()
        
        # Add icons for compatibility
        icons = {
            'general': '🩺',
            'pediatrics': '👶',
            'cardiology': '❤️',
            'dermatology': '🔬',
            'gynecology': '👩‍⚕️',
            'orthopedics': '🦴',
            'psychiatry': '🧠',
            'ophthalmology': '👁️',
            'dentistry': '🦷',
            'nutrition': '🥗',
            'psychology': '🧠',
            'neurology': '🧠',
            'endocrinology': '💊',
            'gastroenterology': '🏥',
            'oncology': '🏥',
            'rheumatology': '🏥',
            'urology': '🏥',
            'other': '🏥'
        }
        
        for specialty in specialties:
            specialty['icon'] = icons.get(specialty['id'], '🏥')
        
        return jsonify({
            'success': True,
            'data': specialties
        })
        
    except Exception as e:
        logger.error(f"Error fetching specialties: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error fetching specialties'
        }), 500

@directory_bp.route('/doctors/<doctor_id>/availability', methods=['GET'])
def get_doctor_availability(doctor_id):
    """Get doctor availability from GHL calendar"""
    try:
        # Get date parameter
        date_str = request.args.get('date')
        if date_str:
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            target_date = datetime.now()
        
        # Get directory profile first
        db = get_firestore_client()
        directory_doc = db.collection('directory_profiles').document(doctor_id).get()
        
        if not directory_doc.exists:
            return jsonify({
                'success': False,
                'message': 'Doctor not found'
            }), 404
        
        directory_profile = directory_doc.to_dict()
        
        # Now get the account using the account_id from directory profile
        account_id = directory_profile.get('account_id')
        if not account_id:
            return jsonify({
                'success': False,
                'message': 'Account not configured'
            }), 400
            
        account_doc = db.collection('accounts').document(account_id).get()
        if not account_doc.exists:
            return jsonify({
                'success': False,
                'message': 'Account not found'
            }), 404
            
        account = account_doc.to_dict()
        
        # Get GHL calendar ID
        calendar_id = account.get('calendar_id')
        if not calendar_id:
            return jsonify({
                'success': False,
                'message': 'Calendar not configured for this doctor'
            }), 400
        
        # Initialize GHL client
        from app.integrations.ghl.client import GoHighLevelClient
        import pytz
        
        ghl_client = GoHighLevelClient()
        tz = pytz.timezone('America/Mexico_City')
        
        # Set time range for the requested date
        start_date = tz.localize(target_date.replace(hour=0, minute=0, second=0))
        end_date = start_date + timedelta(days=1)
        
        # Convert to milliseconds for GHL API
        start_timestamp = int(start_date.timestamp() * 1000)
        end_timestamp = int(end_date.timestamp() * 1000)
        
        logger.info(f"[DEBUG] Doctor availability request:")
        logger.info(f"[DEBUG] - Account ID: {account_id}")
        logger.info(f"[DEBUG] - Calendar ID: {account.get('calendar_id')}")
        logger.info(f"[DEBUG] - Location ID: {account.get('location_id')}")
        logger.info(f"[DEBUG] - User ID: {account.get('assigned_user_id')}")
        logger.info(f"[DEBUG] - Date: {date_str}")
        logger.info(f"[DEBUG] - Start timestamp: {start_timestamp} ({start_date})")
        logger.info(f"[DEBUG] - End timestamp: {end_timestamp} ({end_date})")
        
        try:
            # Get free slots from GHL
            free_slots = ghl_client.get_free_slots(
                account_id=account_id,
                calendar_id=calendar_id,
                start_date=start_timestamp,
                end_date=end_timestamp,
                timezone='America/Mexico_City',
                user_id=account.get('assigned_user_id')
            )
            
            logger.info(f"[DEBUG] Free slots for {date_str}: {len(free_slots)} slots")
            for slot in free_slots[:5]:  # Log first 5 for debugging
                logger.info(f"[DEBUG] Free slot: date={slot.get('date')}, time={slot.get('time')}, datetime={slot.get('datetime')}")
            
            # Get blocked slots to filter out
            blocked_slots = ghl_client.get_blocked_slots(
                account_id=account_id,
                calendar_id=calendar_id,
                start_time=start_timestamp,
                end_time=end_timestamp,
                location_id=account.get('location_id'),
                user_id=account.get('assigned_user_id')
            )
            
            logger.info(f"[DEBUG] Blocked slots response: {len(blocked_slots)} events")
            
            # Create a set of blocked times for quick lookup
            blocked_times = set()
            logger.info(f"[DEBUG] Processing {len(blocked_slots)} blocked events")
            for event in blocked_slots:
                # Extract start time from blocked slot
                event_start = event.get('startTime')
                if event_start:
                    # Parse the datetime and extract just the time part
                    try:
                        # GHL returns datetime with timezone offset like "2023-09-25T16:00:00+05:30"
                        blocked_dt = datetime.fromisoformat(event_start)
                        blocked_local = blocked_dt.astimezone(tz)
                        blocked_time_str = blocked_local.strftime('%H:%M')
                        blocked_date_str = blocked_local.strftime('%Y-%m-%d')
                        blocked_key = f"{blocked_date_str}_{blocked_time_str}"
                        blocked_times.add(blocked_key)
                        logger.info(f"[DEBUG] Added blocked time: {blocked_key} from {event_start} (local: {blocked_local})")
                        
                        # Special check for 18:00
                        if blocked_time_str == "18:00":
                            logger.info(f"[DEBUG] Found 18:00 slot blocked on {blocked_date_str}!")
                    except Exception as e:
                        logger.warning(f"Error parsing blocked slot time '{event_start}': {e}")
            
            logger.info(f"[DEBUG] Total blocked times in set: {len(blocked_times)}")
            logger.info(f"[DEBUG] Blocked times set: {blocked_times}")
            
            # Format slots for frontend - ONLY for the requested date
            formatted_slots = []
            for slot in free_slots:
                # Only include slots for the requested date
                if slot['date'] != date_str:
                    logger.info(f"[DEBUG] Skipping slot for different date: {slot['date']} (requested: {date_str})")
                    continue
                
                # Parse slot datetime
                slot_datetime = datetime.fromisoformat(slot['datetime'])
                if slot_datetime.tzinfo is None:
                    slot_datetime = tz.localize(slot_datetime)
                
                # Check if this slot is blocked
                slot_key = f"{slot['date']}_{slot['time']}"
                is_available = slot_key not in blocked_times
                
                # Special logging for 18:00
                if slot['time'] == "18:00":
                    logger.info(f"[DEBUG] Checking 18:00 slot: key={slot_key}, is_available={is_available}, in_blocked_times={slot_key in blocked_times}")
                
                formatted_slots.append({
                    'time': slot['time'],
                    'datetime': slot_datetime.isoformat(),
                    'date': slot['date'],
                    'available': is_available,
                    'duration_minutes': 50  # 50-minute appointments
                })
            
            # Also check if payment is required
            payment_info = {
                'payment_required': account.get('stripe_enabled', False),
                'price': account.get('appointment_price', 0) / 100,  # Convert from cents
                'currency': account.get('currency', 'MXN')
            }
            
            return jsonify({
                'success': True,
                'data': {
                    'date': date_str,
                    'slots': formatted_slots,
                    'timezone': 'America/Mexico_City',
                    'doctor_id': doctor_id,
                    'payment_info': payment_info
                }
            })
            
        except Exception as e:
            logger.error(f"Error fetching GHL slots: {str(e)}")
            # Fallback to mock data if GHL fails
            slots = []
            for hour in range(9, 18):  # 9 AM to 6 PM
                for minute in [0, 30]:  # Every 30 minutes
                    slot_time = target_date.replace(hour=hour, minute=minute)
                    if slot_time > datetime.now():  # Only future slots
                        slots.append({
                            'date': slot_time.strftime('%Y-%m-%d'),
                            'time': slot_time.strftime('%H:%M'),
                            'datetime': tz.localize(slot_time).isoformat(),
                            'available': True,
                            'duration_minutes': 30
                        })
            
            return jsonify({
                'success': True,
                'data': {
                    'date': date_str,
                    'slots': slots[:10],
                    'timezone': 'America/Mexico_City',
                    'doctor_id': doctor_id,
                    'payment_info': {
                        'payment_required': account.get('stripe_enabled', False),
                        'price': account.get('appointment_price', 0) / 100,
                        'currency': account.get('currency', 'MXN')
                    }
                }
            })
        
    except Exception as e:
        logger.error(f"Error fetching availability for doctor {doctor_id}: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error fetching availability'
        }), 500

@directory_bp.route('/appointments', methods=['POST'])
def create_appointment():
    """Create a new appointment"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = [
            'doctor_id', 'patient_name', 'patient_email',
            'patient_phone', 'appointment_date', 'appointment_time'
        ]
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Validate email and phone
        if not validate_email(data['patient_email']):
            return jsonify({
                'success': False,
                'message': 'Invalid email format'
            }), 400
            
        if not validate_phone(data['patient_phone']):
            return jsonify({
                'success': False,
                'message': 'Invalid phone format'
            }), 400
        
        # Get doctor profile and account
        directory_service = DirectoryService()
        try:
            doctor = directory_service.get_doctor_details(data['doctor_id'])
        except ResourceNotFoundError:
            return jsonify({
                'success': False,
                'message': 'Doctor not found'
            }), 404
        
        # Get account for GHL integration
        account_service = AccountService()
        account = account_service.get_account(doctor.get('account_id', data['doctor_id']))
        
        # Create appointment in GHL if configured
        ghl_service = GHLService(data['doctor_id'])
        
        appointment_data = {
            'calendarId': account.get('ghl_calendar_id'),
            'selectedTimezone': account.get('timezone', 'America/Mexico_City'),
            'selectedSlot': f"{data['appointment_date']} {data['appointment_time']}",
            'name': data['patient_name'],
            'email': data['patient_email'],
            'phone': data['patient_phone'],
            'notes': data.get('reason', ''),
            'source': 'vitalis_connect'
        }
        
        # Try to create in GHL
        try:
            ghl_response = ghl_service.create_appointment(appointment_data)
            appointment_id = ghl_response.get('id') if ghl_response else None
        except Exception as e:
            logger.error(f"Error creating GHL appointment: {str(e)}")
            appointment_id = None
        
        # Save appointment to Firestore
        appointment_doc = {
            'doctor_id': data['doctor_id'],
            'patient_name': data['patient_name'],
            'patient_email': data['patient_email'],
            'patient_phone': data['patient_phone'],
            'appointment_date': data['appointment_date'],
            'appointment_time': data['appointment_time'],
            'reason': data.get('reason', ''),
            'status': 'confirmed' if appointment_id else 'pending',
            'ghl_appointment_id': appointment_id,
            'source': 'vitalis_connect',
            'payment_required': account.get('stripe_enabled', False),
            'payment_status': 'pending' if account.get('stripe_enabled', False) else None,
            'created_at': datetime.now().isoformat()
        }
        
        appointment_ref = db.collection('appointments').add(appointment_doc)
        appointment_doc['id'] = appointment_ref[1].id
        
        # TODO: Send confirmation email/SMS
        
        return jsonify({
            'success': True,
            'data': appointment_doc,
            'message': 'Appointment created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating appointment: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error creating appointment'
        }), 500

@directory_bp.route('/verify-recaptcha', methods=['POST'])
def verify_recaptcha():
    """Verify reCAPTCHA token"""
    try:
        import requests
        
        data = request.get_json()
        token = data.get('token')
        
        if not token:
            return jsonify({
                'success': False,
                'message': 'Missing reCAPTCHA token'
            }), 400
        
        # Verify with Google
        secret_key = os.environ.get('RECAPTCHA_SECRET_KEY', '')
        if not secret_key:
            logger.warning("reCAPTCHA secret key not configured")
            # Return success for development
            return jsonify({
                'success': True,
                'score': 1.0
            })
        
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': secret_key,
                'response': token
            }
        )
        
        result = response.json()
        
        if result.get('success') and result.get('score', 0) > 0.5:
            return jsonify({
                'success': True,
                'score': result.get('score', 1.0)
            })
        else:
            return jsonify({
                'success': False,
                'message': 'reCAPTCHA verification failed'
            }), 400
            
    except Exception as e:
        logger.error(f"Error verifying reCAPTCHA: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error verifying reCAPTCHA'
        }), 500

@directory_bp.route('/analytics', methods=['POST'])
def track_analytics():
    """Track directory analytics events"""
    try:
        data = request.get_json()
        
        # Save event to Firestore
        db = get_firestore_client()
        event = {
            'type': data.get('type'),
            'data': data.get('data', {}),
            'timestamp': datetime.now().isoformat(),
            'source': 'vitalis_connect'
        }
        
        db.collection('directory_analytics').add(event)
        
        return jsonify({
            'success': True,
            'message': 'Event tracked successfully'
        })
        
    except Exception as e:
        logger.error(f"Error tracking analytics: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error tracking event'
        }), 500

@directory_bp.route('/bookings/create', methods=['POST'])
def create_booking():
    """Create a new booking with conditional payment"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['doctor_id', 'patient_info', 'appointment_datetime']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        patient_info = data['patient_info']
        
        # Validate patient info
        if not all(k in patient_info for k in ['name', 'email', 'phone']):
            return jsonify({
                'success': False,
                'message': 'Patient info must include name, email, and phone'
            }), 400
        
        if not validate_email(patient_info['email']):
            return jsonify({
                'success': False,
                'message': 'Invalid email format'
            }), 400
        
        if not validate_phone(patient_info['phone']):
            return jsonify({
                'success': False,
                'message': 'Invalid phone format'
            }), 400
        
        # Get directory profile first to find the account
        db = get_firestore_client()
        directory_doc = db.collection('directory_profiles').document(data['doctor_id']).get()
        
        if not directory_doc.exists:
            return jsonify({
                'success': False,
                'message': 'Doctor not found'
            }), 404
        
        directory_profile = directory_doc.to_dict()
        account_id = directory_profile.get('account_id')
        
        if not account_id:
            return jsonify({
                'success': False,
                'message': 'Account not configured'
            }), 400
        
        # Get account
        account_doc = db.collection('accounts').document(account_id).get()
        if not account_doc.exists:
            return jsonify({
                'success': False,
                'message': 'Account not found'
            }), 404
            
        account = account_doc.to_dict()
        
        # Parse appointment datetime for formatting
        appointment_dt = datetime.fromisoformat(data['appointment_datetime'])
        tz = pytz.timezone('America/Mexico_City')
        if appointment_dt.tzinfo is None:
            appointment_dt = tz.localize(appointment_dt)
        
        # Format appointment date and time
        months_es = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 
                    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        days_es = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
        appointment_date = appointment_dt.strftime('%d de ') + months_es[appointment_dt.month - 1] + appointment_dt.strftime(' de %Y')
        appointment_time = appointment_dt.strftime('%I:%M %p').replace('AM', 'a.m.').replace('PM', 'p.m.')
        appointment_day = days_es[appointment_dt.weekday()]
        
        # Create booking using centralized service
        booking_service = BookingService()
        booking = booking_service.create_booking(
            doctor_id=data['doctor_id'],
            patient_info=patient_info,
            appointment_datetime=appointment_dt,
            appointment_time=appointment_time,
            appointment_date=f"{appointment_day}, {appointment_date}",
            source="vitalis-connect",
            payment_required=account.get('stripe_enabled', False),
            calendar_id=account.get('calendar_id'),
            doctor_name=directory_profile.get('full_name', account.get('name', 'Doctor')),
            location=directory_profile.get('office_address'),
            specialty=directory_profile.get('specialty'),
            consultation_price=account.get('appointment_price') if account.get('stripe_enabled') else None,
            metadata={
                'reason': patient_info.get('reason', ''),
                'account_id': account_id
            }
        )
        booking_id = booking.id
        
        # Verify slot is still available before proceeding
        from app.integrations.ghl.client import GoHighLevelClient
        ghl_client = GoHighLevelClient()
        
        # Check slot availability
        start_timestamp = int(appointment_dt.timestamp() * 1000)
        end_timestamp = start_timestamp + (60 * 60 * 1000)  # 1 hour window
        
        # Get current blocked slots
        blocked_slots = ghl_client.get_blocked_slots(
            account_id=account_id,
            calendar_id=account.get('calendar_id'),
            start_time=start_timestamp,
            end_time=end_timestamp,
            location_id=account.get('location_id'),
            user_id=account.get('assigned_user_id')
        )
        
        # Check if the requested time is already blocked
        requested_time = appointment_dt.strftime('%H:%M')
        for event in blocked_slots:
            event_start = event.get('startTime')
            if event_start:
                try:
                    blocked_dt = datetime.fromisoformat(event_start)
                    blocked_local = blocked_dt.astimezone(tz)
                    if blocked_local.strftime('%H:%M') == requested_time:
                        return jsonify({
                            'success': False,
                            'message': 'Lo sentimos, ese horario ya no está disponible. Por favor selecciona otro horario.'
                        }), 400
                except Exception as e:
                    logger.warning(f"Error parsing blocked slot time '{event_start}': {e}")
        
        # If payment is required, create Stripe checkout session
        if account.get('stripe_enabled') and account.get('stripe_charges_enabled'):
            from app.services.stripe_service import StripeService
            from app.models.account import Account
            
            # Debug logging
            logger.info(f"[DEBUG] Account stripe_connect_account_id: {account.get('stripe_connect_account_id')}")
            logger.info(f"[DEBUG] Account stripe_enabled: {account.get('stripe_enabled')}")
            logger.info(f"[DEBUG] Account stripe_charges_enabled: {account.get('stripe_charges_enabled')}")
            
            stripe_service = StripeService()
            account_model = Account.from_dict(account)
            
            # Create payment checkout session
            payment_result = stripe_service.create_checkout_session(
                account=account_model,
                conversation_id=booking_id,  # Use booking ID as reference
                customer_name=patient_info['name'],
                customer_phone=patient_info['phone'],
                success_url=f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/booking/{booking_id}/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/booking/{booking_id}/cancel",
                metadata={
                    'booking_id': booking_id,
                    'source': 'vitalis-connect'
                }
            )
            
            # Update booking with payment info
            booking_service.link_payment_to_booking(
                booking_id=booking_id,
                payment_id=payment_result.id,
                payment_status='pending'
            )
            
            return jsonify({
                'success': True,
                'booking_id': booking_id,
                'requires_payment': True,
                'payment_url': payment_result.payment_link,
                'amount': payment_result.amount,
                'currency': payment_result.currency
            })
        else:
            # No payment required, create appointment directly
            from app.integrations.ghl.client import GoHighLevelClient
            ghl_client = GoHighLevelClient()
            
            # Parse appointment datetime
            appointment_dt = datetime.fromisoformat(data['appointment_datetime'])
            end_dt = appointment_dt + timedelta(minutes=50)
            
            try:
                # Create contact in GHL
                contact = ghl_client.create_contact(
                    account_id=account_id,
                    location_id=account['location_id'],
                    name=patient_info['name'],
                    phone=patient_info['phone'],
                    email=patient_info['email'],
                    reason=patient_info.get('reason', ''),
                    source='Vitalis Connect'
                )
                
                # Create appointment in GHL
                appointment = ghl_client.create_appointment(
                    account_id=account_id,
                    calendar_id=account['calendar_id'],
                    location_id=account['location_id'],
                    contact_id=contact['id'],
                    assigned_user_id=account['assigned_user_id'],
                    start_time=appointment_dt.isoformat(),
                    end_time=end_dt.isoformat(),
                    title=f"Cita: {patient_info.get('reason', 'Consulta')}"
                )
                
                # Update booking with appointment info
                booking_service.link_appointment_to_booking(
                    booking_id=booking_id,
                    appointment_id=appointment.get('id')
                )
                booking_service.update_booking(
                    booking_id=booking_id,
                    contact_id=contact['id']
                )
                
                # Send WhatsApp confirmation for non-payment bookings
                try:
                    # Get doctor profile for doctor name
                    doctor_doc = db.collection('directory_profiles').document(data['doctor_id']).get()
                    doctor_profile = doctor_doc.to_dict() if doctor_doc.exists else {}
                    
                    # Date and time already formatted above
                    
                    # Create confirmation message
                    confirmation_message = f"""✅ *¡Cita confirmada!*

Hola {patient_info['name']} 👋

Tu cita ha sido agendada exitosamente:

📅 *Fecha:* {appointment_day}, {appointment_date}
🕐 *Hora:* {appointment_time}
👨‍⚕️ *Doctor:* {doctor_profile.get('full_name', account.get('name', 'Doctor'))}
📍 *Ubicación:* {doctor_profile.get('office_address', 'Dirección no disponible')}

*Importante:*
• Llega 10 minutos antes
• Trae tu identificación
• Si necesitas cancelar, hazlo con 24 horas de anticipación

¿Tienes alguna pregunta? Responde a este mensaje.

Gracias por confiar en nosotros 🙏"""
                    
                    # Send WhatsApp template message
                    if account.get('phone_number_id'):
                        whatsapp_template_service = WhatsAppTemplateService()
                        whatsapp_template_service.send_appointment_confirmation_template(
                            phone_number_id=account['phone_number_id'],
                            to_number=patient_info['phone'],
                            patient_name=patient_info['name'],
                            doctor_name=doctor_profile.get('full_name', account.get('name', 'Doctor')),
                            appointment_date=f"{appointment_day}, {appointment_date}",
                            appointment_time=appointment_time,
                            location=doctor_profile.get('office_address', 'Dirección no disponible')
                        )
                        logger.info(f"WhatsApp template confirmation sent for non-payment booking {booking_id} to {patient_info['phone']}")
                    else:
                        logger.warning(f"No WhatsApp phone_number_id configured for account {account_id}")
                        
                except Exception as e:
                    # Don't fail the appointment creation if WhatsApp fails
                    logger.error(f"Error sending WhatsApp confirmation for non-payment booking: {str(e)}")
                
                return jsonify({
                    'success': True,
                    'booking_id': booking_id,
                    'requires_payment': False,
                    'appointment_id': appointment.get('id')
                })
                
            except Exception as e:
                logger.error(f"Error creating GHL appointment: {str(e)}")
                # Still return success but mark as pending
                db.collection('bookings').document(booking_id).update({
                    'status': 'pending_ghl_creation',
                    'error': str(e)
                })
                
                return jsonify({
                    'success': True,
                    'booking_id': booking_id,
                    'requires_payment': False,
                    'warning': 'Appointment creation pending, we will contact you to confirm'
                })
        
    except Exception as e:
        logger.error(f"Error creating booking: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error creating booking'
        }), 500

@directory_bp.route('/bookings/<booking_id>/payment-success', methods=['POST'])
def handle_payment_success(booking_id):
    """Handle successful payment and create appointment"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        payment_intent_id = data.get('payment_intent_id')  # Keep for backward compatibility
        
        if not session_id and not payment_intent_id:
            return jsonify({
                'success': False,
                'message': 'Missing session_id or payment_intent_id'
            }), 400
        
        # Get booking
        db = get_firestore_client()
        booking_doc = db.collection('bookings').document(booking_id).get()
        
        if not booking_doc.exists:
            return jsonify({
                'success': False,
                'message': 'Booking not found'
            }), 404
        
        booking = booking_doc.to_dict()
        
        # Log booking data for debugging
        logger.info(f"Processing payment confirmation for booking {booking_id}: {booking}")
        
        # Check payment status if payment was required
        if booking.get('payment_required') and booking.get('payment_status') != 'completed':
            logger.warning(f"Payment not yet completed for booking {booking_id}. Status: {booking.get('payment_status')}")
            return jsonify({
                'success': False,
                'message': 'El pago aún no ha sido confirmado. Por favor espera un momento.',
                'retry': True  # Tell frontend to retry
            }), 202  # 202 Accepted - processing
        
        # Check if appointment already created (idempotency)
        if booking.get('appointment_id'):
            logger.info(f"Appointment already created for booking {booking_id}")
            return jsonify({
                'success': True,
                'appointment_id': booking.get('appointment_id'),
                'details': {
                    'datetime': booking.get('appointment_datetime'),
                    'doctor_name': 'Doctor',
                    'patient_name': booking.get('patient_info', {}).get('name', 'Patient')
                }
            })
        
        # Get directory profile to find account
        directory_doc = db.collection('directory_profiles').document(booking['doctor_id']).get()
        if not directory_doc.exists:
            return jsonify({
                'success': False,
                'message': 'Doctor not found'
            }), 404
        
        directory_profile = directory_doc.to_dict()
        account_id = directory_profile.get('account_id')
        
        # Get doctor's account
        account_doc = db.collection('accounts').document(account_id).get()
        account = account_doc.to_dict()
        
        # Create appointment in GHL
        from app.integrations.ghl.client import GoHighLevelClient
        ghl_client = GoHighLevelClient()
        
        patient_info = booking['patient_info']
        appointment_dt = datetime.fromisoformat(booking['appointment_datetime'])
        tz = pytz.timezone('America/Mexico_City')
        if appointment_dt.tzinfo is None:
            appointment_dt = tz.localize(appointment_dt)
        
        # Double-check slot is still available before creating appointment
        start_timestamp = int(appointment_dt.timestamp() * 1000)
        end_timestamp = start_timestamp + (60 * 60 * 1000)
        
        blocked_slots = ghl_client.get_blocked_slots(
            account_id=account_id,
            calendar_id=account.get('calendar_id'),
            start_time=start_timestamp,
            end_time=end_timestamp,
            location_id=account.get('location_id'),
            user_id=account.get('assigned_user_id')
        )
        
        # Verify slot is not blocked
        requested_time = appointment_dt.strftime('%H:%M')
        for event in blocked_slots:
            event_start = event.get('startTime')
            if event_start:
                try:
                    blocked_dt = datetime.fromisoformat(event_start)
                    blocked_local = blocked_dt.astimezone(tz)
                    if blocked_local.strftime('%H:%M') == requested_time:
                        # Slot was booked while payment was processing
                        logger.warning(f"Slot became unavailable during payment for booking {booking_id}")
                        db.collection('bookings').document(booking_id).update({
                            'status': 'slot_unavailable',
                            'error': 'Slot became unavailable during payment processing'
                        })
                        return jsonify({
                            'success': False,
                            'message': 'Lo sentimos, el horario seleccionado ya no está disponible. Te contactaremos para reprogramar tu cita.'
                        }), 400
                except Exception as e:
                    logger.warning(f"Error parsing blocked slot time '{event_start}': {e}")
        
        end_dt = appointment_dt + timedelta(minutes=50)
        
        try:
            # Create contact in GHL
            contact = ghl_client.create_contact(
                account_id=account_id,
                location_id=account['location_id'],
                name=patient_info['name'],
                phone=patient_info['phone'],
                email=patient_info['email'],
                reason=patient_info.get('reason', ''),
                source='Vitalis Connect'
            )
            
            # Create appointment in GHL
            appointment = ghl_client.create_appointment(
                account_id=account_id,
                calendar_id=account['calendar_id'],
                location_id=account['location_id'],
                contact_id=contact['id'],
                assigned_user_id=account['assigned_user_id'],
                start_time=appointment_dt.isoformat(),
                end_time=end_dt.isoformat(),
                title=f"Cita: {patient_info.get('reason', 'Consulta')}"
            )
            
            # Update booking using booking service
            booking_service.link_appointment_to_booking(
                booking_id=booking_id,
                appointment_id=appointment.get('id')
            )
            booking_service.update_booking(
                booking_id=booking_id,
                payment_status='completed',
                contact_id=contact['id'],
                confirmed_at=datetime.now().isoformat()
            )
            logger.info(f"Booking {booking_id} confirmed with appointment {appointment.get('id')}")
            
            # Send WhatsApp confirmation
            try:
                # Get directory profile for doctor name and address
                directory_profile = directory_doc.to_dict()
                
                # Format appointment date and time in Spanish
                months_es = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 
                            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
                days_es = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
                
                appointment_date = appointment_dt.strftime('%d de ') + months_es[appointment_dt.month - 1] + appointment_dt.strftime(' de %Y')
                appointment_time = appointment_dt.strftime('%I:%M %p').replace('AM', 'a.m.').replace('PM', 'p.m.')
                appointment_day = days_es[appointment_dt.weekday()]
                
                # Create confirmation message
                confirmation_message = f"""✅ *¡Cita confirmada!*

Hola {patient_info['name']} 👋

Tu cita ha sido agendada exitosamente:

📅 *Fecha:* {appointment_day}, {appointment_date}
🕐 *Hora:* {appointment_time}
👨‍⚕️ *Doctor:* {directory_profile.get('full_name', account.get('name', 'Doctor'))}
📍 *Ubicación:* {directory_profile.get('office_address', 'Dirección no disponible')}

*Importante:*
• Llega 10 minutos antes
• Trae tu identificación
• Si necesitas cancelar, hazlo con 24 horas de anticipación

¿Tienes alguna pregunta? Responde a este mensaje.

Gracias por confiar en nosotros 🙏"""
                
                # Send WhatsApp template message
                if account.get('phone_number_id'):
                    whatsapp_template_service = WhatsAppTemplateService()
                    whatsapp_template_service.send_appointment_confirmation_template(
                        phone_number_id=account['phone_number_id'],
                        to_number=patient_info['phone'],
                        patient_name=patient_info['name'],
                        doctor_name=directory_profile.get('full_name', account.get('name', 'Doctor')),
                        appointment_date=f"{appointment_day}, {appointment_date}",
                        appointment_time=appointment_time,
                        location=directory_profile.get('office_address', 'Dirección no disponible')
                    )
                    logger.info(f"WhatsApp template confirmation sent for booking {booking_id} to {patient_info['phone']}")
                else:
                    logger.warning(f"No WhatsApp phone_number_id configured for account {account_id}")
                    
            except Exception as e:
                # Don't fail the appointment creation if WhatsApp fails
                logger.error(f"Error sending WhatsApp confirmation: {str(e)}")
            
            return jsonify({
                'success': True,
                'appointment_id': appointment.get('id'),
                'details': {
                    'datetime': appointment_dt.isoformat(),
                    'doctor_name': account.get('name', 'Doctor'),
                    'patient_name': patient_info['name']
                }
            })
            
        except Exception as e:
            logger.error(f"Error creating appointment after payment: {str(e)}")
            return jsonify({
                'success': False,
                'message': 'Error creating appointment, please contact support'
            }), 500
            
    except Exception as e:
        logger.error(f"Error handling payment success: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error processing payment confirmation'
        }), 500

@directory_bp.route('/bookings/<booking_id>/payment-cancel', methods=['POST'])
def handle_payment_cancel(booking_id):
    """Handle payment cancellation"""
    try:
        # Update booking status
        db = get_firestore_client()
        db.collection('bookings').document(booking_id).update({
            'status': 'payment_cancelled',
            'cancelled_at': datetime.now().isoformat()
        })
        
        return jsonify({
            'success': True,
            'message': 'Booking cancelled'
        })
        
    except Exception as e:
        logger.error(f"Error handling payment cancel: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Error cancelling booking'
        }), 500

@directory_bp.route('/stripe/webhook', methods=['POST'])
def handle_stripe_webhook():
    """Handle Stripe webhook events for Vitalis Connect payments"""
    try:
        import stripe
        
        # Get the webhook signature
        sig_header = request.headers.get('Stripe-Signature')
        if not sig_header:
            return jsonify({'error': 'No signature'}), 400
        
        # Get webhook secret from config
        webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET_CONNECT')
        if not webhook_secret:
            logger.error("Stripe webhook secret not configured for Connect")
            return jsonify({'error': 'Webhook secret not configured'}), 400
        
        # Verify webhook signature
        try:
            event = stripe.Webhook.construct_event(
                request.data, sig_header, webhook_secret
            )
        except ValueError:
            # Invalid payload
            return jsonify({'error': 'Invalid payload'}), 400
        except stripe.error.SignatureVerificationError:
            # Invalid signature
            return jsonify({'error': 'Invalid signature'}), 400
        
        # Handle checkout.session.completed event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            
            # Find the booking by payment ID (stored in session metadata)
            booking_id = session.get('metadata', {}).get('booking_id')
            if not booking_id:
                # Try to find by client_reference_id (backward compatibility)
                booking_id = session.get('client_reference_id')
            
            if not booking_id:
                logger.error("No booking ID found in checkout session")
                return jsonify({'error': 'No booking ID'}), 400
            
            db = get_firestore_client()
            
            # Get booking
            booking_doc = db.collection('bookings').document(booking_id).get()
            if not booking_doc.exists:
                logger.error(f"Booking {booking_id} not found")
                return jsonify({'error': 'Booking not found'}), 404
            
            booking = booking_doc.to_dict()
            
            # Get payment ID from booking (it should already exist from the main webhook)
            payment_id = booking.get('payment_id')
            if not payment_id:
                # Payment ID from metadata as fallback
                payment_id = session.get('metadata', {}).get('payment_id')
            
            # Update booking with payment completion info
            db.collection('bookings').document(booking_id).update({
                'payment_status': 'completed',
                'payment_id': payment_id,
                'updated_at': datetime.now().isoformat()  # Use updated_at instead of paid_at
            })
            
            logger.info(f"Payment {payment_id} completed for booking {booking_id}")
            
            # Create appointment if not already created
            if not booking.get('appointment_id'):
                try:
                    # Get directory profile to find account
                    directory_doc = db.collection('directory_profiles').document(booking['doctor_id']).get()
                    if not directory_doc.exists:
                        logger.error(f"Doctor not found for booking {booking_id}")
                        return jsonify({'success': True})  # Still return success for webhook
                    
                    directory_profile = directory_doc.to_dict()
                    account_id = directory_profile.get('account_id')
                    
                    # Get doctor's account
                    account_doc = db.collection('accounts').document(account_id).get()
                    account = account_doc.to_dict()
                    
                    # Create appointment in GHL
                    from app.integrations.ghl.client import GoHighLevelClient
                    ghl_client = GoHighLevelClient()
                    
                    patient_info = booking['patient_info']
                    appointment_dt = datetime.fromisoformat(booking['appointment_datetime'])
                    tz = pytz.timezone('America/Mexico_City')
                    if appointment_dt.tzinfo is None:
                        appointment_dt = tz.localize(appointment_dt)
                    
                    end_dt = appointment_dt + timedelta(minutes=50)
                    
                    # Create contact in GHL
                    contact = ghl_client.create_contact(
                        account_id=account_id,
                        location_id=account['location_id'],
                        name=patient_info['name'],
                        phone=patient_info['phone'],
                        email=patient_info['email'],
                        reason=patient_info.get('reason', ''),
                        source='Vitalis Connect'
                    )
                    
                    # Create appointment in GHL
                    appointment = ghl_client.create_appointment(
                        account_id=account_id,
                        calendar_id=account['calendar_id'],
                        location_id=account['location_id'],
                        contact_id=contact['id'],
                        assigned_user_id=account['assigned_user_id'],
                        start_time=appointment_dt.isoformat(),
                        end_time=end_dt.isoformat(),
                        title=f"Cita: {patient_info.get('reason', 'Consulta')}"
                    )
                    
                    # Update booking with appointment info
                    booking_service.link_appointment_to_booking(
                        booking_id=booking_id,
                        appointment_id=appointment.get('id')
                    )
                    booking_service.update_booking(
                        booking_id=booking_id,
                        contact_id=contact['id'],
                        confirmed_at=datetime.now().isoformat()
                    )
                    
                    logger.info(f"Appointment {appointment.get('id')} created via webhook for booking {booking_id}")
                    
                    # Send WhatsApp confirmation if account has WhatsApp enabled
                    if account.get('phone_number_id'):
                        try:
                            whatsapp_template_service = WhatsAppTemplateService()
                            whatsapp_template_service.send_appointment_confirmation_template(
                                phone_number_id=account['phone_number_id'],
                                to_number=patient_info['phone'],
                                patient_name=patient_info['name'],
                                doctor_name=directory_profile.get('name', 'Doctor'),
                                appointment_date=appointment_dt.strftime('%d de %B, %Y'),
                                appointment_time=appointment_dt.strftime('%I:%M %p'),
                                clinic_address=directory_profile.get('address', 'Dirección no especificada')
                            )
                            logger.info(f"WhatsApp confirmation sent for booking {booking_id}")
                        except Exception as e:
                            logger.error(f"Error sending WhatsApp confirmation: {str(e)}")
                    
                except Exception as e:
                    logger.error(f"Error creating appointment in webhook: {str(e)}")
                    # Don't fail the webhook - payment was successful
            
            return jsonify({'success': True})
        
        # Return success for other event types
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error handling Stripe webhook: {str(e)}")
        return jsonify({'error': 'Webhook processing failed'}), 500