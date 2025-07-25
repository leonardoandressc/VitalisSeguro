"""Script to migrate existing phone numbers to normalized format."""
import os
import sys
from datetime import datetime
import pytz
import firebase_admin
from firebase_admin import firestore

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.phone_utils import normalize_phone
from app.utils.firebase import get_firestore_client
from app.core.logging import get_logger

logger = get_logger(__name__)


def migrate_active_reminder_contexts(db):
    """Migrate phone numbers in active_reminder_contexts collection."""
    logger.info("Starting migration of active_reminder_contexts collection")
    
    contexts_ref = db.collection("active_reminder_contexts")
    contexts = list(contexts_ref.stream())
    
    migrated = 0
    skipped = 0
    errors = 0
    
    for doc in contexts:
        try:
            data = doc.to_dict()
            phone = data.get("phone_number")
            
            if not phone:
                logger.warning(f"Document {doc.id} has no phone_number field")
                skipped += 1
                continue
            
            normalized = normalize_phone(phone)
            
            if normalized != phone:
                # Phone needs normalization
                logger.info(f"Migrating {phone} -> {normalized} in document {doc.id}")
                doc.reference.update({
                    "phone_number": normalized,
                    "original_phone": phone,  # Keep original for reference
                    "migrated_at": datetime.now(pytz.UTC).isoformat()
                })
                migrated += 1
            else:
                logger.debug(f"Phone {phone} already normalized in document {doc.id}")
                skipped += 1
                
        except Exception as e:
            logger.error(f"Error migrating document {doc.id}: {e}")
            errors += 1
    
    logger.info(f"Active reminder contexts migration complete: "
                f"{migrated} migrated, {skipped} skipped, {errors} errors")
    
    return {"migrated": migrated, "skipped": skipped, "errors": errors}


def migrate_conversations(db):
    """Migrate phone numbers in conversations collection."""
    logger.info("Starting migration of conversations collection")
    
    conversations_ref = db.collection("conversations")
    conversations = list(conversations_ref.stream())
    
    migrated = 0
    skipped = 0
    errors = 0
    
    for doc in conversations:
        try:
            data = doc.to_dict()
            phone = data.get("phone_number")
            
            if not phone:
                logger.warning(f"Document {doc.id} has no phone_number field")
                skipped += 1
                continue
            
            normalized = normalize_phone(phone)
            
            if normalized != phone:
                # Phone needs normalization
                logger.info(f"Migrating {phone} -> {normalized} in document {doc.id}")
                
                # Update document
                updates = {
                    "phone_number": normalized,
                    "original_phone": phone,
                    "migrated_at": datetime.now(pytz.UTC).isoformat()
                }
                
                # Also update conversation ID if it contains the phone
                old_id = doc.id
                if phone in old_id:
                    new_id = old_id.replace(phone, normalized)
                    logger.info(f"Creating new document with ID {new_id}")
                    
                    # Create new document with normalized ID
                    new_doc_ref = conversations_ref.document(new_id)
                    new_data = data.copy()
                    new_data.update(updates)
                    new_doc_ref.set(new_data)
                    
                    # Delete old document
                    doc.reference.delete()
                    logger.info(f"Deleted old document {old_id}")
                else:
                    # Just update the existing document
                    doc.reference.update(updates)
                
                migrated += 1
            else:
                logger.debug(f"Phone {phone} already normalized in document {doc.id}")
                skipped += 1
                
        except Exception as e:
            logger.error(f"Error migrating document {doc.id}: {e}")
            errors += 1
    
    logger.info(f"Conversations migration complete: "
                f"{migrated} migrated, {skipped} skipped, {errors} errors")
    
    return {"migrated": migrated, "skipped": skipped, "errors": errors}


def migrate_appointment_reminders(db):
    """Migrate phone numbers in appointment_reminders collection."""
    logger.info("Starting migration of appointment_reminders collection")
    
    reminders_ref = db.collection("appointment_reminders")
    reminders = list(reminders_ref.stream())
    
    migrated = 0
    skipped = 0
    errors = 0
    
    for doc in reminders:
        try:
            data = doc.to_dict()
            phone = data.get("contact_phone")
            
            if not phone:
                logger.warning(f"Document {doc.id} has no contact_phone field")
                skipped += 1
                continue
            
            normalized = normalize_phone(phone)
            
            if normalized != phone:
                # Phone needs normalization
                logger.info(f"Migrating {phone} -> {normalized} in document {doc.id}")
                doc.reference.update({
                    "contact_phone": normalized,
                    "original_phone": phone,
                    "migrated_at": datetime.now(pytz.UTC).isoformat()
                })
                migrated += 1
            else:
                logger.debug(f"Phone {phone} already normalized in document {doc.id}")
                skipped += 1
                
        except Exception as e:
            logger.error(f"Error migrating document {doc.id}: {e}")
            errors += 1
    
    logger.info(f"Appointment reminders migration complete: "
                f"{migrated} migrated, {skipped} skipped, {errors} errors")
    
    return {"migrated": migrated, "skipped": skipped, "errors": errors}


def main():
    """Run the migration script."""
    logger.info("Starting phone number migration script")
    
    # Initialize Firestore
    db = get_firestore_client()
    
    # Track overall results
    results = {
        "active_reminder_contexts": {},
        "conversations": {},
        "appointment_reminders": {},
        "started_at": datetime.now(pytz.UTC).isoformat()
    }
    
    # Migrate each collection
    try:
        results["active_reminder_contexts"] = migrate_active_reminder_contexts(db)
    except Exception as e:
        logger.error(f"Failed to migrate active_reminder_contexts: {e}")
        results["active_reminder_contexts"] = {"error": str(e)}
    
    try:
        results["conversations"] = migrate_conversations(db)
    except Exception as e:
        logger.error(f"Failed to migrate conversations: {e}")
        results["conversations"] = {"error": str(e)}
    
    try:
        results["appointment_reminders"] = migrate_appointment_reminders(db)
    except Exception as e:
        logger.error(f"Failed to migrate appointment_reminders: {e}")
        results["appointment_reminders"] = {"error": str(e)}
    
    results["completed_at"] = datetime.now(pytz.UTC).isoformat()
    
    # Store migration results
    migration_ref = db.collection("migration_runs").document()
    migration_ref.set({
        "type": "phone_normalization",
        "results": results,
        "timestamp": datetime.now(pytz.UTC).isoformat()
    })
    
    # Print summary
    print("\n=== Phone Number Migration Summary ===")
    for collection, stats in results.items():
        if isinstance(stats, dict) and "migrated" in stats:
            print(f"\n{collection}:")
            print(f"  Migrated: {stats['migrated']}")
            print(f"  Skipped: {stats['skipped']}")
            print(f"  Errors: {stats['errors']}")
    
    print(f"\nMigration completed. Results stored in document: {migration_ref.id}")


if __name__ == "__main__":
    main()