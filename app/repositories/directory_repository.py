"""Repository for directory profile operations."""
from typing import List, Optional, Dict, Any
from datetime import datetime
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter

from app.models.directory_profile import DirectoryProfile, MedicalSpecialty
from app.core.logging import get_logger
from app.utils.firebase import get_firestore_client

logger = get_logger(__name__)


class DirectoryRepository:
    """Repository for managing directory profiles in Firestore."""
    
    def __init__(self):
        """Initialize directory repository."""
        self.db = get_firestore_client()
        self.collection_name = "directory_profiles"
    
    def create(self, profile: DirectoryProfile) -> DirectoryProfile:
        """Create a new directory profile."""
        try:
            # Add timestamps
            profile.created_at = datetime.now()
            profile.updated_at = datetime.now()
            
            # Convert to dict and remove id
            data = profile.to_dict()
            
            # Create document
            doc_ref = self.db.collection(self.collection_name).add(data)
            profile.id = doc_ref[1].id
            
            logger.info(f"Created directory profile: {profile.id}")
            return profile
            
        except Exception as e:
            logger.error(f"Error creating directory profile: {e}")
            raise
    
    def get_by_id(self, profile_id: str) -> Optional[DirectoryProfile]:
        """Get directory profile by ID."""
        try:
            doc_ref = self.db.collection(self.collection_name).document(profile_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            return DirectoryProfile.from_dict(doc.to_dict(), doc.id)
            
        except Exception as e:
            logger.error(f"Error getting directory profile {profile_id}: {e}")
            raise
    
    def get_by_account_id(self, account_id: str) -> Optional[DirectoryProfile]:
        """Get directory profile by account ID."""
        try:
            query = self.db.collection(self.collection_name).where(
                filter=FieldFilter("account_id", "==", account_id)
            ).limit(1)
            
            docs = list(query.stream())
            if not docs:
                return None
            
            doc = docs[0]
            return DirectoryProfile.from_dict(doc.to_dict(), doc.id)
            
        except Exception as e:
            logger.error(f"Error getting directory profile for account {account_id}: {e}")
            raise
    
    def update(self, profile: DirectoryProfile) -> DirectoryProfile:
        """Update existing directory profile."""
        try:
            if not profile.id:
                raise ValueError("Profile ID is required for update")
            
            # Update timestamp
            profile.updated_at = datetime.now()
            
            # Convert to dict and remove id
            data = profile.to_dict()
            
            # Update document
            doc_ref = self.db.collection(self.collection_name).document(profile.id)
            doc_ref.update(data)
            
            logger.info(f"Updated directory profile: {profile.id}")
            return profile
            
        except Exception as e:
            logger.error(f"Error updating directory profile {profile.id}: {e}")
            raise
    
    def delete(self, profile_id: str) -> bool:
        """Delete directory profile."""
        try:
            doc_ref = self.db.collection(self.collection_name).document(profile_id)
            doc_ref.delete()
            
            logger.info(f"Deleted directory profile: {profile_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting directory profile {profile_id}: {e}")
            raise
    
    def list_enabled(
        self,
        specialty: Optional[MedicalSpecialty] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[DirectoryProfile]:
        """List enabled directory profiles with optional filters."""
        try:
            query = self.db.collection(self.collection_name).where(
                filter=FieldFilter("enabled", "==", True)
            )
            
            if specialty:
                query = query.where(
                    filter=FieldFilter("specialty", "==", specialty.value)
                )
            
            # Only order by created_at if we're not already ordering by something else
            # Remove ordering for now to avoid missing index errors
            # query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
            query = query.limit(limit).offset(offset)
            
            profiles = []
            docs = list(query.stream())
            logger.info(f"Found {len(docs)} enabled directory profiles")
            
            for doc in docs:
                try:
                    profile = DirectoryProfile.from_dict(doc.to_dict(), doc.id)
                    profiles.append(profile)
                except Exception as e:
                    logger.error(f"Error parsing profile {doc.id}: {str(e)}", exc_info=True)
                    continue
            
            return profiles
            
        except Exception as e:
            logger.error(f"Error listing directory profiles: {e}")
            raise
    
    def search_by_location(
        self,
        lat: float,
        lng: float,
        radius_km: float = 50,
        specialty: Optional[MedicalSpecialty] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search profiles by location with distance calculation.
        
        Note: This performs client-side filtering for distance.
        For production, consider using geohashing or a spatial database.
        """
        try:
            # Get all enabled profiles
            query = self.db.collection(self.collection_name).where(
                filter=FieldFilter("enabled", "==", True)
            )
            
            if specialty:
                query = query.where(
                    filter=FieldFilter("specialty", "==", specialty.value)
                )
            
            # Calculate distances client-side
            profiles_with_distance = []
            
            for doc in query.stream():
                profile = DirectoryProfile.from_dict(doc.to_dict(), doc.id)
                
                if profile.location:
                    # Calculate distance using Haversine formula
                    distance = self._calculate_distance(
                        lat, lng,
                        profile.location.lat,
                        profile.location.lng
                    )
                    
                    if distance <= radius_km:
                        profiles_with_distance.append({
                            "profile": profile,
                            "distance": round(distance, 1)
                        })
            
            # Sort by distance
            profiles_with_distance.sort(key=lambda x: x["distance"])
            
            # Apply limit
            return profiles_with_distance[:limit]
            
        except Exception as e:
            logger.error(f"Error searching profiles by location: {e}")
            raise
    
    def update_rating(
        self,
        profile_id: str,
        new_rating: float,
        increment_count: bool = True
    ) -> bool:
        """Update profile rating."""
        try:
            doc_ref = self.db.collection(self.collection_name).document(profile_id)
            
            updates = {
                "rating": new_rating,
                "updated_at": datetime.now()
            }
            
            if increment_count:
                updates["reviews_count"] = firestore.Increment(1)
            
            doc_ref.update(updates)
            
            logger.info(f"Updated rating for profile {profile_id}: {new_rating}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating rating for profile {profile_id}: {e}")
            raise
    
    def get_specialties_with_count(self) -> Dict[str, int]:
        """Get count of enabled profiles by specialty."""
        try:
            query = self.db.collection(self.collection_name).where(
                filter=FieldFilter("enabled", "==", True)
            )
            
            specialty_counts = {}
            
            for doc in query.stream():
                data = doc.to_dict()
                specialty = data.get("specialty", "general")
                specialty_counts[specialty] = specialty_counts.get(specialty, 0) + 1
            
            return specialty_counts
            
        except Exception as e:
            logger.error(f"Error getting specialty counts: {e}")
            raise
    
    def _calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """Calculate distance between two coordinates in kilometers.
        
        Uses Haversine formula.
        """
        import math
        
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) *
            math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def bulk_update_from_accounts(self) -> int:
        """Migrate existing account directory data to directory profiles.
        
        This is a one-time migration utility.
        """
        try:
            # Get all accounts with directory enabled
            accounts_ref = self.db.collection("accounts")
            query = accounts_ref.where(
                filter=FieldFilter("directory_enabled", "==", True)
            )
            
            migrated_count = 0
            
            for doc in query.stream():
                account_data = doc.to_dict()
                account_id = doc.id
                
                # Check if profile already exists
                existing = self.get_by_account_id(account_id)
                if existing:
                    continue
                
                # Create profile from account data
                profile = DirectoryProfile(
                    account_id=account_id,
                    enabled=True,
                    doctor_name=account_data.get("doctor_name", ""),
                    phone=account_data.get("doctor_phone", ""),
                    email=account_data.get("doctor_email"),
                    consultation_price=account_data.get("appointment_price", 0) / 100,  # Convert cents to pesos
                    currency=account_data.get("currency", "MXN")
                )
                
                # Map specialty
                specialty_str = account_data.get("doctor_specialty", "general")
                try:
                    profile.specialty = MedicalSpecialty(specialty_str)
                except ValueError:
                    profile.specialty = MedicalSpecialty.GENERAL
                
                # Map other fields
                if account_data.get("doctor_photo_url"):
                    profile.photo_url = account_data["doctor_photo_url"]
                
                if account_data.get("doctor_about"):
                    profile.about = account_data["doctor_about"]
                
                if account_data.get("doctor_services"):
                    profile.services = account_data["doctor_services"]
                
                if account_data.get("doctor_languages"):
                    profile.languages = account_data["doctor_languages"]
                
                if account_data.get("doctor_insurance"):
                    profile.insurance_accepted = account_data["doctor_insurance"]
                
                if account_data.get("doctor_rating"):
                    profile.rating = account_data["doctor_rating"]
                
                if account_data.get("doctor_reviews_count"):
                    profile.reviews_count = account_data["doctor_reviews_count"]
                
                # Map location
                if account_data.get("location"):
                    loc_data = account_data["location"]
                    from app.models.directory_profile import Location
                    profile.location = Location(
                        lat=loc_data.get("lat", 0),
                        lng=loc_data.get("lng", 0),
                        address=account_data.get("doctor_address", ""),
                        city=account_data.get("doctor_city", ""),
                        state=account_data.get("doctor_state", ""),
                        zip_code=account_data.get("doctor_zip_code", "")
                    )
                
                # Create profile
                self.create(profile)
                migrated_count += 1
                
                logger.info(f"Migrated directory data for account {account_id}")
            
            logger.info(f"Migrated {migrated_count} accounts to directory profiles")
            return migrated_count
            
        except Exception as e:
            logger.error(f"Error during bulk migration: {e}")
            raise