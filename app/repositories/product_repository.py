"""Repository for product and pricing tier management."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.product import Product, ProductStatus, PricingTier
from app.utils.firebase import get_firestore_client
from app.core.logging import get_logger

logger = get_logger(__name__)


class ProductRepository:
    """Repository for managing products in Firestore."""
    
    def __init__(self):
        self.db = get_firestore_client()
        self.collection_name = "products"
    
    def create(self, product: Product) -> Product:
        """Create a new product."""
        try:
            doc_ref = self.db.collection(self.collection_name).document(product.id)
            doc_ref.set(product.to_dict())
            
            logger.info(
                "Created product",
                extra={"product_id": product.id, "product_name": product.name}
            )
            
            return product
        except Exception as e:
            logger.error(f"Error creating product: {e}")
            raise
    
    def get(self, product_id: str) -> Optional[Product]:
        """Get product by ID."""
        try:
            doc = self.db.collection(self.collection_name).document(product_id).get()
            
            if doc.exists:
                return Product.from_dict(doc.to_dict())
            
            return None
        except Exception as e:
            logger.error(f"Error getting product {product_id}: {e}")
            return None
    
    def update(self, product: Product) -> Product:
        """Update an existing product."""
        try:
            product.updated_at = datetime.utcnow()
            
            doc_ref = self.db.collection(self.collection_name).document(product.id)
            doc_ref.update(product.to_dict())
            
            logger.info(
                "Updated product",
                extra={"product_id": product.id}
            )
            
            return product
        except Exception as e:
            logger.error(f"Error updating product: {e}")
            raise
    
    def list_active(self) -> List[Product]:
        """List all active products."""
        try:
            query = self.db.collection(self.collection_name)\
                .where("status", "in", [ProductStatus.ACTIVE.value, ProductStatus.BETA.value])
            
            docs = query.get()
            
            return [Product.from_dict(doc.to_dict()) for doc in docs]
        except Exception as e:
            logger.error(f"Error listing active products: {e}")
            return []
    
    def list_all(self) -> List[Product]:
        """List all products."""
        try:
            docs = self.db.collection(self.collection_name).get()
            return [Product.from_dict(doc.to_dict()) for doc in docs]
        except Exception as e:
            logger.error(f"Error listing all products: {e}")
            return []
    
    def delete(self, product_id: str) -> bool:
        """Delete a product."""
        try:
            self.db.collection(self.collection_name).document(product_id).delete()
            
            logger.info(
                "Deleted product",
                extra={"product_id": product_id}
            )
            
            return True
        except Exception as e:
            logger.error(f"Error deleting product: {e}")
            return False


class PricingTierRepository:
    """Repository for managing pricing tiers in Firestore."""
    
    def __init__(self):
        self.db = get_firestore_client()
        self.collection_name = "pricing_tiers"
    
    def create(self, tier: PricingTier) -> PricingTier:
        """Create a new pricing tier."""
        try:
            doc_ref = self.db.collection(self.collection_name).document(tier.id)
            doc_ref.set(tier.to_dict())
            
            logger.info(
                "Created pricing tier",
                extra={
                    "tier_id": tier.id,
                    "tier_name": tier.name,
                    "monthly_price": tier.monthly_price
                }
            )
            
            return tier
        except Exception as e:
            logger.error(f"Error creating pricing tier: {e}")
            raise
    
    def get(self, tier_id: str) -> Optional[PricingTier]:
        """Get pricing tier by ID."""
        try:
            doc = self.db.collection(self.collection_name).document(tier_id).get()
            
            if doc.exists:
                return PricingTier.from_dict(doc.to_dict())
            
            return None
        except Exception as e:
            logger.error(f"Error getting pricing tier {tier_id}: {e}")
            return None
    
    def update(self, tier: PricingTier) -> PricingTier:
        """Update an existing pricing tier."""
        try:
            tier.updated_at = datetime.utcnow()
            
            doc_ref = self.db.collection(self.collection_name).document(tier.id)
            doc_ref.update(tier.to_dict())
            
            logger.info(
                "Updated pricing tier",
                extra={"tier_id": tier.id}
            )
            
            return tier
        except Exception as e:
            logger.error(f"Error updating pricing tier: {e}")
            raise
    
    def list_all(self) -> List[PricingTier]:
        """List all pricing tiers sorted by order."""
        try:
            query = self.db.collection(self.collection_name)\
                .order_by("sort_order")
            
            docs = query.get()
            
            return [PricingTier.from_dict(doc.to_dict()) for doc in docs]
        except Exception as e:
            logger.error(f"Error listing pricing tiers: {e}")
            return []
    
    def get_by_stripe_price(self, stripe_price_id: str) -> Optional[PricingTier]:
        """Get pricing tier by Stripe price ID."""
        try:
            # Check monthly price ID
            query = self.db.collection(self.collection_name)\
                .where("stripe_monthly_price_id", "==", stripe_price_id)\
                .limit(1)
            
            docs = query.get()
            for doc in docs:
                return PricingTier.from_dict(doc.to_dict())
            
            # Check annual price ID
            query = self.db.collection(self.collection_name)\
                .where("stripe_annual_price_id", "==", stripe_price_id)\
                .limit(1)
            
            docs = query.get()
            for doc in docs:
                return PricingTier.from_dict(doc.to_dict())
            
            return None
        except Exception as e:
            logger.error(f"Error getting tier by Stripe price {stripe_price_id}: {e}")
            return None
    
    def delete(self, tier_id: str) -> bool:
        """Delete a pricing tier."""
        try:
            self.db.collection(self.collection_name).document(tier_id).delete()
            
            logger.info(
                "Deleted pricing tier",
                extra={"tier_id": tier_id}
            )
            
            return True
        except Exception as e:
            logger.error(f"Error deleting pricing tier: {e}")
            return False