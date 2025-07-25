"""Rate limiting middleware for API endpoints."""
from functools import wraps
from typing import Callable, Dict, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import time
from flask import request, jsonify, g
from app.core.config import get_config
from app.core.exceptions import RateLimitError
from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
        self._cleanup_interval = 300  # Clean up every 5 minutes
        self._last_cleanup = time.time()
    
    def is_allowed(self, key: str) -> Tuple[bool, Optional[int]]:
        """Check if request is allowed for the given key.
        
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        now = time.time()
        minute_ago = now - 60
        
        # Clean up old entries periodically
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup()
        
        # Remove requests older than 1 minute
        self.requests[key] = [
            timestamp for timestamp in self.requests[key]
            if timestamp > minute_ago
        ]
        
        # Check if limit exceeded
        if len(self.requests[key]) >= self.requests_per_minute:
            # Calculate when the oldest request will expire
            oldest_request = min(self.requests[key])
            retry_after = int(oldest_request + 60 - now) + 1
            return False, retry_after
        
        # Add current request
        self.requests[key].append(now)
        return True, None
    
    def _cleanup(self):
        """Remove old entries to prevent memory leak."""
        now = time.time()
        minute_ago = now - 60
        
        # Remove keys with no recent requests
        keys_to_remove = []
        for key, timestamps in self.requests.items():
            if not timestamps or max(timestamps) < minute_ago:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.requests[key]
        
        self._last_cleanup = now
        
        if keys_to_remove:
            logger.info(f"Cleaned up {len(keys_to_remove)} rate limit entries")


# Global rate limiter instance
_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        config = get_config()
        _rate_limiter = RateLimiter(config.rate_limit_per_minute)
    return _rate_limiter


def get_rate_limit_key() -> str:
    """Get the rate limit key for the current request."""
    # Use API key if authenticated, otherwise use IP address
    if hasattr(g, "api_key") and g.api_key:
        return f"api_key:{g.api_key}"
    return f"ip:{request.remote_addr}"


def rate_limit(requests_per_minute: Optional[int] = None) -> Callable:
    """Decorator to apply rate limiting to endpoints.
    
    Args:
        requests_per_minute: Override the default rate limit for this endpoint
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            config = get_config()
            
            # Skip rate limiting if disabled
            if not config.enable_rate_limiting:
                return f(*args, **kwargs)
            
            # Get rate limiter
            limiter = get_rate_limiter()
            if requests_per_minute:
                # Create custom limiter for this endpoint
                limiter = RateLimiter(requests_per_minute)
            
            # Check rate limit
            key = get_rate_limit_key()
            is_allowed, retry_after = limiter.is_allowed(key)
            
            if not is_allowed:
                logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "key": key,
                        "path": request.path,
                        "method": request.method,
                        "retry_after": retry_after
                    }
                )
                
                response = jsonify(
                    RateLimitError(retry_after=retry_after).to_dict()
                )
                response.status_code = 429
                response.headers["Retry-After"] = str(retry_after)
                response.headers["X-RateLimit-Limit"] = str(limiter.requests_per_minute)
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(int(time.time()) + retry_after)
                
                return response
            
            # Add rate limit headers to response
            @wraps(f)
            def add_headers(response):
                # Only add headers if response has headers attribute (not a plain string)
                if hasattr(response, 'headers'):
                    remaining = limiter.requests_per_minute - len(limiter.requests[key])
                    response.headers["X-RateLimit-Limit"] = str(limiter.requests_per_minute)
                    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
                    response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
                return response
            
            # Execute the function
            result = f(*args, **kwargs)
            
            # Handle different response types
            if isinstance(result, tuple):
                # Response with status code
                response_data, status_code = result[:2]
                if isinstance(response_data, dict):
                    response = jsonify(response_data)
                    response.status_code = status_code
                else:
                    # If response_data is already a Response object or string
                    response = response_data
            else:
                response = result
            
            return add_headers(response)
        
        return decorated_function
    
    return decorator