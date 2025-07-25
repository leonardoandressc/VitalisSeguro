"""API endpoints for product and pricing tier management."""
from flask import Blueprint, request, jsonify
from app.services.subscription_service import SubscriptionService
from app.repositories.product_repository import ProductRepository
from app.models.product import Product, ProductStatus
from app.core.exceptions import VitalisException, ResourceNotFoundError
from app.core.logging import get_logger
from app.api.middleware.auth import require_api_key
import uuid

logger = get_logger(__name__)
products_bp = Blueprint("products", __name__)


@products_bp.route("/api/products", methods=["GET"])
@require_api_key
def list_products():
    """List all products."""
    try:
        product_repo = ProductRepository()
        products = product_repo.list_all()
        
        return jsonify({
            "products": [p.to_dict() for p in products]
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing products: {e}")
        return jsonify({"error": "Failed to list products"}), 500


@products_bp.route("/api/products", methods=["POST"])
@require_api_key
def create_product():
    """Create a new product."""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get("id") or not data.get("name"):
            return jsonify({"error": "Missing required fields: id and name"}), 400
        
        # Create product
        product = Product(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            status=ProductStatus(data.get("status", ProductStatus.ACTIVE.value)),
            features=data.get("features", [])
        )
        
        product_repo = ProductRepository()
        created = product_repo.create(product)
        
        logger.info(
            "Created product",
            extra={"product_id": created.id}
        )
        
        return jsonify(created.to_dict()), 201
        
    except VitalisException as e:
        logger.error(f"Business error creating product: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        return jsonify({"error": "Failed to create product"}), 500


@products_bp.route("/api/products/<product_id>", methods=["PUT"])
@require_api_key
def update_product(product_id: str):
    """Update a product."""
    try:
        data = request.get_json()
        
        product_repo = ProductRepository()
        product = product_repo.get(product_id)
        
        if not product:
            return jsonify({"error": "Product not found"}), 404
        
        # Update fields
        if "name" in data:
            product.name = data["name"]
        if "description" in data:
            product.description = data["description"]
        if "status" in data:
            product.status = ProductStatus(data["status"])
        if "features" in data:
            product.features = data["features"]
        
        updated = product_repo.update(product)
        
        return jsonify(updated.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Error updating product: {e}")
        return jsonify({"error": "Failed to update product"}), 500


@products_bp.route("/api/products/<product_id>", methods=["DELETE"])
@require_api_key
def delete_product(product_id: str):
    """Delete a product."""
    try:
        product_repo = ProductRepository()
        success = product_repo.delete(product_id)
        
        if success:
            return jsonify({"success": True}), 200
        else:
            return jsonify({"error": "Failed to delete product"}), 500
            
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        return jsonify({"error": "Failed to delete product"}), 500


# Pricing Tier endpoints have been moved to pricing_tiers.py to avoid conflicts