"""Flask application factory."""
from flask import Flask, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials
from app.core.config import get_config
from app.core.exceptions import VitalisException
from app.core.logging import get_logger, setup_logging
from app.api.routes import webhook, auth, accounts, analytics, payment, directory, admin_directory, public_directory
from app.api import stripe, billing, products, pricing_tiers

logger = get_logger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Load configuration
    config = get_config()
    
    # Setup logging
    setup_logging(config)
    
    # Configure Flask
    app.config["DEBUG"] = config.debug
    app.config["TESTING"] = config.testing
    
    # Enable CORS with API key support
    CORS(app, 
         origins=[
             "http://localhost:3000",
             "http://localhost:3001",
             "https://vitalis-insights.vercel.app",
             "https://vitalis-analytics-dashboard.vercel.app",
             "https://vitalis-connect.vercel.app",
             "https://*.vercel.app",
             "https://*.gohighlevel.com",
             "https://*.leadconnectorhq.com"
         ],
         allow_headers=["Content-Type", "X-API-Key", "Authorization"],
         allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         supports_credentials=True)
    
    # Initialize Firebase
    initialize_firebase(config)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register blueprints
    app.register_blueprint(webhook.bp, url_prefix="/")
    app.register_blueprint(auth.bp, url_prefix="/")
    app.register_blueprint(accounts.bp, url_prefix="/api")
    app.register_blueprint(analytics.bp, url_prefix="/api")
    app.register_blueprint(stripe.stripe_bp)
    app.register_blueprint(billing.billing_bp)
    app.register_blueprint(products.products_bp)
    app.register_blueprint(pricing_tiers.pricing_bp)
    app.register_blueprint(payment.bp, url_prefix="/callback")
    app.register_blueprint(directory.directory_bp, url_prefix="/api/directory")
    app.register_blueprint(admin_directory.bp, url_prefix="/api")
    app.register_blueprint(public_directory.bp)
    
    # Health check endpoint
    @app.route("/health", methods=["GET"])
    def health_check():
        """Health check endpoint."""
        return jsonify({
            "status": "healthy",
            "service": "vitalis-chatbot",
            "version": "1.0.0"
        }), 200
    
    logger.info("Application initialized successfully")
    
    return app


def initialize_firebase(config):
    """Initialize Firebase Admin SDK."""
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(config.firebase_credentials_path)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        raise


def register_error_handlers(app: Flask):
    """Register global error handlers."""
    
    @app.errorhandler(VitalisException)
    def handle_vitalis_exception(error: VitalisException):
        """Handle custom Vitalis exceptions."""
        logger.error(
            f"{error.__class__.__name__}: {error.message}",
            extra={"error_code": error.error_code, "details": error.details}
        )
        return jsonify(error.to_dict()), error.status_code
    
    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle 404 errors."""
        return jsonify({
            "error": {
                "code": "NOT_FOUND",
                "message": "The requested resource was not found"
            }
        }), 404
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        """Handle 500 errors."""
        logger.exception("Internal server error")
        return jsonify({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred"
            }
        }), 500