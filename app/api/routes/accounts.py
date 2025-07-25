"""Account management routes."""
from flask import Blueprint, request, jsonify
from app.api.middleware.auth import require_api_key, handle_auth_errors
from app.api.middleware.rate_limit import rate_limit
from app.core.logging import get_logger

logger = get_logger(__name__)

bp = Blueprint("accounts", __name__)


@bp.route("/accounts", methods=["GET"])
@require_api_key
@rate_limit()
@handle_auth_errors
def list_accounts():
    """List all accounts."""
    try:
        from app.services.account_service import AccountService
        account_service = AccountService()
        
        # Get status filter if provided
        status_param = request.args.get("status")
        status = None
        if status_param:
            from app.models.account import AccountStatus
            try:
                status = AccountStatus(status_param)
            except ValueError:
                return jsonify({"error": f"Invalid status: {status_param}"}), 400
        
        accounts = account_service.list_accounts(status=status)
        
        # Check if legacy format is requested (for admin hub compatibility)
        legacy_format = request.headers.get("X-Legacy-Format") == "true"
        
        if legacy_format:
            # Return legacy format for admin hub compatibility
            legacy_accounts = []
            for account in accounts:
                # Get token expiry for this account
                try:
                    account_with_tokens = account_service.get_account_with_tokens(account.id)
                    expires_at = account_with_tokens.get("expires_at")
                except:
                    expires_at = None
                
                legacy_accounts.append({
                    "account_id": account.id,
                    "name": account.name,
                    "phone_number_id": account.phone_number_id,
                    "calendar_id": account.calendar_id,
                    "location_id": account.location_id,
                    "assigned_user_id": account.assigned_user_id,
                    "prompt": account.custom_prompt,
                    "expires_at": expires_at
                })
            
            logger.info(
                "Listed accounts (legacy format)",
                extra={"count": len(legacy_accounts), "status_filter": status_param}
            )
            
            return jsonify(legacy_accounts), 200
        
        # Return new format
        logger.info(
            "Listed accounts",
            extra={"count": len(accounts), "status_filter": status_param}
        )
        
        return jsonify({
            "accounts": [account.to_dict() for account in accounts],
            "count": len(accounts)
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to list accounts: {e}")
        raise


@bp.route("/accounts/<account_id>", methods=["GET"])
@require_api_key
@rate_limit()
@handle_auth_errors
def get_account(account_id: str):
    """Get a specific account."""
    try:
        from app.services.account_service import AccountService
        account_service = AccountService()
        
        account_info = account_service.get_account_with_tokens(account_id)
        
        logger.info(f"Retrieved account: {account_id}")
        
        return jsonify(account_info), 200
        
    except Exception as e:
        logger.error(f"Failed to get account: {e}")
        raise


@bp.route("/accounts", methods=["POST"])
@require_api_key
@rate_limit()
@handle_auth_errors
def create_account():
    """Create a new account.
    
    Request body:
        {
            "name": "Account Name",
            "phone_number_id": "123456789",
            "calendar_id": "cal_123",
            "location_id": "loc_123",
            "assigned_user_id": "user_123",
            "custom_prompt": "Optional custom prompt",
            "register_whatsapp": false,  // Optional: auto-register with WhatsApp
            "whatsapp_pin": "000000",   // Optional: WhatsApp registration PIN
            "data_localization_region": "US"  // Optional: country code
        }
    """
    try:
        from app.services.account_service import AccountService
        account_service = AccountService()
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        account = account_service.create_account(data)
        
        logger.info(f"Created account: {account.id}")
        
        return jsonify({
            "account": account.to_dict(),
            "message": "Account created successfully"
        }), 201
        
    except Exception as e:
        logger.error(f"Failed to create account: {e}")
        raise


@bp.route("/accounts/<account_id>", methods=["PUT"])
@require_api_key
@rate_limit()
@handle_auth_errors
def update_account(account_id: str):
    """Update an account."""
    try:
        from app.services.account_service import AccountService
        account_service = AccountService()
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        account = account_service.update_account(account_id, data)
        
        logger.info(f"Updated account: {account_id}")
        
        return jsonify({
            "account": account.to_dict(),
            "message": "Account updated successfully"
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to update account: {e}")
        raise


@bp.route("/accounts/<account_id>", methods=["DELETE"])
@require_api_key
@rate_limit()
@handle_auth_errors
def delete_account(account_id: str):
    """Delete an account."""
    try:
        from app.services.account_service import AccountService
        account_service = AccountService()
        
        account_service.delete_account(account_id)
        
        logger.info(f"Deleted account: {account_id}")
        
        return jsonify({
            "message": "Account deleted successfully"
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to delete account: {e}")
        raise


@bp.route("/accounts/<account_id>/refresh-token", methods=["POST"])
@require_api_key
@rate_limit()
@handle_auth_errors
def refresh_account_token(account_id: str):
    """Refresh OAuth token for an account."""
    try:
        from app.services.oauth_service import OAuthService
        from app.core.exceptions import ExternalServiceError
        oauth_service = OAuthService()
        
        try:
            success = oauth_service.refresh_token(account_id)
            
            if success:
                return jsonify({
                    "message": "Token refreshed successfully"
                }), 200
            else:
                return jsonify({
                    "error": "Failed to refresh token"
                }), 500
        except ExternalServiceError as e:
            if "Token refresh failed" in str(e):
                return jsonify({
                    "error": "Token refresh failed - reauthorization required",
                    "message": "The refresh token has expired or been revoked. Please reauthorize the account.",
                    "auth_url": f"/auth?account_id={account_id}"
                }), 401
            raise
        
    except Exception as e:
        logger.error(f"Failed to refresh token: {e}")
        raise


@bp.route("/accounts/<account_id>/token-status", methods=["GET"])
@require_api_key
@rate_limit()
@handle_auth_errors
def check_token_status(account_id: str):
    """Check token status for an account."""
    try:
        from app.repositories.token_repository import TokenRepository
        from datetime import datetime
        
        token_repo = TokenRepository()
        tokens = token_repo.get_tokens(account_id)
        
        if not tokens:
            return jsonify({
                "status": "no_tokens",
                "message": "No tokens found for this account"
            }), 404
        
        is_expired = token_repo.is_token_expired(account_id)
        expires_at = tokens.get("expires_at")
        
        if expires_at:
            expires_dt = datetime.fromtimestamp(expires_at)
            time_remaining = expires_dt - datetime.now()
            hours_remaining = time_remaining.total_seconds() / 3600
        else:
            hours_remaining = None
        
        return jsonify({
            "status": "expired" if is_expired else "valid",
            "has_access_token": bool(tokens.get("access_token")),
            "has_refresh_token": bool(tokens.get("refresh_token")),
            "expires_at": expires_at,
            "hours_remaining": hours_remaining,
            "location_id": tokens.get("location_id")
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to check token status: {e}")
        raise


@bp.route("/register-account", methods=["POST"])
@require_api_key
@rate_limit()
@handle_auth_errors
def register_account_legacy():
    """Create a new account (legacy endpoint for admin hub compatibility)."""
    try:
        from app.services.account_service import AccountService
        account_service = AccountService()
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        # Transform legacy format to new format
        # Old format has account_id and prompt, new format has name and custom_prompt
        transformed_data = {
            "name": data.get("account_id", "Account"),  # Use account_id as name if provided
            "phone_number_id": data.get("phone_number_id"),
            "calendar_id": data.get("calendar_id"),
            "location_id": data.get("location_id"),
            "assigned_user_id": data.get("assigned_user_id"),
            "custom_prompt": data.get("custom_prompt") or data.get("prompt", ""),
            # Add WhatsApp registration parameters
            "register_whatsapp": data.get("register_whatsapp", False),
            "whatsapp_pin": data.get("whatsapp_pin", "000000"),
            "data_localization_region": data.get("data_localization_region")
        }
        
        account = account_service.create_account(transformed_data)
        
        logger.info(f"Created account via legacy endpoint: {account.id}")
        
        # Return legacy response format
        return jsonify({
            "status": "ok",
            "account_id": account.id
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to create account via legacy endpoint: {e}")
        raise


@bp.route("/accounts/<account_id>/register-whatsapp", methods=["POST"])
@require_api_key
@rate_limit()
@handle_auth_errors
def register_whatsapp_for_account(account_id: str):
    """Register WhatsApp for an existing account."""
    try:
        from app.services.account_service import AccountService
        from app.integrations.whatsapp.client import WhatsAppClient
        
        account_service = AccountService()
        whatsapp_client = WhatsAppClient()
        
        # Get the account to verify it exists
        account = account_service.get_account(account_id)
        
        # Get registration parameters from request
        data = request.get_json() or {}
        pin = data.get("pin", "000000")
        data_localization_region = data.get("data_localization_region")
        
        # Register the phone number
        registration_result = whatsapp_client.register_phone_number(
            phone_number_id=account.phone_number_id,
            pin=pin,
            data_localization_region=data_localization_region
        )
        
        logger.info(
            "WhatsApp registration completed for account",
            extra={
                "account_id": account_id,
                "phone_number_id": account.phone_number_id,
                "registration_success": registration_result.get("success", False)
            }
        )
        
        return jsonify({
            "message": "WhatsApp registration completed",
            "success": registration_result.get("success", False),
            "account_id": account_id,
            "phone_number_id": account.phone_number_id
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to register WhatsApp for account {account_id}: {e}")
        raise