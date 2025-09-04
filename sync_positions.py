#!/usr/bin/env python3
"""
Sync existing leverage positions with database
"""
import sys
import os
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Trade, User
from services.gmo_api import GMOCoinAPI

def sync_leverage_positions():
    """Sync existing leverage positions with database"""
    with app.app_context():
        try:
            # Get user
            user = User.query.filter_by(username='trading_user').first()
            if not user:
                print("ERROR: User not found")
                return
            
            print(f"Found user: {user.username}")
            print(f"API Key available: {bool(user.api_key)}")
            
            # Initialize API
            api = GMOCoinAPI(user.api_key, user.api_secret)
            
            # Get DOGE_JPY positions
            symbol = 'DOGE_JPY'
            positions = api.get_positions(symbol)
            print(f"Positions API response: {positions}")
            
            if 'data' in positions and 'list' in positions['data']:
                position_list = positions['data']['list']
                print(f"Found {len(position_list)} leverage positions")
                
                for pos in position_list:
                    # Check if this position already exists in database
                    existing_trade = Trade.query.filter_by(
                        user_id=user.id,
                        currency_pair=symbol,
                        trade_type=pos['side'].lower(),
                        status='open',
                        exchange_position_id=str(pos['positionId'])
                    ).first()
                    
                    if existing_trade:
                        print(f"Position {pos['positionId']} already exists in database")
                        continue
                    
                    # Create new trade record
                    new_trade = Trade()
                    new_trade.user_id = user.id
                    new_trade.currency_pair = symbol
                    new_trade.trade_type = pos['side'].lower()
                    new_trade.amount = float(pos['size'])
                    new_trade.price = float(pos['price'])
                    new_trade.status = 'open'
                    new_trade.exchange_position_id = str(pos['positionId'])
                    new_trade.created_at = datetime.utcnow()
                    
                    db.session.add(new_trade)
                    print(f"Added position to database: {pos['side']} {pos['size']} at {pos['price']} (ID: {pos['positionId']})")
                
                db.session.commit()
                print("All positions synced to database successfully")
                
                # Verify sync
                active_trades = Trade.query.filter_by(
                    user_id=user.id,
                    currency_pair=symbol,
                    status='open'
                ).all()
                
                print(f"Database now has {len(active_trades)} active trades:")
                for trade in active_trades:
                    print(f"  - {trade.trade_type.upper()} {trade.amount} {trade.currency_pair} at {trade.price}")
            
            else:
                print("No leverage positions found or API error")
                
        except Exception as e:
            print(f"Error syncing positions: {e}")
            db.session.rollback()

if __name__ == '__main__':
    sync_leverage_positions()