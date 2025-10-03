#!/usr/bin/env python3
"""
アルゴリズム徹底分析スクリプト - 下降トレンド vs 買いシグナルの矛盾を調査
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.data_service import DataService
from services.simple_trading_logic import SimpleTradingLogic
from services.gmo_api import GMOCoinAPI
from config import load_config
import logging
import pandas as pd
import numpy as np
# import matplotlib.pyplot as plt  # Not needed for this analysis
from datetime import datetime, timedelta

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def deep_algorithm_analysis():
    """アルゴリズムの徹底的分析"""

    print("🔍 === アルゴリズム徹底分析開始 ===")
    print("問題: 下降トレンド中なのに買いシグナル継続、BUYポジション損失拡大")

    try:
        # 設定読み込み
        config = load_config()
        api_key = config.get('api_credentials', 'api_key')
        api_secret = config.get('api_credentials', 'api_secret')

        # サービス初期化
        data_service = DataService(api_key, api_secret)
        trading_logic = SimpleTradingLogic()
        api = GMOCoinAPI(api_key, api_secret)

        # 1. 現在の市場データ取得（詳細分析用）
        print("\n1. 📊 市場データ詳細分析...")
        df = data_service.get_data_with_indicators('DOGE_JPY', '5m')

        if df is None or df.empty:
            print("❌ 市場データが取得できません")
            return

        # 最新30本のローソク足分析
        recent_data = df.tail(30).copy()

        print(f"📈 価格動向分析（最新30本）:")
        print(f"   最高価格: ¥{recent_data['high'].max():.3f}")
        print(f"   最安価格: ¥{recent_data['low'].min():.3f}")
        print(f"   現在価格: ¥{recent_data['close'].iloc[-1]:.3f}")
        print(f"   価格変化: ¥{recent_data['close'].iloc[-1] - recent_data['close'].iloc[0]:.3f}")

        # トレンド分析
        prices = recent_data['close'].values
        trend_slope = np.polyfit(range(len(prices)), prices, 1)[0]

        print(f"🔍 トレンド傾斜分析:")
        print(f"   傾斜値: {trend_slope:.6f}")
        if trend_slope > 0.01:
            trend_status = "📈 強い上昇トレンド"
        elif trend_slope > 0:
            trend_status = "↗️ 弱い上昇トレンド"
        elif trend_slope < -0.01:
            trend_status = "📉 強い下降トレンド"
        else:
            trend_status = "↘️ 弱い下降トレンド"
        print(f"   判定: {trend_status}")

        # 2. 現在のテクニカル指標詳細分析
        print("\n2. 📊 テクニカル指標詳細分析...")
        latest_row = df.iloc[-1].to_dict()

        rsi = latest_row.get('rsi_14', 'N/A')
        macd_line = latest_row.get('macd_line', 'N/A')
        macd_signal = latest_row.get('macd_signal', 'N/A')
        bb_upper = latest_row.get('bb_upper', 'N/A')
        bb_lower = latest_row.get('bb_lower', 'N/A')
        bb_middle = latest_row.get('bb_middle', 'N/A')
        ema_20 = latest_row.get('ema_20', 'N/A')
        current_price = latest_row['close']

        print(f"📊 現在の指標値:")
        print(f"   RSI(14): {rsi:.2f}")
        print(f"   MACD Line: {macd_line:.4f}")
        print(f"   MACD Signal: {macd_signal:.4f}")
        print(f"   BB Upper: ¥{bb_upper:.3f}")
        print(f"   BB Middle: ¥{bb_middle:.3f}")
        print(f"   BB Lower: ¥{bb_lower:.3f}")
        print(f"   EMA(20): ¥{ema_20:.3f}")
        print(f"   現在価格: ¥{current_price:.3f}")

        # 3. 各指標の個別シグナル分析
        print("\n3. 🎯 個別指標シグナル分析...")

        # RSI分析
        if rsi < 30:
            rsi_signal = "🟢 BUY (売られすぎ)"
        elif rsi > 70:
            rsi_signal = "🔴 SELL (買われすぎ)"
        else:
            rsi_signal = f"⚪ 中立 (RSI: {rsi:.2f})"
        print(f"   RSI: {rsi_signal}")

        # MACD分析
        if macd_line > macd_signal and macd_line > 0:
            macd_signal_text = "🟢 BUY (強いブリッシュ)"
        elif macd_line > macd_signal:
            macd_signal_text = "🟡 弱いBUY (ブリッシュ転換)"
        elif macd_line < macd_signal and macd_line < 0:
            macd_signal_text = "🔴 SELL (強いベアリッシュ)"
        else:
            macd_signal_text = "🟡 弱いSELL (ベアリッシュ転換)"
        print(f"   MACD: {macd_signal_text}")

        # ボリンジャーバンド分析
        bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) * 100
        if current_price < bb_lower * 1.005:
            bb_signal_text = f"🟢 BUY (下限反発, {bb_position:.1f}%)"
        elif current_price > bb_upper * 0.995:
            bb_signal_text = f"🔴 SELL (上限反転, {bb_position:.1f}%)"
        else:
            bb_signal_text = f"⚪ 中立 (BB内 {bb_position:.1f}%)"
        print(f"   BB: {bb_signal_text}")

        # EMA分析
        ema_diff = (current_price - ema_20) / ema_20 * 100
        if current_price > ema_20 * 1.01:
            ema_signal_text = f"🟢 BUY (EMA上 +{ema_diff:.2f}%)"
        elif current_price < ema_20 * 0.99:
            ema_signal_text = f"🔴 SELL (EMA下 {ema_diff:.2f}%)"
        else:
            ema_signal_text = f"⚪ 中立 (EMA付近 {ema_diff:.2f}%)"
        print(f"   EMA: {ema_signal_text}")

        # 4. 総合シグナル生成テスト
        print("\n4. 🎯 総合シグナル分析...")
        should_trade, trade_type, reason, confidence = trading_logic.should_trade(latest_row)

        print(f"📋 アルゴリズム判定:")
        print(f"   取引推奨: {should_trade}")
        print(f"   シグナル: {trade_type}")
        print(f"   理由: {reason}")
        print(f"   信頼度: {confidence:.2f}")

        # 5. 問題分析
        print("\n5. 🚨 問題分析...")

        issues_found = []

        # トレンドとシグナルの矛盾チェック
        if trend_slope < -0.01 and trade_type == 'BUY':
            issues_found.append("❌ 強い下降トレンド中にBUYシグナル")

        # RSIの感度チェック
        if rsi > 50 and trade_type == 'BUY':
            issues_found.append(f"⚠️ RSI {rsi:.2f}でBUYシグナル（通常30以下で買い）")

        # MACDの判定チェック
        if macd_line < 0 and trade_type == 'BUY':
            issues_found.append(f"⚠️ MACD負値({macd_line:.4f})でBUYシグナル")

        # 価格位置チェック
        if bb_position > 50 and trade_type == 'BUY':
            issues_found.append(f"⚠️ BB上半部({bb_position:.1f}%)でBUYシグナル")

        if issues_found:
            print("🚨 発見された問題:")
            for issue in issues_found:
                print(f"   {issue}")
        else:
            print("✅ 明らかな問題は検出されませんでした")

        # 6. 推奨される修正案
        print("\n6. 🔧 推奨修正案...")

        print("📝 アルゴリズム改善提案:")
        print("   1. トレンドフィルター追加 - 強い下降トレンド中はBUYシグナル抑制")
        print("   2. RSI閾値の動的調整 - 市場状況に応じて30/70から調整")
        print("   3. MACD判定の強化 - 負値での買い判定を制限")
        print("   4. 複数時間足分析 - 短期シグナルを長期トレンドでフィルタ")
        print("   5. 損切り条件の強化 - 下降トレンド継続時の早期損切り")

        # 7. 現在のポジション分析
        print("\n7. 💼 現在のポジション分析...")
        positions_response = api.get_positions(symbol='DOGE_JPY')

        if 'data' in positions_response and 'list' in positions_response['data']:
            positions = positions_response['data']['list']

            for i, pos in enumerate(positions, 1):
                side = pos.get('side', 'UNKNOWN')
                size = float(pos.get('size', 0))
                entry_price = float(pos.get('price', 0))
                position_id = pos.get('positionId', 'N/A')

                pnl_amount = (current_price - entry_price) * size if side == 'BUY' else (entry_price - current_price) * size
                pnl_percent = pnl_amount / (entry_price * size) * 100

                print(f"   Position {i}: {side} {size} @ ¥{entry_price:.3f}")
                print(f"   含み損益: ¥{pnl_amount:+.0f} ({pnl_percent:+.2f}%)")
                print(f"   ID: {position_id}")

                # リスク評価
                if abs(pnl_percent) > 2:
                    risk_level = "🚨 高リスク" if pnl_percent < -2 else "💰 高利益"
                else:
                    risk_level = "📊 通常範囲"
                print(f"   リスク評価: {risk_level}")

        print("\n🎯 === 分析完了 ===")
        print("次のステップ: 発見された問題に基づくアルゴリズム修正")

    except Exception as e:
        print(f"❌ 分析エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    deep_algorithm_analysis()