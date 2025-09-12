#!/usr/bin/env python3
"""
Test script to verify the bi-directional sync fix
"""
import logging
import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import Trade, User

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_sync_fix():
    """Test the bi-directional sync functionality"""
    with app.app_context():
        # Get trading user
        user = User.query.filter_by(username='trading_user').first()
        if not user:
            logger.error("Trading user not found")
            return False
        
        # Check current state
        logger.info("=== BEFORE SYNC TEST ===")
        active_trades = Trade.query.filter_by(user_id=user.id, status='open').all()
        logger.info(f"Active trades in database: {len(active_trades)}")
        
        # Import and test the trading bot sync
        from fixed_trading_loop import FixedTradingBot
        from config import load_config
        
        # Load config
        config = load_config()
        api_key = config['api_credentials'].get('api_key')
        api_secret = config['api_credentials'].get('api_secret')
        
        if not api_key or not api_secret:
            logger.error("API credentials not found")
            return False
        
        # Initialize bot with database session
        bot = FixedTradingBot(user=user, api_key=api_key, api_secret=api_secret, app=app)
        from sqlalchemy.orm import sessionmaker
        from app import db
        Session = sessionmaker(bind=db.engine)
        bot_session = Session()
        bot.set_db_session(bot_session)
        
        # Test the sync function
        logger.info("=== RUNNING SYNC TEST ===")
        try:
            # Get exchange positions
            exchange_positions = bot._get_exchange_positions('DOGE_JPY')
            logger.info(f"Exchange positions: {len(exchange_positions)}")
            
            # Run bi-directional sync
            bot._sync_exchange_positions(exchange_positions, 'DOGE_JPY')
            
            logger.info("=== AFTER SYNC TEST ===")
            active_trades_after = Trade.query.filter_by(user_id=user.id, status='open').all()
            logger.info(f"Active trades in database: {len(active_trades_after)}")
            
            logger.info("✅ Sync test completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error during sync test: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

if __name__ == "__main__":
    logger.info("Starting bi-directional sync fix test...")
    success = test_sync_fix()
    if success:
        logger.info("✅ Test completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Test failed")
        sys.exit(1)