"""Service for managing conversations."""
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models.conversation import Conversation, ConversationStatus, MessageRole
from app.repositories.conversation_repository import ConversationRepository
from app.core.exceptions import ConversationError, ValidationError
from app.core.logging import get_logger
from app.core.config import get_config
from app.utils.phone_utils import normalize_phone

logger = get_logger(__name__)


class ConversationService:
    """Service for conversation business logic."""
    
    def __init__(self):
        self.repository = ConversationRepository()
        self.config = get_config()
    
    def get_or_create_conversation(
        self,
        account_id: str,
        phone_number: str,
        user_name: Optional[str] = None
    ) -> Conversation:
        """Get or create a conversation for a user."""
        # Normalize phone number for consistent storage
        normalized_phone = normalize_phone(phone_number)
        
        # Generate conversation ID based on account and normalized phone
        conversation_id = f"{account_id}_{normalized_phone}"
        
        # Get or create conversation with normalized phone
        conversation = self.repository.get_or_create(account_id, normalized_phone, conversation_id)
        
        # Update user name if provided
        if user_name and not conversation.context.user_name:
            conversation.context.user_name = user_name
            conversation.context.phone_number = phone_number
            self.repository.update(conversation)
        
        return conversation
    
    def add_user_message(
        self,
        conversation_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Conversation:
        """Add a user message to the conversation."""
        conversation = self.repository.get(conversation_id)
        if not conversation:
            raise ConversationError(f"Conversation not found", conversation_id=conversation_id)
        
        if conversation.status != ConversationStatus.ACTIVE:
            raise ConversationError(
                f"Cannot add message to {conversation.status.value} conversation",
                conversation_id=conversation_id
            )
        
        # Add the message
        conversation.add_message(MessageRole.USER, content, metadata)
        
        # Update in repository
        return self.repository.update(conversation)
    
    def add_assistant_message(
        self,
        conversation_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Conversation:
        """Add an assistant message to the conversation."""
        conversation = self.repository.get(conversation_id)
        if not conversation:
            raise ConversationError(f"Conversation not found", conversation_id=conversation_id)
        
        # Add the message
        conversation.add_message(MessageRole.ASSISTANT, content, metadata)
        
        # Update in repository
        return self.repository.update(conversation)
    
    def update_appointment_info(
        self,
        conversation_id: str,
        appointment_info: Dict[str, Any],
        awaiting_confirmation: bool = False
    ) -> Conversation:
        """Update appointment information in conversation context."""
        conversation = self.repository.get(conversation_id)
        if not conversation:
            raise ConversationError(f"Conversation not found", conversation_id=conversation_id)
        
        # Update context
        conversation.context.appointment_info = appointment_info
        conversation.context.awaiting_confirmation = awaiting_confirmation
        
        if awaiting_confirmation:
            conversation.context.confirmation_sent_at = datetime.utcnow()
        
        # Extract user name if available
        if appointment_info.get("name") and not conversation.context.user_name:
            conversation.context.user_name = appointment_info["name"]
        
        # Update in repository
        return self.repository.update(conversation)
    
    def confirm_appointment(self, conversation_id: str) -> Conversation:
        """Mark appointment as confirmed and complete conversation."""
        conversation = self.repository.get(conversation_id)
        if not conversation:
            raise ConversationError(f"Conversation not found", conversation_id=conversation_id)
        
        if not conversation.context.awaiting_confirmation:
            raise ConversationError(
                "No appointment awaiting confirmation",
                conversation_id=conversation_id
            )
        
        # Update context
        conversation.context.awaiting_confirmation = False
        conversation.mark_completed()
        
        # Add system message
        conversation.add_message(
            MessageRole.SYSTEM,
            "Appointment confirmed and created in GoHighLevel",
            {"action": "appointment_confirmed"}
        )
        
        # Update in repository
        return self.repository.update(conversation)
    
    def cancel_appointment(self, conversation_id: str) -> Conversation:
        """Cancel appointment confirmation."""
        conversation = self.repository.get(conversation_id)
        if not conversation:
            raise ConversationError(f"Conversation not found", conversation_id=conversation_id)
        
        # Clear appointment context
        conversation.context.appointment_info = None
        conversation.context.awaiting_confirmation = False
        conversation.context.confirmation_sent_at = None
        
        # Add system message
        conversation.add_message(
            MessageRole.SYSTEM,
            "Appointment cancelled by user",
            {"action": "appointment_cancelled"}
        )
        
        # Update in repository
        return self.repository.update(conversation)
    
    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """Get conversation history formatted for LLM."""
        conversation = self.repository.get(conversation_id)
        if not conversation:
            return []
        
        return conversation.get_messages_for_llm()
    
    def get_active_conversations(self, account_id: str) -> List[Conversation]:
        """Get all active conversations for an account."""
        # This would typically include pagination, but keeping it simple for now
        conversations = []
        
        # Note: This is a simplified implementation
        # In production, you'd want to implement proper querying
        logger.warning("get_active_conversations not fully implemented")
        
        return conversations
    
    def cleanup_expired_conversations(self) -> int:
        """Clean up expired conversations."""
        try:
            count = self.repository.cleanup_expired()
            if count > 0:
                logger.info(f"Cleaned up {count} expired conversations")
            return count
        except Exception as e:
            logger.error(f"Failed to cleanup conversations: {e}")
            raise