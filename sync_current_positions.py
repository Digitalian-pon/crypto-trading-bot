#!/usr/bin/env python3
"""
Sync current exchange positions with database for immediate position management
"""
import logging
import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import load_config
from services.gmo_api import GMOCoinAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def sync_positions():
    """Sync exchange positions with database"""
    try:
        # Load configuration
        config = load_config()
        api_key = config['api_credentials'].get('api_key')
        api_secret = config['api_credentials'].get('api_secret')
        
        if not api_key or not api_secret:
            logger.error("API credentials not found in setting.ini")
            return False
        
        # Initialize API
        api = GMOCoinAPI(api_key, api_secret)
        
        # Get current positions from exchange
        logger.info("Fetching current positions from GMO Coin...")
        response = api.get_positions(symbol='DOGE_JPY')
        
        if response.get('status') != 0:
            logger.error(f"Failed to get positions: {response}")
            return False
        
        positions = response.get('data', {}).get('list', [])
        logger.info(f"Found {len(positions)} positions on exchange")
        
        if not positions:
            logger.info("No positions found on exchange")
            return True
        
        # Initialize database
        from app import app, db
        from models import Trade, User
        
        with app.app_context():
            # Get the trading user
            user = User.query.filter_by(username='trading_user').first()
            if not user:
                logger.error("Trading user not found in database")
                return False
            
            synced_count = 0
            
            for position in positions:
                position_id = position.get('positionId')
                symbol = position.get('symbol')
                side = position.get('side', '').lower()
                size = float(position.get('size', 0))
                price = float(position.get('price', 0))
                
                logger.info(f"Processing position: {position_id} - {side.upper()} {size} {symbol} @ {price}")
                
                # Check if position already exists in database
                existing_trade = Trade.query.filter_by(
                    exchange_position_id=position_id,
                    currency_pair=symbol
                ).first()
                
                if existing_trade:
                    logger.info(f"Position {position_id} already exists in database")
                    continue
                
                # Create new trade record
                new_trade = Trade()
                new_trade.user_id = user.id
                new_trade.currency_pair = symbol
                new_trade.trade_type = side
                new_trade.amount = size
                new_trade.price = price
                new_trade.status = 'open'
                new_trade.exchange_position_id = position_id
                new_trade.created_at = datetime.utcnow()
                new_trade.timestamp = datetime.utcnow()
                
                db.session.add(new_trade)
                synced_count += 1
                logger.info(f"Added new {side.upper()} trade: {size} {symbol} at {price}")
            
            # Commit all changes
            if synced_count > 0:
                db.session.commit()
                logger.info(f"Successfully synced {synced_count} positions to database")
            else:
                logger.info("All positions were already synced")
            
            # Display current database trades
            active_trades = Trade.query.filter_by(
                user_id=user.id,
                status='open'
            ).all()
            
            logger.info(f"Total active trades in database: {len(active_trades)}")
            for trade in active_trades:
                logger.info(f"DB Trade {trade.id}: {trade.trade_type.upper()} {trade.amount} {trade.currency_pair} @ {trade.price}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error syncing positions: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    logger.info("Starting position synchronization...")
    success = sync_positions()
    if success:
        logger.info("Position synchronization completed successfully")
        sys.exit(0)
    else:
        logger.error("Position synchronization failed")
        sys.exit(1)