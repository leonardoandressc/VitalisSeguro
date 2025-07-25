"""API endpoints for Stripe integration."""
from datetime import datetime
from flask import Blueprint, request, jsonify, Response
from app.services.stripe_service import StripeService
from app.services.account_service import AccountService
from app.repositories.payment_repository import PaymentRepository
from app.core.exceptions import VitalisException, ResourceNotFoundError
from app.core.logging import get_logger
from app.core.config import get_config
from app.api.middleware.auth import require_api_key

logger = get_logger(__name__)
stripe_bp = Blueprint("stripe", __name__, url_prefix="/api/stripe")
config = get_config()


@stripe_bp.route("/accounts/<account_id>/connect", methods=["POST"])
@require_api_key
def create_connect_onboarding(account_id: str):
    """Create Stripe Connect onboarding link for an account."""
    try:
        # Get account
        account_service = AccountService()
        account = account_service.get_account(account_id)
        if not account:
            return jsonify({"error": "Account not found"}), 404
        
        # Get return URLs from request
        data = request.get_json() or {}
        return_url = data.get("return_url", f"{config.callback_uri}/stripe/connect/return")
        refresh_url = data.get("refresh_url", f"{config.callback_uri}/stripe/connect/refresh")
        
        # Create onboarding link
        stripe_service = StripeService()
        result = stripe_service.create_connect_account_link(
            account=account,
            return_url=return_url,
            refresh_url=refresh_url
        )
        
        # Save Stripe account ID immediately if new account was created
        if result.get("new_account_created") and result["stripe_account_id"]:
            account.stripe_connect_account_id = result["stripe_account_id"]
            account.stripe_enabled = True
            account_service.update_account(account)
            logger.info(
                "Saved new Stripe account ID immediately",
                extra={
                    "account_id": account_id,
                    "stripe_account_id": result["stripe_account_id"]
                }
            )
        
        logger.info(
            "Created Stripe Connect onboarding link",
            extra={
                "account_id": account_id,
                "stripe_account_id": result.get("stripe_account_id")
            }
        )
        
        return jsonify(result), 200
        
    except VitalisException as e:
        logger.error(f"Business error creating onboarding link: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating onboarding link: {e}")
        return jsonify({"error": "Failed to create onboarding link"}), 500


@stripe_bp.route("/accounts/<account_id>/status", methods=["GET"])
@require_api_key
def get_connect_status(account_id: str):
    """Get Stripe Connect account status."""
    try:
        # Get account
        account_service = AccountService()
        account = account_service.get_account(account_id)
        if not account:
            return jsonify({"error": "Account not found"}), 404
        
        if not account.stripe_connect_account_id:
            return jsonify({
                "connected": False,
                "message": "No Stripe account connected"
            }), 200
        
        # Get status from Stripe
        stripe_service = StripeService()
        status = stripe_service.get_account_status(account.stripe_connect_account_id)
        
        # Update account with latest Stripe status
        account.stripe_charges_enabled = status["charges_enabled"]
        account.stripe_payouts_enabled = status["payouts_enabled"]
        account.stripe_details_submitted = status["details_submitted"]
        
        if status["charges_enabled"] and status["details_submitted"]:
            account.stripe_onboarding_completed = True
            
        account_service.update_account(account)
        
        return jsonify({
            "connected": True,
            "stripe_account_id": account.stripe_connect_account_id,
            **status
        }), 200
        
    except VitalisException as e:
        logger.error(f"Business error getting account status: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting account status: {e}")
        return jsonify({"error": "Failed to get account status"}), 500


