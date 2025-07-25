"""Product domain model."""
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


class ProductStatus(str, Enum):
    """Product status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BETA = "beta"


@dataclass
class Product:
    """Represents a product/feature that can be sold."""
    id: str
    name: str
    description: str
    status: ProductStatus = ProductStatus.ACTIVE
    features: List[str] = field(default_factory=list)  # List of feature flags
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_active(self) -> bool:
        """Check if product is active."""
        return self.status in [ProductStatus.ACTIVE, ProductStatus.BETA]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert product to dictionary for storage."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "features": self.features,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Product":
        """Create product from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            status=ProductStatus(data.get("status", ProductStatus.ACTIVE.value)),
            features=data.get("features", []),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.utcnow(),
            metadata=data.get("metadata", {})
        )


@dataclass
class PricingTier:
    """Represents a pricing tier with products and prices."""
    id: str
    name: str
    description: str
    monthly_price: int  # Price in cents
    annual_price: int  # Price in cents
    currency: str = "MXN"
    products: List[str] = field(default_factory=list)  # List of product IDs
    limits: Dict[str, int] = field(default_factory=dict)  # Usage limits
    features: List[str] = field(default_factory=list)  # Additional features
    trial_days: int = 0  # Trial period in days
    is_popular: bool = False  # Mark as popular/recommended
    sort_order: int = 0  # Display order
    max_appointments_per_month: Optional[int] = None  # Max appointments limit
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Stripe integration
    stripe_monthly_price_id: Optional[str] = None  # Stripe Price ID for monthly
    stripe_annual_price_id: Optional[str] = None  # Stripe Price ID for annual
    
    def get_price(self, billing_cycle: str) -> int:
        """Get price based on billing cycle."""
        if billing_cycle == "annual":
            return self.annual_price
        return self.monthly_price
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert pricing tier to dictionary for storage."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "monthly_price": self.monthly_price,
            "annual_price": self.annual_price,
            "currency": self.currency,
            "products": self.products,
            "limits": self.limits,
            "features": self.features,
            "trial_days": self.trial_days,
            "is_popular": self.is_popular,
            "sort_order": self.sort_order,
            "max_appointments_per_month": self.max_appointments_per_month,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "stripe_monthly_price_id": self.stripe_monthly_price_id,
            "stripe_annual_price_id": self.stripe_annual_price_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PricingTier":
        """Create pricing tier from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            monthly_price=data["monthly_price"],
            annual_price=data["annual_price"],
            currency=data.get("currency", "MXN"),
            products=data.get("products", []),
            limits=data.get("limits", {}),
            features=data.get("features", []),
            trial_days=data.get("trial_days", 0),
            is_popular=data.get("is_popular", False),
            sort_order=data.get("sort_order", 0),
            max_appointments_per_month=data.get("max_appointments_per_month"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.utcnow(),
            metadata=data.get("metadata", {}),
            stripe_monthly_price_id=data.get("stripe_monthly_price_id"),
            stripe_annual_price_id=data.get("stripe_annual_price_id")
        )