"""Service for handling WhatsApp messages."""
from typing import Optional, Dict, Any
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import firestore
from app.utils.phone_utils import normalize_phone, format_phone_for_whatsapp
from app.integrations.whatsapp.models import (
    WhatsAppMessage, OutgoingMessage, InteractiveMessage,
    ButtonReply, MessageType
)
from app.integrations.whatsapp.client import WhatsAppClient
from app.services.account_service import AccountService
from app.services.conversation_service import ConversationService
from app.services.appointment_service import AppointmentService
from app.services.ghl_service import GHLService
from app.models.conversation import MessageRole
from app.core.exceptions import ValidationError, VitalisException
from app.core.logging import get_logger
from app.core.config import get_config
from app.repositories.message_deduplication_repository import MessageDeduplicationRepository
from app.utils.firebase import get_firestore_client

logger = get_logger(__name__)


class MessageService:
    """Service for message processing and routing."""
    
    def __init__(self):
        self.account_service = AccountService()
        self.conversation_service = ConversationService()
        self.appointment_service = AppointmentService()
        self.whatsapp_client = WhatsAppClient()
        self.ghl_service = GHLService()
        self.db = get_firestore_client()
        self.deduplication_repo = MessageDeduplicationRepository()
        self.config = get_config()
    
    def handle_webhook_message(self, data: Dict[str, Any]) -> bool:
        """Handle incoming webhook message from WhatsApp."""
        try:
            # Parse WhatsApp message
            message = WhatsAppMessage.from_webhook_data(data)
            if not message:
                logger.warning(
                    "Could not parse WhatsApp message from webhook data",
                    extra={"webhook_data": data}
                )
                return False
            
            # Check if deduplication is enabled
            enable_deduplication = getattr(self.config, 'enable_message_deduplication', True)
            
            if enable_deduplication:
                # Get account by phone number ID to check deduplication
                account = self.account_service.get_account_by_phone_number_id(message.phone_number_id)
                if account:
                    # Check if message was already processed
                    is_new_message = self.deduplication_repo.check_and_mark_processed(
                        message_id=message.message_id,
                        account_id=account.id,
                        phone_number=message.from_number
                    )
                    
                    if not is_new_message:
                        logger.info(
                            "Skipping duplicate message",
                            extra={
                                "message_id": message.message_id,
                                "account_id": account.id,
                                "from_number": message.from_number
                            }
                        )
                        return True  # Return True to acknowledge receipt
            
            # Route based on message type
            if message.message_type == MessageType.TEXT:
                return self._handle_text_message(message)
            elif message.message_type == MessageType.INTERACTIVE:
                return self._handle_interactive_message(message)
            else:
                logger.info(f"Unsupported message type: {message.message_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error handling webhook message: {e}")
            raise VitalisException(f"Failed to handle message: {str(e)}")
    
    def _handle_text_message(self, message: WhatsAppMessage) -> bool:
        """Handle text message."""
        try:
            # Get account by phone number ID
            account = self.account_service.get_account_by_phone_number_id(message.phone_number_id)
            if not account:
                logger.warning(f"No account found for phone_number_id: {message.phone_number_id}")
                return False
            
            if not account.is_active():
                logger.warning(f"Account {account.id} is not active")
                return False
            
            # Check subscription access
            from app.services.subscription_service import SubscriptionService
            subscription_service = SubscriptionService()
            access = subscription_service.check_access(account)
            
            if not access["has_access"]:
                logger.warning(
                    f"Account {account.id} has no active subscription",
                    extra={"reason": access["reason"]}
                )
                # Send subscription required message
                self._send_subscription_required_message(message.from_number, message.phone_number_id, account)
                return True
            
            # Get or create conversation
            conversation = self.conversation_service.get_or_create_conversation(
                account_id=account.id,
                phone_number=message.from_number
            )
            
            # Check if user has active reminder context
            reminder_context = self._check_reminder_context(message.from_number)
            if reminder_context:
                # Handle appointment modification from reminder
                return self._handle_reminder_response(
                    message=message,
                    reminder_context=reminder_context,
                    account=account,
                    conversation=conversation
                )
            
            # Add user message to conversation
            self.conversation_service.add_user_message(
                conversation_id=conversation.id,
                content=message.text,
                metadata={"message_id": message.message_id}
            )
            
            # Check if we're waiting for appointment confirmation
            if conversation.context.awaiting_confirmation:
                # Check if user is responding to alternative slot suggestions
                appointment_info = conversation.context.appointment_info
                availability = appointment_info.get("availability", {}) if appointment_info else {}
                has_alternatives = len(availability.get("alternatives", [])) > 0
                exact_match = availability.get("exact_match", True)
                
                if appointment_info and has_alternatives and not exact_match:
                    # User is responding to alternative slot suggestions
                    response = self.appointment_service.handle_alternative_slot_selection(
                        conversation_id=conversation.id,
                        selection=message.text,
                        account=account
                    )
                    
                    # Send appropriate response
                    if response.get("type") == "confirmation":
                        # Send interactive confirmation message
                        self._send_confirmation_message(
                            account.phone_number_id,
                            message.from_number,
                            response["message"],
                            response["appointment_info"],
                            conversation.id
                        )
                    else:
                        # Send text response
                        self._send_text_response(
                            account.phone_number_id,
                            message.from_number,
                            response["message"],
                            conversation.id
                        )
                    return True
                else:
                    # User sent text instead of using buttons
                    # Check if user is explicitly cancelling or providing new date/time
                    user_message_lower = message.text.lower().strip()
                    cancel_keywords = ["no", "cancelar", "cancel", "cancela", "no quiero", "dejalo", "olvídalo", "olvidalo"]
                    
                    if any(keyword in user_message_lower for keyword in cancel_keywords):
                        # User is explicitly cancelling
                        self.conversation_service.cancel_appointment(conversation.id)
                        
                        response_text = "Entiendo, he cancelado el proceso de agendamiento. ¿Hay algo más en lo que pueda ayudarte?"
                        
                        # Send response
                        self._send_text_response(
                            account.phone_number_id,
                            message.from_number,
                            response_text,
                            conversation.id
                        )
                        return True
                    else:
                        # User might be providing a new date/time, process it normally
                        # Reset awaiting_confirmation to process the new message
                        self.conversation_service.update_appointment_info(
                            conversation_id=conversation.id,
                            appointment_info=conversation.context.appointment_info,
                            awaiting_confirmation=False
                        )
            
            # Process with appointment service
            response = self.appointment_service.process_message(
                conversation_id=conversation.id,
                account=account,
                contact_name=message.contact_name
            )
            
            # Send appropriate response
            if response.get("type") == "confirmation":
                # Send interactive confirmation message
                self._send_confirmation_message(
                    account.phone_number_id,
                    message.from_number,
                    response["message"],
                    response["appointment_info"],
                    conversation.id
                )
            else:
                # Send text response
                self._send_text_response(
                    account.phone_number_id,
                    message.from_number,
                    response["message"],
                    conversation.id
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling text message: {e}")
            raise
    
    def _handle_interactive_message(self, message: WhatsAppMessage) -> bool:
        """Handle interactive message (button clicks)."""
        try:
            # Get account
            account = self.account_service.get_account_by_phone_number_id(message.phone_number_id)
            if not account:
                logger.warning(f"No account found for phone_number_id: {message.phone_number_id}")
                return False
            
            # Extract button ID first
            button_id = message.interactive_reply.get("button_reply", {}).get("id")
            
            # Check if this is a reminder response button FIRST
            if button_id and button_id.startswith("reminder_"):
                logger.info(
                    f"Processing reminder button: {button_id}",
                    extra={
                        "button_id": button_id,
                        "phone_number": message.from_number,
                        "account_id": account.id
                    }
                )
                
                try:
                    reminder_context = self._check_reminder_context(message.from_number)
                    
                    if not reminder_context:
                        logger.warning(
                            f"No active reminder context found for phone {message.from_number}",
                            extra={"phone_number": message.from_number}
                        )
                        # Send helpful message instead of crashing
                        self._send_text_response(
                            account.phone_number_id,
                            message.from_number,
                            "❌ Lo siento, no pude procesar su respuesta. El recordatorio puede haber expirado.\n\nPor favor contacte directamente al consultorio.",
                            None
                        )
                        return True
                    
                    logger.info(
                        f"Found reminder context",
                        extra={
                            "context_id": reminder_context.get("id"),
                            "appointment_id": reminder_context.get("appointment_id")
                        }
                    )
                    
                    # Get conversation for logging but don't require awaiting_confirmation
                    conversation = self.conversation_service.get_or_create_conversation(
                        account_id=account.id,
                        phone_number=message.from_number
                    )
                    
                    return self._handle_reminder_button_response(
                        button_id=button_id,
                        reminder_context=reminder_context,
                        account=account,
                        phone_number=message.from_number,
                        conversation_id=conversation.id if conversation else None
                    )
                except Exception as e:
                    logger.error(
                        f"Error handling reminder button: {e}",
                        extra={
                            "button_id": button_id,
                            "phone_number": message.from_number,
                            "error": str(e)
                        },
                        exc_info=True
                    )
                    # Send error message to user
                    self._send_text_response(
                        account.phone_number_id,
                        message.from_number,
                        "❌ Hubo un error al procesar su respuesta. Por favor intente nuevamente o contacte directamente.",
                        None
                    )
                    return True
            
            # For non-reminder buttons, get conversation and check awaiting_confirmation
            conversation = self.conversation_service.get_or_create_conversation(
                account_id=account.id,
                phone_number=message.from_number
            )
            
            if not conversation or not conversation.context.awaiting_confirmation:
                logger.warning(f"No pending appointment confirmation found for conversation {conversation.id if conversation else 'None'}")
                return False
            
            if button_id == "confirm_yes":
                # Check if Stripe is enabled for this account
                if account.stripe_enabled:
                    # Check if Stripe Connect account exists and onboarding is complete
                    if not account.stripe_connect_account_id:
                        response_text = (
                            "❌ La cuenta de pagos no está configurada.\n\n"
                            "Por favor contacta al administrador para completar la configuración de Stripe."
                        )
                    elif not account.stripe_onboarding_completed:
                        response_text = (
                            "❌ La configuración de pagos está incompleta.\n\n"
                            "El proceso de verificación de Stripe aún no ha sido completado. "
                            "Por favor contacta al administrador para finalizar la configuración."
                        )
                    elif not account.stripe_charges_enabled:
                        response_text = (
                            "❌ Los pagos no están habilitados en este momento.\n\n"
                            "La cuenta de Stripe está en proceso de activación. "
                            "Por favor intenta más tarde o contacta al administrador."
                        )
                    else:
                        # Create payment instead of direct appointment
                        payment_result = self.appointment_service.create_payment_for_appointment(
                            conversation_id=conversation.id,
                            account=account
                        )
                        
                        if payment_result["success"]:
                            response_text = (
                                "📋 ¡Perfecto! He registrado tu cita.\n\n"
                                f"💳 Para confirmarla, necesitas realizar el pago de ${payment_result['amount']/100:.2f} {payment_result['currency'].upper()}.\n\n"
                                f"🔗 Por favor realiza el pago aquí:\n{payment_result['payment_link']}\n\n"
                                "⏱️ Este enlace expirará en 30 minutos.\n"
                                "Una vez confirmado el pago, tu cita quedará agendada."
                            )
                        else:
                            response_text = (
                                "❌ Lo siento, hubo un problema al generar el enlace de pago.\n"
                                "Por favor, intenta nuevamente más tarde o contacta directamente."
                            )
                else:
                    # No Stripe - create appointment directly
                    result = self.appointment_service.confirm_and_create_appointment(
                        conversation_id=conversation.id,
                        account=account
                    )
                    
                    if result["success"]:
                        response_text = (
                            "✅ ¡Excelente! Tu cita ha sido agendada exitosamente.\n\n"
                            f"📅 {result['details']}\n\n"
                            "Te esperamos. ¡Que tengas un excelente día!"
                        )
                    else:
                        response_text = (
                            "❌ Lo siento, hubo un problema al agendar tu cita.\n"
                            "Por favor, intenta nuevamente más tarde o contacta directamente."
                        )
            
            elif button_id == "confirm_no":
                # Cancel appointment
                self.conversation_service.cancel_appointment(conversation.id)
                response_text = (
                    "Entiendo, no hay problema. La cita no ha sido agendada.\n"
                    "Si deseas agendar en otro momento, estaré aquí para ayudarte."
                )
            
            else:
                logger.warning(f"Unknown button ID: {button_id}")
                return False
            
            # Send response
            self._send_text_response(
                account.phone_number_id,
                message.from_number,
                response_text,
                conversation.id
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling interactive message: {e}")
            raise
    
    def _send_text_response(
        self,
        phone_number_id: str,
        to_number: str,
        text: str,
        conversation_id: str
    ) -> None:
        """Send text response and save to conversation."""
        try:
            # Format phone number for WhatsApp
            formatted_number = format_phone_for_whatsapp(to_number)
            
            # Send message
            self.whatsapp_client.send_text_message(phone_number_id, formatted_number, text)
            
            # Save assistant message to conversation
            self.conversation_service.add_assistant_message(
                conversation_id=conversation_id,
                content=text
            )
        except Exception as e:
            logger.error(f"Failed to send text response: {e}")
            raise
    
    def _send_confirmation_message(
        self,
        phone_number_id: str,
        to_number: str,
        text: str,
        appointment_info: Dict[str, Any],
        conversation_id: str
    ) -> None:
        """Send appointment confirmation message with buttons."""
        try:
            # Format phone number for WhatsApp
            formatted_number = format_phone_for_whatsapp(to_number)
            
            # Check if slot is available and if it's an exact match
            availability = appointment_info.get("availability", {})
            is_available = availability.get("available", True)
            exact_match = availability.get("exact_match", False)
            
            if is_available and exact_match:
                # Standard confirmation with buttons
                interactive = InteractiveMessage(
                    body_text=text,
                    buttons=[
                        ButtonReply(id="confirm_yes", title="✅ Sí, confirmar"),
                        ButtonReply(id="confirm_no", title="❌ No, cancelar")
                    ],
                    footer_text="Por favor confirma tu cita"
                )
                
                message = OutgoingMessage(
                    to=formatted_number,
                    message_type=MessageType.INTERACTIVE,
                    interactive=interactive
                )
                
                # Send interactive message
                self.whatsapp_client.send_message(phone_number_id, message)
            else:
                # Slot unavailable - send as text message (no confirmation buttons)
                self.whatsapp_client.send_text_message(phone_number_id, formatted_number, text)
            
            # Save to conversation
            self.conversation_service.add_assistant_message(
                conversation_id=conversation_id,
                content=text,
                metadata={"type": "confirmation", "appointment_info": appointment_info}
            )
            
        except Exception as e:
            logger.error(f"Failed to send confirmation message: {e}")
            raise
    
    def _check_reminder_context(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Check if user has active reminder context."""
        try:
            # Normalize phone for consistent lookup
            normalized_phone = normalize_phone(phone_number)
            
            logger.info(
                f"Checking reminder context for phone: {phone_number} (normalized: {normalized_phone})",
                extra={"phone_number": phone_number, "normalized_phone": normalized_phone}
            )
            
            # Query active reminder contexts
            contexts_ref = self.db.collection("active_reminder_contexts")
            current_time = datetime.now(pytz.UTC).isoformat()
            
            query = contexts_ref.where("phone_number", "==", normalized_phone).where(
                "expires_at", ">", current_time
            ).limit(1)
            
            docs = list(query.stream())
            
            logger.info(
                f"Reminder context query result",
                extra={
                    "phone_number": phone_number,
                    "current_time": current_time,
                    "found_contexts": len(docs)
                }
            )
            
            if docs:
                context = docs[0].to_dict()
                context["id"] = docs[0].id
                logger.info(
                    f"Found active reminder context",
                    extra={
                        "context_id": context["id"],
                        "appointment_id": context.get("appointment_id"),
                        "expires_at": context.get("expires_at")
                    }
                )
                return context
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking reminder context: {e}")
            return None
    
    def _handle_reminder_response(
        self,
        message: WhatsAppMessage,
        reminder_context: Dict[str, Any],
        account: Any,
        conversation: Any
    ) -> bool:
        """Handle response to appointment reminder."""
        try:
            user_message = message.text.lower().strip()
            appointment_id = reminder_context["appointment_id"]
            
            # Check for cancel keywords
            cancel_keywords = ["cancelar", "cancel", "no", "cancela"]
            reschedule_keywords = ["cambiar", "reprogramar", "mover", "reschedule", "otra hora", "otro dia"]
            confirm_keywords = ["si", "sí", "confirmar", "confirm", "ok", "perfecto"]
            
            if any(keyword in user_message for keyword in cancel_keywords):
                # Cancel appointment
                return self._handle_appointment_cancellation(
                    appointment_id=appointment_id,
                    account=account,
                    phone_number=message.from_number,
                    conversation_id=conversation.id
                )
            elif any(keyword in user_message for keyword in reschedule_keywords):
                # Start rescheduling flow
                return self._handle_appointment_reschedule_request(
                    appointment_id=appointment_id,
                    account=account,
                    phone_number=message.from_number,
                    conversation_id=conversation.id
                )
            elif any(keyword in user_message for keyword in confirm_keywords):
                # Confirm attendance
                response_text = (
                    "¡Perfecto! ✅ Hemos confirmado su asistencia.\n\n"
                    "Le esperamos en su cita. Recuerde llegar 10 minutos antes.\n\n"
                    "¡Hasta pronto! 😊"
                )
                self._send_text_response(
                    account.phone_number_id,
                    message.from_number,
                    response_text,
                    conversation.id
                )
                
                # Clear reminder context
                self._clear_reminder_context(reminder_context["id"])
                return True
            else:
                # Send options message
                self._send_reminder_options(
                    account.phone_number_id,
                    message.from_number,
                    conversation.id
                )
                return True
                
        except Exception as e:
            logger.error(f"Error handling reminder response: {e}")
            return False
    
    def _handle_appointment_cancellation(
        self,
        appointment_id: str,
        account: Any,
        phone_number: str,
        conversation_id: str
    ) -> bool:
        """Handle appointment cancellation from reminder."""
        try:
            # Cancel in GHL
            success = self.ghl_service.cancel_appointment(
                account_id=account.id,
                appointment_id=appointment_id
            )
            
            if success:
                response_text = (
                    "✅ Su cita ha sido cancelada exitosamente.\n\n"
                    "Si desea agendar una nueva cita en el futuro, no dude en contactarnos.\n\n"
                    "¡Que tenga un excelente día! 😊"
                )
            else:
                response_text = (
                    "❌ Hubo un problema al cancelar su cita.\n\n"
                    "Por favor contacte directamente al consultorio para cancelar."
                )
            
            self._send_text_response(
                account.phone_number_id,
                phone_number,
                response_text,
                conversation_id
            )
            
            # Clear reminder context if successful
            if success:
                self._clear_reminder_context_by_phone(phone_number)
            
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling appointment: {e}")
            return False
    
    def _handle_appointment_reschedule_request(
        self,
        appointment_id: str,
        account: Any,
        phone_number: str,
        conversation_id: str
    ) -> bool:
        """Start appointment rescheduling flow."""
        try:
            # Get current appointment details
            appointment = self.ghl_service.get_appointment(
                account_id=account.id,
                appointment_id=appointment_id
            )
            
            if not appointment:
                response_text = (
                    "❌ No pude encontrar los detalles de su cita.\n\n"
                    "Por favor contacte directamente al consultorio para reprogramar."
                )
            else:
                response_text = (
                    "📅 Para reprogramar su cita, por favor indíqueme:\n\n"
                    "• ¿Qué día prefiere? (ejemplo: mañana, viernes, 20 de julio)\n"
                    "• ¿A qué hora le conviene? (ejemplo: 10:00 AM, 3:30 PM)\n\n"
                    "Le buscaré los horarios disponibles más cercanos a su preferencia."
                )
                
                # Store rescheduling context in conversation
                self.conversation_service.update_appointment_info(
                    conversation_id=conversation_id,
                    appointment_info={
                        "rescheduling_appointment_id": appointment_id,
                        "current_appointment": appointment,
                        "action": "reschedule"
                    },
                    awaiting_confirmation=False
                )
            
            self._send_text_response(
                account.phone_number_id,
                phone_number,
                response_text,
                conversation_id
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting reschedule flow: {e}")
            return False
    
    def _send_reminder_options(
        self,
        phone_number_id: str,
        to_number: str,
        conversation_id: str
    ) -> None:
        """Send reminder action options."""
        try:
            interactive = InteractiveMessage(
                body_text=(
                    "¿Qué desea hacer con su cita de hoy?\n\n"
                    "Por favor seleccione una opción:"
                ),
                buttons=[
                    ButtonReply(id="reminder_confirm", title="✅ Confirmar"),
                    ButtonReply(id="reminder_reschedule", title="📅 Reprogramar"),
                    ButtonReply(id="reminder_cancel", title="❌ Cancelar")
                ]
            )
            
            message = OutgoingMessage(
                to=to_number,
                message_type=MessageType.INTERACTIVE,
                interactive=interactive
            )
            
            self.whatsapp_client.send_message(phone_number_id, message)
            
            self.conversation_service.add_assistant_message(
                conversation_id=conversation_id,
                content="Opciones de cita enviadas",
                metadata={"type": "reminder_options"}
            )
            
        except Exception as e:
            logger.error(f"Failed to send reminder options: {e}")
    
    def _clear_reminder_context(self, context_id: str) -> None:
        """Clear a specific reminder context."""
        try:
            self.db.collection("active_reminder_contexts").document(context_id).delete()
        except Exception as e:
            logger.error(f"Error clearing reminder context: {e}")
    
    def _clear_reminder_context_by_phone(self, phone_number: str) -> None:
        """Clear all reminder contexts for a phone number."""
        try:
            # Normalize phone for consistent lookup
            normalized_phone = normalize_phone(phone_number)
            
            contexts_ref = self.db.collection("active_reminder_contexts")
            query = contexts_ref.where("phone_number", "==", normalized_phone)
            
            for doc in query.stream():
                doc.reference.delete()
                
        except Exception as e:
            logger.error(f"Error clearing reminder contexts: {e}")
    
    def _handle_reminder_button_response(
        self,
        button_id: str,
        reminder_context: Dict[str, Any],
        account: Any,
        phone_number: str,
        conversation_id: str
    ) -> bool:
        """Handle button responses for reminder options."""
        try:
            appointment_id = reminder_context["appointment_id"]
            
            if button_id == "reminder_confirm":
                # Confirm attendance
                response_text = (
                    "¡Perfecto! ✅ Hemos confirmado su asistencia.\n\n"
                    "Le esperamos en su cita. Recuerde llegar 10 minutos antes.\n\n"
                    "¡Hasta pronto! 😊"
                )
                self._send_text_response(
                    account.phone_number_id,
                    phone_number,
                    response_text,
                    conversation_id
                )
                self._clear_reminder_context(reminder_context["id"])
                return True
                
            elif button_id == "reminder_cancel":
                # Cancel appointment
                return self._handle_appointment_cancellation(
                    appointment_id=appointment_id,
                    account=account,
                    phone_number=phone_number,
                    conversation_id=conversation_id
                )
                
            elif button_id == "reminder_reschedule":
                # Start rescheduling flow
                return self._handle_appointment_reschedule_request(
                    appointment_id=appointment_id,
                    account=account,
                    phone_number=phone_number,
                    conversation_id=conversation_id
                )
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling reminder button response: {e}")
            return False
    
    def _send_subscription_required_message(
        self,
        to_number: str,
        phone_number_id: str,
        account: Any
    ) -> None:
        """Send message when subscription is required."""
        try:
            message = (
                "⚠️ Lo sentimos, su cuenta no tiene una suscripción activa.\n\n"
                "Para continuar utilizando nuestro servicio de citas por WhatsApp, "
                "necesita activar su suscripción.\n\n"
                "Por favor, contacte a su administrador o visite nuestro portal "
                "para más información."
            )
            
            self.whatsapp_client.send_text_message(
                phone_number_id=phone_number_id,
                to_number=to_number,
                message=message
            )
            
            logger.info(
                "Sent subscription required message",
                extra={
                    "account_id": account.id,
                    "to_number": to_number
                }
            )
        except Exception as e:
            logger.error(f"Error sending subscription required message: {e}")