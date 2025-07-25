"""API endpoints for subscription billing."""
from flask import Blueprint, request, jsonify
from app.services.subscription_service import SubscriptionService
from app.services.account_service import AccountService
from app.models.subscription import BillingCycle
from app.core.exceptions import VitalisException, ResourceNotFoundError
from app.core.logging import get_logger
from app.core.config import get_config
from app.api.middleware.auth import require_api_key
import stripe

logger = get_logger(__name__)
billing_bp = Blueprint("billing", __name__, url_prefix="/api/billing")
config = get_config()


@billing_bp.route("/checkout/create", methods=["POST"])
@require_api_key
def create_checkout_session():
    """Create a checkout session for subscription."""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ["account_id", "tier_id", "billing_cycle"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Get account
        account_service = AccountService()
        account = account_service.get_account(data["account_id"])
        if not account:
            return jsonify({"error": "Account not found"}), 404
        
        # Create checkout session
        subscription_service = SubscriptionService()
        result = subscription_service.create_checkout_session(
            account=account,
            tier_id=data["tier_id"],
            billing_cycle=BillingCycle(data["billing_cycle"]),
            success_url=data.get("success_url", f"{config.callback_uri}/billing/success"),
            cancel_url=data.get("cancel_url", f"{config.callback_uri}/billing/cancel")
        )
        
        return jsonify(result), 200
        
    except VitalisException as e:
        logger.error(f"Business error creating checkout session: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        return jsonify({"error": "Failed to create checkout session"}), 500


@billing_bp.route("/portal/create", methods=["POST"])
@require_api_key
def create_portal_session():
    """Create a customer portal session for subscription management."""
    try:
        data = request.get_json()
        
        if not data.get("account_id"):
            return jsonify({"error": "Missing required field: account_id"}), 400
        
        # Get account
        account_service = AccountService()
        account = account_service.get_account(data["account_id"])
        if not account:
            return jsonify({"error": "Account not found"}), 404
        
        # Create portal session
        subscription_service = SubscriptionService()
        result = subscription_service.create_portal_session(
            account=account,
            return_url=data.get("return_url", f"{config.callback_uri}/billing/portal/return")
        )
        
        return jsonify(result), 200
        
    except VitalisException as e:
        logger.error(f"Business error creating portal session: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating portal session: {e}")
        return jsonify({"error": "Failed to create portal session"}), 500


@billing_bp.route("/webhooks", methods=["POST"])
def handle_billing_webhook():
    """Handle Stripe billing webhooks."""
    try:
        # Get webhook data
        payload = request.get_data()
        signature = request.headers.get("Stripe-Signature")
        
        if not signature:
            return jsonify({"error": "Missing signature"}), 400
        
        # Verify webhook
        webhook_secret = config.stripe_billing_webhook_secret
        if not webhook_secret:
            logger.error("Stripe billing webhook secret not configured")
            return jsonify({"error": "Webhook configuration error"}), 500
        
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            return jsonify({"error": "Invalid payload"}), 400
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            return jsonify({"error": "Invalid signature"}), 400
        
        logger.info(
            "Received Stripe billing webhook",
            extra={
                "event_type": event["type"],
                "event_id": event["id"]
            }
        )
        
        subscription_service = SubscriptionService()
        
        # Handle different event types
        if event["type"] == "customer.subscription.created":
            subscription_service.handle_subscription_created(event["data"]["object"])
            
        elif event["type"] == "customer.subscription.updated":
            subscription_service.handle_subscription_updated(event["data"]["object"])
            
        elif event["type"] == "customer.subscription.deleted":
            subscription_service.handle_subscription_deleted(event["data"]["object"])
            
        elif event["type"] == "customer.subscription.trial_will_end":
            # Handle trial ending soon (3 days before)
            subscription = event["data"]["object"]
            logger.info(
                "Trial ending soon",
                extra={
                    "subscription_id": subscription["id"],
                    "trial_end": subscription["trial_end"]
                }
            )
            # TODO: Send notification to customer
            
        elif event["type"] == "invoice.payment_succeeded":
            invoice = event["data"]["object"]
            logger.info(
                "Invoice payment succeeded",
                extra={
                    "invoice_id": invoice["id"],
                    "customer": invoice["customer"],
                    "amount": invoice["amount_paid"]
                }
            )
            
        elif event["type"] == "invoice.payment_failed":
            invoice = event["data"]["object"]
            logger.warning(
                "Invoice payment failed",
                extra={
                    "invoice_id": invoice["id"],
                    "customer": invoice["customer"],
                    "amount": invoice["amount_due"]
                }
            )
            # TODO: Send notification to customer
        
        return jsonify({"received": True}), 200
        
    except Exception as e:
        logger.error(f"Error handling billing webhook: {e}")
        return jsonify({"error": "Webhook processing failed"}), 500


@billing_bp.route("/subscriptions/<account_id>", methods=["GET"])
@require_api_key
def get_subscription(account_id):
    """Get subscription for an account."""
    try:
        # Get account
        account_service = AccountService()
        account = account_service.get_account(account_id)
        if not account:
            return jsonify({"error": "Account not found"}), 404
        
        # Get subscription
        subscription_service = SubscriptionService()
        subscription = subscription_service.get_subscription(account)
        
        if subscription:
            return jsonify(subscription.to_dict()), 200
        else:
            # Return empty object instead of 404 to avoid frontend errors
            return jsonify({}), 200
            
    except Exception as e:
        logger.error(f"Error getting subscription: {e}")
        return jsonify({"error": "Failed to get subscription"}), 500


@billing_bp.route("/subscriptions/<account_id>/cancel", methods=["POST"])
@require_api_key
def cancel_subscription(account_id):
    """Cancel a subscription."""
    try:
        # Get account
        account_service = AccountService()
        account = account_service.get_account(account_id)
        if not account:
            return jsonify({"error": "Account not found"}), 404
        
        # Cancel subscription
        subscription_service = SubscriptionService()
        result = subscription_service.cancel_subscription(account)
        
        return jsonify(result), 200
        
    except VitalisException as e:
        logger.error(f"Business error canceling subscription: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error canceling subscription: {e}")
        return jsonify({"error": "Failed to cancel subscription"}), 500


@billing_bp.route("/accounts/<account_id>/free", methods=["POST"])
@require_api_key
def set_free_account(account_id):
    """Set account as free or paid."""
    try:
        data = request.get_json()
        logger.info(f"Free account endpoint - Request data: {data}")
        
        if data is None:
            logger.error("No JSON data in request body")
            return jsonify({"error": "No data provided"}), 400
        
        # Get account
        account_service = AccountService()
        account = account_service.get_account(account_id)
        if not account:
            return jsonify({"error": "Account not found"}), 404
        
        # Update free account status
        subscription_service = SubscriptionService()
        result = subscription_service.set_free_account(
            account=account,
            is_free=data.get("is_free", False),
            reason=data.get("reason"),
            expires_at=data.get("expires_at"),
            products=data.get("products")
        )
        
        return jsonify(result), 200
        
    except VitalisException as e:
        logger.error(f"Business error setting free account: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error setting free account: {e}")
        return jsonify({"error": "Failed to update account"}), 500


@billing_bp.route("/invoice/send", methods=["POST"])
@require_api_key
def send_invoice():
    """Send invoice via WhatsApp or email."""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get("account_id"):
            return jsonify({"error": "Missing required field: account_id"}), 400
            
        if not data.get("phone_number") and not data.get("email"):
            return jsonify({"error": "Either phone_number or email is required"}), 400
        
        # Get account
        account_service = AccountService()
        account = account_service.get_account(data["account_id"])
        if not account:
            return jsonify({"error": "Account not found"}), 404
        
        # Send invoice
        subscription_service = SubscriptionService()
        result = subscription_service.send_invoice(
            account=account,
            phone_number=data.get("phone_number"),
            email=data.get("email")
        )
        
        return jsonify(result), 200
        
    except VitalisException as e:
        logger.error(f"Business error sending invoice: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error sending invoice: {e}")
        return jsonify({"error": "Failed to send invoice"}), 500


@billing_bp.route("/subscriptions/<account_id>/assign", methods=["POST"])
@require_api_key
def assign_subscription(account_id):
    """Admin endpoint to assign a subscription to an account."""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ["tier_id", "billing_cycle"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Get account
        account_service = AccountService()
        account = account_service.get_account(account_id)
        if not account:
            return jsonify({"error": "Account not found"}), 404
        
        # Assign subscription
        subscription_service = SubscriptionService()
        result = subscription_service.assign_subscription_admin(
            account=account,
            tier_id=data["tier_id"],
            billing_cycle=BillingCycle(data["billing_cycle"]),
            send_invoice=data.get("send_invoice", True),
            invoice_delivery=data.get("invoice_delivery", {})
        )
        
        return jsonify(result), 200
        
    except VitalisException as e:
        logger.error(f"Business error assigning subscription: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error assigning subscription: {e}")
        return jsonify({"error": "Failed to assign subscription"}), 500