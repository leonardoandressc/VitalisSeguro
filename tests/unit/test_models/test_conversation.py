"""Unit tests for Conversation model."""
import pytest
from datetime import datetime, timedelta
from app.models.conversation import (
    Conversation, Message, ConversationContext,
    ConversationStatus, MessageRole
)


class TestMessage:
    """Test Message model."""
    
    def test_message_creation(self):
        """Test creating a message."""
        message = Message(
            role=MessageRole.USER,
            content="Hello, I need an appointment"
        )
        
        assert message.role == MessageRole.USER
        assert message.content == "Hello, I need an appointment"
        assert isinstance(message.timestamp, datetime)
        assert message.metadata == {}
    
    def test_message_to_dict(self):
        """Test converting message to dictionary."""
        timestamp = datetime.utcnow()
        message = Message(
            role=MessageRole.ASSISTANT,
            content="Sure, I can help you",
            timestamp=timestamp,
            metadata={"intent": "appointment"}
        )
        
        result = message.to_dict()
        
        assert result["role"] == "assistant"
        assert result["content"] == "Sure, I can help you"
        assert result["timestamp"] == timestamp.isoformat()
        assert result["metadata"] == {"intent": "appointment"}
    
    def test_message_from_dict(self):
        """Test creating message from dictionary."""
        timestamp = datetime.utcnow()
        data = {
            "role": "user",
            "content": "Test message",
            "timestamp": timestamp.isoformat(),
            "metadata": {"key": "value"}
        }
        
        message = Message.from_dict(data)
        
        assert message.role == MessageRole.USER
        assert message.content == "Test message"
        assert message.timestamp == timestamp
        assert message.metadata == {"key": "value"}


class TestConversationContext:
    """Test ConversationContext model."""
    
    def test_context_creation(self):
        """Test creating conversation context."""
        context = ConversationContext(
            user_name="John Doe",
            phone_number="+521234567890",
            awaiting_confirmation=True
        )
        
        assert context.user_name == "John Doe"
        assert context.phone_number == "+521234567890"
        assert context.awaiting_confirmation is True
        assert context.appointment_info is None
    
    def test_context_to_dict(self):
        """Test converting context to dictionary."""
        timestamp = datetime.utcnow()
        context = ConversationContext(
            appointment_info={"name": "John", "reason": "Checkup"},
            awaiting_confirmation=True,
            confirmation_sent_at=timestamp
        )
        
        result = context.to_dict()
        
        assert result["appointment_info"] == {"name": "John", "reason": "Checkup"}
        assert result["awaiting_confirmation"] is True
        assert result["confirmation_sent_at"] == timestamp.isoformat()


class TestConversation:
    """Test Conversation model."""
    
    def test_conversation_creation(self):
        """Test creating a conversation."""
        conversation = Conversation(
            id="test_123",
            account_id="account_456",
            phone_number="+521234567890"
        )
        
        assert conversation.id == "test_123"
        assert conversation.account_id == "account_456"
        assert conversation.phone_number == "+521234567890"
        assert conversation.status == ConversationStatus.ACTIVE
        assert len(conversation.messages) == 0
    
    def test_add_message(self):
        """Test adding messages to conversation."""
        conversation = Conversation(
            id="test_123",
            account_id="account_456",
            phone_number="+521234567890"
        )
        
        conversation.add_message(MessageRole.USER, "Hello")
        conversation.add_message(MessageRole.ASSISTANT, "Hi there!")
        
        assert len(conversation.messages) == 2
        assert conversation.messages[0].content == "Hello"
        assert conversation.messages[1].content == "Hi there!"
    
    def test_get_messages_for_llm(self):
        """Test getting messages formatted for LLM."""
        conversation = Conversation(
            id="test_123",
            account_id="account_456",
            phone_number="+521234567890"
        )
        
        conversation.add_message(MessageRole.USER, "Hello")
        conversation.add_message(MessageRole.ASSISTANT, "Hi there!")
        conversation.add_message(MessageRole.SYSTEM, "Internal note")
        
        llm_messages = conversation.get_messages_for_llm()
        
        assert len(llm_messages) == 2  # System message excluded
        assert llm_messages[0] == {"role": "user", "content": "Hello"}
        assert llm_messages[1] == {"role": "assistant", "content": "Hi there!"}
    
    def test_is_expired(self):
        """Test conversation expiration check."""
        conversation = Conversation(
            id="test_123",
            account_id="account_456",
            phone_number="+521234567890"
        )
        
        # Not expired (no expiration set)
        assert conversation.is_expired() is False
        
        # Set future expiration
        conversation.expires_at = datetime.utcnow() + timedelta(hours=1)
        assert conversation.is_expired() is False
        
        # Set past expiration
        conversation.expires_at = datetime.utcnow() - timedelta(hours=1)
        assert conversation.is_expired() is True
    
    def test_mark_completed(self):
        """Test marking conversation as completed."""
        conversation = Conversation(
            id="test_123",
            account_id="account_456",
            phone_number="+521234567890"
        )
        
        original_updated_at = conversation.updated_at
        conversation.mark_completed()
        
        assert conversation.status == ConversationStatus.COMPLETED
        assert conversation.updated_at > original_updated_at