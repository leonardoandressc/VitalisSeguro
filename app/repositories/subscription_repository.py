"""Repository for subscription management."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.subscription import Subscription, SubscriptionStatus
from app.utils.firebase import get_firestore_client
from app.core.logging import get_logger

logger = get_logger(__name__)


class SubscriptionRepository:
    """Repository for managing subscriptions in Firestore."""
    
    def __init__(self):
        self.db = get_firestore_client()
        self.collection_name = "subscriptions"
    
    def create(self, subscription: Subscription) -> Subscription:
        """Create a new subscription."""
        try:
            doc_ref = self.db.collection(self.collection_name).document(subscription.id)
            doc_ref.set(subscription.to_dict())
            
            logger.info(
                "Created subscription",
                extra={
                    "subscription_id": subscription.id,
                    "account_id": subscription.account_id,
                    "tier_id": subscription.tier_id
                }
            )
            
            return subscription
        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            raise
    
    def get(self, subscription_id: str) -> Optional[Subscription]:
        """Get subscription by ID."""
        try:
            doc = self.db.collection(self.collection_name).document(subscription_id).get()
            
            if doc.exists:
                return Subscription.from_dict(doc.to_dict())
            
            return None
        except Exception as e:
            logger.error(f"Error getting subscription {subscription_id}: {e}")
            return None
    
    def get_by_account(self, account_id: str) -> Optional[Subscription]:
        """Get subscription by account ID."""
        try:
            query = self.db.collection(self.collection_name)\
                .where("account_id", "==", account_id)\
                .limit(1)
            
            docs = query.get()
            
            for doc in docs:
                return Subscription.from_dict(doc.to_dict())
            
            return None
        except Exception as e:
            logger.error(f"Error getting subscription for account {account_id}: {e}")
            return None
    
    def get_by_stripe_subscription(self, stripe_subscription_id: str) -> Optional[Subscription]:
        """Get subscription by Stripe subscription ID."""
        try:
            query = self.db.collection(self.collection_name)\
                .where("stripe_subscription_id", "==", stripe_subscription_id)\
                .limit(1)
            
            docs = query.get()
            
            for doc in docs:
                return Subscription.from_dict(doc.to_dict())
            
            return None
        except Exception as e:
            logger.error(f"Error getting subscription for Stripe ID {stripe_subscription_id}: {e}")
            return None
    
    def update(self, subscription: Subscription) -> Subscription:
        """Update an existing subscription."""
        try:
            subscription.updated_at = datetime.utcnow()
            
            doc_ref = self.db.collection(self.collection_name).document(subscription.id)
            doc_ref.update(subscription.to_dict())
            
            logger.info(
                "Updated subscription",
                extra={
                    "subscription_id": subscription.id,
                    "status": subscription.status.value
                }
            )
            
            return subscription
        except Exception as e:
            logger.error(f"Error updating subscription: {e}")
            raise
    
    def list_by_status(self, status: SubscriptionStatus, limit: int = 100) -> List[Subscription]:
        """List subscriptions by status."""
        try:
            query = self.db.collection(self.collection_name)\
                .where("status", "==", status.value)\
                .limit(limit)
            
            docs = query.get()
            
            return [Subscription.from_dict(doc.to_dict()) for doc in docs]
        except Exception as e:
            logger.error(f"Error listing subscriptions by status: {e}")
            return []
    
    def list_expiring_trials(self, days_ahead: int = 3) -> List[Subscription]:
        """List subscriptions with trials expiring soon."""
        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)
            
            query = self.db.collection(self.collection_name)\
                .where("status", "==", SubscriptionStatus.TRIALING.value)\
                .where("trial_end", "<=", cutoff_date.isoformat())\
                .limit(100)
            
            docs = query.get()
            
            return [Subscription.from_dict(doc.to_dict()) for doc in docs]
        except Exception as e:
            logger.error(f"Error listing expiring trials: {e}")
            return []
    
    def list_past_due(self) -> List[Subscription]:
        """List all past due subscriptions."""
        return self.list_by_status(SubscriptionStatus.PAST_DUE)
    
    def delete(self, subscription_id: str) -> bool:
        """Delete a subscription."""
        try:
            self.db.collection(self.collection_name).document(subscription_id).delete()
            
            logger.info(
                "Deleted subscription",
                extra={"subscription_id": subscription_id}
            )
            
            return True
        except Exception as e:
            logger.error(f"Error deleting subscription: {e}")
            return False