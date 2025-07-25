"""Firebase utilities for the application."""
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import Client
from app.core.config import get_config
from app.core.logging import get_logger

logger = get_logger(__name__)


def initialize_firebase() -> None:
    """Initialize Firebase Admin SDK if not already initialized."""
    if not firebase_admin._apps:
        config = get_config()
        cred = credentials.Certificate(config.firebase_credentials_path)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized successfully")


def get_firestore_client() -> Client:
    """Get Firestore client instance.
    
    Returns:
        Firestore client instance
    """
    # Ensure Firebase is initialized
    initialize_firebase()
    
    # Return Firestore client
    return firestore.client()