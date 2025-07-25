#!/usr/bin/env python3
"""Script to delete conversations by phone number.

This script allows deleting all conversations for a specific phone number
with safety confirmations and preview mode.

Usage:
    python scripts/delete_conversations.py --phone +521234567890 --preview
    python scripts/delete_conversations.py --phone +521234567890
    python scripts/delete_conversations.py --phone +521234567890 --force
    python scripts/delete_conversations.py --phone +521234567890 --account-id <id>
"""
import os
import sys
import argparse
from typing import Any

# Add parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, firestore

from app.core.config import get_config
from app.core.logging import get_logger, setup_logging
from app.models.account import AccountStatus
from app.repositories.account_repository import AccountRepository

# Load environment variables
load_dotenv()

# Initialize Firebase
config = get_config()
if not firebase_admin._apps:
    cred = credentials.Certificate(config.firebase_credentials_path)
    firebase_admin.initialize_app(cred)

logger = get_logger(__name__)


def format_conversation_summary(conversation: Any) -> str:
    """Format a conversation summary for display."""
    messages_count = len(conversation.messages) if hasattr(conversation, 'messages') else 0
    created_at = conversation.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(conversation, 'created_at') else "Unknown"
    status = conversation.status.value if hasattr(conversation, 'status') else "Unknown"
    
    summary = f"  ID: {conversation.id}\n"
    summary += f"  Created: {created_at}\n"
    summary += f"  Status: {status}\n"
    summary += f"  Messages: {messages_count}\n"
    
    if hasattr(conversation, 'context') and conversation.context.appointment_info:
        apt_info = conversation.context.appointment_info
        summary += f"  Appointment: {apt_info.get('name', 'N/A')} - {apt_info.get('reason', 'N/A')}\n"
    
    return summary


def main():
    """Main entry point for delete conversations script."""
    parser = argparse.ArgumentParser(
        description="Delete conversations by phone number"
    )
    parser.add_argument(
        "--phone",
        type=str,
        required=True,
        help="Phone number to delete conversations for (with country code, e.g. +521234567890)"
    )
    parser.add_argument(
        "--account-id",
        type=str,
        default=None,
        help="Only delete conversations for this specific account ID"
    )
    parser.add_argument(
        "--account-name",
        type=str,
        default=None,
        help="Only delete conversations for this specific account name"
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force deletion without confirmation prompt"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(config)
    
    logger.info(
        "Starting conversation deletion process",
        extra={
            "phone": args.phone,
            "account_id": args.account_id,
            "account_name": args.account_name,
            "preview_mode": args.preview
        }
    )
    
    try:
        # Initialize repositories
        account_repo = AccountRepository()
        
        # Get account filter if specified
        account_id_filter = args.account_id
        
        if args.account_name and not account_id_filter:
            # Find account by name
            accounts = account_repo.list_all(status=AccountStatus.ACTIVE)
            matching_accounts = [a for a in accounts if a.name.lower() == args.account_name.lower()]
            
            if not matching_accounts:
                print(f"\n❌ No active account found with name '{args.account_name}'")
                print("\nAvailable accounts:")
                for a in accounts:
                    print(f"  - {a.name}")
                sys.exit(1)
            
            account_id_filter = matching_accounts[0].id
            print(f"\n✓ Found account: {matching_accounts[0].name} ({account_id_filter})")
        
        # Find all conversations for this phone number
        print(f"\nSearching for conversations with phone number: {args.phone}")
        
        # Query conversations
        db = firestore.client()
        query = db.collection("conversations").where("phone_number", "==", args.phone)
        
        if account_id_filter:
            query = query.where("account_id", "==", account_id_filter)
        
        docs = list(query.stream())
        
        if not docs:
            print(f"\n✓ No conversations found for phone number: {args.phone}")
            return
        
        print(f"\n{'PREVIEW MODE - ' if args.preview else ''}Found {len(docs)} conversation(s) to delete:")
        print("=" * 60)
        
        conversations_to_delete = []
        for doc in docs:
            conv_data = doc.to_dict()
            conv_data['id'] = doc.id
            
            # Display conversation info
            print(f"\nConversation #{len(conversations_to_delete) + 1}:")
            print(f"  ID: {doc.id}")
            print(f"  Account ID: {conv_data.get('account_id', 'N/A')}")
            print(f"  Status: {conv_data.get('status', 'N/A')}")
            print(f"  Created: {conv_data.get('created_at', 'N/A')}")
            print(f"  Messages: {len(conv_data.get('messages', []))}")
            
            # Show appointment info if exists
            context = conv_data.get('context', {})
            if context and context.get('appointment_info'):
                apt_info = context['appointment_info']
                print(f"  Appointment: {apt_info.get('name', 'N/A')} - {apt_info.get('reason', 'N/A')}")
            
            conversations_to_delete.append(doc)
        
        print("=" * 60)
        
        if args.preview:
            print("\n✓ Preview complete. No conversations were deleted.")
            print(f"  To actually delete these {len(conversations_to_delete)} conversation(s), run without --preview")
            return
        
        # Confirm deletion
        if not args.force:
            print(f"\n⚠️  You are about to delete {len(conversations_to_delete)} conversation(s).")
            confirmation = input("Are you sure you want to proceed? (yes/no): ")
            
            if confirmation.lower() not in ['yes', 'y']:
                print("\n✓ Deletion cancelled.")
                return
        
        # Delete conversations
        print(f"\nDeleting {len(conversations_to_delete)} conversation(s)...")
        
        deleted_count = 0
        for doc in conversations_to_delete:
            try:
                doc.reference.delete()
                deleted_count += 1
                print(f"  ✓ Deleted conversation: {doc.id}")
            except Exception as e:
                print(f"  ❌ Failed to delete conversation {doc.id}: {e}")
        
        print(f"\n✓ Successfully deleted {deleted_count} conversation(s)")
        
        if deleted_count != len(conversations_to_delete):
            print(f"⚠️  {len(conversations_to_delete) - deleted_count} conversation(s) failed to delete")
        
    except Exception as e:
        logger.error(f"Error in delete conversations script: {e}", exc_info=True)
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()