"""Repository for managing OAuth tokens in Firestore."""
from typing import Optional, Dict, Any
from datetime import datetime
import firebase_admin
from firebase_admin import firestore
from app.core.exceptions import ResourceNotFoundError, VitalisException, TokenError
from app.core.logging import get_logger
from app.utils.firebase import get_firestore_client
import json

logger = get_logger(__name__)


class TokenRepository:
    """Repository for OAuth token data access."""
    
    COLLECTION_NAME = "tokens"
    
    def __init__(self):
        self.db = get_firestore_client()
        self.collection = self.db.collection(self.COLLECTION_NAME)
    
    def save_tokens(self, account_id: str, tokens: Dict[str, Any]) -> bool:
        """Save or update OAuth tokens for an account."""
        try:
            # Use the same structure as working version: accounts/{account_id}/tokens/default
            doc_ref = self.db.collection("accounts").document(account_id).collection("tokens").document("default")
            
            # Calculate expires_at as absolute timestamp (like working version)
            import time
            expires_at = int(time.time()) + tokens.get("expires_in", 3600)
            
            token_data = {
                "access_token": tokens.get("access_token"),
                "refresh_token": tokens.get("refresh_token"),
                "location_id": tokens.get("locationId"),  # Include location_id like working version
                "expires_at": expires_at,
                "expires_in": tokens.get("expires_in"),
                "token_type": tokens.get("token_type", "Bearer"),
                "scope": tokens.get("scope"),
                "updated_at": datetime.utcnow().isoformat(),
                "created_at": datetime.utcnow().isoformat()
            }
            
            # If document exists, preserve created_at
            existing = doc_ref.get()
            if existing.exists:
                existing_data = existing.to_dict()
                token_data["created_at"] = existing_data.get("created_at", token_data["created_at"])
            
            doc_ref.set(token_data)
            
            logger.info(
                "Saved tokens for account",
                extra={"account_id": account_id}
            )
            
            return True
        except Exception as e:
            logger.error(
                f"Failed to save tokens: {e}",
                extra={"account_id": account_id}
            )
            raise TokenError(f"Failed to save tokens: {str(e)}", account_id=account_id)
    
    def get_tokens(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get OAuth tokens for an account."""
        try:
            # Use the same structure as working version: accounts/{account_id}/tokens/default
            doc = self.db.collection("accounts").document(account_id).collection("tokens").document("default").get()
            
            if not doc.exists:
                logger.warning(
                    "No tokens found for account",
                    extra={"account_id": account_id}
                )
                return None
            
            return doc.to_dict()
        except Exception as e:
            logger.error(
                f"Failed to get tokens: {e}",
                extra={"account_id": account_id}
            )
            raise TokenError(f"Failed to get tokens: {str(e)}", account_id=account_id)
    
    def update_access_token(self, account_id: str, access_token: str, expires_in: int) -> bool:
        """Update only the access token (after refresh)."""
        try:
            # Use the same structure as working version: accounts/{account_id}/tokens/default
            doc_ref = self.db.collection("accounts").document(account_id).collection("tokens").document("default")
            
            # Check if document exists
            if not doc_ref.get().exists:
                raise ResourceNotFoundError("Token", account_id)
            
            # Calculate new expires_at as absolute timestamp
            import time
            expires_at = int(time.time()) + expires_in
            
            doc_ref.update({
                "access_token": access_token,
                "expires_in": expires_in,
                "expires_at": expires_at,
                "updated_at": datetime.utcnow().isoformat()
            })
            
            logger.info(
                "Updated access token for account",
                extra={"account_id": account_id}
            )
            
            return True
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update access token: {e}",
                extra={"account_id": account_id}
            )
            raise TokenError(f"Failed to update access token: {str(e)}", account_id=account_id)
    
    def delete_tokens(self, account_id: str) -> bool:
        """Delete tokens for an account."""
        try:
            # Use the same structure as working version: accounts/{account_id}/tokens/default
            self.db.collection("accounts").document(account_id).collection("tokens").document("default").delete()
            
            logger.info(
                "Deleted tokens for account",
                extra={"account_id": account_id}
            )
            
            return True
        except Exception as e:
            logger.error(
                f"Failed to delete tokens: {e}",
                extra={"account_id": account_id}
            )
            raise TokenError(f"Failed to delete tokens: {str(e)}", account_id=account_id)
    
    def is_token_expired(self, account_id: str) -> bool:
        """Check if the access token is expired."""
        try:
            tokens = self.get_tokens(account_id)
            if not tokens:
                return True
            
            # Use expires_at absolute timestamp (like working version)
            expires_at = tokens.get("expires_at")
            if not expires_at:
                return True
            
            import time
            return int(time.time()) >= expires_at
        except Exception as e:
            logger.error(
                f"Failed to check token expiration: {e}",
                extra={"account_id": account_id}
            )
            # If we can't check, assume expired to be safe
            return True