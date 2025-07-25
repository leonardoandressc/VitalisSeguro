"""Geocoding service for converting addresses to coordinates."""
import requests
from typing import Optional, Tuple
from app.core.logging import get_logger
import time

logger = get_logger(__name__)


class GeocodingService:
    """Service for geocoding addresses using OpenStreetMap Nominatim API."""
    
    BASE_URL = "https://nominatim.openstreetmap.org/search"
    USER_AGENT = "VitalisConnect/1.0"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT
        })
    
    def geocode_address(self, address: str, city: str, state: str, 
                       zip_code: str, country: str = "Mexico") -> Optional[Tuple[float, float]]:
        """
        Geocode an address to latitude and longitude coordinates.
        
        Args:
            address: Street address
            city: City name
            state: State name
            zip_code: Postal code
            country: Country name (default: Mexico)
            
        Returns:
            Tuple of (latitude, longitude) or None if geocoding fails
        """
        try:
            # Build the full address string
            address_parts = []
            if address:
                address_parts.append(address)
            if city:
                address_parts.append(city)
            if state:
                address_parts.append(state)
            if zip_code:
                address_parts.append(zip_code)
            if country:
                address_parts.append(country)
            
            if not address_parts:
                logger.warning("No address components provided for geocoding")
                return None
            
            full_address = ", ".join(address_parts)
            
            # Prepare request parameters
            params = {
                "q": full_address,
                "format": "json",
                "limit": 1,
                "countrycodes": "mx"  # Limit to Mexico
            }
            
            # Rate limiting - Nominatim requires max 1 request per second
            time.sleep(1)
            
            # Make the request
            response = self.session.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            
            results = response.json()
            
            if not results:
                logger.warning(f"No geocoding results found for address: {full_address}")
                return None
            
            # Extract coordinates from the first result
            result = results[0]
            lat = float(result.get("lat"))
            lng = float(result.get("lon"))
            
            logger.info(f"Successfully geocoded address: {full_address} -> ({lat}, {lng})")
            return (lat, lng)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error during geocoding: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing geocoding response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during geocoding: {e}")
            return None
    
    def search_address(self, query: str, limit: int = 10) -> list:
        """
        Search for addresses matching a query.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List of matching addresses with coordinates
        """
        try:
            params = {
                "q": query,
                "format": "json",
                "limit": limit,
                "addressdetails": 1,
                "countrycodes": "mx"  # Limit to Mexico
            }
            
            # Rate limiting
            time.sleep(1)
            
            response = self.session.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            
            results = response.json()
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching addresses: {e}")
            return []
    
    def reverse_geocode(self, lat: float, lng: float) -> Optional[dict]:
        """
        Reverse geocode coordinates to an address.
        
        Args:
            lat: Latitude
            lng: Longitude
            
        Returns:
            Dictionary with address components or None if reverse geocoding fails
        """
        try:
            params = {
                "lat": lat,
                "lon": lng,
                "format": "json"
            }
            
            # Rate limiting
            time.sleep(1)
            
            response = self.session.get(
                "https://nominatim.openstreetmap.org/reverse",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            result = response.json()
            
            if "error" in result:
                logger.warning(f"Reverse geocoding error: {result.get('error')}")
                return None
            
            address = result.get("address", {})
            
            return {
                "address": address.get("road", ""),
                "city": address.get("city") or address.get("town") or address.get("village", ""),
                "state": address.get("state", ""),
                "zip_code": address.get("postcode", ""),
                "country": address.get("country", "")
            }
            
        except Exception as e:
            logger.error(f"Error during reverse geocoding: {e}")
            return None