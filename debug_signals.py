"""
現在の市場状況とシグナルをデバッグするスクリプト
"""

import sys
from services.gmo_api import GMOCoinAPI
from services.optimized_trading_logic import OptimizedTradingLogic
from services.data_service import DataService
from config import load_config
import logging

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def main():
    """デバッグメイン"""
    try:
        # 設定読み込み
        config = load_config()
        api_key = config.get('api_credentials', 'api_key')
        api_secret = config.get('api_credentials', 'api_secret')

        # APIとロジック初期化
        api = GMOCoinAPI(api_key, api_secret)
        data_service = DataService(api_key, api_secret)
        trading_logic = OptimizedTradingLogic()

        symbol = 'DOGE_JPY'
        timeframe = '5m'

        print("\n" + "="*80)
        print(f"🔍 デバッグ: {symbol} シグナル分析")
        print("="*80 + "\n")

        # 1. 市場データ取得
        print("📊 市場データ取得中...")
        df = data_service.get_data_with_indicators(symbol, interval=timeframe, limit=100)

        if df is None or df.empty:
            print("❌ データ取得失敗")
            return

        # 2. 現在のポジション確認
        print("\n📈 現在のポジション:")
        positions = api.get_positions(symbol=symbol)
        if positions:
            for pos in positions:
                print(f"  - {pos.get('side')} {pos.get('size')} @ ¥{pos.get('price')}")
        else:
            print("  ポジションなし")

        # 3. 残高確認
        print("\n💰 残高情報:")
        balance = api.get_account_balance()
        if 'data' in balance:
            for asset in balance['data']:
                if asset['symbol'] in ['JPY', 'DOGE']:
                    print(f"  {asset['symbol']}: {float(asset['available']):.2f}")

        # 4. 最新の市場データ
        current_price = float(df['close'].iloc[-1])
        last_row = df.iloc[-1].to_dict()

        print(f"\n💹 現在価格: ¥{current_price:.3f}")
        print(f"\n📊 テクニカル指標:")
        print(f"  RSI: {last_row.get('rsi', 'N/A'):.2f}")
        print(f"  MACD Line: {last_row.get('macd_line', 0):.4f}")
        print(f"  MACD Signal: {last_row.get('macd_signal', 0):.4f}")
        print(f"  MACD Histogram: {last_row.get('macd_histogram', 0):.4f}")
        print(f"  BB Upper: {last_row.get('bb_upper', 0):.3f}")
        print(f"  BB Middle: {last_row.get('bb_middle', 0):.3f}")
        print(f"  BB Lower: {last_row.get('bb_lower', 0):.3f}")
        print(f"  EMA 20: {last_row.get('ema_20', 0):.3f}")
        print(f"  EMA 50: {last_row.get('ema_50', 0):.3f}")

        # 5. シグナル分析（3パターン）
        print("\n" + "="*80)
        print("🔍 シグナル分析（3パターン）")
        print("="*80)

        # パターン1: 通常取引
        print("\n【パターン1: 通常取引】")
        should_trade, trade_type, reason, confidence, sl, tp = trading_logic.should_trade(
            last_row, df, skip_price_filter=False, is_tpsl_continuation=False
        )
        print(f"  取引可否: {'YES ✅' if should_trade else 'NO ❌'}")
        print(f"  取引タイプ: {trade_type or 'なし'}")
        print(f"  信頼度: {confidence:.2f}")
        print(f"  理由: {reason}")
        if sl and tp:
            print(f"  SL: ¥{sl:.2f}, TP: ¥{tp:.2f}")

        # パターン2: 反転シグナルモード
        print("\n【パターン2: 反転シグナルモード（価格フィルタースキップ）】")
        should_trade2, trade_type2, reason2, confidence2, sl2, tp2 = trading_logic.should_trade(
            last_row, df, skip_price_filter=True, is_tpsl_continuation=False
        )
        print(f"  取引可否: {'YES ✅' if should_trade2 else 'NO ❌'}")
        print(f"  取引タイプ: {trade_type2 or 'なし'}")
        print(f"  信頼度: {confidence2:.2f}")
        print(f"  理由: {reason2}")
        if sl2 and tp2:
            print(f"  SL: ¥{sl2:.2f}, TP: ¥{tp2:.2f}")

        # パターン3: TP/SL継続モード
        print("\n【パターン3: TP/SL継続モード（中程度の閾値）】")
        should_trade3, trade_type3, reason3, confidence3, sl3, tp3 = trading_logic.should_trade(
            last_row, df, skip_price_filter=False, is_tpsl_continuation=True
        )
        print(f"  取引可否: {'YES ✅' if should_trade3 else 'NO ❌'}")
        print(f"  取引タイプ: {trade_type3 or 'なし'}")
        print(f"  信頼度: {confidence3:.2f}")
        print(f"  理由: {reason3}")
        if sl3 and tp3:
            print(f"  SL: ¥{sl3:.2f}, TP: ¥{tp3:.2f}")

        # 6. パフォーマンス統計
        print("\n" + "="*80)
        print("📊 パフォーマンス統計")
        print("="*80)
        stats = trading_logic.get_performance_stats()
        if stats and stats['total_trades'] > 0:
            print(f"  総取引数: {stats['total_trades']}")
            print(f"  勝率: {stats['win_rate']*100:.1f}% ({stats['wins']}勝 {stats['losses']}敗)")
            print(f"  総損益: ¥{stats['total_pnl']:.2f}")
            print(f"  平均損益: ¥{stats['avg_pnl']:.2f}")
        else:
            print("  取引履歴なし")

        print("\n" + "="*80)
        print("✅ デバッグ完了")
        print("="*80 + "\n")

    except Exception as e:
        logger.error(f"デバッグエラー: {e}", exc_info=True)

if __name__ == "__main__":
    main()
