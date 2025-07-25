"""WhatsApp service for sending messages."""
from typing import Dict, Any, Optional
from app.integrations.whatsapp.client import WhatsAppClient
from app.integrations.whatsapp.models import OutgoingMessage, MessageType, InteractiveMessage
from app.core.logging import get_logger

logger = get_logger(__name__)


class WhatsAppService:
    """Service for WhatsApp messaging operations."""
    
    def __init__(self):
        """Initialize WhatsApp service."""
        self.client = WhatsAppClient()
    
    def send_text_message(
        self, 
        phone_number_id: str, 
        to_number: str, 
        message: str
    ) -> Optional[Dict[str, Any]]:
        """Send a text message via WhatsApp.
        
        Args:
            phone_number_id: WhatsApp Business phone number ID
            to_number: Recipient phone number (with country code)
            message: Text message to send
            
        Returns:
            Response from WhatsApp API or None if failed
        """
        try:
            # Ensure phone number has country code
            if not to_number.startswith('+'):
                # Assume Mexico if no country code
                if len(to_number) == 10:
                    to_number = f"+52{to_number}"
                elif len(to_number) == 12 and to_number.startswith('52'):
                    to_number = f"+{to_number}"
            
            logger.info(
                "Sending text message via WhatsApp",
                extra={
                    "phone_number_id": phone_number_id,
                    "to": to_number,
                    "message_length": len(message)
                }
            )
            
            response = self.client.send_text_message(
                phone_number_id=phone_number_id,
                to=to_number,
                text=message
            )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Failed to send WhatsApp message: {e}",
                extra={
                    "phone_number_id": phone_number_id,
                    "to": to_number,
                    "error": str(e)
                }
            )
            return None
    
    def send_template_message(
        self,
        phone_number_id: str,
        to_number: str,
        template_name: str,
        template_params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Send a template message via WhatsApp.
        
        Args:
            phone_number_id: WhatsApp Business phone number ID
            to_number: Recipient phone number
            template_name: Name of the approved template
            template_params: Parameters for the template
            
        Returns:
            Response from WhatsApp API or None if failed
        """
        # TODO: Implement template message sending when needed
        logger.warning("Template message sending not yet implemented")
        return None
    
    def mark_message_as_read(
        self,
        phone_number_id: str,
        message_id: str
    ) -> bool:
        """Mark a message as read.
        
        Args:
            phone_number_id: WhatsApp Business phone number ID
            message_id: ID of the message to mark as read
            
        Returns:
            True if successful, False otherwise
        """
        try:
            return self.client.mark_as_read(
                phone_number_id=phone_number_id,
                message_id=message_id
            )
        except Exception as e:
            logger.error(
                f"Failed to mark message as read: {e}",
                extra={
                    "phone_number_id": phone_number_id,
                    "message_id": message_id
                }
            )
            return False
    
    def send_interactive_reminder(
        self,
        phone_number_id: str,
        to_number: str,
        interactive: InteractiveMessage
    ) -> Optional[Dict[str, Any]]:
        """Send an interactive reminder message via WhatsApp.
        
        Args:
            phone_number_id: WhatsApp Business phone number ID
            to_number: Recipient phone number (with country code)
            interactive: Interactive message object with buttons
            
        Returns:
            Response from WhatsApp API or None if failed
        """
        try:
            # Ensure phone number has country code
            if not to_number.startswith('+'):
                # Assume Mexico if no country code
                if len(to_number) == 10:
                    to_number = f"+52{to_number}"
                elif len(to_number) == 12 and to_number.startswith('52'):
                    to_number = f"+{to_number}"
            
            logger.info(
                "Sending interactive reminder via WhatsApp",
                extra={
                    "phone_number_id": phone_number_id,
                    "to": to_number,
                    "button_count": len(interactive.buttons) if hasattr(interactive, 'buttons') else 0
                }
            )
            
            # Create outgoing message
            message = OutgoingMessage(
                to=to_number,
                message_type=MessageType.INTERACTIVE,
                interactive=interactive
            )
            
            # Send via client
            response = self.client.send_message(
                phone_number_id=phone_number_id,
                message=message
            )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Failed to send interactive reminder: {e}",
                extra={
                    "phone_number_id": phone_number_id,
                    "to": to_number,
                    "error": str(e)
                }
            )
            return None