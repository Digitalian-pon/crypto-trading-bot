"""
簡易バックテスト - 最適化ロジックの動作確認用
"""

import sys
import logging
from services.data_service import DataService
from services.optimized_trading_logic import OptimizedTradingLogic
from services.enhanced_trading_logic import EnhancedTradingLogic
from config import load_config

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def quick_test():
    """簡易テスト - 最新データで両方のロジックを比較"""

    print("="*70)
    print("  QUICK LOGIC COMPARISON TEST")
    print("="*70)

    # データ取得
    config = load_config()
    api_key = config.get('api_credentials', 'api_key')
    api_secret = config.get('api_credentials', 'api_secret')

    data_service = DataService(api_key, api_secret)

    print("\n📊 Fetching latest market data...")
    df = data_service.get_data_with_indicators(
        symbol='DOGE_JPY',
        interval='5m',
        limit=100
    )

    if df is None or df.empty:
        print("❌ Failed to get market data")
        return

    print(f"✅ Got {len(df)} candles")

    current_price = df['close'].iloc[-1]
    print(f"💹 Current DOGE_JPY price: ¥{current_price:.2f}")

    # 最新データ
    latest_data = df.iloc[-1].to_dict()

    print("\n" + "-"*70)
    print("  TESTING ENHANCED LOGIC (Current)")
    print("-"*70)

    enhanced = EnhancedTradingLogic()
    should_trade1, type1, reason1, conf1 = enhanced.should_trade(latest_data)

    print(f"Signal: {type1 if should_trade1 else 'NO TRADE'}")
    print(f"Confidence: {conf1:.2f}")
    print(f"Reason: {reason1}")

    print("\n" + "-"*70)
    print("  TESTING OPTIMIZED LOGIC (New)")
    print("-"*70)

    optimized = OptimizedTradingLogic()
    should_trade2, type2, reason2, conf2, sl2, tp2 = optimized.should_trade(latest_data, df)

    print(f"Signal: {type2 if should_trade2 else 'NO TRADE'}")
    print(f"Confidence: {conf2:.2f}")
    print(f"Reason: {reason2}")

    if should_trade2 and sl2 and tp2:
        print(f"Stop Loss: ¥{sl2:.2f}")
        print(f"Take Profit: ¥{tp2:.2f}")
        if type2 == 'BUY':
            risk = current_price - sl2
            reward = tp2 - current_price
        else:
            risk = sl2 - current_price
            reward = current_price - tp2
        print(f"Risk/Reward Ratio: 1:{reward/risk:.2f}" if risk > 0 else "N/A")

    print("\n" + "="*70)
    print("  COMPARISON SUMMARY")
    print("="*70)

    print(f"\n{'Metric':<30} {'Enhanced':<20} {'Optimized':<20}")
    print("-"*70)
    print(f"{'Signal':<30} {type1 if should_trade1 else 'NO TRADE':<20} {type2 if should_trade2 else 'NO TRADE':<20}")
    print(f"{'Confidence':<30} {conf1:<20.2f} {conf2:<20.2f}")
    print(f"{'Dynamic SL/TP':<30} {'No':<20} {'Yes' if sl2 else 'No':<20}")
    print(f"{'Market Regime Detection':<30} {'No':<20} {'Yes':<20}")
    print(f"{'Trend Quality (R²)':<30} {'No':<20} {'Yes':<20}")
    print(f"{'Price Action Analysis':<30} {'No':<20} {'Yes':<20}")

    print("\n" + "="*70)
    print("  MARKET INDICATORS (Latest Candle)")
    print("="*70)

    print(f"RSI: {latest_data.get('rsi', 0):.2f}")
    print(f"MACD: {latest_data.get('macd_line', 0):.4f} / {latest_data.get('macd_signal', 0):.4f}")
    print(f"BB: ¥{latest_data.get('bb_lower', 0):.2f} - ¥{latest_data.get('bb_upper', 0):.2f}")
    print(f"EMA20: ¥{latest_data.get('ema_20', 0):.2f}")
    print(f"EMA50: ¥{latest_data.get('ema_50', 0):.2f}")
    print(f"Market Regime: {latest_data.get('market_regime', 'Unknown')}")

    print("\n" + "="*70 + "\n")

    # 推奨
    print("💡 RECOMMENDATION:")
    if should_trade2 and conf2 >= 1.5:
        print(f"✅ OPTIMIZED LOGIC shows STRONG {type2} signal (confidence={conf2:.2f})")
        print(f"   Recommended action: Consider {type2}ing with SL=¥{sl2:.2f}, TP=¥{tp2:.2f}")
    elif should_trade1 and conf1 >= 1.0:
        print(f"⚠️  ENHANCED LOGIC shows {type1} signal (confidence={conf1:.2f})")
        print("   But OPTIMIZED LOGIC is more cautious - consider waiting")
    else:
        print("⏸️  Both logics suggest NO TRADE at this moment")
        print("   Market conditions may not be ideal for entry")

    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    quick_test()
