"""OAuth authentication routes."""
from flask import Blueprint, request, redirect, jsonify
from app.core.logging import get_logger
from app.core.config import get_config

logger = get_logger(__name__)

bp = Blueprint("auth", __name__)


@bp.route("/auth", methods=["GET"])
def oauth_authorize():
    """Initiate OAuth flow for GoHighLevel."""
    try:
        account_id = request.args.get("account_id")
        if not account_id:
            return jsonify({"error": "account_id parameter required"}), 400
        
        from app.services.oauth_service import OAuthService
        oauth_service = OAuthService()
        
        auth_url = oauth_service.get_authorization_url(account_id)
        
        logger.info(
            "OAuth authorization initiated",
            extra={"account_id": account_id}
        )
        
        return redirect(auth_url)
        
    except Exception as e:
        logger.error(f"OAuth authorization failed: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/callback", methods=["GET"])
def oauth_callback():
    """Handle OAuth callback from GoHighLevel."""
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")
        
        if error:
            logger.error(f"OAuth error: {error}")
            return jsonify({"error": f"OAuth failed: {error}"}), 400
        
        if not code or not state:
            return jsonify({"error": "Missing code or state parameter"}), 400
        
        from app.services.oauth_service import OAuthService
        oauth_service = OAuthService()
        
        result = oauth_service.handle_callback(code, state)
        
        logger.info(
            "OAuth callback processed",
            extra={"account_id": result.get("account_id")}
        )
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        return jsonify({"error": str(e)}), 500