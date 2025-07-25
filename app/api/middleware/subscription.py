"""Middleware for subscription-based access control."""
from functools import wraps
from flask import request, jsonify
from app.services.account_service import AccountService
from app.services.subscription_service import SubscriptionService
from app.core.logging import get_logger
from typing import Optional, List

logger = get_logger(__name__)


def require_subscription(required_products: Optional[List[str]] = None):
    """
    Decorator to check if account has active subscription and required products.
    
    Args:
        required_products: List of product IDs required for access
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get account ID from request
            account_id = None
            
            # Try to get from URL parameter
            if "account_id" in kwargs:
                account_id = kwargs["account_id"]
            # Try to get from request body
            elif request.is_json and request.get_json():
                account_id = request.get_json().get("account_id")
            # Try to get from query parameter
            elif request.args.get("account_id"):
                account_id = request.args.get("account_id")
            
            if not account_id:
                logger.warning("No account ID found in request")
                return jsonify({"error": "Account ID required"}), 400
            
            # Get account
            account_service = AccountService()
            account = account_service.get_account(account_id)
            
            if not account:
                logger.warning(f"Account not found: {account_id}")
                return jsonify({"error": "Account not found"}), 404
            
            # Check subscription access
            subscription_service = SubscriptionService()
            access = subscription_service.check_access(account)
            
            if not access["has_access"]:
                logger.warning(
                    "Access denied - no active subscription",
                    extra={
                        "account_id": account_id,
                        "reason": access["reason"]
                    }
                )
                return jsonify({
                    "error": "Subscription required",
                    "reason": access["reason"],
                    "subscription_status": access.get("subscription_status")
                }), 403
            
            # Check required products if specified
            if required_products:
                account_products = subscription_service.get_account_products(account)
                
                # "all" product means access to everything
                if "all" not in account_products:
                    missing_products = [p for p in required_products if p not in account_products]
                    
                    if missing_products:
                        logger.warning(
                            "Access denied - missing required products",
                            extra={
                                "account_id": account_id,
                                "required_products": required_products,
                                "account_products": account_products,
                                "missing_products": missing_products
                            }
                        )
                        return jsonify({
                            "error": "Product access required",
                            "required_products": required_products,
                            "missing_products": missing_products
                        }), 403
            
            # Add account to request context
            request.vitalis_account = account
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def optional_subscription():
    """
    Decorator to optionally check subscription status without blocking access.
    Adds subscription info to request context.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get account ID from request (same logic as above)
            account_id = None
            
            if "account_id" in kwargs:
                account_id = kwargs["account_id"]
            elif request.is_json and request.get_json():
                account_id = request.get_json().get("account_id")
            elif request.args.get("account_id"):
                account_id = request.args.get("account_id")
            
            if account_id:
                account_service = AccountService()
                account = account_service.get_account(account_id)
                
                if account:
                    subscription_service = SubscriptionService()
                    access = subscription_service.check_access(account)
                    products = subscription_service.get_account_products(account)
                    
                    # Add to request context
                    request.vitalis_account = account
                    request.vitalis_subscription = {
                        "has_access": access["has_access"],
                        "reason": access["reason"],
                        "products": products
                    }
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator