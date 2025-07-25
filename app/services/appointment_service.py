"""Service for managing appointments."""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import pytz
import firebase_admin
from firebase_admin import firestore
from app.utils.phone_utils import normalize_phone, format_phone_for_ghl
from app.models.account import Account
from app.models.appointment import AppointmentInfo
from app.models.booking import Booking
from app.integrations.llm.client import LLMClient
from app.integrations.ghl.client import GoHighLevelClient
from app.services.conversation_service import ConversationService
from app.services.booking_service import BookingService
from app.core.exceptions import VitalisException, ExternalServiceError
from app.core.logging import get_logger
from app.core.config import get_config
from app.utils.firebase import get_firestore_client

logger = get_logger(__name__)


class AppointmentService:
    """Service for appointment business logic."""
    
    def __init__(self):
        self.llm_client = LLMClient()
        self.ghl_client = GoHighLevelClient()
        self.conversation_service = ConversationService()
        self.booking_service = BookingService()
        self.config = get_config()
        self.db = get_firestore_client()
        # Lazy import to avoid circular dependencies
        self.stripe_service = None
    
    def _to_local_timezone(self, dt: datetime) -> datetime:
        """Convert datetime to local timezone (Mexico City) consistently."""
        tz = pytz.timezone(self.config.timezone)
        
        if dt.tzinfo is not None:
            # Has timezone info, convert to local timezone
            return dt.astimezone(tz)
        else:
            # No timezone info, assume it's already in local timezone
            return tz.localize(dt)
    
    def _format_datetime_spanish(self, dt: datetime) -> tuple[str, str]:
        """Format datetime in Spanish with consistent timezone handling."""
        local_dt = self._to_local_timezone(dt)
        
        # Spanish month names
        months = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
            5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
            9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
        }
        
        date_str = f"{local_dt.day} de {months[local_dt.month]} de {local_dt.year}"
        time_str = local_dt.strftime("%I:%M %p")
        
        return date_str, time_str
    
    def process_message(
        self,
        conversation_id: str,
        account: Account,
        contact_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a message for appointment scheduling."""
        try:
            # Get conversation history
            conversation = self.conversation_service.repository.get(conversation_id)
            if not conversation:
                raise VitalisException(f"Conversation not found: {conversation_id}")
            
            # Get messages for LLM
            messages = conversation.get_messages_for_llm()
            
            # Generate response using LLM
            response = self.llm_client.process_conversation(
                messages=messages,
                system_prompt=self._get_system_prompt(account)
            )
            
            # Format conversation for extraction
            conversation_text = self._format_conversation_for_extraction(messages)
            
            # Extract customer name independently of appointment info
            extracted_name = self.llm_client.extract_customer_name(conversation_text)
            if extracted_name and not contact_name:
                contact_name = extracted_name
                logger.info(f"Extracted customer name from conversation: {extracted_name}")
            
            # Create/update contact as soon as we have a name
            if contact_name:
                self._create_or_update_contact(
                    account=account,
                    conversation_id=conversation_id,
                    name=contact_name,
                    phone=conversation.phone_number
                )
            
            # Check if we have complete appointment information
            appointment_info = self.llm_client.extract_appointment_info(
                conversation_text=conversation_text,
                custom_prompt=account.custom_prompt
            )
            
            if appointment_info and appointment_info.get("has_appointment_info"):
                # Use WhatsApp contact name as fallback if LLM didn't extract name
                if not appointment_info.get("name") and contact_name:
                    appointment_info["name"] = contact_name
                    logger.info(f"Using WhatsApp contact profile name as fallback: {contact_name}")
                
                # Update contact with appointment-specific information
                if appointment_info.get("email") or appointment_info.get("reason"):
                    self._create_or_update_contact(
                        account=account,
                        conversation_id=conversation_id,
                        name=appointment_info.get("name") or contact_name,
                        phone=conversation.phone_number,
                        email=appointment_info.get("email"),
                        reason=appointment_info.get("reason")
                    )
                
                # Validate and format appointment info
                formatted_info = self._format_appointment_info(appointment_info)
                
                if formatted_info:
                    # Check slot availability
                    appointment_dt = datetime.fromisoformat(formatted_info["datetime"])
                    availability_check = self.check_slot_availability(account, appointment_dt)
                    
                    # Add availability info to formatted_info
                    formatted_info["availability"] = availability_check
                    
                    # Create booking record for WhatsApp appointment
                    booking = self.booking_service.create_booking(
                        doctor_id=account.id,
                        patient_info={
                            "name": formatted_info.get("name") or contact_name or "Cliente",
                            "phone": conversation.phone_number,
                            "email": formatted_info.get("email")
                        },
                        appointment_datetime=appointment_dt,
                        appointment_time=formatted_info.get("time", ""),
                        appointment_date=formatted_info.get("date", ""),
                        source="vitalis-whatsapp",
                        payment_required=account.stripe_enabled,
                        calendar_id=account.calendar_id,
                        doctor_name=account.name,
                        location=account.location_id,
                        consultation_price=account.appointment_price if account.stripe_enabled else None,
                        metadata={
                            "reason": formatted_info.get("reason"),
                            "conversation_id": conversation_id
                        }
                    )
                    
                    # Update conversation context with booking ID
                    self.conversation_service.update_appointment_info(
                        conversation_id=conversation_id,
                        appointment_info={
                            **formatted_info,
                            "booking_id": booking.id
                        },
                        awaiting_confirmation=True
                    )
                    
                    # Generate confirmation message (will include alternatives if needed)
                    confirmation_msg = self._generate_confirmation_message(formatted_info)
                    
                    return {
                        "type": "confirmation",
                        "message": confirmation_msg,
                        "appointment_info": formatted_info
                    }
            
            # Regular conversation response
            return {
                "type": "text",
                "message": response
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                "type": "text",
                "message": "Lo siento, hubo un error procesando tu mensaje. Por favor intenta nuevamente."
            }
    
    def _validate_stripe_account(self, account: Account) -> Dict[str, Any]:
        """Validate if Stripe account is ready for payments."""
        if not account.stripe_enabled:
            return {
                "is_valid": False,
                "message": "Stripe payments are not enabled for this account"
            }
        
        if not account.stripe_connect_account_id:
            return {
                "is_valid": False,
                "message": "No Stripe Connect account linked"
            }
        
        if not account.stripe_onboarding_completed:
            return {
                "is_valid": False,
                "message": "Stripe onboarding is not completed"
            }
        
        if not account.stripe_charges_enabled:
            return {
                "is_valid": False,
                "message": "Stripe charges are not enabled yet"
            }
        
        return {
            "is_valid": True,
            "message": "Stripe account is ready"
        }
    
    def create_payment_for_appointment(
        self,
        conversation_id: str,
        account: Account
    ) -> Dict[str, Any]:
        """Create payment checkout session for appointment."""
        try:
            # Validate Stripe account is ready
            validation = self._validate_stripe_account(account)
            if not validation["is_valid"]:
                return {
                    "success": False,
                    "error": validation["message"]
                }
            
            # Lazy import
            if not self.stripe_service:
                from app.services.stripe_service import StripeService
                self.stripe_service = StripeService()
            
            # Get conversation
            conversation = self.conversation_service.repository.get(conversation_id)
            if not conversation or not conversation.context.appointment_info:
                raise VitalisException("No appointment information found")
            
            appointment_info = conversation.context.appointment_info
            
            # Create payment with source tracking
            payment = self.stripe_service.create_checkout_session(
                account=account,
                conversation_id=conversation_id,
                customer_name=appointment_info["name"],
                customer_phone=conversation.phone_number,
                success_url=f"{self.config.callback_uri}/payment/success?conversation_id={conversation_id}",
                cancel_url=f"{self.config.callback_uri}/payment/cancel?conversation_id={conversation_id}",
                metadata={
                    "source": "vitalis-whatsapp",
                    "booking_id": appointment_info.get("booking_id")
                }
            )
            
            # Link payment to booking
            if appointment_info.get("booking_id"):
                self.booking_service.link_payment_to_booking(
                    booking_id=appointment_info["booking_id"],
                    payment_id=payment.id,
                    payment_status="pending"
                )
            
            # Store payment ID in conversation context
            self.conversation_service.update_appointment_info(
                conversation_id=conversation_id,
                appointment_info={
                    **appointment_info,
                    "payment_id": payment.id,
                    "payment_status": "pending"
                },
                awaiting_confirmation=True
            )
            
            return {
                "success": True,
                "payment_link": payment.payment_link,
                "payment_id": payment.id,
                "amount": payment.amount,
                "currency": payment.currency
            }
            
        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def confirm_and_create_appointment(
        self,
        conversation_id: str,
        account: Account,
        payment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Confirm and create appointment in GoHighLevel."""
        try:
            # Get conversation
            conversation = self.conversation_service.repository.get(conversation_id)
            if not conversation or not conversation.context.appointment_info:
                raise VitalisException("No appointment information found")
            
            appointment_info = conversation.context.appointment_info
            
            # If Stripe is enabled and payment is required, verify payment
            if account.stripe_enabled and not payment_id:
                # Check if payment was completed
                payment_status = appointment_info.get("payment_status")
                if payment_status != "completed":
                    raise VitalisException("Payment not completed")
            
            # Get existing contact or create if not exists
            contact_id = conversation.context.metadata.get("contact_id") if conversation.context.metadata else None
            
            if contact_id:
                # Use existing contact
                logger.info(f"Using existing contact {contact_id} for appointment")
                contact = {"id": contact_id}
            else:
                # Create contact if not exists (fallback)
                logger.info("No existing contact found, creating new one")
                # Normalize phone for GHL
                normalized_phone = normalize_phone(conversation.phone_number)
                ghl_phone = format_phone_for_ghl(normalized_phone)
                
                contact = self.ghl_client.create_contact(
                    account_id=account.id,
                    location_id=account.location_id,
                    name=appointment_info["name"],
                    phone=ghl_phone,
                    email=appointment_info.get("email"),
                    reason=appointment_info.get("reason")
                )
            
            # Parse datetime and calculate end time
            start_time = datetime.fromisoformat(appointment_info["datetime"])
            
            # Ensure timezone is set properly
            if start_time.tzinfo is None:
                tz = pytz.timezone(self.config.timezone)
                start_time = tz.localize(start_time)
            
            end_time = start_time + timedelta(minutes=50)  # 50-minute appointments
            
            logger.info(f"Creating appointment: start={start_time.isoformat()}, end={end_time.isoformat()}")
            
            # Create appointment in GHL
            appointment = self.ghl_client.create_appointment(
                account_id=account.id,
                calendar_id=account.calendar_id,
                location_id=account.location_id,
                contact_id=contact["id"],
                assigned_user_id=account.assigned_user_id,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                title=f"Cita: {appointment_info['reason']}"
            )
            
            # Update booking with appointment ID
            if appointment_info.get("booking_id"):
                self.booking_service.link_appointment_to_booking(
                    booking_id=appointment_info["booking_id"],
                    appointment_id=appointment.get("id")
                )
            
            # Mark conversation as completed
            self.conversation_service.confirm_appointment(conversation_id)
            
            # Format appointment details for user using standardized formatting
            date_str, time_str = self._format_datetime_spanish(start_time)
            
            details = (
                f"Fecha: {date_str}\n"
                f"Hora: {time_str}\n"
                f"Motivo: {appointment_info['reason']}"
            )
            
            return {
                "success": True,
                "appointment_id": appointment.get("id"),
                "details": details
            }
            
        except ExternalServiceError as e:
            logger.error(f"GHL API error: {e}")
            return {
                "success": False,
                "error": "Failed to create appointment in system"
            }
        except Exception as e:
            logger.error(f"Error creating appointment: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _create_or_update_contact(
        self,
        account: Account,
        conversation_id: str,
        name: str,
        phone: str,
        email: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create or update a contact in GHL and track in conversation."""
        try:
            # Get conversation to check if contact already exists
            conversation = self.conversation_service.repository.get(conversation_id)
            if not conversation:
                logger.error(f"Conversation {conversation_id} not found")
                return None
            
            contact_id = conversation.context.metadata.get("contact_id") if conversation.context.metadata else None
            
            if contact_id:
                # Update existing contact with new information
                logger.info(f"Updating existing contact {contact_id} with new information")
                contact = self.ghl_client.update_contact(
                    account_id=account.id,
                    contact_id=contact_id,
                    name=name,
                    email=email,
                    reason=reason
                )
            else:
                # Create new contact
                logger.info(
                    f"Creating new contact",
                    extra={
                        "contact_name": name,
                        "phone": phone,
                        "account_id": account.id,
                        "location_id": account.location_id
                    }
                )
                
                try:
                    # Normalize phone for GHL
                    normalized_phone = normalize_phone(phone)
                    ghl_phone = format_phone_for_ghl(normalized_phone)
                    
                    contact = self.ghl_client.create_contact(
                        account_id=account.id,
                        location_id=account.location_id,
                        name=name,
                        phone=ghl_phone,
                        email=email,
                        reason=reason
                    )
                    
                    if not contact:
                        logger.error(
                            "Contact creation returned None",
                            extra={
                                "contact_name": name,
                                "phone": phone,
                                "account_id": account.id
                            }
                        )
                        return None
                        
                    logger.info(
                        "Contact created successfully",
                        extra={
                            "contact_id": contact.get("id"),
                            "contact_name": contact.get("name")
                        }
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to create contact: {e}",
                        extra={
                            "contact_name": name,
                            "phone": phone,
                            "account_id": account.id,
                            "error": str(e)
                        },
                        exc_info=True
                    )
                    return None
                
                # Store contact ID in conversation metadata
                if contact and contact.get("id"):
                    metadata = conversation.context.metadata or {}
                    metadata["contact_id"] = contact["id"]
                    self.conversation_service.repository.update_metadata(
                        conversation_id=conversation_id,
                        metadata=metadata
                    )
                    logger.info(f"Stored contact ID {contact['id']} in conversation {conversation_id}")
            
            return contact
            
        except Exception as e:
            logger.error(
                f"Error in ensure_contact_exists: {e}",
                extra={
                    "conversation_id": conversation_id,
                    "account_id": account.id,
                    "error": str(e)
                },
                exc_info=True
            )
            return None
    
    def _get_system_prompt(self, account: Account) -> str:
        """Get system prompt for conversation."""
        from app.integrations.llm.prompts import get_conversation_prompt
        
        context = f"Negocio: {account.name}"
        return get_conversation_prompt(
            custom_prompt=account.custom_prompt,
            context=context
        )
    
    def _format_conversation_for_extraction(self, messages: List[Dict[str, str]]) -> str:
        """Format conversation messages for appointment extraction."""
        lines = []
        for msg in messages:
            role = "Usuario" if msg["role"] == "user" else "Asistente"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)
    
    def _format_appointment_info(self, raw_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Format and validate appointment information."""
        try:
            # Parse datetime string
            datetime_str = raw_info.get("datetime")
            if not datetime_str:
                return None
            
            # Try to parse the datetime
            try:
                # Parse the datetime string
                if datetime_str.endswith("Z"):
                    dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
                elif "+" in datetime_str or datetime_str.count("-") > 2:
                    dt = datetime.fromisoformat(datetime_str)
                else:
                    # Assume timezone-naive datetime, apply Mexico City timezone
                    dt = datetime.fromisoformat(datetime_str)
                    tz = pytz.timezone(self.config.timezone)
                    dt = tz.localize(dt)
            except:
                # Try to parse with custom format
                from dateutil import parser
                dt = parser.parse(datetime_str)
                if dt.tzinfo is None:
                    # Apply Mexico City timezone if timezone-naive
                    tz = pytz.timezone(self.config.timezone)
                    dt = tz.localize(dt)
            
            # Ensure datetime is in the future
            now = datetime.now(pytz.UTC)
            dt_utc = dt.astimezone(pytz.UTC) if dt.tzinfo else dt.replace(tzinfo=pytz.UTC)
            if dt_utc <= now:
                logger.warning(f"Appointment datetime {dt_utc} is in the past (now: {now})")
                return None
            
            return {
                "name": raw_info["name"],
                "reason": raw_info["reason"],
                "datetime": dt.isoformat(),
                "raw_datetime": raw_info.get("raw_datetime", datetime_str),
                "phone_number": raw_info.get("phone_number"),
                "email": raw_info.get("email"),
                "notes": raw_info.get("notes")
            }
            
        except Exception as e:
            logger.error(f"Error formatting appointment info: {e}")
            return None
    
    def _generate_confirmation_message(self, appointment_info: Dict[str, Any]) -> str:
        """Generate confirmation message for appointment."""
        # Parse datetime and format using standardized function
        dt = datetime.fromisoformat(appointment_info["datetime"])
        date_str, time_str = self._format_datetime_spanish(dt)
        
        # Check availability
        availability = appointment_info.get("availability", {})
        is_available = availability.get("available", True)
        alternatives = availability.get("alternatives", [])
        exact_match = availability.get("exact_match", False)
        error = availability.get("error")
        
        # Check for authentication errors
        if error == "authentication_failed":
            return availability.get("message", "Lo siento, hay un problema con la conexión al sistema de citas. Por favor, contacta al administrador para resolver este problema.")
        
        if is_available and exact_match:
            # Exact time requested is available - standard confirmation
            message = (
                f"📋 *Confirma tu cita:*\n\n"
                f"👤 *Nombre:* {appointment_info['name']}\n"
                f"📝 *Motivo:* {appointment_info['reason']}\n"
                f"📅 *Fecha:* {date_str}\n"
                f"🕐 *Hora:* {time_str}\n"
            )
            
            if appointment_info.get("notes"):
                message += f"📌 *Notas:* {appointment_info['notes']}\n"
            
            message += "\n¿Deseas confirmar esta cita?"
        
        elif alternatives:
            # Show available slots for the requested date or alternatives
            slots_for_date = availability.get("slots_for_date", False)
            
            if is_available and slots_for_date:
                # Exact time not available but other slots are available on the same date
                message = (
                    f"⚠️ *La hora exacta solicitada no está disponible*\n\n"
                    f"👤 *Nombre:* {appointment_info['name']}\n"
                    f"📝 *Motivo:* {appointment_info['reason']}\n"
                    f"📅 *Fecha solicitada:* {date_str}\n"
                    f"🕐 *Hora solicitada:* {time_str}\n\n"
                    f"⏰ *Horarios disponibles para {date_str}:*\n"
                )
            else:
                # No slots available on requested date - showing alternatives
                message = (
                    f"❌ *No hay horarios disponibles para esa fecha*\n\n"
                    f"👤 *Nombre:* {appointment_info['name']}\n"
                    f"📝 *Motivo:* {appointment_info['reason']}\n"
                    f"📅 *Fecha solicitada:* {date_str}\n"
                    f"🕐 *Hora solicitada:* {time_str}\n\n"
                    f"🔄 *Próximos horarios disponibles:*\n"
                )
            
            for i, alt in enumerate(alternatives, 1):
                message += f"\n{i}. 📅 {alt['display_date']} - 🕐 {alt['display_time']}"
            
            message += "\n\n💡 ¿Te gustaría agendar en alguno de estos horarios?\nResponde con el número de tu preferencia o escribe 'no' para cancelar."
        
        else:
            # No alternatives available
            message = (
                f"❌ *Lo siento, no hay horarios disponibles*\n\n"
                f"👤 *Nombre:* {appointment_info['name']}\n"
                f"📝 *Motivo:* {appointment_info['reason']}\n"
                f"📅 *Fecha solicitada:* {date_str}\n"
                f"🕐 *Hora solicitada:* {time_str}\n\n"
                f"❌ No hay horarios disponibles en los próximos días.\n"
                f"Por favor contacta directamente al consultorio para verificar disponibilidad."
            )
        
        return message
    
    def check_slot_availability(
        self,
        account: Account,
        appointment_datetime: datetime
    ) -> Dict[str, Any]:
        """Get available slots for the requested date and return them as options."""
        try:
            # Get the requested date (start of day) with proper timezone handling
            local_datetime = self._to_local_timezone(appointment_datetime)
            requested_date = local_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
            start_timestamp = int(requested_date.timestamp() * 1000)
            
            # Check for the full day (24 hours from start of requested date)
            end_timestamp = start_timestamp + (24 * 60 * 60 * 1000)
            
            logger.info(f"Requesting slots for date range: {requested_date.isoformat()} to {(requested_date + timedelta(days=1)).isoformat()}")
            
            # Get all free slots for the requested date
            free_slots = self.ghl_client.get_free_slots(
                account_id=account.id,
                calendar_id=account.calendar_id,
                start_date=start_timestamp,
                end_date=end_timestamp,
                user_id=account.assigned_user_id
            )
            
            logger.info(f"Found {len(free_slots)} free slots for requested date {requested_date.strftime('%Y-%m-%d')}")
            
            if not free_slots:
                # No slots available on requested date, find alternatives in next 24 hours
                alternatives = self._find_alternative_slots(account, appointment_datetime)
                return {
                    "available": False,
                    "appointment_datetime": appointment_datetime,
                    "alternatives": alternatives,
                    "exact_match": False,
                    "message": "No hay horarios disponibles para la fecha solicitada"
                }
            
            # Convert free slots to alternatives format
            alternatives = self._format_slots_as_alternatives(free_slots)
            
            # Check if the alternatives are actually for the same date as requested
            # Use local timezone for consistent date comparison
            requested_date_str = local_datetime.strftime("%Y-%m-%d")
            same_date_alternatives = []
            other_date_alternatives = []
            
            for alt in alternatives:
                # Convert alternative datetime to local timezone for comparison
                alt_datetime = datetime.fromisoformat(alt["datetime"])
                alt_local = self._to_local_timezone(alt_datetime)
                alt_date = alt_local.strftime("%Y-%m-%d")
                if alt_date == requested_date_str:
                    same_date_alternatives.append(alt)
                else:
                    other_date_alternatives.append(alt)
            
            logger.info(f"Slots analysis: {len(same_date_alternatives)} for requested date {requested_date_str}, {len(other_date_alternatives)} for other dates")
            
            # Check if user's exact requested time is in the available slots
            is_exact_match = self._is_time_slot_available(appointment_datetime, free_slots)
            
            if is_exact_match:
                # Exact time is available, show all options for the day
                return {
                    "available": True,
                    "appointment_datetime": appointment_datetime,
                    "alternatives": alternatives[:5],  # Show up to 5 options
                    "exact_match": True
                }
            elif same_date_alternatives:
                # Exact time not available, but other slots available for the same date
                return {
                    "available": True,
                    "appointment_datetime": appointment_datetime,
                    "alternatives": same_date_alternatives[:5],  # Show only same date slots
                    "exact_match": False,
                    "slots_for_date": True
                }
            else:
                # No slots for requested date, but found slots for other dates
                # This means GHL returned slots outside our date range - treat as no slots for date
                alternatives = self._find_alternative_slots(account, appointment_datetime)
                return {
                    "available": False,
                    "appointment_datetime": appointment_datetime,
                    "alternatives": alternatives,
                    "exact_match": False,
                    "message": "No hay horarios disponibles para la fecha solicitada"
                }
            
        except ExternalServiceError as e:
            logger.error(f"Error checking slot availability: {e}")
            # Check if it's a token refresh error
            if "Token refresh failed" in str(e):
                return {
                    "available": False,
                    "appointment_datetime": appointment_datetime,
                    "alternatives": [],
                    "error": "authentication_failed",
                    "message": "Lo siento, hay un problema con la conexión al sistema de citas. Por favor, contacta al administrador para resolver este problema."
                }
            # For other external service errors, try to find alternatives
            alternatives = self._find_alternative_slots(account, appointment_datetime)
            return {
                "available": False,
                "appointment_datetime": appointment_datetime,
                "alternatives": alternatives,
                "exact_match": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error checking slot availability: {e}")
            # If we can't check availability, find alternatives
            alternatives = self._find_alternative_slots(account, appointment_datetime)
            return {
                "available": False,
                "appointment_datetime": appointment_datetime,
                "alternatives": alternatives,
                "exact_match": False,
                "error": str(e)
            }
    
    def _is_time_slot_available(
        self, 
        appointment_datetime: datetime, 
        free_slots: List[Dict[str, Any]]
    ) -> bool:
        """Check if a specific time slot is available in the free slots."""
        # Format appointment datetime to match GHL slot format
        appointment_date = appointment_datetime.strftime("%Y-%m-%d")
        appointment_time = appointment_datetime.strftime("%H:%M")
        
        for slot in free_slots:
            slot_date = slot.get("date")
            slot_time = slot.get("time")
            
            if slot_date == appointment_date and slot_time == appointment_time:
                return True
        
        return False
    
    def _find_alternative_slots(
        self,
        account: Account,
        original_datetime: datetime,
        days_to_search: int = 7
    ) -> List[Dict[str, Any]]:
        """Find alternative appointment slots within the specified days."""
        try:
            # Search from original time to specified days later (default 7 days)
            start_timestamp = int(original_datetime.timestamp() * 1000)
            end_timestamp = start_timestamp + (days_to_search * 24 * 60 * 60 * 1000)
            
            # Get all free slots in the search window
            free_slots = self.ghl_client.get_free_slots(
                account_id=account.id,
                calendar_id=account.calendar_id,
                start_date=start_timestamp,
                end_date=end_timestamp,
                user_id=account.assigned_user_id
            )
            
            alternatives = []
            tz = pytz.timezone(self.config.timezone)
            
            # Format date and time names in Spanish
            months = {
                1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
                5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
                9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
            }
            
            for slot in free_slots[:5]:  # Limit to 5 alternatives
                slot_datetime_str = slot.get("datetime")
                if slot_datetime_str:
                    try:
                        # Parse the datetime string (format: "2025-06-09T14:00:00")
                        slot_datetime = datetime.fromisoformat(slot_datetime_str)
                        
                        # Localize to timezone if needed
                        if slot_datetime.tzinfo is None:
                            slot_datetime = tz.localize(slot_datetime)
                        
                        # Format for display in Spanish
                        date_str = f"{slot_datetime.day} de {months[slot_datetime.month]} de {slot_datetime.year}"
                        time_str = slot_datetime.strftime("%I:%M %p")
                        
                        alternatives.append({
                            "datetime": slot_datetime.isoformat(),
                            "display_date": date_str,
                            "display_time": time_str,
                            "date": slot.get("date"),
                            "time": slot.get("time")
                        })
                    except Exception as e:
                        logger.error(f"Error parsing slot datetime {slot_datetime_str}: {e}")
                        continue
            
            return alternatives
            
        except ExternalServiceError as e:
            logger.error(f"Error finding alternative slots: {e}")
            # Don't try to find alternatives if authentication failed
            if "Token refresh failed" in str(e):
                return []
            return []
        except Exception as e:
            logger.error(f"Error finding alternative slots: {e}")
            return []
    
    def _format_slots_as_alternatives(self, free_slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format free slots into alternatives format."""
        alternatives = []
        
        for slot in free_slots:
            slot_datetime_str = slot.get("datetime")
            if slot_datetime_str:
                try:
                    # Parse the datetime string (format: "2025-06-09T14:00:00")
                    slot_datetime = datetime.fromisoformat(slot_datetime_str)
                    
                    # Format for display using standardized function
                    date_str, time_str = self._format_datetime_spanish(slot_datetime)
                    
                    slot_data = {
                        "datetime": slot_datetime.isoformat(),
                        "display_date": date_str,
                        "display_time": time_str,
                        "date": slot.get("date"),
                        "time": slot.get("time")
                    }
                    logger.info(f"Formatted slot: {slot_data}")
                    alternatives.append(slot_data)
                except Exception as e:
                    logger.error(f"Error parsing slot datetime {slot_datetime_str}: {e}")
                    continue
        
        return alternatives
    
    def handle_alternative_slot_selection(
        self,
        conversation_id: str,
        selection: str,
        account: Account
    ) -> Dict[str, Any]:
        """Handle user selection of an alternative appointment slot."""
        try:
            # Get conversation to access stored alternatives
            conversation = self.conversation_service.repository.get(conversation_id)
            if not conversation or not conversation.context.appointment_info:
                return {
                    "type": "text",
                    "message": "No se encontró información de cita para procesar tu selección."
                }
            
            appointment_info = conversation.context.appointment_info
            availability = appointment_info.get("availability", {})
            alternatives = availability.get("alternatives", [])
            
            # Check if user wants to cancel
            if selection.lower() in ["no", "cancelar", "cancel"]:
                self.conversation_service.cancel_appointment(conversation_id)
                return {
                    "type": "text",
                    "message": "Entiendo, he cancelado el proceso de agendamiento. ¿Hay algo más en lo que pueda ayudarte?"
                }
            
            # Try to parse selection as a number
            try:
                slot_index = int(selection) - 1  # Convert to 0-based index
                if 0 <= slot_index < len(alternatives):
                    # Update appointment info with selected alternative
                    selected_slot = alternatives[slot_index]
                    logger.info(f"User selected alternative slot {slot_index + 1}: {selected_slot}")
                    appointment_info["datetime"] = selected_slot["datetime"]
                    appointment_info["availability"] = {
                        "available": True, 
                        "alternatives": [],
                        "exact_match": True  # User selected this specific slot
                    }
                    
                    # Update conversation context
                    self.conversation_service.update_appointment_info(
                        conversation_id=conversation_id,
                        appointment_info=appointment_info,
                        awaiting_confirmation=True
                    )
                    
                    # Generate new confirmation message for selected slot
                    confirmation_msg = self._generate_confirmation_message(appointment_info)
                    
                    return {
                        "type": "confirmation",
                        "message": confirmation_msg,
                        "appointment_info": appointment_info
                    }
                else:
                    return {
                        "type": "text",
                        "message": f"Por favor selecciona un número entre 1 y {len(alternatives)}, o escribe 'no' para cancelar."
                    }
            except ValueError:
                return {
                    "type": "text",
                    "message": f"Por favor selecciona un número entre 1 y {len(alternatives)}, o escribe 'no' para cancelar."
                }
                
        except Exception as e:
            logger.error(f"Error handling alternative slot selection: {e}")
            return {
                "type": "text",
                "message": "Hubo un error procesando tu selección. Por favor intenta nuevamente."
            }
    
