"""Service for managing accounts."""
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
from app.models.account import Account, AccountStatus
from app.repositories.account_repository import AccountRepository
from app.repositories.token_repository import TokenRepository
from app.core.exceptions import ValidationError, ResourceNotFoundError, VitalisException
from app.core.logging import get_logger

logger = get_logger(__name__)


class AccountService:
    """Service for account business logic."""
    
    def __init__(self):
        self.repository = AccountRepository()
        self.token_repository = TokenRepository()
    
    def create_account(self, data: Dict[str, Any]) -> Account:
        """Create a new account."""
        # Validate required fields
        required_fields = ["name", "phone_number_id", "calendar_id", "location_id", "assigned_user_id"]
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationError(f"Missing required field: {field}", field=field)
        
        # Generate account ID
        account_id = str(uuid.uuid4())
        
        # Create account object
        account = Account(
            id=account_id,
            name=data["name"],
            email=data.get("email"),
            phone_number_id=data["phone_number_id"],
            calendar_id=data["calendar_id"],
            location_id=data["location_id"],
            assigned_user_id=data["assigned_user_id"],
            custom_prompt=data.get("custom_prompt"),
            status=AccountStatus.ACTIVE,
            # Stripe fields - use provided values or defaults from model
            stripe_enabled=data.get("stripe_enabled", False),
            stripe_connect_account_id=data.get("stripe_connect_account_id"),
            stripe_onboarding_completed=data.get("stripe_onboarding_completed", False),
            appointment_price=data.get("appointment_price", 50000),
            currency=data.get("currency", "mxn"),
            payment_description=data.get("payment_description", "Pago de consulta médica"),
            stripe_charges_enabled=data.get("stripe_charges_enabled", False),
            stripe_payouts_enabled=data.get("stripe_payouts_enabled", False)
        )
        
        # Save to repository
        created_account = self.repository.create(account)
        
        # Register WhatsApp phone number if requested
        if data.get("register_whatsapp", False):
            try:
                from app.integrations.whatsapp.client import WhatsAppClient
                whatsapp_client = WhatsAppClient()
                
                # Get optional registration parameters
                pin = data.get("whatsapp_pin", "000000")
                data_localization_region = data.get("data_localization_region")
                
                registration_result = whatsapp_client.register_phone_number(
                    phone_number_id=created_account.phone_number_id,
                    pin=pin,
                    data_localization_region=data_localization_region
                )
                
                logger.info(
                    "WhatsApp registration completed for account",
                    extra={
                        "account_id": created_account.id,
                        "phone_number_id": created_account.phone_number_id,
                        "registration_success": registration_result.get("success", False)
                    }
                )
            except Exception as e:
                logger.error(
                    f"WhatsApp registration failed for account {created_account.id}: {e}",
                    extra={
                        "account_id": created_account.id,
                        "phone_number_id": created_account.phone_number_id,
                        "error": str(e)
                    }
                )
                # Don't fail account creation if WhatsApp registration fails
                # The admin can try to register manually later
        
        logger.info(
            "Account created successfully",
            extra={
                "account_id": created_account.id,
                "account_name": created_account.name
            }
        )
        
        return created_account
    
    def get_account(self, account_id: str) -> Account:
        """Get an account by ID."""
        account = self.repository.get(account_id)
        if not account:
            raise ResourceNotFoundError("Account", account_id)
        return account
    
    def get_account_by_phone_number_id(self, phone_number_id: str) -> Optional[Account]:
        """Get an account by WhatsApp phone number ID."""
        return self.repository.get_by_phone_number_id(phone_number_id)
    
    def get_account_by_email(self, email: str) -> Optional[Account]:
        """Get an account by email address."""
        return self.repository.get_by_email(email)
    
    def list_accounts(self, status: Optional[AccountStatus] = None) -> List[Account]:
        """List all accounts."""
        return self.repository.list_all(status=status)
    
    def update_account(self, account_id_or_account, data=None):
        """Update an account."""
        # Handle both Account object and account_id string
        if isinstance(account_id_or_account, Account):
            account = account_id_or_account
            account_id = account.id
            # When Account object is passed, we just save it
            updated_account = self.repository.update(account)
            data = {}  # Set empty data for logging
        else:
            # Get existing account
            account_id = account_id_or_account
            account = self.get_account(account_id)
            
            if data is None:
                data = {}
            
            # Update allowed fields
            updatable_fields = [
                "name", "email", "custom_prompt", "calendar_id", "location_id", "assigned_user_id", "status",
                # Stripe fields
                "stripe_enabled", "stripe_connect_account_id", "stripe_onboarding_completed",
                "appointment_price", "currency", "payment_description",
                "stripe_charges_enabled", "stripe_payouts_enabled", "stripe_details_submitted",
                "stripe_capability_status", "stripe_last_webhook_update",
                # Subscription fields
                "stripe_customer_id", "subscription_tier_id", "subscription_status", 
                "subscription_current_period_end",
                # Free account fields
                "is_free_account", "free_account_reason", "free_account_expires", "products_override"
            ]
            
            for field in updatable_fields:
                if field in data:
                    if field == "status" and isinstance(data[field], str):
                        # Convert status string to enum
                        try:
                            setattr(account, field, AccountStatus(data[field]))
                        except ValueError:
                            raise ValidationError(f"Invalid status: {data[field]}", field="status")
                    else:
                        setattr(account, field, data[field])
            
            # Save updates
            updated_account = self.repository.update(account)
        
        logger.info(
            "Account updated successfully",
            extra={
                "account_id": account_id,
                "updated_fields": list(data.keys())
            }
        )
        
        return updated_account
    
    def delete_account(self, account_id: str) -> bool:
        """Delete an account and its associated data."""
        # Verify account exists
        account = self.get_account(account_id)
        
        # Delete tokens first
        try:
            self.token_repository.delete_tokens(account_id)
        except Exception as e:
            logger.warning(f"Failed to delete tokens for account {account_id}: {e}")
        
        # Delete account
        result = self.repository.delete(account_id)
        
        logger.info(
            "Account deleted successfully",
            extra={"account_id": account_id}
        )
        
        return result
    
    def activate_account(self, account_id: str) -> Account:
        """Activate an account."""
        return self.update_account(account_id, {"status": AccountStatus.ACTIVE.value})
    
    def deactivate_account(self, account_id: str) -> Account:
        """Deactivate an account."""
        return self.update_account(account_id, {"status": AccountStatus.INACTIVE.value})
    
    def get_account_with_tokens(self, account_id: str) -> Dict[str, Any]:
        """Get account with its OAuth tokens."""
        account = self.get_account(account_id)
        tokens = self.token_repository.get_tokens(account_id)
        
        return {
            "account": account.to_dict(),
            "has_tokens": tokens is not None,
            "token_expired": self.token_repository.is_token_expired(account_id) if tokens else None
        }
    
    def save_oauth_tokens(self, account_id: str, tokens: Dict[str, Any]) -> bool:
        """Save OAuth tokens for an account."""
        # Verify account exists
        account = self.get_account(account_id)
        
        # Save tokens
        return self.token_repository.save_tokens(account_id, tokens)