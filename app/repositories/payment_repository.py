"""Repository for managing payments in Firestore."""
from typing import Optional, List, Dict, Any
from datetime import datetime
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter
from app.models.payment import Payment, PaymentStatus
from app.core.exceptions import ResourceNotFoundError, VitalisException
from app.core.logging import get_logger
from app.utils.firebase import get_firestore_client

logger = get_logger(__name__)


class PaymentRepository:
    """Repository for payment data access."""
    
    COLLECTION_NAME = "payments"
    
    def __init__(self):
        self.db = get_firestore_client()
        self.collection = self.db.collection(self.COLLECTION_NAME)
    
    def create(self, payment: Payment) -> Payment:
        """Create a new payment in Firestore."""
        try:
            doc_ref = self.collection.document(payment.id)
            doc_ref.set(payment.to_dict())
            
            logger.info(
                "Created payment",
                extra={
                    "payment_id": payment.id,
                    "account_id": payment.account_id,
                    "amount": payment.amount,
                    "status": payment.status.value
                }
            )
            
            return payment
        except Exception as e:
            logger.error(
                f"Failed to create payment: {e}",
                extra={"payment_id": payment.id}
            )
            raise VitalisException(f"Failed to create payment: {str(e)}")
    
    def get(self, payment_id: str) -> Optional[Payment]:
        """Get a payment by ID."""
        try:
            doc = self.collection.document(payment_id).get()
            
            if not doc.exists:
                return None
            
            return Payment.from_dict(doc.to_dict())
        except Exception as e:
            logger.error(
                f"Failed to get payment: {e}",
                extra={"payment_id": payment_id}
            )
            raise VitalisException(f"Failed to get payment: {str(e)}")
    
    def update(self, payment: Payment) -> Payment:
        """Update an existing payment."""
        try:
            doc_ref = self.collection.document(payment.id)
            doc_ref.update(payment.to_dict())
            
            logger.info(
                "Updated payment",
                extra={
                    "payment_id": payment.id,
                    "status": payment.status.value
                }
            )
            
            return payment
        except Exception as e:
            logger.error(
                f"Failed to update payment: {e}",
                extra={"payment_id": payment.id}
            )
            raise VitalisException(f"Failed to update payment: {str(e)}")
    
    def get_by_checkout_session(self, session_id: str) -> Optional[Payment]:
        """Get payment by Stripe checkout session ID."""
        try:
            query = self.collection.where(
                filter=FieldFilter("stripe_checkout_session_id", "==", session_id)
            ).limit(1)
            
            docs = list(query.stream())
            
            if not docs:
                return None
            
            return Payment.from_dict(docs[0].to_dict())
        except Exception as e:
            logger.error(
                f"Failed to get payment by checkout session: {e}",
                extra={"session_id": session_id}
            )
            raise VitalisException(f"Failed to get payment: {str(e)}")
    
    def get_by_conversation(self, conversation_id: str) -> List[Payment]:
        """Get all payments for a conversation."""
        try:
            query = self.collection.where(
                filter=FieldFilter("conversation_id", "==", conversation_id)
            ).order_by("created_at", direction=firestore.Query.DESCENDING)
            
            docs = query.stream()
            payments = []
            
            for doc in docs:
                payment = Payment.from_dict(doc.to_dict())
                payments.append(payment)
            
            return payments
        except Exception as e:
            logger.error(
                f"Failed to get payments by conversation: {e}",
                extra={"conversation_id": conversation_id}
            )
            raise VitalisException(f"Failed to get payments: {str(e)}")
    
    def get_by_account(
        self, 
        account_id: str,
        status: Optional[PaymentStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Payment]:
        """Get payments for an account with optional filters."""
        try:
            query = self.collection.where(
                filter=FieldFilter("account_id", "==", account_id)
            )
            
            if status:
                query = query.where(
                    filter=FieldFilter("status", "==", status.value)
                )
            
            if start_date:
                query = query.where(
                    filter=FieldFilter("created_at", ">=", start_date.isoformat())
                )
            
            if end_date:
                query = query.where(
                    filter=FieldFilter("created_at", "<=", end_date.isoformat())
                )
            
            query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
            
            docs = query.stream()
            payments = []
            
            for doc in docs:
                payment = Payment.from_dict(doc.to_dict())
                payments.append(payment)
            
            return payments
        except Exception as e:
            logger.error(
                f"Failed to get payments by account: {e}",
                extra={"account_id": account_id}
            )
            raise VitalisException(f"Failed to get payments: {str(e)}")
    
    def update_status(
        self, 
        payment_id: str, 
        status: PaymentStatus,
        paid_at: Optional[datetime] = None,
        appointment_id: Optional[str] = None
    ) -> bool:
        """Update payment status and related fields."""
        try:
            update_data = {
                "status": status.value
            }
            
            if paid_at:
                update_data["paid_at"] = paid_at.isoformat()
            
            if appointment_id:
                update_data["appointment_id"] = appointment_id
            
            doc_ref = self.collection.document(payment_id)
            doc_ref.update(update_data)
            
            logger.info(
                "Updated payment status",
                extra={
                    "payment_id": payment_id,
                    "new_status": status.value,
                    "appointment_id": appointment_id
                }
            )
            
            return True
        except Exception as e:
            logger.error(
                f"Failed to update payment status: {e}",
                extra={"payment_id": payment_id}
            )
            raise VitalisException(f"Failed to update payment status: {str(e)}")