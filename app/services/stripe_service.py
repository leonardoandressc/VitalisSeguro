"""Service for handling Stripe operations."""
import stripe
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from app.models.account import Account
from app.models.payment import Payment, PaymentStatus
from app.repositories.payment_repository import PaymentRepository
from app.core.config import get_config
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)


class StripeService:
    """Service for Stripe payment operations."""
    
    def __init__(self):
        self.config = get_config()
        stripe.api_key = self.config.stripe_secret_key
        self.payment_repo = PaymentRepository()
    
    def create_connect_account_link(
        self,
        account: Account,
        return_url: str,
        refresh_url: str
    ) -> Dict[str, Any]:
        """Create Stripe Connect onboarding link."""
        try:
            new_account_created = False
            
            # Create account if doesn't exist
            if not account.stripe_connect_account_id:
                # Use actual email if available, otherwise use placeholder
                email = account.email if account.email else f"{account.id}@vitalis.com"
                
                stripe_account = stripe.Account.create(
                    type="express",
                    country="MX",
                    email=email,
                    capabilities={
                        "card_payments": {"requested": True},
                        "transfers": {"requested": True}
                    },
                    business_profile={
                        "name": account.name,
                        "product_description": "Servicios médicos y consultas"
                    }
                )
                account.stripe_connect_account_id = stripe_account.id
                new_account_created = True
                # IMPORTANT: Caller must update the account in the repository immediately
            
            # Create account link
            account_link = stripe.AccountLink.create(
                account=account.stripe_connect_account_id,
                return_url=return_url,
                refresh_url=refresh_url,
                type="account_onboarding"
            )
            
            logger.info(
                "Created Stripe Connect onboarding link",
                extra={
                    "account_id": account.id,
                    "stripe_account_id": account.stripe_connect_account_id
                }
            )
            
            return {
                "url": account_link.url,
                "expires_at": account_link.expires_at,
                "stripe_account_id": account.stripe_connect_account_id,
                "new_account_created": new_account_created
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating account link: {e}")
            raise ExternalServiceError(
                "Stripe",
                f"Failed to create onboarding link: {str(e)}"
            )
    
    def get_account_status(self, stripe_account_id: str) -> Dict[str, Any]:
        """Get Stripe Connect account status."""
        try:
            account = stripe.Account.retrieve(stripe_account_id)
            
            return {
                "charges_enabled": account.charges_enabled,
                "payouts_enabled": account.payouts_enabled,
                "details_submitted": account.details_submitted,
                "requirements": account.requirements.to_dict() if account.requirements else {},
                "business_profile": account.business_profile.to_dict() if account.business_profile else {},
                "created": account.created
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error getting account status: {e}")
            raise ExternalServiceError(
                "Stripe",
                f"Failed to get account status: {str(e)}"
            )
    
    def create_checkout_session(
        self,
        account: Account,
        conversation_id: str,
        customer_name: str,
        customer_phone: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> Payment:
        """Create a Stripe Checkout session for appointment payment."""
        try:
            # Generate payment ID
            payment_id = str(uuid.uuid4())
            
            # Calculate platform fee: 5% with minimum of MXN$10 (1000 cents)
            calculated_fee = int(account.appointment_price * 0.05)
            platform_fee = max(calculated_fee, 1000)  # Minimum 10 MXN
            
            # Debug logging
            logger.info(
                "Creating checkout session with destination charges",
                extra={
                    "stripe_account": account.stripe_connect_account_id,
                    "amount": account.appointment_price,
                    "calculated_fee_percent": calculated_fee,
                    "platform_fee": platform_fee,
                    "platform_fee_mxn": platform_fee / 100,
                    "doctor_receives": account.appointment_price - platform_fee
                }
            )
            
            # Create checkout session with destination charges
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": account.currency,
                        "product_data": {
                            "name": account.payment_description,
                            "description": f"Cita médica - {account.name}"
                        },
                        "unit_amount": account.appointment_price
                    },
                    "quantity": 1
                }],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                expires_at=int((datetime.utcnow() + timedelta(minutes=30)).timestamp()),
                metadata={
                    "payment_id": payment_id,
                    "conversation_id": conversation_id,
                    "account_id": account.id,
                    **(metadata or {})  # Include any additional metadata
                },
                payment_intent_data={
                    "application_fee_amount": platform_fee,
                    "transfer_data": {
                        "destination": account.stripe_connect_account_id
                    }
                }
            )
            
            # Create payment record
            payment = Payment(
                id=payment_id,
                account_id=account.id,
                conversation_id=conversation_id,
                customer_phone=customer_phone,
                customer_name=customer_name,
                amount=account.appointment_price,
                currency=account.currency,
                stripe_payment_intent_id=session.payment_intent or "",
                stripe_checkout_session_id=session.id,
                payment_link=session.url,
                status=PaymentStatus.PENDING,
                source=metadata.get("source", "vitalis-whatsapp") if metadata else "vitalis-whatsapp",
                metadata={
                    "stripe_account": account.stripe_connect_account_id,
                    "expires_at": session.expires_at,
                    "booking_id": metadata.get("booking_id") if metadata else None
                }
            )
            
            # Save payment
            self.payment_repo.create(payment)
            
            logger.info(
                "Created checkout session",
                extra={
                    "payment_id": payment_id,
                    "session_id": session.id,
                    "amount": account.appointment_price
                }
            )
            
            return payment
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            raise ExternalServiceError(
                "Stripe",
                f"Failed to create payment session: {str(e)}"
            )
    
    def handle_checkout_completed(self, session_id: str) -> Optional[Payment]:
        """Handle successful checkout completion."""
        try:
            # Get payment by session ID
            payment = self.payment_repo.get_by_checkout_session(session_id)
            if not payment:
                logger.error(f"No payment found for session {session_id}")
                return None
            
            # Update payment status
            payment.status = PaymentStatus.COMPLETED
            payment.paid_at = datetime.utcnow()
            
            # Get session details from Stripe (now on platform account)
            session = stripe.checkout.Session.retrieve(session_id)
            
            if session.payment_intent:
                payment.stripe_payment_intent_id = session.payment_intent
            
            # Update payment
            self.payment_repo.update(payment)
            
            logger.info(
                "Payment completed",
                extra={
                    "payment_id": payment.id,
                    "amount": payment.amount
                }
            )
            
            return payment
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error handling checkout completion: {e}")
            return None
        except Exception as e:
            logger.error(f"Error handling checkout completion: {e}")
            return None
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        webhook_secret: str
    ) -> Dict[str, Any]:
        """Verify Stripe webhook signature and return event."""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            return event
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            raise ValueError("Invalid payload")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise ValueError("Invalid signature")