"""API endpoints for pricing tier management."""
from flask import Blueprint, request, jsonify
from app.services.subscription_service import SubscriptionService
from app.repositories.product_repository import PricingTierRepository
from app.models.product import PricingTier
from app.core.exceptions import VitalisException, ResourceNotFoundError, ValidationError
from app.core.logging import get_logger
from app.api.middleware.auth import require_api_key
import uuid

logger = get_logger(__name__)
pricing_bp = Blueprint("pricing", __name__, url_prefix="/api/pricing-tiers")


@pricing_bp.route("", methods=["GET"])
@require_api_key
def list_pricing_tiers():
    """List all pricing tiers."""
    try:
        tier_repo = PricingTierRepository()
        tiers = tier_repo.list_all()
        
        return jsonify({
            "tiers": [tier.to_dict() for tier in tiers],
            "count": len(tiers)
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing pricing tiers: {e}")
        return jsonify({"error": "Failed to list pricing tiers"}), 500


@pricing_bp.route("", methods=["POST"])
@require_api_key
def create_pricing_tier():
    """Create a new pricing tier."""
    logger.info("POST /api/pricing-tiers endpoint hit")
    
    try:
        # Check content type
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Request data exists: {request.data}")
        
        # Try to get JSON data
        data = request.get_json()
        
        if data is None:
            logger.error("No JSON data in request body")
            return jsonify({"error": "No JSON data provided"}), 400
            
        logger.info(f"Received pricing tier data: {data}")
        
        # Validate required fields
        required_fields = ["name", "description", "monthly_price", "annual_price"]
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Create pricing tier
        tier = PricingTier(
            id=str(uuid.uuid4()),
            name=data["name"],
            description=data["description"],
            monthly_price=data["monthly_price"],
            annual_price=data["annual_price"],
            products=data.get("products", []),
            features=data.get("features", []),
            is_popular=data.get("is_popular", False),
            sort_order=data.get("sort_order", 0),
            stripe_monthly_price_id=data.get("stripe_monthly_price_id"),
            stripe_annual_price_id=data.get("stripe_annual_price_id"),
            trial_days=data.get("trial_days", 0),
            max_appointments_per_month=data.get("max_appointments_per_month"),
            metadata=data.get("metadata", {})
        )
        
        # Save to repository
        tier_repo = PricingTierRepository()
        saved_tier = tier_repo.create(tier)
        
        logger.info(
            "Created pricing tier",
            extra={
                "tier_id": saved_tier.id,
                "tier_name": saved_tier.name,
                "monthly_price": saved_tier.monthly_price
            }
        )
        
        return jsonify(saved_tier.to_dict()), 201
        
    except ValidationError as e:
        logger.error(f"Validation error creating pricing tier: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating pricing tier: {e}", exc_info=True)
        return jsonify({"error": f"Failed to create pricing tier: {str(e)}"}), 500


@pricing_bp.route("/<tier_id>", methods=["GET"])
@require_api_key
def get_pricing_tier(tier_id):
    """Get a specific pricing tier."""
    try:
        tier_repo = PricingTierRepository()
        tier = tier_repo.get(tier_id)
        
        if not tier:
            return jsonify({"error": "Pricing tier not found"}), 404
            
        return jsonify(tier.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Error getting pricing tier: {e}")
        return jsonify({"error": "Failed to get pricing tier"}), 500


@pricing_bp.route("/<tier_id>", methods=["PUT"])
@require_api_key
def update_pricing_tier(tier_id):
    """Update a pricing tier."""
    try:
        data = request.get_json()
        
        # Get existing tier
        tier_repo = PricingTierRepository()
        tier = tier_repo.get(tier_id)
        
        if not tier:
            return jsonify({"error": "Pricing tier not found"}), 404
        
        # Update fields
        if "name" in data:
            tier.name = data["name"]
        if "description" in data:
            tier.description = data["description"]
        if "monthly_price" in data:
            tier.monthly_price = data["monthly_price"]
        if "annual_price" in data:
            tier.annual_price = data["annual_price"]
        if "products" in data:
            tier.products = data["products"]
        if "features" in data:
            tier.features = data["features"]
        if "is_popular" in data:
            tier.is_popular = data["is_popular"]
        if "sort_order" in data:
            tier.sort_order = data["sort_order"]
        if "stripe_monthly_price_id" in data:
            tier.stripe_monthly_price_id = data["stripe_monthly_price_id"]
        if "stripe_annual_price_id" in data:
            tier.stripe_annual_price_id = data["stripe_annual_price_id"]
        if "trial_days" in data:
            tier.trial_days = data["trial_days"]
        if "max_appointments_per_month" in data:
            tier.max_appointments_per_month = data["max_appointments_per_month"]
        if "metadata" in data:
            tier.metadata = data["metadata"]
        
        # Save updates
        updated_tier = tier_repo.update(tier)
        
        logger.info(
            "Updated pricing tier",
            extra={"tier_id": tier_id}
        )
        
        return jsonify(updated_tier.to_dict()), 200
        
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error updating pricing tier: {e}")
        return jsonify({"error": "Failed to update pricing tier"}), 500


@pricing_bp.route("/<tier_id>", methods=["DELETE"])
@require_api_key
def delete_pricing_tier(tier_id):
    """Delete a pricing tier."""
    try:
        # Check if tier exists
        tier_repo = PricingTierRepository()
        tier = tier_repo.get(tier_id)
        
        if not tier:
            return jsonify({"error": "Pricing tier not found"}), 404
        
        # Check if tier is in use
        subscription_service = SubscriptionService()
        if subscription_service.is_tier_in_use(tier_id):
            return jsonify({
                "error": "Cannot delete pricing tier that is in use by active subscriptions"
            }), 400
        
        # Delete tier
        success = tier_repo.delete(tier_id)
        
        if success:
            logger.info(
                "Deleted pricing tier",
                extra={"tier_id": tier_id}
            )
            return jsonify({"success": True, "message": "Pricing tier deleted"}), 200
        else:
            return jsonify({"error": "Failed to delete pricing tier"}), 500
            
    except Exception as e:
        logger.error(f"Error deleting pricing tier: {e}")
        return jsonify({"error": "Failed to delete pricing tier"}), 500