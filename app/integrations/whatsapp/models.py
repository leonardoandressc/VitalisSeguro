"""WhatsApp message models."""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from app.utils.phone_utils import normalize_phone


class MessageType(str, Enum):
    """WhatsApp message types."""
    TEXT = "text"
    INTERACTIVE = "interactive"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    LOCATION = "location"
    CONTACTS = "contacts"
    STICKER = "sticker"


class InteractiveType(str, Enum):
    """WhatsApp interactive message types."""
    BUTTON_REPLY = "button_reply"
    LIST_REPLY = "list_reply"


@dataclass
class WhatsAppMessage:
    """Incoming WhatsApp message."""
    message_id: str
    from_number: str
    phone_number_id: str
    message_type: MessageType
    timestamp: str
    text: Optional[str] = None
    interactive_reply: Optional[Dict[str, Any]] = None
    media_id: Optional[str] = None
    media_url: Optional[str] = None
    contact_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_webhook_data(cls, data: Dict[str, Any]) -> Optional["WhatsAppMessage"]:
        """Parse WhatsApp message from webhook data."""
        try:
            # Extract message data from webhook structure
            entry = data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])
            
            if not messages:
                return None
            
            message = messages[0]
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            
            # Extract contact name from contacts data
            contact_name = None
            contacts = value.get("contacts", [])
            if contacts:
                contact_name = contacts[0].get("profile", {}).get("name")
            
            # Determine message type and extract content
            message_type = None
            text = None
            interactive_reply = None
            media_id = None
            
            if "text" in message:
                message_type = MessageType.TEXT
                text = message["text"]["body"]
            elif "interactive" in message:
                message_type = MessageType.INTERACTIVE
                interactive_reply = message["interactive"]
                # Extract button reply text if available
                if interactive_reply.get("type") == "button_reply":
                    text = interactive_reply.get("button_reply", {}).get("title")
            elif "image" in message:
                message_type = MessageType.IMAGE
                media_id = message["image"].get("id")
            # Add other message types as needed
            
            if not message_type:
                return None
            
            # Normalize the phone number for consistent storage
            from_number = normalize_phone(message["from"])
            
            return cls(
                message_id=message["id"],
                from_number=from_number,
                phone_number_id=phone_number_id,
                message_type=message_type,
                timestamp=message["timestamp"],
                text=text,
                interactive_reply=interactive_reply,
                media_id=media_id,
                contact_name=contact_name,
                metadata={"raw_message": message}
            )
        except (KeyError, IndexError, TypeError) as e:
            return None


@dataclass
class ButtonReply:
    """Button for interactive messages."""
    id: str
    title: str
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to WhatsApp API format."""
        return {
            "type": "reply",
            "reply": {
                "id": self.id,
                "title": self.title
            }
        }


@dataclass
class InteractiveMessage:
    """Interactive message with buttons."""
    body_text: str
    buttons: List[ButtonReply]
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to WhatsApp API format."""
        interactive = {
            "type": "button",
            "body": {"text": self.body_text},
            "action": {
                "buttons": [button.to_dict() for button in self.buttons]
            }
        }
        
        if self.header_text:
            interactive["header"] = {"type": "text", "text": self.header_text}
        
        if self.footer_text:
            interactive["footer"] = {"text": self.footer_text}
        
        return interactive


@dataclass
class OutgoingMessage:
    """Outgoing WhatsApp message."""
    to: str
    message_type: MessageType
    text: Optional[str] = None
    interactive: Optional[InteractiveMessage] = None
    
    def to_dict(self, phone_number_id: str) -> Dict[str, Any]:
        """Convert to WhatsApp API format."""
        message = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self.to
        }
        
        if self.message_type == MessageType.TEXT and self.text:
            message["type"] = "text"
            message["text"] = {"body": self.text}
        elif self.message_type == MessageType.INTERACTIVE and self.interactive:
            message["type"] = "interactive"
            message["interactive"] = self.interactive.to_dict()
        
        return message