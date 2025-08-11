"""
Render startup file for the Telegram Mini App Bot
This file is used by Render to start the application
"""

import os
import logging
from main import main

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting Telegram Mini App Bot...")
    
    # Run the main function which sets up webhook and starts Flask
    main()
