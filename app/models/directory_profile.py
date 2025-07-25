"""Directory profile model for doctor listings."""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class MedicalSpecialty(str, Enum):
    """Medical specialty types."""
    GENERAL = "general"
    PEDIATRICS = "pediatrics"
    CARDIOLOGY = "cardiology"
    DERMATOLOGY = "dermatology"
    GYNECOLOGY = "gynecology"
    ORTHOPEDICS = "orthopedics"
    PSYCHIATRY = "psychiatry"
    OPHTHALMOLOGY = "ophthalmology"
    DENTISTRY = "dentistry"
    NUTRITION = "nutrition"
    PSYCHOLOGY = "psychology"
    NEUROLOGY = "neurology"
    ENDOCRINOLOGY = "endocrinology"
    GASTROENTEROLOGY = "gastroenterology"
    ONCOLOGY = "oncology"
    RHEUMATOLOGY = "rheumatology"
    UROLOGY = "urology"
    OTHER = "other"


@dataclass
class Location:
    """Location information."""
    lat: float
    lng: float
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country: str = "Mexico"


@dataclass
class DirectoryProfile:
    """Directory profile for medical professionals."""
    id: Optional[str] = None
    account_id: str = ""
    enabled: bool = False
    
    # Basic Information
    doctor_name: str = ""
    specialty: MedicalSpecialty = MedicalSpecialty.GENERAL
    photo_url: Optional[str] = None
    license_number: Optional[str] = None
    
    # Professional Details
    years_experience: int = 0
    education: List[str] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=lambda: ["Español"])
    about: str = ""
    
    # Services & Pricing
    services: List[str] = field(default_factory=list)
    consultation_price: float = 0.0
    currency: str = "MXN"
    insurance_accepted: List[str] = field(default_factory=list)
    
    # Contact Information
    phone: str = ""
    email: Optional[str] = None
    website: Optional[str] = None
    
    # Location
    location: Optional[Location] = None
    
    # Schedule (day -> hours)
    schedule: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    # Ratings & Reviews
    rating: float = 0.0
    reviews_count: int = 0
    
    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Firestore."""
        data = {
            "account_id": self.account_id,
            "enabled": self.enabled,
            "doctor_name": self.doctor_name,
            "specialty": self.specialty.value,
            "photo_url": self.photo_url,
            "license_number": self.license_number,
            "years_experience": self.years_experience,
            "education": self.education,
            "certifications": self.certifications,
            "languages": self.languages,
            "about": self.about,
            "services": self.services,
            "consultation_price": self.consultation_price,
            "currency": self.currency,
            "insurance_accepted": self.insurance_accepted,
            "phone": self.phone,
            "email": self.email,
            "website": self.website,
            "schedule": self.schedule,
            "rating": self.rating,
            "reviews_count": self.reviews_count
        }
        
        if self.location:
            data["location"] = {
                "lat": self.location.lat,
                "lng": self.location.lng,
                "address": self.location.address,
                "city": self.location.city,
                "state": self.location.state,
                "zip_code": self.location.zip_code,
                "country": self.location.country
            }
        
        if self.created_at:
            data["created_at"] = self.created_at
        if self.updated_at:
            data["updated_at"] = self.updated_at
            
        # Remove None values
        return {k: v for k, v in data.items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> "DirectoryProfile":
        """Create from dictionary."""
        profile = cls(
            id=doc_id,
            account_id=data.get("account_id", ""),
            enabled=data.get("enabled", False),
            doctor_name=data.get("doctor_name", ""),
            specialty=MedicalSpecialty(data.get("specialty", "general")),
            photo_url=data.get("photo_url"),
            license_number=data.get("license_number"),
            years_experience=data.get("years_experience", 0),
            education=data.get("education", []),
            certifications=data.get("certifications", []),
            languages=data.get("languages", ["Español"]),
            about=data.get("about", ""),
            services=data.get("services", []),
            consultation_price=data.get("consultation_price", 0.0),
            currency=data.get("currency", "MXN"),
            insurance_accepted=data.get("insurance_accepted", []),
            phone=data.get("phone", ""),
            email=data.get("email"),
            website=data.get("website"),
            schedule=data.get("schedule", {}),
            rating=data.get("rating", 0.0),
            reviews_count=data.get("reviews_count", 0),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at")
        )
        
        # Handle location
        if "location" in data and data["location"]:
            loc_data = data["location"]
            profile.location = Location(
                lat=loc_data.get("lat", 0),
                lng=loc_data.get("lng", 0),
                address=loc_data.get("address", ""),
                city=loc_data.get("city", ""),
                state=loc_data.get("state", ""),
                zip_code=loc_data.get("zip_code", ""),
                country=loc_data.get("country", "Mexico")
            )
        
        return profile
    
    def get_display_specialty(self) -> str:
        """Get human-readable specialty name."""
        specialty_names = {
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
        return specialty_names.get(self.specialty, self.specialty.value)