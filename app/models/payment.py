"""Payment domain model."""
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


class PaymentStatus(str, Enum):
    """Payment status enumeration."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass
class Payment:
    """Represents a payment for an appointment."""
    id: str
    account_id: str
    conversation_id: str
    customer_phone: str
    customer_name: str
    amount: int  # in cents
    currency: str
    stripe_payment_intent_id: str
    stripe_checkout_session_id: str
    status: PaymentStatus = PaymentStatus.PENDING
    payment_link: Optional[str] = None
    appointment_id: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = "vitalis-whatsapp"  # Default for backward compatibility
    
    def is_completed(self) -> bool:
        """Check if payment is completed."""
        return self.status == PaymentStatus.COMPLETED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert payment to dictionary for storage."""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "conversation_id": self.conversation_id,
            "appointment_id": self.appointment_id,
            "customer_phone": self.customer_phone,
            "customer_name": self.customer_name,
            "amount": self.amount,
            "currency": self.currency,
            "stripe_payment_intent_id": self.stripe_payment_intent_id,
            "stripe_checkout_session_id": self.stripe_checkout_session_id,
            "status": self.status.value,
            "payment_link": self.payment_link,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "source": self.source
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Payment":
        """Create payment from dictionary."""
        return cls(
            id=data["id"],
            account_id=data["account_id"],
            conversation_id=data["conversation_id"],
            appointment_id=data.get("appointment_id"),
            customer_phone=data["customer_phone"],
            customer_name=data["customer_name"],
            amount=data["amount"],
            currency=data["currency"],
            stripe_payment_intent_id=data["stripe_payment_intent_id"],
            stripe_checkout_session_id=data["stripe_checkout_session_id"],
            status=PaymentStatus(data.get("status", PaymentStatus.PENDING.value)),
            payment_link=data.get("payment_link"),
            paid_at=datetime.fromisoformat(data["paid_at"]) if data.get("paid_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            metadata=data.get("metadata", {}),
            source=data.get("source", "vitalis-whatsapp")  # Default for backward compatibility
        )