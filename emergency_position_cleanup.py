#!/usr/bin/env python3
"""
Emergency Position Cleanup Script
緊急ポジション整理スクリプト

This script will:
1. Check all current DOGE_JPY positions
2. Close all simultaneous BUY/SELL positions to prevent conflicts
3. Provide detailed logging of actions taken
"""

import sys
import os
import logging
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import User
from services.gmo_api import GMOCoinAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/data/data/com.termux/files/home/crypto-trading-bot/logs/emergency_cleanup.log')
    ]
)
logger = logging.getLogger(__name__)

class EmergencyPositionCleanup:
    def __init__(self):
        """Initialize with API credentials from database"""
        with app.app_context():
            user = User.query.filter_by(username='trading_user').first()
            if not user:
                raise ValueError("Trading user not found in database")

            self.api = GMOCoinAPI(user.api_key, user.api_secret)
            logger.info("Emergency cleanup initialized with API credentials")

    def get_current_positions(self, symbol='DOGE_JPY'):
        """Get current positions for the symbol"""
        logger.info(f"Getting current positions for {symbol}")

        positions_response = self.api.get_positions(symbol=symbol)

        if positions_response.get('status') != 0:
            logger.error(f"Failed to get positions: {positions_response}")
            return []

        if not positions_response.get('data') or not positions_response['data'].get('list'):
            logger.info("No positions found")
            return []

        positions = positions_response['data']['list']
        logger.info(f"Found {len(positions)} positions")

        for i, pos in enumerate(positions):
            logger.info(f"Position {i+1}: ID={pos.get('positionId')}, Side={pos.get('side')}, "
                       f"Size={pos.get('size')}, Entry={pos.get('price')}, P/L={pos.get('lossGain')}")

        return positions

    def analyze_simultaneous_positions(self, positions):
        """Analyze if there are simultaneous BUY/SELL positions"""
        buy_positions = [p for p in positions if p.get('side') == 'BUY']
        sell_positions = [p for p in positions if p.get('side') == 'SELL']

        logger.info(f"Analysis: {len(buy_positions)} BUY positions, {len(sell_positions)} SELL positions")

        if len(buy_positions) > 0 and len(sell_positions) > 0:
            logger.warning("🚨 SIMULTANEOUS BUY/SELL POSITIONS DETECTED!")
            return True, buy_positions, sell_positions
        elif len(positions) == 0:
            logger.info("✅ No positions found")
            return False, [], []
        else:
            logger.info(f"✅ Only {positions[0].get('side')} positions found - no conflict")
            return False, buy_positions, sell_positions

    def close_all_positions_emergency(self, symbol='DOGE_JPY'):
        """Emergency close all positions for the symbol"""
        logger.info(f"🚨 EMERGENCY: Closing ALL positions for {symbol}")

        positions = self.get_current_positions(symbol)
        if not positions:
            logger.info("No positions to close")
            return True

        # Group by side for bulk closing
        buy_positions = [p for p in positions if p.get('side') == 'BUY']
        sell_positions = [p for p in positions if p.get('side') == 'SELL']

        success = True

        # Close all BUY positions
        if buy_positions:
            buy_size = sum(float(p.get('size', 0)) for p in buy_positions)
            logger.info(f"Closing {len(buy_positions)} BUY positions, total size: {buy_size}")

            result = self.api.close_bulk_position(
                symbol=symbol,
                side='BUY',
                execution_type='MARKET',
                size=str(int(buy_size))  # DOGE requires integer size
            )

            if result.get('status') == 0:
                logger.info(f"✅ Successfully closed all BUY positions: {result}")
            else:
                logger.error(f"❌ Failed to close BUY positions: {result}")
                success = False

        # Close all SELL positions
        if sell_positions:
            sell_size = sum(float(p.get('size', 0)) for p in sell_positions)
            logger.info(f"Closing {len(sell_positions)} SELL positions, total size: {sell_size}")

            result = self.api.close_bulk_position(
                symbol=symbol,
                side='SELL',
                execution_type='MARKET',
                size=str(int(sell_size))  # DOGE requires integer size
            )

            if result.get('status') == 0:
                logger.info(f"✅ Successfully closed all SELL positions: {result}")
            else:
                logger.error(f"❌ Failed to close SELL positions: {result}")
                success = False

        return success

    def smart_cleanup_simultaneous_positions(self, symbol='DOGE_JPY'):
        """Smart cleanup - close smaller side to minimize loss"""
        logger.info("Starting smart cleanup of simultaneous positions")

        positions = self.get_current_positions(symbol)
        if not positions:
            return True

        has_simultaneous, buy_positions, sell_positions = self.analyze_simultaneous_positions(positions)

        if not has_simultaneous:
            logger.info("No simultaneous positions detected - no cleanup needed")
            return True

        # Calculate total sizes
        buy_size = sum(float(p.get('size', 0)) for p in buy_positions)
        sell_size = sum(float(p.get('size', 0)) for p in sell_positions)

        # Calculate total P/L for each side
        buy_pnl = sum(float(p.get('lossGain', 0)) for p in buy_positions)
        sell_pnl = sum(float(p.get('lossGain', 0)) for p in sell_positions)

        logger.info(f"BUY side: {len(buy_positions)} positions, size={buy_size}, P/L={buy_pnl}")
        logger.info(f"SELL side: {len(sell_positions)} positions, size={sell_size}, P/L={sell_pnl}")

        # Strategy: Close the side with worse P/L (more negative)
        if buy_pnl <= sell_pnl:
            logger.info(f"Closing BUY side (worse P/L: {buy_pnl} vs {sell_pnl})")
            result = self.api.close_bulk_position(
                symbol=symbol,
                side='BUY',
                execution_type='MARKET',
                size=str(int(buy_size))
            )
        else:
            logger.info(f"Closing SELL side (worse P/L: {sell_pnl} vs {buy_pnl})")
            result = self.api.close_bulk_position(
                symbol=symbol,
                side='SELL',
                execution_type='MARKET',
                size=str(int(sell_size))
            )

        if result.get('status') == 0:
            logger.info(f"✅ Smart cleanup successful: {result}")
            return True
        else:
            logger.error(f"❌ Smart cleanup failed: {result}")
            return False

    def run_emergency_cleanup(self, strategy='smart'):
        """Run emergency cleanup with specified strategy"""
        logger.info(f"=== STARTING EMERGENCY POSITION CLEANUP ({strategy.upper()}) ===")
        logger.info(f"Timestamp: {datetime.now()}")

        try:
            if strategy == 'smart':
                success = self.smart_cleanup_simultaneous_positions()
            elif strategy == 'all':
                success = self.close_all_positions_emergency()
            else:
                logger.error(f"Unknown strategy: {strategy}")
                return False

            # Verify cleanup
            logger.info("Verifying cleanup results...")
            positions_after = self.get_current_positions()

            if not positions_after:
                logger.info("✅ All positions successfully closed")
            else:
                has_simultaneous, _, _ = self.analyze_simultaneous_positions(positions_after)
                if not has_simultaneous:
                    logger.info("✅ No more simultaneous positions")
                else:
                    logger.warning("⚠️ Simultaneous positions still exist")

            logger.info("=== EMERGENCY CLEANUP COMPLETED ===")
            return success

        except Exception as e:
            logger.error(f"Emergency cleanup failed with exception: {e}")
            return False

def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        strategy = sys.argv[1].lower()
        if strategy not in ['smart', 'all']:
            print("Usage: python emergency_position_cleanup.py [smart|all]")
            print("  smart: Close only the side with worse P/L (default)")
            print("  all: Close all positions")
            sys.exit(1)
    else:
        strategy = 'smart'

    try:
        cleanup = EmergencyPositionCleanup()
        success = cleanup.run_emergency_cleanup(strategy)

        if success:
            print("✅ Emergency cleanup completed successfully")
            sys.exit(0)
        else:
            print("❌ Emergency cleanup failed")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Emergency cleanup error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()