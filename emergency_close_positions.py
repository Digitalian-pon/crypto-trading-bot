#!/usr/bin/env python3
"""
緊急用 - 全SELLポジション一括決済スクリプト
BUYシグナルが出ているにも関わらず、SELLポジションが決済されない時に実行
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.gmo_api import GMOCoinAPI
from config import load_config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def emergency_close_sell_positions():
    """全SELLポジションを緊急一括決済"""
    logger.info("🚨 緊急SELLポジション一括決済を開始します")

    # Load config and initialize API
    config = load_config()
    api_key = config['api_credentials'].get('api_key', '')
    api_secret = config['api_credentials'].get('api_secret', '')

    if not api_key or not api_secret:
        logger.error("API credentials not found!")
        return False

    api = GMOCoinAPI(api_key, api_secret)

    try:
        # Get all positions
        positions_response = api.get_positions()
        if 'data' not in positions_response or not positions_response['data']:
            logger.info("ポジションが見つかりません")
            return True

        sell_positions = []
        for position in positions_response['data']:
            if position.get('symbol') == 'DOGE_JPY' and position.get('side') == 'SELL':
                sell_positions.append(position)

        if not sell_positions:
            logger.info("SELLポジションが見つかりません")
            return True

        logger.info(f"🔄 {len(sell_positions)}個のSELLポジションを一括決済します")

        success_count = 0
        for position in sell_positions:
            position_id = position.get('positionId')
            size = position.get('size')
            entry_price = position.get('price')

            logger.info(f"決済中: Position {position_id}, Size: {size}, Entry: {entry_price}")

            # Close position with BUY order
            result = api.close_position(
                symbol='DOGE_JPY',
                side='BUY',
                execution_type='MARKET',
                position_id=position_id,
                size=str(size)
            )

            if result.get('status') == 0:
                logger.info(f"✅ Position {position_id} 決済成功: {result}")
                success_count += 1
            else:
                logger.error(f"❌ Position {position_id} 決済失敗: {result}")

        logger.info(f"🎯 緊急決済完了: {success_count}/{len(sell_positions)} 成功")
        return success_count == len(sell_positions)

    except Exception as e:
        logger.error(f"緊急決済中にエラーが発生: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = emergency_close_sell_positions()
    if success:
        print("✅ 緊急決済が正常に完了しました")
    else:
        print("❌ 緊急決済に失敗しました")
        sys.exit(1)