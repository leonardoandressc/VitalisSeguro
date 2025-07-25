"""Service for handling subscription operations."""
import stripe
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from app.models.account import Account
from app.models.subscription import Subscription, SubscriptionStatus, BillingCycle
from app.models.product import PricingTier
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.product_repository import PricingTierRepository
from app.services.account_service import AccountService
from app.core.config import get_config
from app.core.exceptions import BusinessLogicError, ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)


class SubscriptionService:
    """Service for subscription operations."""
    
    def __init__(self):
        self.config = get_config()
        stripe.api_key = self.config.stripe_secret_key
        self.subscription_repo = SubscriptionRepository()
        self.tier_repo = PricingTierRepository()
        self.account_service = AccountService()
        # Feature flag for subscription enforcement
        self.enforcement_enabled = self.config.subscription_enforcement_enabled
        self.grace_period_days = self.config.subscription_grace_period_days
    
    def create_checkout_session(
        self,
        account: Account,
        tier_id: str,
        billing_cycle: BillingCycle,
        success_url: str,
        cancel_url: str
    ) -> Dict[str, Any]:
        """Create Stripe Checkout session for subscription."""
        try:
            # Get pricing tier
            tier = self.tier_repo.get(tier_id)
            if not tier:
                raise BusinessLogicError(f"Pricing tier {tier_id} not found")
            
            # Get or create Stripe customer
            if not account.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=account.email,
                    metadata={
                        "account_id": account.id,
                        "account_name": account.name
                    }
                )
                account.stripe_customer_id = customer.id
                self.account_service.update_account(account)
            
            # Determine price ID
            if billing_cycle == BillingCycle.ANNUAL:
                price_id = tier.stripe_annual_price_id
            else:
                price_id = tier.stripe_monthly_price_id
            
            if not price_id:
                # Create price in Stripe if not exists
                price_id = self._create_stripe_price(tier, billing_cycle)
            
            # Create checkout session
            session_params = {
                "mode": "subscription",
                "customer": account.stripe_customer_id,
                "line_items": [{
                    "price": price_id,
                    "quantity": 1
                }],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {
                    "account_id": account.id,
                    "tier_id": tier_id,
                    "billing_cycle": billing_cycle.value
                }
            }
            
            # Add trial period if applicable
            if tier.trial_days > 0 and not self._has_previous_subscription(account.id):
                session_params["subscription_data"] = {
                    "trial_period_days": tier.trial_days
                }
            
            session = stripe.checkout.Session.create(**session_params)
            
            logger.info(
                "Created subscription checkout session",
                extra={
                    "account_id": account.id,
                    "tier_id": tier_id,
                    "session_id": session.id
                }
            )
            
            return {
                "checkout_url": session.url,
                "session_id": session.id
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            raise ExternalServiceError("Stripe", f"Failed to create checkout session: {str(e)}")
    
    def create_portal_session(self, account: Account, return_url: str) -> Dict[str, Any]:
        """Create Stripe Customer Portal session for subscription management."""
        try:
            if not account.stripe_customer_id:
                raise BusinessLogicError("No Stripe customer found for this account")
            
            session = stripe.billing_portal.Session.create(
                customer=account.stripe_customer_id,
                return_url=return_url
            )
            
            return {
                "portal_url": session.url
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating portal session: {e}")
            raise ExternalServiceError("Stripe", f"Failed to create portal session: {str(e)}")
    
    def handle_subscription_created(self, stripe_subscription: Dict[str, Any]) -> Optional[Subscription]:
        """Handle subscription created webhook."""
        try:
            customer_id = stripe_subscription["customer"]
            
            # Find account by customer ID
            accounts = self.account_service.list_accounts()
            account = None
            for acc in accounts:
                if acc.stripe_customer_id == customer_id:
                    account = acc
                    break
            
            if not account:
                logger.error(f"No account found for customer {customer_id}")
                return None
            
            # Create or update subscription
            subscription = self.subscription_repo.get_by_account(account.id)
            if not subscription:
                subscription = Subscription(
                    id=str(uuid.uuid4()),
                    account_id=account.id,
                    stripe_customer_id=customer_id
                )
            
            # Update subscription details
            subscription.stripe_subscription_id = stripe_subscription["id"]
            subscription.status = SubscriptionStatus(stripe_subscription["status"])
            
            # Handle period dates - they might not exist for send_invoice subscriptions
            if stripe_subscription.get("current_period_start"):
                subscription.current_period_start = datetime.fromtimestamp(stripe_subscription["current_period_start"])
            if stripe_subscription.get("current_period_end"):
                subscription.current_period_end = datetime.fromtimestamp(stripe_subscription["current_period_end"])
            
            # Get tier from price
            if stripe_subscription["items"]["data"]:
                price_id = stripe_subscription["items"]["data"][0]["price"]["id"]
                tier = self.tier_repo.get_by_stripe_price(price_id)
                if tier:
                    subscription.tier_id = tier.id
                    # Determine billing cycle
                    if price_id == tier.stripe_annual_price_id:
                        subscription.billing_cycle = BillingCycle.ANNUAL
                    else:
                        subscription.billing_cycle = BillingCycle.MONTHLY
            
            # Handle trial
            if stripe_subscription.get("trial_start"):
                subscription.trial_start = datetime.fromtimestamp(stripe_subscription["trial_start"])
            if stripe_subscription.get("trial_end"):
                subscription.trial_end = datetime.fromtimestamp(stripe_subscription["trial_end"])
            
            # Save subscription
            existing_subscription = self.subscription_repo.get(subscription.id)
            if existing_subscription:
                self.subscription_repo.update(subscription)
            else:
                self.subscription_repo.create(subscription)
            
            # Update account
            account.subscription_tier_id = subscription.tier_id
            account.subscription_status = subscription.status.value
            account.subscription_current_period_end = subscription.current_period_end
            self.account_service.update_account(account)
            
            logger.info(
                "Handled subscription created",
                extra={
                    "subscription_id": subscription.id,
                    "account_id": account.id,
                    "stripe_subscription_id": stripe_subscription["id"]
                }
            )
            
            return subscription
            
        except Exception as e:
            logger.error(f"Error handling subscription created: {e}")
            return None
    
    def handle_subscription_updated(self, stripe_subscription: Dict[str, Any]) -> Optional[Subscription]:
        """Handle subscription updated webhook."""
        try:
            subscription = self.subscription_repo.get_by_stripe_subscription(stripe_subscription["id"])
            if not subscription:
                # Try to create it if it doesn't exist
                return self.handle_subscription_created(stripe_subscription)
            
            # Update subscription
            subscription.status = SubscriptionStatus(stripe_subscription["status"])
            
            # Handle period dates - they might not exist for send_invoice subscriptions
            if stripe_subscription.get("current_period_start"):
                subscription.current_period_start = datetime.fromtimestamp(stripe_subscription["current_period_start"])
            if stripe_subscription.get("current_period_end"):
                subscription.current_period_end = datetime.fromtimestamp(stripe_subscription["current_period_end"])
                
            subscription.cancel_at_period_end = stripe_subscription.get("cancel_at_period_end", False)
            
            if stripe_subscription.get("canceled_at"):
                subscription.canceled_at = datetime.fromtimestamp(stripe_subscription["canceled_at"])
            
            self.subscription_repo.update(subscription)
            
            # Update account
            account = self.account_service.get_account(subscription.account_id)
            if account:
                account.subscription_status = subscription.status.value
                account.subscription_current_period_end = subscription.current_period_end
                self.account_service.update_account(account)
            
            logger.info(
                "Handled subscription updated",
                extra={
                    "subscription_id": subscription.id,
                    "status": subscription.status.value
                }
            )
            
            return subscription
            
        except Exception as e:
            logger.error(f"Error handling subscription updated: {e}")
            return None
    
    def handle_subscription_deleted(self, stripe_subscription: Dict[str, Any]) -> bool:
        """Handle subscription deleted webhook."""
        try:
            subscription = self.subscription_repo.get_by_stripe_subscription(stripe_subscription["id"])
            if not subscription:
                logger.warning(f"No subscription found for Stripe ID {stripe_subscription['id']}")
                return False
            
            # Update subscription status
            subscription.status = SubscriptionStatus.CANCELED
            self.subscription_repo.update(subscription)
            
            # Update account
            account = self.account_service.get_account(subscription.account_id)
            if account:
                account.subscription_status = SubscriptionStatus.CANCELED.value
                account.subscription_tier_id = None
                self.account_service.update_account(account)
            
            logger.info(
                "Handled subscription deleted",
                extra={"subscription_id": subscription.id}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling subscription deleted: {e}")
            return False
    
    def check_access(self, account: Account) -> Dict[str, Any]:
        """Check if account has access based on subscription."""
        # If enforcement is disabled, always allow access
        if not self.enforcement_enabled:
            return {
                "has_access": True,
                "reason": "subscription_enforcement_disabled"
            }
        
        # Check if account is free
        if account.is_free_account:
            return {
                "has_access": True,
                "reason": "free_account"
            }
        
        # Only allow active or trialing subscriptions
        if account.subscription_status in ["active", "trialing"]:
            return {
                "has_access": True,
                "reason": f"{account.subscription_status}_subscription"
            }
        
        # All other cases are denied (including past_due, canceled, unpaid, etc.)
        return {
            "has_access": False,
            "reason": "no_active_subscription",
            "subscription_status": account.subscription_status or "none"
        }
    
    def get_account_products(self, account: Account) -> List[str]:
        """Get list of products available to an account."""
        # If account has product overrides, use those
        if account.products_override:
            return account.products_override
        
        # If free account with no tier, return all products
        if account.is_free_account and not account.subscription_tier_id:
            return ["all"]
        
        # Get products from tier
        if account.subscription_tier_id:
            tier = self.tier_repo.get(account.subscription_tier_id)
            if tier:
                return tier.products
        
        return []
    
    def send_invoice(
        self,
        account: Account,
        phone_number: Optional[str] = None,
        email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send invoice to customer via WhatsApp or email."""
        try:
            # Create Stripe customer if it doesn't exist
            if not account.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=account.email,
                    metadata={
                        "account_id": account.id,
                        "account_name": account.name
                    }
                )
                account.stripe_customer_id = customer.id
                self.account_service.update_account(account)
                logger.info(f"Created Stripe customer {customer.id} for account {account.id}")
            
            # Get latest invoice
            invoices = stripe.Invoice.list(
                customer=account.stripe_customer_id,
                limit=1
            )
            
            if not invoices.data:
                raise BusinessLogicError("No invoices found for this account")
            
            invoice = invoices.data[0]
            
            # Send invoice
            if email:
                # Send invoice via Stripe
                stripe.Invoice.send_invoice(invoice.id)
                
            result = {
                "invoice_id": invoice.id,
                "invoice_url": invoice.hosted_invoice_url,
                "amount": invoice.amount_due,
                "currency": invoice.currency,
                "status": invoice.status
            }
            
            # Send via WhatsApp if requested
            if phone_number:
                from app.services.whatsapp_template_service import WhatsAppTemplateService
                from datetime import datetime, timedelta
                
                # Calculate due date based on invoice due date or 1 day from now
                if invoice.due_date:
                    due_date = datetime.fromtimestamp(invoice.due_date)
                else:
                    due_date = datetime.now() + timedelta(days=1)
                
                # Format date in Spanish
                months_es = {
                    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
                    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
                    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
                }
                formatted_due_date = f"{due_date.day} de {months_es[due_date.month]} {due_date.year}"
                
                whatsapp_service = WhatsAppTemplateService()
                whatsapp_result = whatsapp_service.send_invoice_notification_template(
                    phone_number_id=account.phone_number_id,
                    to_number=phone_number,
                    doctor_name=account.name,
                    invoice_number=invoice.number or invoice.id,
                    amount=invoice.amount_due / 100,
                    currency=invoice.currency,
                    due_date=formatted_due_date,
                    invoice_url=invoice.hosted_invoice_url or ""
                )
                
                result["whatsapp_sent"] = bool(whatsapp_result)
            
            logger.info(
                "Sent invoice",
                extra={
                    "account_id": account.id,
                    "invoice_id": invoice.id,
                    "email": email,
                    "phone": phone_number
                }
            )
            
            return result
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error sending invoice: {e}")
            raise ExternalServiceError("Stripe", f"Failed to send invoice: {str(e)}")
    
    def _create_stripe_price(self, tier: PricingTier, billing_cycle: BillingCycle) -> str:
        """Create Stripe price for a tier."""
        try:
            # Create product in Stripe if needed
            product_id = f"tier_{tier.id}"
            try:
                product = stripe.Product.retrieve(product_id)
            except stripe.error.InvalidRequestError:
                product = stripe.Product.create(
                    id=product_id,
                    name=f"Vitalis {tier.name}",
                    description=tier.description
                )
            
            # Create price
            price = stripe.Price.create(
                product=product.id,
                currency=tier.currency.lower(),
                unit_amount=tier.get_price(billing_cycle.value),
                recurring={
                    "interval": "year" if billing_cycle == BillingCycle.ANNUAL else "month"
                },
                metadata={
                    "tier_id": tier.id,
                    "billing_cycle": billing_cycle.value
                }
            )
            
            # Update tier with price ID
            if billing_cycle == BillingCycle.ANNUAL:
                tier.stripe_annual_price_id = price.id
            else:
                tier.stripe_monthly_price_id = price.id
            
            self.tier_repo.update(tier)
            
            return price.id
            
        except stripe.error.StripeError as e:
            logger.error(f"Error creating Stripe price: {e}")
            raise
    
    def _has_previous_subscription(self, account_id: str) -> bool:
        """Check if account has had a previous subscription."""
        subscription = self.subscription_repo.get_by_account(account_id)
        return subscription is not None
    
    def list_all(self) -> List[Subscription]:
        """List all subscriptions (temporary method for migration)."""
        # This is a simple implementation since we don't have a list_all in the repo
        # In production, you'd want to implement proper pagination
        active = self.subscription_repo.list_by_status(SubscriptionStatus.ACTIVE)
        past_due = self.subscription_repo.list_by_status(SubscriptionStatus.PAST_DUE)
        trialing = self.subscription_repo.list_by_status(SubscriptionStatus.TRIALING)
        
        return active + past_due + trialing
    
    def is_tier_in_use(self, tier_id: str) -> bool:
        """Check if a pricing tier is being used by any active subscriptions."""
        # Get all subscriptions using this tier
        active = self.subscription_repo.list_by_status(SubscriptionStatus.ACTIVE)
        past_due = self.subscription_repo.list_by_status(SubscriptionStatus.PAST_DUE)
        trialing = self.subscription_repo.list_by_status(SubscriptionStatus.TRIALING)
        
        all_subs = active + past_due + trialing
        
        # Check if any subscription uses this tier
        for sub in all_subs:
            if sub.tier_id == tier_id:
                return True
                
        return False
    
    def assign_subscription_admin(
        self,
        account: Account,
        tier_id: str,
        billing_cycle: BillingCycle,
        send_invoice: bool = True,
        invoice_delivery: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Admin method to assign a subscription and create it in Stripe."""
        try:
            # Get pricing tier
            tier = self.tier_repo.get(tier_id)
            if not tier:
                raise BusinessLogicError(f"Pricing tier {tier_id} not found")
            
            # Create or get Stripe customer
            if not account.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=account.email,
                    metadata={
                        "account_id": account.id,
                        "account_name": account.name
                    }
                )
                account.stripe_customer_id = customer.id
                self.account_service.update_account(account)
            
            # Determine price ID
            if billing_cycle == BillingCycle.ANNUAL:
                price_id = tier.stripe_annual_price_id
            else:
                price_id = tier.stripe_monthly_price_id
            
            if not price_id:
                # Create price in Stripe if not exists
                price_id = self._create_stripe_price(tier, billing_cycle)
            
            # Create subscription in Stripe
            subscription_params = {
                "customer": account.stripe_customer_id,
                "items": [{
                    "price": price_id
                }],
                "collection_method": "send_invoice",
                "days_until_due": 1,  # 1 day grace period before past_due
                "payment_behavior": "default_incomplete",  # Ensures proper payment flow
                "payment_settings": {
                    "save_default_payment_method": "on_subscription"  # Automatically save payment method
                },
                "metadata": {
                    "account_id": account.id,
                    "tier_id": tier_id,
                    "billing_cycle": billing_cycle.value,
                    "admin_assigned": "true"
                }
            }
            
            # Create subscription
            stripe_subscription = stripe.Subscription.create(**subscription_params)
            
            # Handle the subscription creation in our system
            subscription = self.handle_subscription_created(stripe_subscription)
            
            # Always return a valid result even if local handling fails
            result = {
                "subscription_id": subscription.id if subscription else None,
                "stripe_subscription_id": stripe_subscription.id,
                "status": stripe_subscription.status,
                "success": True
            }
            
            if not subscription:
                logger.warning(f"Failed to create local subscription record for Stripe subscription {stripe_subscription.id}")
                result["warning"] = "Subscription created in Stripe but local record creation failed"
            
            # Send invoice if requested
            if send_invoice and invoice_delivery:
                try:
                    # Get and finalize the invoice created with the subscription
                    if stripe_subscription.latest_invoice:
                        # Finalize the draft invoice to generate payment URL
                        invoice = stripe.Invoice.finalize_invoice(stripe_subscription.latest_invoice)
                        logger.info(f"Finalized invoice {invoice.id} with URL: {invoice.hosted_invoice_url}")
                    else:
                        # Fallback: Get the latest invoice
                        invoices = stripe.Invoice.list(
                            customer=account.stripe_customer_id,
                            limit=1
                        )
                        invoice = invoices.data[0] if invoices.data else None
                    
                    if invoice:
                        
                        # Send email invoice if requested
                        if invoice_delivery.get("email"):
                            stripe.Invoice.send_invoice(invoice.id)
                            logger.info(f"Sent invoice email to {invoice_delivery.get('email')}")
                        
                        # Send WhatsApp notification if phone number provided
                        if invoice_delivery.get("phone_number"):
                            from app.services.whatsapp_template_service import WhatsAppTemplateService
                            from datetime import datetime, timedelta
                            
                            # Calculate due date (1 day from now)
                            due_date = datetime.now() + timedelta(days=1)
                            # Format date in Spanish
                            months_es = {
                                1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
                                5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
                                9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
                            }
                            formatted_due_date = f"{due_date.day} de {months_es[due_date.month]} {due_date.year}"
                            
                            whatsapp_service = WhatsAppTemplateService()
                            whatsapp_result = whatsapp_service.send_invoice_notification_template(
                                phone_number_id=account.phone_number_id,
                                to_number=invoice_delivery.get("phone_number"),
                                doctor_name=account.name,
                                invoice_number=invoice.number or invoice.id,
                                amount=invoice.amount_due / 100,
                                currency=invoice.currency,
                                due_date=formatted_due_date,
                                invoice_url=invoice.hosted_invoice_url
                            )
                            
                            if whatsapp_result:
                                logger.info(f"Sent WhatsApp invoice notification to {invoice_delivery.get('phone_number')}")
                            else:
                                logger.warning(f"Failed to send WhatsApp invoice notification")
                        
                        result["invoice"] = {
                            "invoice_id": invoice.id,
                            "invoice_url": invoice.hosted_invoice_url,
                            "amount": invoice.amount_due,
                            "currency": invoice.currency,
                            "status": invoice.status,
                            "email_sent": bool(invoice_delivery.get("email")),
                            "whatsapp_sent": bool(invoice_delivery.get("phone_number") and whatsapp_result)
                        }
                    else:
                        logger.warning("No invoice found after subscription creation")
                        
                except Exception as e:
                    logger.error(f"Failed to send invoice: {e}")
                    result["invoice_error"] = str(e)
            
            logger.info(
                "Admin assigned subscription",
                extra={
                    "account_id": account.id,
                    "tier_id": tier_id,
                    "stripe_subscription_id": stripe_subscription.id
                }
            )
            
            return result
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error assigning subscription: {e}")
            raise ExternalServiceError("Stripe", f"Failed to create subscription: {str(e)}")
    
    def get_subscription(self, account: Account) -> Optional[Subscription]:
        """Get subscription for an account."""
        return self.subscription_repo.get_by_account(account.id)
    
    def cancel_subscription(self, account: Account) -> Dict[str, Any]:
        """Cancel a subscription at period end."""
        try:
            subscription = self.subscription_repo.get_by_account(account.id)
            if not subscription:
                raise BusinessLogicError("No subscription found for this account")
            
            if not subscription.stripe_subscription_id:
                raise BusinessLogicError("No Stripe subscription found")
            
            # Cancel in Stripe
            stripe_sub = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            # Update our records
            subscription.cancel_at_period_end = True
            self.subscription_repo.update(subscription)
            
            return {
                "success": True,
                "cancel_at": stripe_sub.cancel_at,
                "current_period_end": stripe_sub.current_period_end
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error canceling subscription: {e}")
            raise ExternalServiceError("Stripe", f"Failed to cancel subscription: {str(e)}")
    
    def set_free_account(
        self,
        account: Account,
        is_free: bool,
        reason: Optional[str] = None,
        expires_at: Optional[str] = None,
        products: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Set account as free or remove free status."""
        from datetime import datetime
        
        account.is_free_account = is_free
        
        if is_free:
            account.free_account_reason = reason
            if expires_at:
                account.free_account_expires = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            else:
                account.free_account_expires = None
            
            if products:
                account.products_override = products
        else:
            account.free_account_reason = None
            account.free_account_expires = None
            account.products_override = None
        
        self.account_service.update_account(account)
        
        return {
            "success": True,
            "is_free_account": account.is_free_account,
            "free_account_reason": account.free_account_reason,
            "free_account_expires": account.free_account_expires.isoformat() if account.free_account_expires else None
        }