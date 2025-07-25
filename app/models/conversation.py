"""Conversation domain model."""
from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


class ConversationStatus(str, Enum):
    """Conversation status enumeration."""
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class MessageRole(str, Enum):
    """Message role enumeration."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """Represents a single message in a conversation."""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create message from dictionary."""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {})
        )


@dataclass
class ConversationContext:
    """Context information extracted from conversation."""
    appointment_info: Optional[Dict[str, Any]] = None
    user_name: Optional[str] = None
    phone_number: Optional[str] = None
    awaiting_confirmation: bool = False
    confirmation_sent_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "appointment_info": self.appointment_info,
            "user_name": self.user_name,
            "phone_number": self.phone_number,
            "awaiting_confirmation": self.awaiting_confirmation,
            "confirmation_sent_at": self.confirmation_sent_at.isoformat() if self.confirmation_sent_at else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        """Create context from dictionary."""
        return cls(
            appointment_info=data.get("appointment_info"),
            user_name=data.get("user_name"),
            phone_number=data.get("phone_number"),
            awaiting_confirmation=data.get("awaiting_confirmation", False),
            confirmation_sent_at=datetime.fromisoformat(data["confirmation_sent_at"]) if data.get("confirmation_sent_at") else None,
            metadata=data.get("metadata")
        )


@dataclass
class Conversation:
    """Represents a conversation with a user."""
    id: str
    account_id: str
    phone_number: str
    messages: List[Message] = field(default_factory=list)
    context: ConversationContext = field(default_factory=ConversationContext)
    status: ConversationStatus = ConversationStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    def add_message(self, role: MessageRole, content: str, metadata: Dict[str, Any] = None) -> None:
        """Add a message to the conversation."""
        message = Message(role=role, content=content, metadata=metadata or {})
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
    
    def get_messages_for_llm(self) -> List[Dict[str, str]]:
        """Get messages formatted for LLM input."""
        return [
            {"role": msg.role.value, "content": msg.content}
            for msg in self.messages
            if msg.role != MessageRole.SYSTEM  # Exclude system messages from LLM context
        ]
    
    def is_expired(self) -> bool:
        """Check if conversation has expired."""
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        return False
    
    def mark_completed(self) -> None:
        """Mark conversation as completed."""
        self.status = ConversationStatus.COMPLETED
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert conversation to dictionary for storage."""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "phone_number": self.phone_number,
            "messages": [msg.to_dict() for msg in self.messages],
            "context": self.context.to_dict(),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Conversation":
        """Create conversation from dictionary."""
        return cls(
            id=data["id"],
            account_id=data["account_id"],
            phone_number=data["phone_number"],
            messages=[Message.from_dict(msg) for msg in data.get("messages", [])],
            context=ConversationContext.from_dict(data.get("context", {})),
            status=ConversationStatus(data.get("status", ConversationStatus.ACTIVE.value)),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None
        )