@stripe_bp.route("/accounts/<account_id>/onboarding-link", methods=["GET"])
@require_api_key
def get_onboarding_link(account_id: str):
    """Get a shareable onboarding link for the doctor."""
    try:
        # Get account
        account_service = AccountService()
        account = account_service.get_account(account_id)
        if not account:
            return jsonify({"error": "Account not found"}), 404
        
        # Check if email is set
        if not account.email:
            return jsonify({
                "error": "Account email is required for onboarding link generation"
            }), 400
        
        # Generate shareable link
        # This link will redirect to the actual Stripe onboarding
        base_url = request.host_url.rstrip('/')
        onboarding_link = f"{base_url}/api/stripe/onboard/{account.id}"
        
        return jsonify({
            "account_id": account.id,
            "account_name": account.name,
            "email": account.email,
            "onboarding_link": onboarding_link,
            "instructions": "Share this link with the doctor to complete Stripe onboarding"
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating onboarding link: {e}")
        return jsonify({"error": "Failed to generate onboarding link"}), 500


@stripe_bp.route("/onboard/<account_id>", methods=["GET"])
def redirect_to_stripe_onboarding(account_id: str):
    """Public endpoint that redirects to Stripe onboarding."""
    try:
        # Get account (no auth required for this public endpoint)
        account_service = AccountService()
        account = account_service.get_account(account_id)
        if not account:
            return jsonify({"error": "Invalid onboarding link"}), 404
        
        # Create or refresh onboarding link
        stripe_service = StripeService()
        result = stripe_service.create_connect_account_link(
            account=account,
            return_url=request.host_url.rstrip('/') + '/api/stripe/onboarding-complete',
            refresh_url=request.host_url.rstrip('/') + f'/api/stripe/onboard/{account_id}'
        )
        
        # Save Stripe account ID immediately if new account was created
        if result.get("new_account_created") and result["stripe_account_id"]:
            account.stripe_connect_account_id = result["stripe_account_id"]
            account.stripe_enabled = True
            account_service.update_account(account)
            logger.info(
                "Saved new Stripe account ID immediately",
                extra={
                    "account_id": account_id,
                    "stripe_account_id": result["stripe_account_id"]
                }
            )
        
        # Redirect to Stripe
        from flask import redirect
        return redirect(result["url"])
        
    except Exception as e:
        logger.error(f"Error redirecting to Stripe: {e}")
        return jsonify({"error": "Failed to start onboarding process"}), 500


@stripe_bp.route("/onboarding-complete", methods=["GET"])
def onboarding_complete():
    """Landing page after Stripe onboarding completion."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Onboarding Complete</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            .success { color: #28a745; }
            .container { max-width: 600px; margin: 0 auto; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="success">✅ Stripe Onboarding Complete!</h1>
            <p>Your Stripe account has been successfully set up.</p>
            <p>You can now close this window. The admin will be notified of your account status.</p>
        </div>
    </body>
    </html>
    """, 200


@stripe_bp.route("/payments/create", methods=["POST"])
@require_api_key
def create_payment():
    """Create a payment checkout session."""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ["account_id", "conversation_id", "customer_name", "customer_phone"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Get account
        account_service = AccountService()
        account = account_service.get_account(data["account_id"])
        if not account:
            return jsonify({"error": "Account not found"}), 404
        
        # Check if Stripe is enabled
        if not account.stripe_enabled:
            return jsonify({"error": "Stripe payments not enabled for this account"}), 400
        
        if not account.stripe_connect_account_id:
            return jsonify({"error": "Stripe account not connected"}), 400
        
        if not account.stripe_onboarding_completed:
            return jsonify({"error": "Stripe onboarding not completed"}), 400
        
        if not account.stripe_charges_enabled:
            return jsonify({"error": "Stripe charges not enabled for this account"}), 400
        
        # Create checkout session
        stripe_service = StripeService()
        payment = stripe_service.create_checkout_session(
            account=account,
            conversation_id=data["conversation_id"],
            customer_name=data["customer_name"],
            customer_phone=data["customer_phone"],
            success_url=data.get("success_url", config.stripe_success_url),
            cancel_url=data.get("cancel_url", config.stripe_cancel_url)
        )
        
        logger.info(
            "Created payment checkout session",
            extra={
                "payment_id": payment.id,
                "amount": payment.amount,
                "account_id": account.id
            }
        )
        
        return jsonify({
            "payment_id": payment.id,
            "payment_link": payment.payment_link,
            "amount": payment.amount,
            "currency": payment.currency,
            "expires_at": payment.metadata.get("expires_at")
        }), 200
        
    except VitalisException as e:
        logger.error(f"Business error creating payment: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating payment: {e}")
        return jsonify({"error": "Failed to create payment"}), 500


@stripe_bp.route("/webhooks", methods=["POST"])
def handle_webhook():
    """Handle Stripe webhooks."""
    try:
        # Get webhook data
        payload = request.get_data()
        signature = request.headers.get("Stripe-Signature")
        
        if not signature:
            return jsonify({"error": "Missing signature"}), 400
        
        # Verify webhook
        stripe_service = StripeService()
        event = stripe_service.verify_webhook_signature(
            payload=payload,
            signature=signature,
            webhook_secret=config.stripe_webhook_secret
        )
        
        logger.info(
            "Received Stripe webhook",
            extra={
                "event_type": event["type"],
                "event_id": event["id"]
            }
        )
        
        # Handle different event types
        if event["type"] == "account.updated":
            # Handle Connect account updates
            stripe_account = event["data"]["object"]
            account_id = event.get("account")  # This is the Connect account ID
            
            logger.info(
                "Stripe Connect account updated",
                extra={
                    "stripe_account_id": account_id,
                    "charges_enabled": stripe_account.get("charges_enabled"),
                    "details_submitted": stripe_account.get("details_submitted"),
                    "email": stripe_account.get("email")
                }
            )
            
            # Try to match and update Vitalis account
            if stripe_account.get("email"):
                from app.services.account_service import AccountService
                account_service = AccountService()
                
                # Try to find account by email
                account = account_service.get_account_by_email(stripe_account["email"])
                if account:
                    # Update account with Stripe info
                    account.stripe_connect_account_id = account_id
                    account.stripe_charges_enabled = stripe_account.get("charges_enabled", False)
                    account.stripe_payouts_enabled = stripe_account.get("payouts_enabled", False)
                    account.stripe_details_submitted = stripe_account.get("details_submitted", False)
                    account.stripe_capability_status = stripe_account.get("capabilities", {}).get("card_payments", "inactive")
                    account.stripe_last_webhook_update = datetime.utcnow()
                    
                    # Check if onboarding is complete
                    if (stripe_account.get("charges_enabled") and 
                        stripe_account.get("details_submitted")):
                        account.stripe_onboarding_completed = True
                    
                    account_service.update_account(account)
                    
                    logger.info(
                        "Updated Vitalis account with Stripe Connect info",
                        extra={
                            "account_id": account.id,
                            "stripe_account_id": account_id,
                            "email": stripe_account.get("email")
                        }
                    )
                else:
                    logger.warning(
                        "No Vitalis account found for Stripe email",
                        extra={
                            "email": stripe_account.get("email"),
                            "stripe_account_id": account_id
                        }
                    )
        
        elif event["type"] == "account.application.authorized":
            # Handle OAuth authorization completion
            stripe_account_id = event["account"]
            
            logger.info(
                "Stripe Connect OAuth authorized",
                extra={"stripe_account_id": stripe_account_id}
            )
            
            # We'll need to handle this through the OAuth callback
            # as we won't have the email here
        
        elif event["type"] == "capability.updated":
            # Handle capability updates
            capability = event["data"]["object"]
            stripe_account_id = event["account"]
            
            logger.info(
                "Stripe capability updated",
                extra={
                    "stripe_account_id": stripe_account_id,
                    "capability": capability.get("id"),
                    "status": capability.get("status")
                }
            )
            
            # Update account if we can find it
            from app.services.account_service import AccountService
            account_service = AccountService()
            
            # Find by Stripe account ID
            accounts = account_service.list_accounts()
            for account in accounts:
                if account.stripe_connect_account_id == stripe_account_id:
                    account.stripe_capability_status = capability.get("status", "inactive")
                    account.stripe_last_webhook_update = datetime.utcnow()
                    account_service.update_account(account)
                    break
        
        elif event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            payment = stripe_service.handle_checkout_completed(session["id"])
            
            if payment:
                # Import required services
                from app.services.account_service import AccountService
                from app.services.appointment_service import AppointmentService
                from app.services.whatsapp_service import WhatsAppService
                from app.services.booking_service import BookingService
                
                account_service = AccountService()
                appointment_service = AppointmentService()
                whatsapp_service = WhatsAppService()
                booking_service = BookingService()
                
                # Check if this payment has a booking_id (Vitalis Connect)
                booking_id = payment.metadata.get("booking_id") if payment.metadata else None
                
                if booking_id:
                    # This is a Vitalis Connect booking
                    booking = booking_service.get_booking(booking_id)
                    if booking:
                        # Update booking payment status
                        booking_service.update_booking(
                            booking_id=booking_id,
                            payment_status="completed"
                        )
                        
                        logger.info(
                            "Payment completed for Vitalis Connect booking",
                            extra={
                                "payment_id": payment.id,
                                "booking_id": booking_id,
                                "source": "vitalis-connect"
                            }
                        )
                        # The directory endpoint will handle appointment creation
                else:
                    # This is a WhatsApp booking
                    account = account_service.get_account(payment.account_id)
                    if account:
                        # Update conversation context to mark payment as completed
                        from app.services.conversation_service import ConversationService
                        conversation_service = ConversationService()
                        conversation = conversation_service.repository.get(payment.conversation_id)
                        
                        if conversation:
                            # Update payment status in conversation
                            appointment_info = conversation.context.appointment_info
                            appointment_info["payment_status"] = "completed"
                            appointment_info["payment_id"] = payment.id
                            
                            # Update booking if it exists
                            if appointment_info.get("booking_id"):
                                booking_service.update_booking(
                                    booking_id=appointment_info["booking_id"],
                                    payment_status="completed"
                                )
                            
                            conversation_service.update_appointment_info(
                                conversation_id=payment.conversation_id,
                                appointment_info=appointment_info,
                                awaiting_confirmation=True
                            )
                            
                            # Create appointment
                            result = appointment_service.confirm_and_create_appointment(
                                conversation_id=payment.conversation_id,
                                account=account,
                                payment_id=payment.id
                            )
                            
                            if result["success"]:
                                # Update payment with appointment ID
                                payment_repo = PaymentRepository()
                                payment_repo.update_status(
                                    payment_id=payment.id,
                                    status=payment.status,
                                    appointment_id=result.get("appointment_id")
                                )
                                
                                # Send success message to customer
                                success_message = (
                                    "✅ ¡Pago recibido! Tu cita ha sido confirmada.\n\n"
                                    f"📅 {result['details']}\n\n"
                                    "Recibirás un recordatorio el día de tu cita.\n"
                                    "¡Gracias por tu preferencia!"
                                )
                                
                                whatsapp_service.send_text_message(
                                    phone_number_id=account.phone_number_id,
                                    to_number=payment.customer_phone,
                                    message=success_message
                                )
                                
                                logger.info(
                                    "Appointment created after payment",
                                    extra={
                                        "payment_id": payment.id,
                                        "appointment_id": result.get("appointment_id"),
                                        "conversation_id": payment.conversation_id,
                                        "source": "vitalis-whatsapp"
                                    }
                                )
        
        return jsonify({"received": True}), 200
        
    except ValueError as e:
        logger.error(f"Invalid webhook: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return jsonify({"error": "Webhook processing failed"}), 500


@stripe_bp.route("/payments/<payment_id>", methods=["GET"])
@require_api_key
def get_payment(payment_id: str):
    """Get payment details."""
    try:
        payment_repo = PaymentRepository()
        payment = payment_repo.get(payment_id)
        
        if not payment:
            return jsonify({"error": "Payment not found"}), 404
        
        return jsonify(payment.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Error getting payment: {e}")
        return jsonify({"error": "Failed to get payment"}), 500


@stripe_bp.route("/accounts/<account_id>/disconnect", methods=["DELETE"])
@require_api_key
def delete_stripe_account(account_id: str):
    """Delete/disconnect a Stripe connected account."""
    try:
        import stripe
        
        # Get account
        account_service = AccountService()
        account = account_service.get_account(account_id)
        if not account:
            return jsonify({"error": "Account not found"}), 404
        
        if not account.stripe_connect_account_id:
            return jsonify({"error": "No Stripe account connected"}), 400
        
        stripe_account_id = account.stripe_connect_account_id
        
        # Initialize Stripe
        stripe.api_key = config.stripe_secret_key
        
        # Try to delete from Stripe
        try:
            deleted = stripe.Account.delete(stripe_account_id)
            logger.info(
                "Deleted Stripe account",
                extra={
                    "account_id": account_id,
                    "stripe_account_id": stripe_account_id,
                    "deleted": deleted.deleted
                }
            )
        except stripe.error.InvalidRequestError as e:
            if "No such account" in str(e):
                logger.warning(f"Stripe account not found: {e}")
                # Continue to clear from database even if not found in Stripe
            else:
                logger.error(f"Error deleting Stripe account: {e}")
                return jsonify({"error": str(e)}), 400
        
        # Clear Stripe fields in database
        account.stripe_connect_account_id = None
        account.stripe_onboarding_completed = False
        account.stripe_charges_enabled = False
        account.stripe_payouts_enabled = False
        account.stripe_details_submitted = False
        account.stripe_capability_status = None
        
        # Update account
        account_service.update_account(account)
        
        logger.info(
            "Cleared Stripe fields from account",
            extra={"account_id": account_id}
        )
        
        return jsonify({
            "success": True,
            "message": "Stripe account disconnected successfully",
            "account_id": account_id,
            "former_stripe_account_id": stripe_account_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting Stripe account: {e}")
        return jsonify({"error": "Failed to delete Stripe account"}), 500