"""WhatsApp Template Service for sending template messages."""
from typing import Dict, Any, Optional, List
from datetime import datetime
import pytz
from app.core.logging import get_logger
from app.integrations.whatsapp.client import WhatsAppClient
from app.integrations.whatsapp.models import OutgoingMessage, MessageType
from app.utils.phone_utils import format_phone_for_whatsapp

logger = get_logger(__name__)


class WhatsAppTemplateService:
    """Service for sending WhatsApp template messages."""
    
    # Template names as configured in WhatsApp Business
    APPOINTMENT_CONFIRMATION_TEMPLATE = "appointment_confirmation"
    APPOINTMENT_REMINDER_TEMPLATE = "appointment_reminder"
    
    def __init__(self):
        """Initialize WhatsApp template service."""
        self.client = WhatsAppClient()
    
    def send_appointment_confirmation_template(
        self,
        phone_number_id: str,
        to_number: str,
        patient_name: str,
        doctor_name: str,
        appointment_date: str,
        appointment_time: str,
        location: str,
        language_code: str = "es_MX"
    ) -> Optional[Dict[str, Any]]:
        """Send appointment confirmation using WhatsApp template.
        
        Args:
            phone_number_id: WhatsApp Business phone number ID
            to_number: Recipient phone number
            patient_name: Patient's name
            doctor_name: Doctor's name
            appointment_date: Formatted date string
            appointment_time: Formatted time string
            location: Office location/address
            language_code: Template language code (default: Spanish Mexico)
            
        Returns:
            Response from WhatsApp API or None if failed
        """
        try:
            # Format phone number
            formatted_phone = format_phone_for_whatsapp(to_number)
            
            logger.info(
                "Sending appointment confirmation template",
                extra={
                    "phone_number_id": phone_number_id,
                    "to": formatted_phone,
                    "patient": patient_name,
                    "doctor": doctor_name,
                    "date": appointment_date,
                    "time": appointment_time
                }
            )
            
            # Build template message
            template_data = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": formatted_phone,
                "type": "template",
                "template": {
                    "name": self.APPOINTMENT_CONFIRMATION_TEMPLATE,
                    "language": {
                        "code": language_code
                    },
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": patient_name},
                                {"type": "text", "text": appointment_date},
                                {"type": "text", "text": appointment_time},
                                {"type": "text", "text": doctor_name},
                                {"type": "text", "text": location}
                            ]
                        }
                    ]
                }
            }
            
            # Send via client
            response = self.client.send_template_message(
                phone_number_id=phone_number_id,
                template_data=template_data
            )
            
            if response:
                logger.info(
                    "Appointment confirmation template sent successfully",
                    extra={
                        "message_id": response.get("messages", [{}])[0].get("id"),
                        "to": formatted_phone
                    }
                )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Failed to send appointment confirmation template: {e}",
                extra={
                    "phone_number_id": phone_number_id,
                    "to": to_number,
                    "error": str(e)
                }
            )
            return None
    
    def send_appointment_reminder_template(
        self,
        phone_number_id: str,
        to_number: str,
        patient_name: str,
        appointment_time: str,
        calendar_name: Optional[str] = None,
        language_code: str = "es_MX"
    ) -> Optional[Dict[str, Any]]:
        """Send appointment reminder using WhatsApp template.
        
        Args:
            phone_number_id: WhatsApp Business phone number ID
            to_number: Recipient phone number
            patient_name: Patient's name
            appointment_time: Formatted time string
            calendar_name: Optional calendar/service name
            language_code: Template language code (default: Spanish Mexico)
            
        Returns:
            Response from WhatsApp API or None if failed
        """
        try:
            # Format phone number
            formatted_phone = format_phone_for_whatsapp(to_number)
            
            logger.info(
                "Sending appointment reminder template",
                extra={
                    "phone_number_id": phone_number_id,
                    "to": formatted_phone,
                    "patient": patient_name,
                    "time": appointment_time,
                    "calendar": calendar_name
                }
            )
            
            # Build template parameters
            parameters = [
                {"type": "text", "text": patient_name},
                {"type": "text", "text": appointment_time}
            ]
            
            # Add calendar name if provided
            if calendar_name:
                parameters.append({"type": "text", "text": calendar_name})
            
            # Build template message
            template_data = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": formatted_phone,
                "type": "template",
                "template": {
                    "name": self.APPOINTMENT_REMINDER_TEMPLATE,
                    "language": {
                        "code": language_code
                    },
                    "components": [
                        {
                            "type": "body",
                            "parameters": parameters
                        }
                    ]
                }
            }
            
            # Add interactive buttons if template supports them
            # This depends on how the template is configured in WhatsApp Business
            template_data["template"]["components"].append({
                "type": "button",
                "sub_type": "quick_reply",
                "index": "0",
                "parameters": []
            })
            template_data["template"]["components"].append({
                "type": "button",
                "sub_type": "quick_reply",
                "index": "1",
                "parameters": []
            })
            template_data["template"]["components"].append({
                "type": "button",
                "sub_type": "quick_reply",
                "index": "2",
                "parameters": []
            })
            
            # Send via client
            response = self.client.send_template_message(
                phone_number_id=phone_number_id,
                template_data=template_data
            )
            
            if response:
                logger.info(
                    "Appointment reminder template sent successfully",
                    extra={
                        "message_id": response.get("messages", [{}])[0].get("id"),
                        "to": formatted_phone
                    }
                )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Failed to send appointment reminder template: {e}",
                extra={
                    "phone_number_id": phone_number_id,
                    "to": to_number,
                    "error": str(e)
                }
            )
            return None
    
    def send_generic_template(
        self,
        phone_number_id: str,
        to_number: str,
        template_name: str,
        language_code: str,
        header_params: Optional[List[Dict[str, str]]] = None,
        body_params: Optional[List[Dict[str, str]]] = None,
        button_params: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """Send a generic WhatsApp template message.
        
        Args:
            phone_number_id: WhatsApp Business phone number ID
            to_number: Recipient phone number
            template_name: Template name as configured in WhatsApp Business
            language_code: Template language code
            header_params: Optional header parameters
            body_params: Optional body parameters
            button_params: Optional button parameters
            
        Returns:
            Response from WhatsApp API or None if failed
        """
        try:
            # Format phone number
            formatted_phone = format_phone_for_whatsapp(to_number)
            
            # Build template message
            template_data = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": formatted_phone,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {
                        "code": language_code
                    },
                    "components": []
                }
            }
            
            # Add header parameters if provided
            if header_params:
                template_data["template"]["components"].append({
                    "type": "header",
                    "parameters": header_params
                })
            
            # Add body parameters if provided
            if body_params:
                template_data["template"]["components"].append({
                    "type": "body",
                    "parameters": body_params
                })
            
            # Add button parameters if provided
            if button_params:
                for idx, button in enumerate(button_params):
                    template_data["template"]["components"].append({
                        "type": "button",
                        "sub_type": button.get("sub_type", "quick_reply"),
                        "index": str(idx),
                        "parameters": button.get("parameters", [])
                    })
            
            # Send via client
            response = self.client.send_template_message(
                phone_number_id=phone_number_id,
                template_data=template_data
            )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Failed to send template message: {e}",
                extra={
                    "phone_number_id": phone_number_id,
                    "to": to_number,
                    "template": template_name,
                    "error": str(e)
                }
            )
            return None
    
    def send_invoice_notification_template(
        self,
        phone_number_id: str,
        to_number: str,
        doctor_name: str,
        invoice_number: str,
        amount: float,
        currency: str,
        due_date: str,
        invoice_url: str
    ) -> Optional[Dict[str, Any]]:
        """Send invoice notification template via WhatsApp.
        
        Args:
            phone_number_id: WhatsApp Business phone number ID
            to_number: Recipient phone number (with country code)
            doctor_name: Name of the doctor
            invoice_number: Invoice number or ID
            amount: Invoice amount (already divided by 100)
            currency: Currency code (e.g., 'MXN')
            due_date: Formatted due date string
            invoice_url: URL to view/pay the invoice
            
        Returns:
            Response from WhatsApp API or None if failed
        """
        try:
            # Format amount with 2 decimals and thousands separator
            formatted_amount = f"{amount:,.2f}"
            
            template_data = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "template",
                "template": {
                    "name": "invoice_notification",
                    "language": {
                        "code": "es_MX"
                    },
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": doctor_name},
                                {"type": "text", "text": invoice_number},
                                {"type": "text", "text": formatted_amount},
                                {"type": "text", "text": currency.upper()},
                                {"type": "text", "text": due_date},
                                {"type": "text", "text": invoice_url}
                            ]
                        }
                    ]
                }
            }
            
            # Send via client
            response = self.client.send_template_message(
                phone_number_id=phone_number_id,
                template_data=template_data
            )
            
            if response:
                logger.info(
                    "Invoice notification sent via WhatsApp",
                    extra={
                        "invoice_number": invoice_number,
                        "to": to_number,
                        "amount": formatted_amount,
                        "currency": currency
                    }
                )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Failed to send invoice notification: {e}",
                extra={
                    "phone_number_id": phone_number_id,
                    "to": to_number,
                    "invoice_number": invoice_number,
                    "error": str(e)
                }
            )
            return None