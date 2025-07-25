"""Repository for message deduplication using Firestore."""
from typing import Optional
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter
from app.core.logging import get_logger
from app.core.config import get_config
from app.utils.firebase import get_firestore_client

logger = get_logger(__name__)


class MessageDeduplicationRepository:
    """Repository for tracking processed messages to prevent duplicates."""
    
    COLLECTION_NAME = "processed_messages"
    
    def __init__(self):
        self.db = get_firestore_client()
        self.config = get_config()
        self.collection = self.db.collection(self.COLLECTION_NAME)
    
    def check_and_mark_processed(
        self,
        message_id: str,
        account_id: str,
        phone_number: str
    ) -> bool:
        """
        Atomically check if a message has been processed and mark it if not.
        
        Args:
            message_id: WhatsApp message ID
            account_id: Account that received the message
            phone_number: Sender's phone number
            
        Returns:
            True if message is new and was marked as processed
            False if message was already processed
        """
        try:
            # Create document reference
            doc_ref = self.collection.document(f"{account_id}_{message_id}")
            
            # Use transaction for atomic check-and-set
            transaction = self.db.transaction()
            
            @firestore.transactional
            def check_and_create(transaction, doc_ref):
                # Check if document exists
                doc = doc_ref.get(transaction=transaction)
                
                if doc.exists:
                    # Message already processed
                    processed_at = doc.to_dict().get("processed_at")
                    processed_at_str = processed_at.isoformat() if processed_at else None
                    logger.info(
                        "Duplicate message detected",
                        extra={
                            "message_id": message_id,
                            "account_id": account_id,
                            "processed_at": processed_at_str
                        }
                    )
                    return False
                
                # Mark as processed
                transaction.set(doc_ref, {
                    "message_id": message_id,
                    "account_id": account_id,
                    "phone_number": phone_number,
                    "processed_at": datetime.utcnow(),
                    "ttl": datetime.utcnow() + timedelta(hours=2)  # Auto-cleanup after 2 hours
                })
                
                logger.info(
                    "Message marked as processed",
                    extra={
                        "message_id": message_id,
                        "account_id": account_id
                    }
                )
                return True
            
            # Execute transaction
            return check_and_create(transaction, doc_ref)
            
        except Exception as e:
            logger.error(
                f"Error in message deduplication: {e}",
                extra={
                    "message_id": message_id,
                    "account_id": account_id
                }
            )
            # On error, allow processing to continue
            return True
    
    def cleanup_old_messages(self, hours: Optional[int] = None) -> int:
        """
        Remove processed messages older than specified hours.
        
        Args:
            hours: Number of hours to keep messages (default from config)
            
        Returns:
            Number of documents deleted
        """
        try:
            if hours is None:
                hours = getattr(self.config, 'message_deduplication_ttl_hours', 2)
            
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Query for old documents
            old_docs = self.collection.where(
                filter=FieldFilter("processed_at", "<", cutoff_time)
            ).stream()
            
            # Delete in batches
            batch = self.db.batch()
            count = 0
            
            for doc in old_docs:
                batch.delete(doc.reference)
                count += 1
                
                # Commit every 500 deletes
                if count % 500 == 0:
                    batch.commit()
                    batch = self.db.batch()
            
            # Commit remaining
            if count % 500 != 0:
                batch.commit()
            
            logger.info(f"Cleaned up {count} old processed messages")
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up old messages: {e}")
            return 0
    
    def get_processed_count(self, account_id: Optional[str] = None) -> int:
        """
        Get count of processed messages.
        
        Args:
            account_id: Optional account ID to filter by
            
        Returns:
            Number of processed messages
        """
        try:
            query = self.collection
            
            if account_id:
                query = query.where(
                    filter=FieldFilter("account_id", "==", account_id)
                )
            
            # Note: This is expensive for large collections
            # In production, consider using aggregation queries
            return sum(1 for _ in query.stream())
            
        except Exception as e:
            logger.error(f"Error getting processed count: {e}")
            return 0