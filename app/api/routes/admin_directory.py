"""Admin directory management routes."""
from flask import Blueprint, request, jsonify
from app.api.middleware.auth import require_api_key, handle_auth_errors
from app.api.middleware.rate_limit import rate_limit
from app.core.logging import get_logger
from app.services.directory_service import DirectoryService
from app.services.geocoding_service import GeocodingService
from app.models.directory_profile import MedicalSpecialty, Location

logger = get_logger(__name__)

bp = Blueprint("admin_directory", __name__)


@bp.route("/accounts/<account_id>/directory", methods=["GET"])
@require_api_key
@rate_limit()
@handle_auth_errors
def get_directory_profile(account_id: str):
    """Get directory profile for an account."""
    try:
        directory_service = DirectoryService()
        profile = directory_service.get_profile_by_account(account_id)
        
        if not profile:
            # Return empty profile structure
            return jsonify({
                "success": True,
                "data": {
                    "enabled": False,
                    "doctor_name": "",
                    "specialty": "general",
                    "photo_url": None,
                    "license_number": "",
                    "years_experience": 0,
                    "education": [],
                    "certifications": [],
                    "languages": ["Español"],
                    "about": "",
                    "services": [],
                    "consultation_price": 500.0,
                    "currency": "MXN",
                    "insurance_accepted": [],
                    "phone": "",
                    "email": "",
                    "website": "",
                    "location": {
                        "address": "",
                        "city": "",
                        "state": "",
                        "zip_code": "",
                        "lat": None,
                        "lng": None
                    },
                    "schedule": {}
                }
            }), 200
        
        # Format response
        data = {
            "enabled": profile.enabled,
            "doctor_name": profile.doctor_name,
            "specialty": profile.specialty.value,
            "photo_url": profile.photo_url,
            "license_number": profile.license_number,
            "years_experience": profile.years_experience,
            "education": profile.education,
            "certifications": profile.certifications,
            "languages": profile.languages,
            "about": profile.about,
            "services": profile.services,
            "consultation_price": profile.consultation_price,
            "currency": profile.currency,
            "insurance_accepted": profile.insurance_accepted,
            "phone": profile.phone,
            "email": profile.email,
            "website": profile.website,
            "location": {
                "address": profile.location.address if profile.location else "",
                "city": profile.location.city if profile.location else "",
                "state": profile.location.state if profile.location else "",
                "zip_code": profile.location.zip_code if profile.location else "",
                "lat": profile.location.lat if profile.location else None,
                "lng": profile.location.lng if profile.location else None
            } if profile.location else None,
            "schedule": profile.schedule,
            "rating": profile.rating,
            "reviews_count": profile.reviews_count
        }
        
        return jsonify({
            "success": True,
            "data": data
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get directory profile: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/accounts/<account_id>/directory", methods=["PUT"])
@require_api_key
@rate_limit()
@handle_auth_errors
def update_directory_profile(account_id: str):
    """Update directory profile for an account."""
    try:
        directory_service = DirectoryService()
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body required"
            }), 400
        
        # Parse specialty if provided
        if "specialty" in data:
            try:
                data["specialty"] = MedicalSpecialty(data["specialty"])
            except ValueError:
                return jsonify({
                    "success": False,
                    "error": f"Invalid specialty: {data['specialty']}"
                }), 400
        
        # Parse location if provided
        if "location" in data and data["location"]:
            loc_data = data["location"]
            
            # Get address components
            address = loc_data.get("address", "")
            city = loc_data.get("city", "")
            state = loc_data.get("state", "")
            zip_code = loc_data.get("zip_code", "")
            country = loc_data.get("country", "Mexico")
            
            # Check if we need to geocode
            lat = loc_data.get("lat")
            lng = loc_data.get("lng")
            
            # If coordinates are not provided or are 0, try to geocode
            if (not lat or not lng or lat == 0 or lng == 0) and (address or city):
                geocoding_service = GeocodingService()
                coordinates = geocoding_service.geocode_address(
                    address=address,
                    city=city,
                    state=state,
                    zip_code=zip_code,
                    country=country
                )
                
                if coordinates:
                    lat, lng = coordinates
                    logger.info(f"Geocoded address for account {account_id}: ({lat}, {lng})")
                else:
                    logger.warning(f"Failed to geocode address for account {account_id}")
                    lat = None
                    lng = None
            
            data["location"] = Location(
                lat=lat,
                lng=lng,
                address=address,
                city=city,
                state=state,
                zip_code=zip_code,
                country=country
            )
        
        # Update or create profile
        profile = directory_service.create_or_update_profile(account_id, data)
        
        logger.info(f"Updated directory profile for account: {account_id}")
        
        return jsonify({
            "success": True,
            "message": "Directory profile updated successfully",
            "data": {
                "id": profile.id,
                "enabled": profile.enabled
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to update directory profile: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/accounts/<account_id>/directory/photo", methods=["POST"])
@require_api_key
@rate_limit()
@handle_auth_errors
def upload_directory_photo(account_id: str):
    """Upload photo for directory profile."""
    try:
        directory_service = DirectoryService()
        
        # Check if file was uploaded
        if "photo" not in request.files:
            return jsonify({
                "success": False,
                "error": "No photo file provided"
            }), 400
        
        file = request.files["photo"]
        
        if file.filename == "":
            return jsonify({
                "success": False,
                "error": "No file selected"
            }), 400
        
        # Validate file type
        allowed_types = {"image/jpeg", "image/png", "image/webp"}
        if file.content_type not in allowed_types:
            return jsonify({
                "success": False,
                "error": f"Invalid file type. Allowed: {', '.join(allowed_types)}"
            }), 400
        
        # Validate file size (max 5MB)
        file_data = file.read()
        if len(file_data) > 5 * 1024 * 1024:
            return jsonify({
                "success": False,
                "error": "File too large. Maximum size is 5MB"
            }), 400
        
        # Upload photo
        photo_url = directory_service.update_profile_photo(
            account_id=account_id,
            photo_data=file_data,
            content_type=file.content_type
        )
        
        logger.info(f"Uploaded photo for account {account_id}")
        
        return jsonify({
            "success": True,
            "message": "Photo uploaded successfully",
            "data": {
                "photo_url": photo_url
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to upload photo: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/accounts/<account_id>/directory/geocode", methods=["POST"])
@require_api_key
@rate_limit()
@handle_auth_errors
def geocode_address(account_id: str):
    """Geocode an address without saving the profile."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body required"
            }), 400
        
        address = data.get("address", "")
        city = data.get("city", "")
        state = data.get("state", "")
        zip_code = data.get("zip_code", "")
        
        if not any([address, city, state]):
            return jsonify({
                "success": False,
                "error": "At least one address component required"
            }), 400
        
        geocoding_service = GeocodingService()
        coordinates = geocoding_service.geocode_address(
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            country="Mexico"
        )
        
        if coordinates:
            lat, lng = coordinates
            logger.info(f"Geocoded address for account {account_id}: ({lat}, {lng})")
            
            return jsonify({
                "success": True,
                "data": {
                    "lat": lat,
                    "lng": lng
                }
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": "Could not geocode the provided address"
            }), 404
        
    except Exception as e:
        logger.error(f"Failed to geocode address: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/accounts/<account_id>/directory/toggle", methods=["POST"])
@require_api_key
@rate_limit()
@handle_auth_errors
def toggle_directory(account_id: str):
    """Toggle directory listing on/off."""
    try:
        directory_service = DirectoryService()
        data = request.get_json()
        
        enabled = data.get("enabled", False) if data else False
        
        profile = directory_service.toggle_directory_status(account_id, enabled)
        
        logger.info(f"Toggled directory for account {account_id}: {enabled}")
        
        return jsonify({
            "success": True,
            "message": f"Directory {'enabled' if enabled else 'disabled'} successfully",
            "data": {
                "enabled": profile.enabled
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to toggle directory: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/directory/specialties", methods=["GET"])
@require_api_key
@rate_limit()
@handle_auth_errors
def get_specialties_options():
    """Get list of available medical specialties."""
    try:
        # Return all specialty options for the dropdown
        specialties = []
        for specialty in MedicalSpecialty:
            display_name = {
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
            }.get(specialty, specialty.value)
            
            specialties.append({
                "value": specialty.value,
                "label": display_name
            })
        
        return jsonify({
            "success": True,
            "data": specialties
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get specialties: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route("/directory/migrate", methods=["POST"])
@require_api_key
@rate_limit()
@handle_auth_errors
def migrate_directory_data():
    """Migrate existing account directory data to new collection.
    
    This is a one-time migration endpoint.
    """
    try:
        directory_service = DirectoryService()
        count = directory_service.migrate_from_accounts()
        
        logger.info(f"Migrated {count} accounts to directory profiles")
        
        return jsonify({
            "success": True,
            "message": f"Successfully migrated {count} accounts",
            "data": {
                "migrated_count": count
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to migrate directory data: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500