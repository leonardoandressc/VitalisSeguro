"""Account domain model."""
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


class AccountStatus(str, Enum):
    """Account status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


@dataclass
class Account:
    """Represents a business account with WhatsApp-to-GHL integration."""
    id: str
    name: str
    phone_number_id: str
    calendar_id: str
    location_id: str
    assigned_user_id: str
    email: Optional[str] = None  # Doctor's email for Stripe account matching
    custom_prompt: Optional[str] = None
    status: AccountStatus = AccountStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Stripe Connect fields (for patient payments)
    stripe_enabled: bool = False
    stripe_connect_account_id: Optional[str] = None
    stripe_onboarding_completed: bool = False
    stripe_charges_enabled: bool = False
    stripe_payouts_enabled: bool = False
    stripe_details_submitted: bool = False  # Track if account details are submitted
    stripe_capability_status: Optional[str] = None  # Track capability status
    stripe_last_webhook_update: Optional[datetime] = None  # Track last webhook update
    appointment_price: int = 50000  # in cents (500.00 MXN)
    currency: str = "mxn"
    payment_description: str = "Pago de consulta médica"
    
    # Subscription fields (for platform billing)
    stripe_customer_id: Optional[str] = None  # Customer ID for subscription billing
    subscription_tier_id: Optional[str] = None  # Current pricing tier
    subscription_status: Optional[str] = None  # active, past_due, canceled, etc.
    subscription_current_period_end: Optional[datetime] = None
    is_free_account: bool = False  # For beta/testing accounts
    free_account_reason: Optional[str] = None  # beta_tester, internal, partner, etc.
    free_account_expires: Optional[datetime] = None  # When free access expires
    products_override: Optional[List[str]] = None  # Override tier products for this account
    
    def is_active(self) -> bool:
        """Check if account is active."""
        return self.status == AccountStatus.ACTIVE
    
    def has_subscription_access(self) -> bool:
        """Check if account has active subscription access."""
        # Free accounts always have access (unless expired)
        if self.is_free_account:
            # Check if free access has expired
            if self.free_account_expires and datetime.utcnow() > self.free_account_expires:
                return False
            return True
        
        # Only active and trialing subscriptions have access
        # No grace period for past_due - immediate access denial
        return self.subscription_status in ["active", "trialing"]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert account to dictionary for storage."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone_number_id": self.phone_number_id,
            "calendar_id": self.calendar_id,
            "location_id": self.location_id,
            "assigned_user_id": self.assigned_user_id,
            "custom_prompt": self.custom_prompt,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            # Stripe fields
            "stripe_enabled": self.stripe_enabled,
            "stripe_connect_account_id": self.stripe_connect_account_id,
            "stripe_onboarding_completed": self.stripe_onboarding_completed,
            "stripe_charges_enabled": self.stripe_charges_enabled,
            "stripe_payouts_enabled": self.stripe_payouts_enabled,
            "stripe_details_submitted": self.stripe_details_submitted,
            "stripe_capability_status": self.stripe_capability_status,
            "stripe_last_webhook_update": self.stripe_last_webhook_update.isoformat() if self.stripe_last_webhook_update else None,
            "appointment_price": self.appointment_price,
            "currency": self.currency,
            "payment_description": self.payment_description,
            # Subscription fields
            "stripe_customer_id": self.stripe_customer_id,
            "subscription_tier_id": self.subscription_tier_id,
            "subscription_status": self.subscription_status,
            "subscription_current_period_end": self.subscription_current_period_end.isoformat() if self.subscription_current_period_end else None,
            "is_free_account": self.is_free_account,
            "free_account_reason": self.free_account_reason,
            "free_account_expires": self.free_account_expires.isoformat() if self.free_account_expires else None,
            "products_override": self.products_override
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Account":
        """Create account from dictionary."""
        # Check if Stripe is functionally enabled (has connect account and completed onboarding)
        stripe_enabled = data.get("stripe_enabled", False)
        
        # If stripe_enabled is not explicitly set but we have a connect account and onboarding is complete,
        # consider Stripe as enabled
        if not stripe_enabled and data.get("stripe_connect_account_id") and data.get("stripe_onboarding_completed"):
            stripe_enabled = True
            
        # Additional check: if charges are enabled and payouts are enabled, Stripe is functionally enabled
        if not stripe_enabled and data.get("stripe_charges_enabled") and data.get("stripe_payouts_enabled"):
            stripe_enabled = True
            
        # Log the detection for debugging
        if data.get("stripe_connect_account_id") or data.get("stripe_charges_enabled"):
            from app.core.logging import get_logger
            logger = get_logger(__name__)
            logger.info(
                "Stripe detection for account",
                extra={
                    "account_id": data.get("id"),
                    "stripe_enabled_field": data.get("stripe_enabled"),
                    "stripe_connect_account_id": bool(data.get("stripe_connect_account_id")),
                    "stripe_onboarding_completed": data.get("stripe_onboarding_completed"),
                    "stripe_charges_enabled": data.get("stripe_charges_enabled"),
                    "stripe_payouts_enabled": data.get("stripe_payouts_enabled"),
                    "final_stripe_enabled": stripe_enabled
                }
            )
        
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),  # Use ID as fallback if name is missing
            email=data.get("email"),
            phone_number_id=data["phone_number_id"],
            calendar_id=data["calendar_id"],
            location_id=data["location_id"],
            assigned_user_id=data["assigned_user_id"],
            custom_prompt=data.get("custom_prompt"),
            status=AccountStatus(data.get("status", AccountStatus.ACTIVE.value)),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.utcnow(),
            metadata=data.get("metadata", {}),
            # Stripe fields with defaults
            stripe_enabled=stripe_enabled,
            stripe_connect_account_id=data.get("stripe_connect_account_id"),
            stripe_onboarding_completed=data.get("stripe_onboarding_completed", False),
            stripe_charges_enabled=data.get("stripe_charges_enabled", False),
            stripe_payouts_enabled=data.get("stripe_payouts_enabled", False),
            stripe_details_submitted=data.get("stripe_details_submitted", False),
            stripe_capability_status=data.get("stripe_capability_status"),
            stripe_last_webhook_update=datetime.fromisoformat(data["stripe_last_webhook_update"]) if data.get("stripe_last_webhook_update") else None,
            appointment_price=data.get("appointment_price", 50000),
            currency=data.get("currency", "mxn"),
            payment_description=data.get("payment_description", "Pago de consulta médica"),
            # Subscription fields
            stripe_customer_id=data.get("stripe_customer_id"),
            subscription_tier_id=data.get("subscription_tier_id"),
            subscription_status=data.get("subscription_status"),
            subscription_current_period_end=datetime.fromisoformat(data["subscription_current_period_end"]) if data.get("subscription_current_period_end") else None,
            is_free_account=data.get("is_free_account", False),
            free_account_reason=data.get("free_account_reason"),
            free_account_expires=datetime.fromisoformat(data["free_account_expires"]) if data.get("free_account_expires") else None,
            products_override=data.get("products_override")
        )