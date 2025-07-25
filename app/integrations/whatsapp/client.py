"""WhatsApp API client."""
import requests
from typing import Optional, Dict, Any
from app.integrations.whatsapp.models import OutgoingMessage, MessageType
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.core.config import get_config

logger = get_logger(__name__)


class WhatsAppClient:
    """Client for WhatsApp Business API."""
    
    def __init__(self):
        self.config = get_config()
        self.base_url = "https://graph.facebook.com/v18.0"
        self.headers = {
            "Authorization": f"Bearer {self.config.graph_api_token}",
            "Content-Type": "application/json"
        }
    
    def send_message(self, phone_number_id: str, message: OutgoingMessage) -> Dict[str, Any]:
        """Send a message via WhatsApp API."""
        try:
            url = f"{self.base_url}/{phone_number_id}/messages"
            payload = message.to_dict(phone_number_id)
            
            logger.info(
                "Sending WhatsApp message",
                extra={
                    "to": message.to,
                    "type": message.message_type.value,
                    "phone_number_id": phone_number_id
                }
            )
            
            response = requests.post(url, json=payload, headers=self.headers)
            
            # Log detailed error for debugging
            if response.status_code != 200:
                logger.error(
                    f"WhatsApp API error: {response.status_code} - {response.text}",
                    extra={
                        "status_code": response.status_code,
                        "response_text": response.text,
                        "payload": payload
                    }
                )
            
            response.raise_for_status()
            
            result = response.json()
            logger.info(
                "WhatsApp message sent successfully",
                extra={
                    "message_id": result.get("messages", [{}])[0].get("id"),
                    "to": message.to
                }
            )
            
            return result
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Failed to send WhatsApp message: {e}",
                extra={
                    "to": message.to,
                    "type": message.message_type.value,
                    "error": str(e)
                }
            )
            raise ExternalServiceError(
                "WhatsApp",
                f"Failed to send message: {str(e)}",
                {"to": message.to, "type": message.message_type.value}
            )
    
    def send_text_message(self, phone_number_id: str, to: str, text: str) -> Dict[str, Any]:
        """Send a simple text message."""
        message = OutgoingMessage(
            to=to,
            message_type=MessageType.TEXT,
            text=text
        )
        return self.send_message(phone_number_id, message)
    
    def mark_as_read(self, phone_number_id: str, message_id: str) -> bool:
        """Mark a message as read."""
        try:
            url = f"{self.base_url}/{phone_number_id}/messages"
            payload = {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id
            }
            
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            
            logger.info(
                "Message marked as read",
                extra={"message_id": message_id}
            )
            
            return True
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Failed to mark message as read: {e}",
                extra={"message_id": message_id}
            )
            return False
    
    def get_media_url(self, media_id: str) -> Optional[str]:
        """Get download URL for media."""
        try:
            url = f"{self.base_url}/{media_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            return response.json().get("url")
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Failed to get media URL: {e}",
                extra={"media_id": media_id}
            )
            return None
    
    def register_phone_number(self, phone_number_id: str, pin: str = "000000", 
                            data_localization_region: Optional[str] = None) -> Dict[str, Any]:
        """Register a phone number with WhatsApp Cloud API.
        
        Args:
            phone_number_id: The WhatsApp phone number ID
            pin: 6-digit registration PIN (default: "000000")
            data_localization_region: Country code for data localization
            
        Returns:
            Registration response from WhatsApp API
        """
        try:
            # Use v20.0 as v21 has known issues with registration
            url = f"https://graph.facebook.com/v20.0/{phone_number_id}/register"
            
            payload = {
                "messaging_product": "whatsapp",
                "pin": pin
            }
            
            # Add data localization region if provided
            if data_localization_region:
                payload["data_localization_region"] = data_localization_region
            
            logger.info(
                "Registering WhatsApp phone number",
                extra={"phone_number_id": phone_number_id}
            )
            
            response = requests.post(url, json=payload, headers=self.headers)
            
            # Log detailed error for debugging
            if response.status_code != 200:
                logger.error(
                    f"WhatsApp registration failed: {response.status_code} - {response.text}",
                    extra={
                        "phone_number_id": phone_number_id,
                        "status_code": response.status_code,
                        "response": response.text
                    }
                )
            
            response.raise_for_status()
            
            result = response.json()
            logger.info(
                "WhatsApp phone number registered successfully",
                extra={
                    "phone_number_id": phone_number_id,
                    "success": result.get("success", False)
                }
            )
            
            return result
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Failed to register WhatsApp phone number: {e}",
                extra={
                    "phone_number_id": phone_number_id,
                    "error": str(e)
                }
            )
            raise ExternalServiceError(
                "WhatsApp",
                f"Failed to register phone number: {str(e)}",
                {"phone_number_id": phone_number_id}
            )
    
    def send_template_message(
        self,
        phone_number_id: str,
        template_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Send a template message via WhatsApp API.
        
        Args:
            phone_number_id: WhatsApp Business phone number ID
            template_data: Complete template message data structure
            
        Returns:
            Response from WhatsApp API or None if failed
        """
        try:
            url = f"{self.base_url}/{phone_number_id}/messages"
            
            logger.info(
                "Sending WhatsApp template message",
                extra={
                    "to": template_data.get("to"),
                    "template": template_data.get("template", {}).get("name"),
                    "phone_number_id": phone_number_id
                }
            )
            
            response = requests.post(url, json=template_data, headers=self.headers)
            
            # Log detailed error for debugging
            if response.status_code != 200:
                logger.error(
                    f"WhatsApp template API error: {response.status_code} - {response.text}",
                    extra={
                        "status_code": response.status_code,
                        "response_text": response.text,
                        "template_data": template_data
                    }
                )
            
            response.raise_for_status()
            
            result = response.json()
            if result.get("messages"):
                logger.info(
                    "WhatsApp template message sent successfully",
                    extra={
                        "message_id": result["messages"][0]["id"],
                        "to": template_data.get("to")
                    }
                )
            else:
                logger.warning(
                    "WhatsApp template message sent but no message ID returned",
                    extra={"response": result}
                )
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"Failed to send WhatsApp template message: {e}",
                extra={
                    "to": template_data.get("to"),
                    "template": template_data.get("template", {}).get("name"),
                    "error": str(e)
                }
            )
            return None