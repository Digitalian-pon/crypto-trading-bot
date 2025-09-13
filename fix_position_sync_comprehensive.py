#!/usr/bin/env python3
"""
Comprehensive Position Synchronization Fix
Handles both phantom positions and missing positions between database and exchange
"""
import sys
import os
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Trade, User
from services.gmo_api import GMOCoinAPI

def comprehensive_position_sync():
    """
    Comprehensive synchronization between database and exchange positions
    """
    with app.app_context():
        try:
            user = User.query.filter_by(username='trading_user').first()
            if not user:
                print("ERROR: User not found")
                return

            print("=== 包括的ポジション同期修正 ===")
            print(f"実行時刻: {datetime.now()}")

            # Initialize API
            api = GMOCoinAPI(user.api_key, user.api_secret)

            # Get database positions
            db_trades = Trade.query.filter_by(
                user_id=user.id,
                currency_pair='DOGE_JPY',
                status='open'
            ).all()

            # Get actual API positions
            api_positions = api.get_positions('DOGE_JPY')
            actual_position_ids = set()
            actual_positions = []

            if 'data' in api_positions and 'list' in api_positions['data']:
                actual_positions = api_positions['data']['list']
                actual_position_ids = {str(pos['positionId']) for pos in actual_positions}

            print(f"\nデータベース: {len(db_trades)}個のオープンポジション")
            print(f"GMO API: {len(actual_positions)}個のオープンポジション")

            # Show detailed comparison
            print("\n=== データベースポジション ===")
            for trade in db_trades:
                print(f"DB ID:{trade.id} {trade.trade_type.upper()} {trade.amount} at ¥{trade.price} (Exchange ID: {trade.exchange_position_id})")

            print("\n=== GMO APIポジション ===")
            for pos in actual_positions:
                print(f"API ID:{pos['positionId']} {pos['side']} {pos['size']} at ¥{pos['price']}")

            # Fix 1: Add missing positions from API to database
            missing_in_db = []
            for pos in actual_positions:
                if str(pos['positionId']) not in {trade.exchange_position_id for trade in db_trades if trade.exchange_position_id}:
                    missing_in_db.append(pos)

            if missing_in_db:
                print(f"\n=== {len(missing_in_db)}個の未同期ポジションをDBに追加 ===")
                for pos in missing_in_db:
                    new_trade = Trade()
                    new_trade.user_id = user.id
                    new_trade.currency_pair = 'DOGE_JPY'
                    new_trade.trade_type = pos['side'].lower()
                    new_trade.amount = float(pos['size'])
                    new_trade.price = float(pos['price'])
                    new_trade.status = 'open'
                    new_trade.exchange_position_id = str(pos['positionId'])
                    new_trade.created_at = datetime.utcnow()

                    db.session.add(new_trade)
                    print(f"追加: {pos['side']} {pos['size']} at ¥{pos['price']} (ID: {pos['positionId']})")

                db.session.commit()

            # Fix 2: Remove phantom positions from database
            phantom_trades = []
            for trade in db_trades:
                if trade.exchange_position_id and trade.exchange_position_id not in actual_position_ids:
                    phantom_trades.append(trade)

            if phantom_trades:
                print(f"\n=== {len(phantom_trades)}個の幽霊ポジションをクローズ ===")
                for trade in phantom_trades:
                    trade.status = 'closed'
                    trade.closed_at = datetime.utcnow()
                    trade.closing_price = trade.price
                    trade.profit_loss = 0.0

                    if not trade.indicators_data:
                        trade.indicators_data = {}

                    # Store as string to avoid JSON serialization issues
                    trade.indicators_data = str({
                        'close_reason': 'COMPREHENSIVE_SYNC_FIX',
                        'sync_fix_date': datetime.utcnow().isoformat(),
                        'original_issue': 'Position not found on exchange during comprehensive sync'
                    })

                    print(f"クローズ: DB ID {trade.id} (Exchange ID: {trade.exchange_position_id})")

                db.session.commit()

            # Fix 3: Handle positions with NULL exchange IDs
            null_id_trades = [trade for trade in db_trades if not trade.exchange_position_id]
            if null_id_trades:
                print(f"\n=== {len(null_id_trades)}個のNULL Exchange IDポジションをクローズ ===")
                for trade in null_id_trades:
                    trade.status = 'closed'
                    trade.closed_at = datetime.utcnow()
                    trade.closing_price = trade.price
                    trade.profit_loss = 0.0

                    trade.indicators_data = str({
                        'close_reason': 'NULL_EXCHANGE_ID_FIX',
                        'sync_fix_date': datetime.utcnow().isoformat(),
                        'original_issue': 'Position created without proper exchange ID'
                    })

                    print(f"クローズ: DB ID {trade.id} (NULL Exchange ID)")

                db.session.commit()

            # Final verification
            final_db_count = Trade.query.filter_by(
                user_id=user.id,
                currency_pair='DOGE_JPY',
                status='open'
            ).count()

            print(f"\n=== 同期完了 ===")
            print(f"データベース: {final_db_count}個のオープンポジション")
            print(f"GMO API: {len(actual_positions)}個のオープンポジション")
            print(f"同期状況: {'✅ 完全同期' if final_db_count == len(actual_positions) else '❌ 未同期'}")

        except Exception as e:
            print(f"Error in comprehensive position sync: {e}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    comprehensive_position_sync()