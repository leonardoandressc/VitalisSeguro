"""Main entry point for the application."""
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.main import create_app
from app.core.config import get_config
from app.core.logging import setup_logging

if __name__ == "__main__":
    # Get configuration
    config = get_config()
    
    # Setup logging
    setup_logging(config)
    
    # Create and run the app
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=config.port,
        debug=config.debug
    )