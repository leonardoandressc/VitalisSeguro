#!/usr/bin/env python3
"""
Delete a Stripe connected account and clear related fields in Firestore.

Usage:
    python scripts/delete_stripe_account.py <account_id> [--dry-run]
"""

import os
import sys
import stripe
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_config
from app.services.account_service import AccountService
from app.repositories.account_repository import AccountRepository
from app.utils.firebase import get_firestore_client
from app.core.logging import get_logger

logger = get_logger(__name__)


def delete_stripe_account(account_id: str, dry_run: bool = False) -> None:
    """Delete a Stripe connected account and update Firestore."""
    
    # Initialize services
    config = get_config()
    stripe.api_key = config.stripe_secret_key
    account_service = AccountService()
    account_repo = AccountRepository()
    
    try:
        # Get account from database
        print(f"\nFetching account {account_id}...")
        account = account_service.get_account(account_id)
        
        if not account:
            print(f"❌ Account {account_id} not found")
            return
        
        # Display account details
        print(f"\n📋 Account Details:")
        print(f"   Name: {account.name}")
        print(f"   Email: {account.email}")
        print(f"   Status: {account.status}")
        print(f"   Stripe Enabled: {account.stripe_enabled}")
        print(f"   Stripe Account ID: {account.stripe_connect_account_id or 'None'}")
        print(f"   Onboarding Completed: {account.stripe_onboarding_completed}")
        print(f"   Charges Enabled: {account.stripe_charges_enabled}")
        
        if not account.stripe_connect_account_id:
            print("\n⚠️  This account does not have a Stripe connected account.")
            return
        
        if dry_run:
            print("\n🔍 DRY RUN MODE - No changes will be made")
        else:
            # Confirmation prompt
            print(f"\n⚠️  WARNING: This will permanently delete the Stripe connected account!")
            print(f"   Stripe Account ID: {account.stripe_connect_account_id}")
            confirmation = input("\nType 'DELETE' to confirm deletion: ")
            
            if confirmation != 'DELETE':
                print("❌ Deletion cancelled")
                return
        
        # Delete from Stripe
        if not dry_run:
            print(f"\n🗑️  Deleting Stripe account {account.stripe_connect_account_id}...")
            try:
                deleted = stripe.Account.delete(account.stripe_connect_account_id)
                print(f"✅ Stripe account deleted successfully")
                logger.info(
                    f"Deleted Stripe account",
                    extra={
                        "account_id": account_id,
                        "stripe_account_id": account.stripe_connect_account_id,
                        "deleted": deleted.deleted
                    }
                )
            except stripe.error.InvalidRequestError as e:
                if "No such account" in str(e):
                    print(f"⚠️  Stripe account not found (may already be deleted)")
                    logger.warning(f"Stripe account not found: {e}")
                else:
                    print(f"❌ Error deleting Stripe account: {e}")
                    logger.error(f"Error deleting Stripe account: {e}")
                    return
            except Exception as e:
                print(f"❌ Unexpected error deleting Stripe account: {e}")
                logger.error(f"Unexpected error deleting Stripe account: {e}")
                return
        
        # Update Firestore
        if not dry_run:
            print("\n📝 Updating account in Firestore...")
            
            # Clear Stripe-related fields
            updates = {
                "stripe_connect_account_id": None,
                "stripe_onboarding_completed": False,
                "stripe_charges_enabled": False,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Optionally disable Stripe entirely
            disable_stripe = input("\nDisable Stripe for this account? (y/N): ").lower() == 'y'
            if disable_stripe:
                updates["stripe_enabled"] = False
            
            # Update in Firestore
            db = get_firestore_client()
            doc_ref = db.collection("accounts").document(account_id)
            doc_ref.update(updates)
            
            print("✅ Account updated successfully")
            logger.info(
                f"Updated account after Stripe deletion",
                extra={
                    "account_id": account_id,
                    "updates": updates
                }
            )
        
        # Final summary
        print(f"\n✅ {'DRY RUN COMPLETED' if dry_run else 'DELETION COMPLETED'}")
        if not dry_run:
            print(f"   - Stripe account {account.stripe_connect_account_id} deleted")
            print(f"   - Firestore account {account_id} updated")
            print(f"   - Stripe fields cleared")
            if disable_stripe:
                print(f"   - Stripe disabled for account")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error(f"Error in delete_stripe_account: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Delete a Stripe connected account and clear related fields in Firestore"
    )
    parser.add_argument(
        "account_id",
        help="The account ID to delete Stripe account for"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without making any changes"
    )
    
    args = parser.parse_args()
    
    # Check if running from correct directory
    if not os.path.exists("app.py"):
        print("❌ Please run this script from the project root directory")
        print("   Example: python scripts/delete_stripe_account.py <account_id>")
        sys.exit(1)
    
    delete_stripe_account(args.account_id, args.dry_run)


if __name__ == "__main__":
    main()