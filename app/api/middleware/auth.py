"""Authentication middleware for API endpoints."""
from functools import wraps
from typing import Callable, Optional, List
from flask import request, jsonify, g
from app.core.config import get_config
from app.core.exceptions import AuthenticationError, AuthorizationError, ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)


def require_api_key(f: Callable) -> Callable:
    """Decorator to require API key authentication for endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        config = get_config()
        
        # Skip auth in testing mode
        if config.testing:
            return f(*args, **kwargs)
        
        # Get API key from header
        api_key = request.headers.get(config.api_key_header)
        
        if not api_key:
            logger.warning(
                "Missing API key",
                extra={
                    "path": request.path,
                    "method": request.method,
                    "remote_addr": request.remote_addr
                }
            )
            raise AuthenticationError("API key required")
        
        # Validate API key
        if api_key not in config.api_keys:
            logger.warning(
                "Invalid API key",
                extra={
                    "path": request.path,
                    "method": request.method,
                    "remote_addr": request.remote_addr,
                    "api_key_prefix": api_key[:8] + "..." if len(api_key) > 8 else "***"
                }
            )
            raise AuthenticationError("Invalid API key")
        
        # Store authenticated status in g
        g.authenticated = True
        g.api_key = api_key
        
        logger.info(
            "API key authentication successful",
            extra={
                "path": request.path,
                "method": request.method
            }
        )
        
        return f(*args, **kwargs)
    
    return decorated_function


def verify_webhook_token(f: Callable) -> Callable:
    """Decorator to verify WhatsApp webhook token."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        config = get_config()
        
        # For GET requests (webhook verification)
        if request.method == "GET":
            token = request.args.get("hub.verify_token")
            if token != config.webhook_verify_token:
                logger.warning(
                    "Invalid webhook verification token",
                    extra={
                        "remote_addr": request.remote_addr,
                        "provided_token": token[:10] + "..." if token and len(token) > 10 else "None"
                    }
                )
                return jsonify({"error": "Invalid verification token"}), 403
        
        # For POST requests, we trust WhatsApp's signature verification
        # In production, you should verify the X-Hub-Signature-256 header
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_account_access(account_id_param: str = "account_id") -> Callable:
    """Decorator to verify user has access to the specified account."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get account_id from route parameters
            account_id = kwargs.get(account_id_param)
            
            if not account_id:
                raise ValidationError(f"Missing {account_id_param}")
            
            # In a real implementation, you would check if the authenticated
            # user has access to this account. For now, we'll just log it.
            logger.info(
                "Account access check",
                extra={
                    "account_id": account_id,
                    "api_key": g.get("api_key", "N/A")
                }
            )
            
            # Store account_id in g for use in route handlers
            g.account_id = account_id
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator


def handle_auth_errors(f: Callable) -> Callable:
    """Decorator to handle authentication/authorization errors."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except (AuthenticationError, AuthorizationError) as e:
            logger.error(
                f"{e.__class__.__name__}: {e.message}",
                extra={
                    "path": request.path,
                    "method": request.method,
                    "remote_addr": request.remote_addr
                }
            )
            return jsonify(e.to_dict()), e.status_code
        except Exception as e:
            logger.exception(
                "Unexpected error in auth middleware",
                extra={
                    "path": request.path,
                    "method": request.method
                }
            )
            return jsonify({
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred"
                }
            }), 500
    
    return decorated_function