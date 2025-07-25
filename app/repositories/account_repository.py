"""Repository for managing accounts in Firestore."""
from typing import Optional, List, Dict, Any
from datetime import datetime
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter
from app.models.account import Account, AccountStatus
from app.core.exceptions import ResourceNotFoundError, VitalisException
from app.core.logging import get_logger
from app.utils.firebase import get_firestore_client

logger = get_logger(__name__)


class AccountRepository:
    """Repository for account data access."""
    
    COLLECTION_NAME = "accounts"
    
    def __init__(self):
        self.db = get_firestore_client()
        self.collection = self.db.collection(self.COLLECTION_NAME)
    
    def create(self, account: Account) -> Account:
        """Create a new account in Firestore."""
        try:
            # Check if account with same phone_number_id exists
            existing = self.get_by_phone_number_id(account.phone_number_id)
            if existing:
                raise VitalisException(
                    f"Account with phone_number_id {account.phone_number_id} already exists"
                )
            
            # Convert to dict and store
            doc_ref = self.collection.document(account.id)
            doc_ref.set(account.to_dict())
            
            logger.info(
                "Created account",
                extra={
                    "account_id": account.id,
                    "account_name": account.name,
                    "phone_number_id": account.phone_number_id
                }
            )
            
            return account
        except Exception as e:
            logger.error(
                f"Failed to create account: {e}",
                extra={"account_id": account.id}
            )
            raise VitalisException(f"Failed to create account: {str(e)}")
    
    def get(self, account_id: str) -> Optional[Account]:
        """Get an account by ID."""
        try:
            doc = self.collection.document(account_id).get()
            
            if not doc.exists:
                return None
            
            data = doc.to_dict()
            data["id"] = doc.id  # Add document ID to data
            return Account.from_dict(data)
        except Exception as e:
            logger.error(
                f"Failed to get account: {e}",
                extra={"account_id": account_id}
            )
            raise VitalisException(f"Failed to get account: {str(e)}")
    
    def get_by_phone_number_id(self, phone_number_id: str) -> Optional[Account]:
        """Get an account by WhatsApp phone number ID."""
        try:
            query = self.collection.where(
                filter=FieldFilter("phone_number_id", "==", phone_number_id)
            ).limit(1)
            
            docs = list(query.stream())
            
            if not docs:
                return None
            
            doc = docs[0]
            data = doc.to_dict()
            data["id"] = doc.id  # Add document ID to data
            return Account.from_dict(data)
        except Exception as e:
            logger.error(
                f"Failed to get account by phone_number_id: {e}",
                extra={"phone_number_id": phone_number_id}
            )
            raise VitalisException(f"Failed to get account: {str(e)}")
    
    def get_by_location_id(self, location_id: str) -> Optional[Account]:
        """Get an account by GHL location ID."""
        try:
            query = self.collection.where(
                filter=FieldFilter("location_id", "==", location_id)
            ).limit(1)
            
            docs = list(query.stream())
            
            if not docs:
                return None
            
            doc = docs[0]
            data = doc.to_dict()
            data["id"] = doc.id  # Add document ID to data
            
            # Debug logging for account data
            logger.info(
                "Loading account from Firestore",
                extra={
                    "location_id": location_id,
                    "doc_id": doc.id,
                    "has_stripe_enabled": "stripe_enabled" in data,
                    "stripe_enabled_value": data.get("stripe_enabled"),
                    "has_stripe_connect_id": "stripe_connect_account_id" in data,
                    "stripe_connect_id": data.get("stripe_connect_account_id"),
                    "all_fields": list(data.keys())
                }
            )
            
            return Account.from_dict(data)
        except Exception as e:
            logger.error(
                f"Failed to get account by location_id: {e}",
                extra={"location_id": location_id}
            )
            raise VitalisException(f"Failed to get account: {str(e)}")
    
    def get_by_email(self, email: str) -> Optional[Account]:
        """Get an account by email address."""
        try:
            query = self.collection.where(
                filter=FieldFilter("email", "==", email)
            ).limit(1)
            
            docs = list(query.stream())
            
            if not docs:
                return None
            
            doc = docs[0]
            data = doc.to_dict()
            data["id"] = doc.id  # Add document ID to data
            return Account.from_dict(data)
        except Exception as e:
            logger.error(
                f"Failed to get account by email: {e}",
                extra={"email": email}
            )
            raise VitalisException(f"Failed to get account: {str(e)}")
    
    def list_all(self, status: Optional[AccountStatus] = None) -> List[Account]:
        """List all accounts, optionally filtered by status."""
        try:
            query = self.collection
            
            if status:
                query = query.where(
                    filter=FieldFilter("status", "==", status.value)
                )
            
            # Order by created_at descending - remove this as it may cause issues if created_at doesn't exist
            # query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
            
            docs = query.stream()
            accounts = []
            
            logger.info("Fetching accounts from Firestore", extra={
                "collection": self.COLLECTION_NAME,
                "has_status_filter": status is not None,
                "status_filter": status.value if status else None
            })
            
            doc_count = 0
            for doc in docs:
                doc_count += 1
                data = doc.to_dict()
                data["id"] = doc.id  # Add document ID to data
                
                logger.debug("Processing account document", extra={
                    "doc_id": doc.id,
                    "account_data_keys": list(data.keys())
                })
                
                try:
                    account = Account.from_dict(data)
                    accounts.append(account)
                except Exception as e:
                    logger.error(f"Failed to parse account from document {doc.id}: {e}", extra={
                        "doc_id": doc.id,
                        "doc_data": data
                    })
            
            logger.info("Completed accounts fetch", extra={
                "total_docs_processed": doc_count,
                "valid_accounts_returned": len(accounts)
            })
            
            return accounts
        except Exception as e:
            logger.error(f"Failed to list accounts: {e}")
            raise VitalisException(f"Failed to list accounts: {str(e)}")
    
    def update(self, account: Account) -> Account:
        """Update an existing account."""
        try:
            # Check if account exists
            existing = self.get(account.id)
            if not existing:
                raise ResourceNotFoundError("Account", account.id)
            
            account.updated_at = datetime.utcnow()
            
            doc_ref = self.collection.document(account.id)
            doc_ref.update(account.to_dict())
            
            logger.info(
                "Updated account",
                extra={
                    "account_id": account.id,
                    "status": account.status.value
                }
            )
            
            return account
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update account: {e}",
                extra={"account_id": account.id}
            )
            raise VitalisException(f"Failed to update account: {str(e)}")
    
    def delete(self, account_id: str) -> bool:
        """Delete an account."""
        try:
            # Check if account exists
            existing = self.get(account_id)
            if not existing:
                raise ResourceNotFoundError("Account", account_id)
            
            self.collection.document(account_id).delete()
            
            logger.info(
                "Deleted account",
                extra={"account_id": account_id}
            )
            
            return True
        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to delete account: {e}",
                extra={"account_id": account_id}
            )
            raise VitalisException(f"Failed to delete account: {str(e)}")