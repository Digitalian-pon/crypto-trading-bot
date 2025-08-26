#!/usr/bin/env python3
"""
Standalone script to start the trading bot
This avoids circular import issues
"""

import os
import sys
import logging
import time
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/trading_bot.log', mode='a')
    ]
)

logger = logging.getLogger(__name__)

def main():
    logger.info("="*50)
    logger.info("Starting Trading Bot Manually")
    logger.info("="*50)
    
    try:
        # Import Flask app to initialize database
        from app import app, db
        from models import User, TradingSettings
        from services.trading_bot import TradingBot
        
        with app.app_context():
            # Find the trading user
            user = User.query.filter_by(username='trading_user').first()
            
            if not user:
                logger.error("Trading user not found!")
                return False
                
            logger.info(f"Found user: {user.username}")
            logger.info(f"User has API key: {bool(user.api_key)}")
            logger.info(f"User has API secret: {bool(user.api_secret)}")
            
            if not user.settings:
                logger.error("User has no trading settings!")
                return False
                
            logger.info(f"Trading enabled: {user.settings.trading_enabled}")
            logger.info(f"Currency pair: {user.settings.currency_pair}")
            
            if not user.settings.trading_enabled:
                logger.error("Trading is not enabled in user settings!")
                return False
                
            if not user.api_key or not user.api_secret:
                logger.error("User API credentials are missing!")
                return False
            
            # Create and start trading bot
            logger.info("Creating trading bot instance...")
            trading_bot = TradingBot(user=user, api_key=user.api_key, api_secret=user.api_secret)
            trading_bot.set_db_session(db.session)
            
            logger.info("Starting trading bot...")
            if trading_bot.start(interval=60):
                logger.info("Trading bot started successfully!")
                logger.info("Bot is running. Press Ctrl+C to stop.")
                
                try:
                    # Keep the script running
                    while True:
                        time.sleep(60)
                        logger.info(f"Bot status check: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                except KeyboardInterrupt:
                    logger.info("Received interrupt signal. Stopping bot...")
                    trading_bot.stop()
                    logger.info("Trading bot stopped.")
                    
            else:
                logger.error("Failed to start trading bot!")
                return False
                
    except Exception as e:
        logger.error(f"Error in main: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)