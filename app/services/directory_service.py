"""Service layer for directory profile management."""
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import uuid
try:
    from firebase_admin import storage
except ImportError:
    storage = None

from app.models.directory_profile import DirectoryProfile, MedicalSpecialty
from app.repositories.directory_repository import DirectoryRepository
from app.repositories.account_repository import AccountRepository
from app.core.logging import get_logger
from app.core.exceptions import ValidationError, ResourceNotFoundError

logger = get_logger(__name__)


class DirectoryService:
    """Service for managing directory profiles."""
    
    def __init__(self):
        """Initialize directory service."""
        self.directory_repo = DirectoryRepository()
        self.account_repo = AccountRepository()
        self.storage_bucket = storage.bucket() if storage and hasattr(storage, '_apps') and storage._apps else None
    
    def create_or_update_profile(
        self,
        account_id: str,
        profile_data: Dict[str, Any]
    ) -> DirectoryProfile:
        """Create or update directory profile for an account."""
        try:
            # Verify account exists
            account = self.account_repo.get(account_id)
            if not account:
                raise ResourceNotFoundError("Account", account_id)
            
            # Check if profile already exists
            existing_profile = self.directory_repo.get_by_account_id(account_id)
            
            if existing_profile:
                # Update existing profile
                for key, value in profile_data.items():
                    if hasattr(existing_profile, key) and value is not None:
                        setattr(existing_profile, key, value)
                
                return self.directory_repo.update(existing_profile)
            else:
                # Create new profile
                profile = DirectoryProfile(
                    account_id=account_id,
                    **profile_data
                )
                return self.directory_repo.create(profile)
                
        except Exception as e:
            logger.error(f"Error creating/updating profile for account {account_id}: {e}")
            raise
    
    def get_profile_by_account(self, account_id: str) -> Optional[DirectoryProfile]:
        """Get directory profile by account ID."""
        try:
            return self.directory_repo.get_by_account_id(account_id)
        except Exception as e:
            logger.error(f"Error getting profile for account {account_id}: {e}")
            raise
    
    def update_profile_photo(
        self,
        account_id: str,
        photo_data: bytes,
        content_type: str = "image/jpeg"
    ) -> str:
        """Upload photo to Firebase Storage and update profile."""
        try:
            if not self.storage_bucket:
                raise ValidationError("Storage bucket not configured")
            
            # Get or create profile
            profile = self.directory_repo.get_by_account_id(account_id)
            if not profile:
                profile = DirectoryProfile(account_id=account_id)
                profile = self.directory_repo.create(profile)
            
            # Generate unique filename
            file_extension = content_type.split("/")[-1]
            filename = f"directory/{account_id}/{uuid.uuid4()}.{file_extension}"
            
            # Delete old photo if exists
            if profile.photo_url:
                try:
                    old_path = profile.photo_url.split("/o/")[-1].split("?")[0]
                    old_blob = self.storage_bucket.blob(old_path)
                    old_blob.delete()
                except Exception as e:
                    logger.warning(f"Failed to delete old photo: {e}")
            
            # Upload new photo
            blob = self.storage_bucket.blob(filename)
            blob.upload_from_string(photo_data, content_type=content_type)
            
            # Make publicly accessible
            blob.make_public()
            
            # Update profile with new photo URL
            profile.photo_url = blob.public_url
            self.directory_repo.update(profile)
            
            logger.info(f"Updated photo for account {account_id}: {profile.photo_url}")
            return profile.photo_url
            
        except Exception as e:
            logger.error(f"Error updating photo for account {account_id}: {e}")
            raise
    
    def toggle_directory_status(
        self,
        account_id: str,
        enabled: bool
    ) -> DirectoryProfile:
        """Enable or disable directory listing for an account."""
        try:
            profile = self.directory_repo.get_by_account_id(account_id)
            
            if not profile:
                # Create new profile if doesn't exist
                profile = DirectoryProfile(
                    account_id=account_id,
                    enabled=enabled
                )
                return self.directory_repo.create(profile)
            
            profile.enabled = enabled
            return self.directory_repo.update(profile)
            
        except Exception as e:
            logger.error(f"Error toggling directory status for account {account_id}: {e}")
            raise
    
    def search_doctors(
        self,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        specialty: Optional[str] = None,
        radius_km: float = 50,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Search for doctors with filters."""
        try:
            offset = (page - 1) * limit
            
            # Parse specialty
            specialty_enum = None
            if specialty:
                try:
                    specialty_enum = MedicalSpecialty(specialty)
                except ValueError:
                    logger.warning(f"Invalid specialty: {specialty}")
            
            # Search with location if provided
            if lat and lng:
                results = self.directory_repo.search_by_location(
                    lat=lat,
                    lng=lng,
                    radius_km=radius_km,
                    specialty=specialty_enum,
                    limit=limit + offset  # Get extra for pagination
                )
                
                # Apply pagination
                paginated_results = results[offset:offset + limit]
                
                # Format response
                doctors = []
                for result in paginated_results:
                    profile = result["profile"]
                    doctor_data = self._format_doctor_response(profile)
                    doctor_data["distance"] = result["distance"]
                    doctors.append(doctor_data)
                
                total = len(results)
            else:
                # Search without location
                profiles = self.directory_repo.list_enabled(
                    specialty=specialty_enum,
                    limit=limit,
                    offset=offset
                )
                
                doctors = [
                    self._format_doctor_response(profile)
                    for profile in profiles
                ]
                
                # Get total count
                all_profiles = self.directory_repo.list_enabled(
                    specialty=specialty_enum,
                    limit=1000  # Reasonable max
                )
                total = len(all_profiles)
            
            return {
                "success": True,
                "data": doctors,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "total_pages": (total + limit - 1) // limit
                }
            }
            
        except Exception as e:
            logger.error(f"Error searching doctors: {e}")
            raise
    
    def get_doctor_details(self, profile_id: str) -> Dict[str, Any]:
        """Get detailed doctor information."""
        try:
            profile = self.directory_repo.get_by_id(profile_id)
            
            if not profile or not profile.enabled:
                raise ResourceNotFoundError("Doctor", profile_id)
            
            # Get account for additional info
            account = self.account_repo.get(profile.account_id)
            
            doctor_data = self._format_doctor_response(profile)
            
            # Add additional details
            doctor_data.update({
                "about": profile.about,
                "education": profile.education,
                "experience_years": profile.years_experience,
                "languages": profile.languages,
                "insurance_accepted": profile.insurance_accepted,
                "schedule": profile.schedule,
                "certifications": profile.certifications,
                "license_number": profile.license_number,
                "ghl_calendar_id": account.calendar_id if account else None
            })
            
            return doctor_data
            
        except Exception as e:
            logger.error(f"Error getting doctor details {profile_id}: {e}")
            raise
    
    def get_specialties_list(self) -> List[Dict[str, Any]]:
        """Get list of specialties with doctor counts."""
        try:
            counts = self.directory_repo.get_specialties_with_count()
            
            specialties = []
            for specialty in MedicalSpecialty:
                count = counts.get(specialty.value, 0)
                if count > 0:
                    specialties.append({
                        "id": specialty.value,
                        "name": specialty.value,
                        "display_name": self._get_specialty_display_name(specialty),
                        "doctor_count": count
                    })
            
            # Sort by count
            specialties.sort(key=lambda x: x["doctor_count"], reverse=True)
            
            return specialties
            
        except Exception as e:
            logger.error(f"Error getting specialties: {e}")
            raise
    
    def migrate_from_accounts(self) -> int:
        """Migrate existing account directory data."""
        try:
            return self.directory_repo.bulk_update_from_accounts()
        except Exception as e:
            logger.error(f"Error during migration: {e}")
            raise
    
    def _format_doctor_response(self, profile: DirectoryProfile) -> Dict[str, Any]:
        """Format directory profile for API response."""
        try:
            # Handle location safely
            location_data = {
                "address": "",
                "city": "",
                "state": "",
                "zip_code": "",
                "lat": None,
                "lng": None
            }
            
            if hasattr(profile, 'location') and profile.location:
                location_data.update({
                    "address": getattr(profile.location, 'address', ''),
                    "city": getattr(profile.location, 'city', ''),
                    "state": getattr(profile.location, 'state', ''),
                    "zip_code": getattr(profile.location, 'zip_code', ''),
                    "lat": getattr(profile.location, 'lat', None),
                    "lng": getattr(profile.location, 'lng', None)
                })
            
            return {
                "id": getattr(profile, 'id', None),
                "name": getattr(profile, 'doctor_name', ''),
                "specialty": getattr(profile.specialty, 'value', 'general') if hasattr(profile, 'specialty') else 'general',
                "specialty_display": profile.get_display_specialty() if hasattr(profile, 'get_display_specialty') else 'Medicina General',
                "photo_url": getattr(profile, 'photo_url', None),
                "rating": getattr(profile, 'rating', 0.0),
                "reviews_count": getattr(profile, 'reviews_count', 0),
                "location": location_data,
                "contact": {
                    "phone": getattr(profile, 'phone', ''),
                    "email": getattr(profile, 'email', ''),
                    "website": getattr(profile, 'website', None)
                },
                "services": getattr(profile, 'services', []),
                "consultation_price": getattr(profile, 'consultation_price', 0.0),
                "currency": getattr(profile, 'currency', 'MXN'),
                "is_active": getattr(profile, 'enabled', False)
            }
        except Exception as e:
            logger.error(f"Error formatting doctor response: {str(e)}", exc_info=True)
            raise
    
    def _get_specialty_display_name(self, specialty: MedicalSpecialty) -> str:
        """Get display name for specialty."""
        display_names = {
            MedicalSpecialty.GENERAL: "Medicina General",
            MedicalSpecialty.PEDIATRICS: "Pediatría",
            MedicalSpecialty.CARDIOLOGY: "Cardiología",
            MedicalSpecialty.DERMATOLOGY: "Dermatología",
            MedicalSpecialty.GYNECOLOGY: "Ginecología",
            MedicalSpecialty.ORTHOPEDICS: "Ortopedia",
            MedicalSpecialty.PSYCHIATRY: "Psiquiatría",
            MedicalSpecialty.OPHTHALMOLOGY: "Oftalmología",
            MedicalSpecialty.DENTISTRY: "Odontología",
            MedicalSpecialty.NUTRITION: "Nutrición",
            MedicalSpecialty.PSYCHOLOGY: "Psicología",
            MedicalSpecialty.NEUROLOGY: "Neurología",
            MedicalSpecialty.ENDOCRINOLOGY: "Endocrinología",
            MedicalSpecialty.GASTROENTEROLOGY: "Gastroenterología",
            MedicalSpecialty.ONCOLOGY: "Oncología",
            MedicalSpecialty.RHEUMATOLOGY: "Reumatología",
            MedicalSpecialty.UROLOGY: "Urología",
            MedicalSpecialty.OTHER: "Otra Especialidad"
        }
        return display_names.get(specialty, specialty.value)