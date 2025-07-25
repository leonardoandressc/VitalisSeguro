"""Repository for managing conversations in Firestore."""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter
from app.models.conversation import Conversation, ConversationStatus
from app.core.exceptions import ResourceNotFoundError, VitalisException
from app.core.logging import get_logger
from app.core.config import get_config
from app.utils.firebase import get_firestore_client

logger = get_logger(__name__)


class ConversationRepository:
    """Repository for conversation data access."""
    
    COLLECTION_NAME = "conversations"
    
    def __init__(self):
        self.db = get_firestore_client()
        self.collection = self.db.collection(self.COLLECTION_NAME)
        self.config = get_config()
    
    def create(self, conversation: Conversation) -> Conversation:
        """Create a new conversation in Firestore."""
        try:
            # Set expiration time
            if not conversation.expires_at:
                conversation.expires_at = datetime.utcnow() + timedelta(hours=self.config.conversation_ttl_hours)
            
            # Convert to dict and store
            doc_ref = self.collection.document(conversation.id)
            doc_ref.set(conversation.to_dict())
            
            logger.info(
                "Created conversation",
                extra={
                    "conversation_id": conversation.id,
                    "account_id": conversation.account_id,
                    "phone_number": conversation.phone_number
                }
            )
            
            return conversation
        except Exception as e:
            logger.error(
                f"Failed to create conversation: {e}",
                extra={"conversation_id": conversation.id}
            )
            raise VitalisException(f"Failed to create conversation: {str(e)}")
    
    def get(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        try:
            doc = self.collection.document(conversation_id).get()
            
            if not doc.exists:
                return None
            
            conversation = Conversation.from_dict(doc.to_dict())
            
            # Check if expired
            if conversation.is_expired():
                logger.info(
                    "Conversation has expired",
                    extra={"conversation_id": conversation_id}
                )
                conversation.status = ConversationStatus.EXPIRED
                self.update(conversation)
            
            return conversation
        except Exception as e:
            logger.error(
                f"Failed to get conversation: {e}",
                extra={"conversation_id": conversation_id}
            )
            raise VitalisException(f"Failed to get conversation: {str(e)}")
    
    def get_or_create(self, account_id: str, phone_number: str, conversation_id: str) -> Conversation:
        """Get existing conversation or create a new one."""
        # First, check if there's an active conversation for this user
        active_conversations = self.find_active_by_phone(phone_number, account_id)
        if active_conversations:
            # Return the most recent active conversation
            active_conversation = active_conversations[0]  # Already ordered by updated_at desc
            logger.info(
                f"Reusing existing active conversation",
                extra={
                    "conversation_id": active_conversation.id,
                    "account_id": account_id,
                    "phone_number": phone_number
                }
            )
            return active_conversation
        
        # Try to get the specific conversation requested
        conversation = self.get(conversation_id)
        
        if conversation:
            # Check if it's the same account and phone number
            if conversation.account_id != account_id or conversation.phone_number != phone_number:
                logger.warning(
                    "Conversation ID mismatch",
                    extra={
                        "conversation_id": conversation_id,
                        "expected_account_id": account_id,
                        "actual_account_id": conversation.account_id,
                        "expected_phone": phone_number,
                        "actual_phone": conversation.phone_number
                    }
                )
                # Create new conversation with different ID
                conversation_id = f"{account_id}_{phone_number}_{datetime.utcnow().timestamp()}"
            elif conversation.status in [ConversationStatus.COMPLETED, ConversationStatus.EXPIRED, ConversationStatus.CANCELLED]:
                # Conversation is completed/expired/cancelled, create a new session
                logger.info(
                    f"Creating new conversation session as existing one is {conversation.status.value}",
                    extra={
                        "old_conversation_id": conversation_id,
                        "old_status": conversation.status.value
                    }
                )
                # Generate new conversation ID with session counter
                session_number = self._get_next_session_number(account_id, phone_number)
                if session_number == 1:
                    # First new session after the original - start with session_2
                    conversation_id = f"{account_id}_{phone_number}_session_2"
                else:
                    conversation_id = f"{account_id}_{phone_number}_session_{session_number}"
            else:
                return conversation
        
        # Create new conversation
        conversation = Conversation(
            id=conversation_id,
            account_id=account_id,
            phone_number=phone_number
        )
        
        return self.create(conversation)
    
    def _get_next_session_number(self, account_id: str, phone_number: str) -> int:
        """Get the next session number for a user's conversations."""
        try:
            # Query conversations by account_id and phone_number fields instead of document ID
            docs = self.collection.where(
                filter=FieldFilter("account_id", "==", account_id)
            ).where(
                filter=FieldFilter("phone_number", "==", phone_number)
            ).get()
            
            highest_session = 0
            for doc in docs:
                doc_id = doc.id
                if "_session_" in doc_id:
                    try:
                        session_part = doc_id.split("_session_")[-1]
                        session_num = int(session_part)
                        highest_session = max(highest_session, session_num)
                    except (ValueError, IndexError):
                        continue
            
            return highest_session + 1
            
        except Exception as e:
            logger.error(f"Error getting next session number: {e}")
            # Fallback to timestamp-based if session counting fails
            return int(datetime.utcnow().timestamp()) % 10000
    
    def update(self, conversation: Conversation) -> Conversation:
        """Update an existing conversation."""
        try:
            conversation.updated_at = datetime.utcnow()
            
            # Check message count limit
            if len(conversation.messages) > self.config.max_conversation_messages:
                # Keep only the most recent messages
                conversation.messages = conversation.messages[-self.config.max_conversation_messages:]
                logger.warning(
                    "Conversation message limit reached, truncating",
                    extra={
                        "conversation_id": conversation.id,
                        "message_count": len(conversation.messages)
                    }
                )
            
            doc_ref = self.collection.document(conversation.id)
            doc_ref.update(conversation.to_dict())
            
            logger.info(
                "Updated conversation",
                extra={
                    "conversation_id": conversation.id,
                    "status": conversation.status.value,
                    "message_count": len(conversation.messages)
                }
            )
            
            return conversation
        except Exception as e:
            logger.error(
                f"Failed to update conversation: {e}",
                extra={"conversation_id": conversation.id}
            )
            raise VitalisException(f"Failed to update conversation: {str(e)}")
    
    def find_active_by_phone(self, phone_number: str, account_id: Optional[str] = None) -> List[Conversation]:
        """Find active conversations by phone number."""
        try:
            query = self.collection
            query = query.where(filter=FieldFilter("phone_number", "==", phone_number))
            query = query.where(filter=FieldFilter("status", "==", ConversationStatus.ACTIVE.value))
            
            if account_id:
                query = query.where(filter=FieldFilter("account_id", "==", account_id))
            
            # Note: Removed order_by to avoid composite index requirement
            # We'll sort in memory instead
            docs = query.stream()
            conversations = []
            
            for doc in docs:
                conversation = Conversation.from_dict(doc.to_dict())
                if not conversation.is_expired():
                    conversations.append(conversation)
            
            # Sort by updated_at in memory (most recent first)
            conversations.sort(key=lambda c: c.updated_at, reverse=True)
            
            return conversations
        except Exception as e:
            logger.error(
                f"Failed to find conversations: {e}",
                extra={"phone_number": phone_number, "account_id": account_id}
            )
            raise VitalisException(f"Failed to find conversations: {str(e)}")
    
    def get_by_account_id(self, account_id: str) -> List[Conversation]:
        """Get all conversations for an account."""
        try:
            query = self.collection.where(
                filter=FieldFilter("account_id", "==", account_id)
            )
            
            docs = query.stream()
            conversations = []
            
            for doc in docs:
                conversation = Conversation.from_dict(doc.to_dict())
                conversations.append(conversation)
            
            return conversations
        except Exception as e:
            logger.error(
                f"Failed to get conversations by account: {e}",
                extra={"account_id": account_id}
            )
            raise VitalisException(f"Failed to get conversations: {str(e)}")
    
    def get_by_date_range(
        self, 
        account_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Conversation]:
        """Get conversations within a date range for an account."""
        try:
            query = self.collection.where(
                filter=FieldFilter("account_id", "==", account_id)
            ).where(
                filter=FieldFilter("created_at", ">=", start_date.isoformat())
            ).where(
                filter=FieldFilter("created_at", "<=", end_date.isoformat())
            )
            
            docs = query.stream()
            conversations = []
            
            for doc in docs:
                conversation = Conversation.from_dict(doc.to_dict())
                conversations.append(conversation)
            
            return conversations
        except Exception as e:
            logger.error(
                f"Failed to get conversations by date range: {e}",
                extra={
                    "account_id": account_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
            )
            raise VitalisException(f"Failed to get conversations: {str(e)}")
    
    def cleanup_expired(self) -> int:
        """Clean up expired conversations."""
        try:
            now = datetime.utcnow()
            
            # Query for expired conversations
            query = self.collection.where(
                filter=FieldFilter("expires_at", "<=", now.isoformat())
            )
            
            docs = query.stream()
            deleted_count = 0
            
            for doc in docs:
                doc.reference.delete()
                deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired conversations")
            
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup expired conversations: {e}")
            raise VitalisException(f"Failed to cleanup conversations: {str(e)}")
    
    def delete(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        try:
            self.collection.document(conversation_id).delete()
            logger.info(
                "Deleted conversation",
                extra={"conversation_id": conversation_id}
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to delete conversation: {e}",
                extra={"conversation_id": conversation_id}
            )
            raise VitalisException(f"Failed to delete conversation: {str(e)}")
    
    def update_metadata(self, conversation_id: str, metadata: Dict[str, Any]) -> bool:
        """Update conversation metadata."""
        try:
            conversation = self.get(conversation_id)
            if not conversation:
                raise ResourceNotFoundError(f"Conversation {conversation_id} not found")
            
            # Update metadata
            if not conversation.context.metadata:
                conversation.context.metadata = {}
            conversation.context.metadata.update(metadata)
            
            # Update the conversation
            self.update(conversation)
            
            logger.info(
                "Updated conversation metadata",
                extra={
                    "conversation_id": conversation_id,
                    "metadata_keys": list(metadata.keys())
                }
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to update conversation metadata: {e}",
                extra={"conversation_id": conversation_id}
            )
            raise VitalisException(f"Failed to update metadata: {str(e)}")