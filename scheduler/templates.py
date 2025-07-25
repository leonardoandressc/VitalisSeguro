"""WhatsApp message templates for appointment reminders."""
from typing import Optional, Dict, Any
from app.integrations.whatsapp.models import (
    OutgoingMessage, InteractiveMessage, ButtonReply, MessageType
)


class ReminderTemplates:
    """Templates for appointment reminder messages."""
    
    def get_reminder_message(
        self, 
        customer_name: str,
        appointment_time: str,
        calendar_name: Optional[str] = None
    ) -> str:
        """Get a formatted reminder message in Spanish."""
        # Base greeting
        greeting = self._get_greeting()
        
        # Main reminder message
        if calendar_name:
            message = (
                f"{greeting} {customer_name}! 👋\n\n"
                f"Este es un recordatorio amistoso de que tiene una cita programada para hoy:\n\n"
                f"📅 *Cita:* {calendar_name}\n"
                f"🕐 *Hora:* {appointment_time}\n\n"
                f"Por favor, llegue 10 minutos antes de su cita.\n\n"
                f"Si necesita cancelar o reprogramar, responda a este mensaje y con gusto le ayudaremos.\n\n"
                f"¡Esperamos verle pronto! 😊"
            )
        else:
            message = (
                f"{greeting} {customer_name}! 👋\n\n"
                f"Este es un recordatorio amistoso de que tiene una cita programada para hoy a las *{appointment_time}*.\n\n"
                f"Por favor, llegue 10 minutos antes de su cita.\n\n"
                f"Si necesita cancelar o reprogramar, responda a este mensaje y con gusto le ayudaremos.\n\n"
                f"¡Esperamos verle pronto! 😊"
            )
        
        return message
    
    def get_interactive_reminder_message(
        self,
        customer_name: str,
        appointment_time: str,
        calendar_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get an interactive reminder message with buttons."""
        greeting = self._get_greeting()
        
        # Create body text
        if calendar_name:
            body_text = (
                f"{greeting} {customer_name}! 👋\n\n"
                f"Recordatorio de su cita para hoy:\n\n"
                f"📅 *{calendar_name}*\n"
                f"🕐 *{appointment_time}*\n\n"
                f"Por favor confirme su asistencia:"
            )
        else:
            body_text = (
                f"{greeting} {customer_name}! 👋\n\n"
                f"Tiene una cita programada para hoy a las *{appointment_time}*.\n\n"
                f"Por favor confirme su asistencia:"
            )
        
        # Create interactive message
        interactive = InteractiveMessage(
            body_text=body_text,
            buttons=[
                ButtonReply(id="reminder_confirm", title="✅ Confirmar"),
                ButtonReply(id="reminder_reschedule", title="📅 Reprogramar"),
                ButtonReply(id="reminder_cancel", title="❌ Cancelar")
            ],
            footer_text="Llegue 10 minutos antes"
        )
        
        return {
            "type": "interactive",
            "interactive": interactive
        }
    
    def get_confirmation_request(
        self,
        customer_name: str,
        appointment_time: str
    ) -> str:
        """Get a confirmation request message."""
        greeting = self._get_greeting()
        
        message = (
            f"{greeting} {customer_name}! 👋\n\n"
            f"Queremos confirmar su cita para hoy a las *{appointment_time}*.\n\n"
            f"Por favor responda:\n"
            f"✅ *SI* para confirmar\n"
            f"❌ *NO* si necesita cancelar o reprogramar\n\n"
            f"Gracias!"
        )
        
        return message
    
    def get_rescheduling_message(self, customer_name: str) -> str:
        """Get a rescheduling assistance message."""
        return (
            f"Entendido {customer_name}, le ayudaremos a reprogramar su cita.\n\n"
            f"¿Qué día y hora le conviene mejor?\n\n"
            f"Nuestro horario de atención es:\n"
            f"Lunes a Viernes: 9:00 AM - 6:00 PM\n"
            f"Sábados: 9:00 AM - 2:00 PM"
        )
    
    def get_cancellation_confirmation(self, customer_name: str) -> str:
        """Get a cancellation confirmation message."""
        return (
            f"Su cita ha sido cancelada, {customer_name}.\n\n"
            f"Si desea agendar una nueva cita en el futuro, no dude en contactarnos.\n\n"
            f"¡Que tenga un excelente día! 😊"
        )
    
    def get_confirmation_thanks(self, customer_name: str) -> str:
        """Get a thank you message for confirmation."""
        return (
            f"¡Perfecto {customer_name}! ✅\n\n"
            f"Su cita está confirmada. Le esperamos hoy.\n\n"
            f"Recuerde llegar 10 minutos antes.\n\n"
            f"¡Hasta pronto! 😊"
        )
    
    def _get_greeting(self) -> str:
        """Get appropriate greeting based on time of day."""
        from datetime import datetime
        import pytz
        
        # Use a default timezone (can be made configurable)
        tz = pytz.timezone("America/Los_Angeles")
        current_hour = datetime.now(tz).hour
        
        if current_hour < 12:
            return "¡Buenos días"
        elif current_hour < 19:
            return "¡Buenas tardes"
        else:
            return "¡Buenas noches"