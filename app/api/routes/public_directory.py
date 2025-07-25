"""
Public directory routes that don't require authentication.
"""
from flask import Blueprint, request, jsonify
from app.services.geocoding_service import GeocodingService
from app.core.logging import get_logger

logger = get_logger(__name__)

bp = Blueprint("public_directory", __name__, url_prefix="/api/public/directory")

geocoding_service = GeocodingService()

@bp.route("/geocode", methods=["POST"])
def geocode_address():
    """
    Public endpoint to geocode an address to coordinates.
    """
    try:
        data = request.get_json()
        
        if not data or not data.get("query"):
            return jsonify({
                "success": False,
                "error": "Query parameter is required"
            }), 400
        
        query = data["query"]
        
        # Try to parse as coordinates first (lat, lng format)
        if "," in query:
            parts = query.split(",")
            if len(parts) == 2:
                try:
                    lat = float(parts[0].strip())
                    lng = float(parts[1].strip())
                    if -90 <= lat <= 90 and -180 <= lng <= 180:
                        return jsonify({
                            "success": True,
                            "data": {
                                "lat": lat,
                                "lng": lng,
                                "display_name": f"{lat:.6f}, {lng:.6f}"
                            }
                        })
                except ValueError:
                    pass
        
        # Search for the address
        results = geocoding_service.search_address(query)
        
        if not results:
            return jsonify({
                "success": False,
                "error": "No results found for the given query"
            }), 404
        
        # Format results for frontend
        formatted_results = []
        for result in results[:5]:  # Limit to 5 results
            formatted_results.append({
                "lat": float(result.get("lat", 0)),
                "lng": float(result.get("lon", 0)),
                "display_name": result.get("display_name", ""),
                "address": {
                    "city": result.get("city") or result.get("town") or result.get("village", ""),
                    "state": result.get("state", ""),
                    "country": result.get("country", ""),
                    "postcode": result.get("postcode", "")
                }
            })
        
        return jsonify({
            "success": True,
            "data": formatted_results
        })
        
    except Exception as e:
        logger.error(f"Geocoding error: {str(e)}")
        return jsonify({
            "success": False,
            "error": "An error occurred while geocoding"
        }), 500

@bp.route("/autocomplete", methods=["GET"])
def autocomplete_address():
    """
    Public endpoint for address autocomplete suggestions.
    """
    try:
        query = request.args.get("q", "").strip()
        
        if not query or len(query) < 3:
            return jsonify({
                "success": True,
                "data": []
            })
        
        # Search for addresses with limit
        results = geocoding_service.search_address(query, limit=5)
        
        # Format suggestions
        suggestions = []
        for result in results:
            suggestions.append({
                "value": result.get("display_name", ""),
                "lat": float(result.get("lat", 0)),
                "lng": float(result.get("lon", 0)),
                "city": result.get("city") or result.get("town") or result.get("village", ""),
                "state": result.get("state", ""),
                "country": result.get("country", "")
            })
        
        return jsonify({
            "success": True,
            "data": suggestions
        })
        
    except Exception as e:
        logger.error(f"Autocomplete error: {str(e)}")
        return jsonify({
            "success": True,
            "data": []
        })