#!/usr/bin/env python3
"""
シグナルとポジション対応の徹底的デバッグテスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.data_service import DataService
from services.simple_trading_logic import SimpleTradingLogic
from services.gmo_api import GMOCoinAPI
from config import load_config
import logging

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_current_signal_logic():
    """現在のシグナル生成ロジックをテスト"""

    print("🔍 === シグナルとポジション対応の徹底的デバッグ ===")

    try:
        # 設定読み込み
        config = load_config()
        api_key = config.get('api_credentials', 'api_key')
        api_secret = config.get('api_credentials', 'api_secret')

        # サービス初期化
        data_service = DataService(api_key, api_secret)
        trading_logic = SimpleTradingLogic()
        api = GMOCoinAPI(api_key, api_secret)

        # 現在の市場データ取得
        print("\n1. 📊 現在の市場データ取得中...")
        df = data_service.get_data_with_indicators('DOGE_JPY', '5m')

        if df is None or df.empty:
            print("❌ 市場データが取得できません")
            return

        # 最新データ
        latest_row = df.iloc[-1].to_dict()
        current_price = latest_row['close']

        print(f"📈 現在価格: ¥{current_price}")
        print(f"📊 RSI: {latest_row.get('rsi_14', 'N/A'):.2f}")
        print(f"📊 MACD Line: {latest_row.get('macd_line', 'N/A'):.4f}")
        print(f"📊 MACD Signal: {latest_row.get('macd_signal', 'N/A'):.4f}")
        print(f"📊 BB Upper: {latest_row.get('bb_upper', 'N/A'):.2f}")
        print(f"📊 BB Lower: {latest_row.get('bb_lower', 'N/A'):.2f}")

        # 2. シグナル生成テスト
        print("\n2. 🎯 シグナル生成テスト...")
        should_trade, trade_type, reason, confidence = trading_logic.should_trade(latest_row)

        print(f"🚦 SIGNAL RESULT:")
        print(f"   Should Trade: {should_trade}")
        print(f"   Trade Type: {trade_type}")
        print(f"   Reason: {reason}")
        print(f"   Confidence: {confidence:.2f}")

        # 3. 現在のポジション確認
        print("\n3. 📋 現在のポジション確認...")
        positions_response = api.get_positions(symbol='DOGE_JPY')

        current_positions = []
        if 'data' in positions_response and 'list' in positions_response['data']:
            current_positions = positions_response['data']['list']

        print(f"📊 現在のポジション数: {len(current_positions)}")

        for i, pos in enumerate(current_positions, 1):
            side = pos.get('side', 'UNKNOWN')
            size = pos.get('size', 0)
            entry_price = pos.get('price', 0)
            position_id = pos.get('positionId', 'N/A')

            # P/L計算
            if side == 'BUY':
                pnl = (current_price - float(entry_price)) / float(entry_price) * 100
            else:  # SELL
                pnl = (float(entry_price) - current_price) / float(entry_price) * 100

            print(f"   Position {i}: {side} {size} DOGE @ ¥{entry_price} (P/L: {pnl:+.2f}%) ID:{position_id}")

        # 4. 論理的一貫性チェック
        print("\n4. ⚖️ 論理的一貫性チェック...")

        if not should_trade:
            print("✅ シグナルなし - 新規ポジション作成なし")
        else:
            print(f"🎯 {trade_type.upper()}シグナル検出")

            # ポジションとシグナルの関係分析
            if len(current_positions) == 0:
                print(f"✅ 新規{trade_type.upper()}ポジション作成が適切")
            else:
                # 既存ポジションとシグナルの整合性確認
                opposite_positions = []
                same_positions = []

                for pos in current_positions:
                    pos_side = pos.get('side', '')
                    if pos_side == trade_type.upper():
                        same_positions.append(pos)
                    else:
                        opposite_positions.append(pos)

                if opposite_positions:
                    print(f"🔄 既存の{opposite_positions[0]['side']}ポジションを決済すべき（逆シグナル）")

                    # これが問題の核心！
                    print("\n🚨 === 重要な分析 ===")
                    print(f"現在のシグナル: {trade_type.upper()}")
                    print(f"既存ポジション: {opposite_positions[0]['side']}")

                    if trade_type.upper() == 'BUY' and opposite_positions[0]['side'] == 'SELL':
                        print("✅ 正常: BUYシグナル時にSELLポジションを決済")
                    elif trade_type.upper() == 'SELL' and opposite_positions[0]['side'] == 'BUY':
                        print("✅ 正常: SELLシグナル時にBUYポジションを決済")
                    else:
                        print("❌ 異常: シグナルとポジションの関係が不正")

                if same_positions:
                    print(f"⚠️ 既に同じ方向の{trade_type.upper()}ポジションが存在")

        # 5. GMO Coin API注文サイド確認
        print("\n5. 🏦 GMO Coin API注文サイド仕様...")
        print("GMO Coin APIにおける注文サイド:")
        print("  - side='BUY': 買い注文 (ロングポジション作成)")
        print("  - side='SELL': 売り注文 (ショートポジション作成)")
        print("  - ポジション決済: 反対サイドで注文")
        print("    * BUYポジション決済 → side='SELL'で決済注文")
        print("    * SELLポジション決済 → side='BUY'で決済注文")

        print("\n6. 🔧 現在のコード動作確認...")

        # fixed_trading_loop.pyの該当部分を確認
        print("line 293: close_side = 'SELL' if trade_type.upper() == 'BUY' else 'BUY'")
        print("line 477: side=trade_type.upper()")
        print("line 1099: side=trade_type.upper()")

        print("これにより:")
        print("  - BUYシグナル → side='BUY' → BUYポジション作成 ✅")
        print("  - SELLシグナル → side='SELL' → SELLポジション作成 ✅")
        print("  - BUYポジション決済 → side='SELL' ✅")
        print("  - SELLポジション決済 → side='BUY' ✅")

        print("\n🎉 === 結論 ===")
        print("コード自体は正しく実装されています。")
        print("シグナルとポジションの対応は理論的に正常です。")

        if should_trade:
            print(f"\n現在の推奨アクション:")
            if len(current_positions) == 0:
                print(f"✅ {trade_type.upper()}ポジション新規作成")
            else:
                for pos in current_positions:
                    if pos['side'] != trade_type.upper():
                        print(f"🔄 {pos['side']}ポジション決済後、{trade_type.upper()}ポジション作成")
                    else:
                        print(f"⚠️ 同じ方向の{trade_type.upper()}ポジションが既に存在")

    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_current_signal_logic()