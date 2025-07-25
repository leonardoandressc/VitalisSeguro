"""Subscription domain model."""
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


class SubscriptionStatus(str, Enum):
    """Subscription status enumeration."""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"
    UNPAID = "unpaid"
    PAUSED = "paused"


class BillingCycle(str, Enum):
    """Billing cycle enumeration."""
    MONTHLY = "monthly"
    ANNUAL = "annual"


@dataclass
class Subscription:
    """Represents a platform subscription for an account."""
    id: str
    account_id: str
    stripe_customer_id: str
    stripe_subscription_id: Optional[str] = None
    tier_id: Optional[str] = None
    status: SubscriptionStatus = SubscriptionStatus.INCOMPLETE
    billing_cycle: BillingCycle = BillingCycle.MONTHLY
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    canceled_at: Optional[datetime] = None
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Custom overrides
    custom_price: Optional[int] = None  # Override tier price in cents
    custom_products: Optional[List[str]] = None  # Override tier products
    discount_percentage: Optional[int] = None  # Discount percentage (0-100)
    
    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
    
    def is_past_due(self) -> bool:
        """Check if subscription is past due."""
        return self.status == SubscriptionStatus.PAST_DUE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert subscription to dictionary for storage."""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "stripe_customer_id": self.stripe_customer_id,
            "stripe_subscription_id": self.stripe_subscription_id,
            "tier_id": self.tier_id,
            "status": self.status.value,
            "billing_cycle": self.billing_cycle.value,
            "current_period_start": self.current_period_start.isoformat() if self.current_period_start else None,
            "current_period_end": self.current_period_end.isoformat() if self.current_period_end else None,
            "cancel_at_period_end": self.cancel_at_period_end,
            "canceled_at": self.canceled_at.isoformat() if self.canceled_at else None,
            "trial_start": self.trial_start.isoformat() if self.trial_start else None,
            "trial_end": self.trial_end.isoformat() if self.trial_end else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "custom_price": self.custom_price,
            "custom_products": self.custom_products,
            "discount_percentage": self.discount_percentage
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subscription":
        """Create subscription from dictionary."""
        return cls(
            id=data["id"],
            account_id=data["account_id"],
            stripe_customer_id=data["stripe_customer_id"],
            stripe_subscription_id=data.get("stripe_subscription_id"),
            tier_id=data.get("tier_id"),
            status=SubscriptionStatus(data.get("status", SubscriptionStatus.INCOMPLETE.value)),
            billing_cycle=BillingCycle(data.get("billing_cycle", BillingCycle.MONTHLY.value)),
            current_period_start=datetime.fromisoformat(data["current_period_start"]) if data.get("current_period_start") else None,
            current_period_end=datetime.fromisoformat(data["current_period_end"]) if data.get("current_period_end") else None,
            cancel_at_period_end=data.get("cancel_at_period_end", False),
            canceled_at=datetime.fromisoformat(data["canceled_at"]) if data.get("canceled_at") else None,
            trial_start=datetime.fromisoformat(data["trial_start"]) if data.get("trial_start") else None,
            trial_end=datetime.fromisoformat(data["trial_end"]) if data.get("trial_end") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.utcnow(),
            metadata=data.get("metadata", {}),
            custom_price=data.get("custom_price"),
            custom_products=data.get("custom_products"),
            discount_percentage=data.get("discount_percentage")
        )