"""Service for managing payments."""
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models.payment import Payment, PaymentStatus
from app.repositories.payment_repository import PaymentRepository
from app.core.exceptions import ValidationError, ResourceNotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)


class PaymentService:
    """Service for payment business logic."""
    
    def __init__(self):
        self.repository = PaymentRepository()
    
    def create_payment(self, payment: Payment) -> Payment:
        """Create a new payment."""
        # Validate payment
        if payment.amount <= 0:
            raise ValidationError("Payment amount must be greater than 0")
        
        # Create in repository
        return self.repository.create(payment)
    
    def get_payment(self, payment_id: str) -> Optional[Payment]:
        """Get a payment by ID."""
        return self.repository.get(payment_id)
    
    def update_payment_status(
        self,
        payment_id: str,
        status: PaymentStatus,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Payment:
        """Update payment status."""
        payment = self.repository.get(payment_id)
        if not payment:
            raise ResourceNotFoundError(f"Payment not found: {payment_id}")
        
        # Update status
        payment.status = status
        payment.updated_at = datetime.utcnow()
        
        # Update metadata if provided
        if metadata:
            if not payment.metadata:
                payment.metadata = {}
            payment.metadata.update(metadata)
        
        # Save to repository
        return self.repository.update(payment)
    
    def get_payments_by_conversation(self, conversation_id: str) -> List[Payment]:
        """Get all payments for a conversation."""
        return self.repository.get_by_conversation(conversation_id)
    
    def get_payments_by_account(
        self,
        account_id: str,
        status: Optional[PaymentStatus] = None
    ) -> List[Payment]:
        """Get payments for an account, optionally filtered by status."""
        return self.repository.get_by_account(account_id, status)
    
    def cancel_payment(self, payment_id: str) -> Payment:
        """Cancel a payment."""
        payment = self.repository.get(payment_id)
        if not payment:
            raise ResourceNotFoundError(f"Payment not found: {payment_id}")
        
        if payment.status != PaymentStatus.PENDING:
            raise ValidationError(
                f"Cannot cancel payment with status: {payment.status.value}"
            )
        
        # Update status
        payment.status = PaymentStatus.CANCELLED
        payment.updated_at = datetime.utcnow()
        
        # Add cancellation metadata
        if not payment.metadata:
            payment.metadata = {}
        payment.metadata["cancelled_at"] = datetime.utcnow().isoformat()
        
        # Save to repository
        return self.repository.update(payment)
    
    def mark_payment_completed(
        self,
        payment_id: str,
        transaction_id: Optional[str] = None
    ) -> Payment:
        """Mark a payment as completed."""
        payment = self.repository.get(payment_id)
        if not payment:
            raise ResourceNotFoundError(f"Payment not found: {payment_id}")
        
        if payment.status != PaymentStatus.PENDING:
            raise ValidationError(
                f"Cannot complete payment with status: {payment.status.value}"
            )
        
        # Update status
        payment.status = PaymentStatus.COMPLETED
        payment.updated_at = datetime.utcnow()
        
        # Add completion metadata
        if not payment.metadata:
            payment.metadata = {}
        payment.metadata["completed_at"] = datetime.utcnow().isoformat()
        
        if transaction_id:
            payment.metadata["transaction_id"] = transaction_id
        
        # Save to repository
        return self.repository.update(payment)
    
    def get_payment_stats(self, account_id: str) -> Dict[str, Any]:
        """Get payment statistics for an account."""
        payments = self.repository.get_by_account(account_id)
        
        stats = {
            "total_payments": len(payments),
            "total_amount": 0,
            "completed_amount": 0,
            "pending_amount": 0,
            "cancelled_amount": 0,
            "by_status": {}
        }
        
        for status in PaymentStatus:
            stats["by_status"][status.value] = 0
        
        for payment in payments:
            stats["by_status"][payment.status.value] += 1
            stats["total_amount"] += payment.amount
            
            if payment.status == PaymentStatus.COMPLETED:
                stats["completed_amount"] += payment.amount
            elif payment.status == PaymentStatus.PENDING:
                stats["pending_amount"] += payment.amount
            elif payment.status == PaymentStatus.CANCELLED:
                stats["cancelled_amount"] += payment.amount
        
        return stats