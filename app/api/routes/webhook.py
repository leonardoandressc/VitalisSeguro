"""WhatsApp webhook routes."""
from flask import Blueprint, request, jsonify
from app.api.middleware.auth import verify_webhook_token
from app.api.middleware.rate_limit import rate_limit
from app.core.logging import get_logger
from app.core.config import get_config

logger = get_logger(__name__)

bp = Blueprint("webhook", __name__)


@bp.route("/webhook", methods=["GET", "POST"])
@verify_webhook_token
@rate_limit(requests_per_minute=100)
def webhook():
    """WhatsApp webhook endpoint."""
    if request.method == "GET":
        # Webhook verification
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        logger.info(
            "Webhook verification request",
            extra={"mode": mode}
        )
        
        if mode == "subscribe" and token == get_config().webhook_verify_token:
            return challenge, 200
        else:
            return "Forbidden", 403
    
    # Handle POST request (incoming messages)
    try:
        data = request.get_json()
        logger.info("Webhook POST received", extra={"data": data})
        
        # Import here to avoid circular imports
        from app.services.message_service import MessageService
        message_service = MessageService()
        
        # Process the webhook message
        result = message_service.handle_webhook_message(data)
        
        if result:
            return jsonify({"status": "ok"}), 200
        else:
            return jsonify({"status": "no_message_processed"}), 200
            
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        # Return 200 to prevent WhatsApp from retrying
        return jsonify({"status": "error", "message": str(e)}), 200