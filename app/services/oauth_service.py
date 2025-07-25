"""Service for handling OAuth flows."""
import uuid
import requests
import time
from typing import Dict, Any, Optional
from urllib.parse import urlencode
from app.services.account_service import AccountService
from app.core.config import get_config
from app.core.exceptions import ValidationError, ExternalServiceError
from app.core.logging import get_logger
from app.utils.firebase import get_firestore_client

logger = get_logger(__name__)


class OAuthService:
    """Service for OAuth authentication flows."""
    
    def __init__(self):
        self.account_service = AccountService()
        self.config = get_config()
        self.oauth_base_url = "https://marketplace.gohighlevel.com"
        # Temporary in-memory fallback for state storage
        self._states_fallback: Dict[str, str] = {}
    
    def get_authorization_url(self, account_id: str) -> str:
        """Generate OAuth authorization URL for GoHighLevel."""
        # Verify account exists
        account = self.account_service.get_account(account_id)
        
        # Generate state for CSRF protection
        state = str(uuid.uuid4())
        
        # Store state in Firebase with expiration
        self._store_oauth_state(state, account_id)
        
        # Build authorization URL
        params = {
            "response_type": "code",
            "client_id": self.config.ghl_client_id,
            "redirect_uri": self.config.callback_uri,
            "scope": "calendars.readonly calendars.write calendars/events.readonly calendars/events.write contacts.readonly contacts.write",
            "state": state
        }
        
        auth_url = f"{self.oauth_base_url}/oauth/chooselocation?{urlencode(params)}"
        
        logger.info(
            "Generated OAuth authorization URL",
            extra={"account_id": account_id, "state": state}
        )
        
        return auth_url
    
    def handle_callback(self, code: str, state: str) -> Dict[str, Any]:
        """Handle OAuth callback from GoHighLevel."""
        # Validate state
        account_id = self._get_oauth_state(state)
        if not account_id:
            raise ValidationError("Invalid state parameter")
        
        # Remove state to prevent reuse
        self._delete_oauth_state(state)
        
        try:
            # Exchange code for tokens
            response = requests.post(
                "https://services.leadconnectorhq.com/oauth/token",
                data={
                    "client_id": self.config.ghl_client_id,
                    "client_secret": self.config.ghl_client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.config.callback_uri
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )
            
            # Log request details for debugging
            if response.status_code != 200:
                logger.error(
                    f"OAuth token exchange failed with status {response.status_code}",
                    extra={
                        "status_code": response.status_code,
                        "response_text": response.text,
                        "request_data": {
                            "grant_type": "authorization_code",
                            "code": code[:10] + "...",  # Log partial code for security
                            "redirect_uri": self.config.callback_uri,
                            "client_id": self.config.ghl_client_id[:10] + "..." if self.config.ghl_client_id else None
                        }
                    }
                )
            
            response.raise_for_status()
            tokens = response.json()
            
            # Save tokens
            self.account_service.save_oauth_tokens(account_id, tokens)
            
            logger.info(
                "OAuth flow completed successfully",
                extra={"account_id": account_id}
            )
            
            return {
                "success": True,
                "account_id": account_id,
                "message": "Authorization successful"
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(
                f"OAuth token exchange failed: {e}",
                extra={"account_id": account_id}
            )
            raise ExternalServiceError(
                "GoHighLevel",
                f"Failed to exchange authorization code: {str(e)}"
            )
    
    def refresh_token(self, account_id: str) -> bool:
        """Refresh OAuth tokens for an account."""
        try:
            # Use GHL client to refresh token
            from app.integrations.ghl.client import GoHighLevelClient
            ghl_client = GoHighLevelClient()
            ghl_client.refresh_token(account_id)
            
            return True
        except Exception as e:
            logger.error(
                f"Failed to refresh token: {e}",
                extra={"account_id": account_id}
            )
            return False
    
    def revoke_tokens(self, account_id: str) -> bool:
        """Revoke OAuth tokens for an account."""
        try:
            # In GoHighLevel, there's no revoke endpoint
            # So we just delete the tokens from our storage
            from app.repositories.token_repository import TokenRepository
            token_repo = TokenRepository()
            return token_repo.delete_tokens(account_id)
        except Exception as e:
            logger.error(
                f"Failed to revoke tokens: {e}",
                extra={"account_id": account_id}
            )
            return False
    
    def _store_oauth_state(self, state: str, account_id: str) -> None:
        """Store OAuth state in Firebase with expiration."""
        try:
            db = get_firestore_client()
            
            # Store state with 1 hour expiration
            expiry_time = int(time.time()) + 3600
            
            db.collection("oauth_states").document(state).set({
                "account_id": account_id,
                "expires_at": expiry_time,
                "created_at": int(time.time())
            })
            
            logger.debug(f"Stored OAuth state in Firebase: {state} for account: {account_id}")
        except Exception as e:
            logger.warning(f"Failed to store OAuth state in Firebase, using in-memory fallback: {e}")
            # Fallback to in-memory storage
            self._states_fallback[state] = account_id
    
    def _get_oauth_state(self, state: str) -> Optional[str]:
        """Retrieve and validate OAuth state from Firebase."""
        try:
            db = get_firestore_client()
            
            doc = db.collection("oauth_states").document(state).get()
            if not doc.exists:
                return None
            
            data = doc.to_dict()
            current_time = int(time.time())
            
            # Check if expired
            if data.get("expires_at", 0) < current_time:
                # Clean up expired state
                db.collection("oauth_states").document(state).delete()
                return None
            
            return data.get("account_id")
        except Exception as e:
            logger.warning(f"Failed to get OAuth state from Firebase, trying in-memory fallback: {e}")
            # Fallback to in-memory storage
            return self._states_fallback.get(state)
    
    def _delete_oauth_state(self, state: str) -> None:
        """Delete OAuth state from Firebase."""
        try:
            db = get_firestore_client()
            
            db.collection("oauth_states").document(state).delete()
            logger.debug(f"Deleted OAuth state from Firebase: {state}")
        except Exception as e:
            logger.warning(f"Failed to delete OAuth state from Firebase: {e}")
        
        # Always try to delete from fallback storage
        if state in self._states_fallback:
            del self._states_fallback[state]