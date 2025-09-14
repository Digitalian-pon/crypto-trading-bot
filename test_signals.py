#!/usr/bin/env python3
"""
Test trading signals generation directly
"""

import sys
import os
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import User
from services.data_service import DataService
from services.simple_trading_logic import SimpleTradingLogic

def test_signals():
    """Test signal generation directly"""
    with app.app_context():
        try:
            print(f"=== Trading Signal Test at {datetime.now()} ===")

            # Initialize services
            data_service = DataService()
            trading_logic = SimpleTradingLogic()

            print("Getting market data with indicators...")
            # Get market data with indicators using 5m interval (same as trading bot)
            market_data_response = data_service.get_data_with_indicators('DOGE_JPY', interval='5m')

            if market_data_response is None or 'data' not in market_data_response:
                print("❌ No market data available")
                return

            market_data = market_data_response['data']
            if market_data is None or len(market_data) == 0:
                print("❌ Market data is empty")
                return
            print(f"✅ Market data retrieved: {len(market_data)} indicators")

            # Display current indicators
            print("\n=== Current Market Indicators ===")
            current_price = market_data.get('close', 'N/A')
            rsi = market_data.get('rsi_14', 'N/A')
            macd_line = market_data.get('macd_line', 'N/A')
            macd_signal = market_data.get('macd_signal', 'N/A')
            bb_upper = market_data.get('bb_upper', 'N/A')
            bb_lower = market_data.get('bb_lower', 'N/A')
            bb_middle = market_data.get('bb_middle', 'N/A')
            ema_20 = market_data.get('ema_20', 'N/A')

            print(f"Current Price: ¥{current_price}")
            print(f"RSI (14): {rsi}")
            print(f"MACD Line: {macd_line}")
            print(f"MACD Signal: {macd_signal}")
            print(f"BB Upper: {bb_upper}")
            print(f"BB Middle: {bb_middle}")
            print(f"BB Lower: {bb_lower}")
            print(f"EMA 20: {ema_20}")

            # Generate trading signals
            print("\n=== Generating Trading Signal ===")
            should_trade, trade_type, reason, confidence = trading_logic.should_trade(market_data)

            print(f"Should Trade: {should_trade}")
            print(f"Trade Type: {trade_type}")
            print(f"Reason: {reason}")
            print(f"Confidence: {confidence:.2f}/1.0")

            # Get market summary
            market_summary = trading_logic.get_market_summary(market_data)
            print(f"\n=== Market Summary ===")
            print(f"Market Condition: {market_summary.get('condition', 'Unknown')}")
            print(f"Volatility: {market_summary.get('volatility', 'Unknown')}")

            # Display signal interpretation
            if should_trade and trade_type:
                signal_icon = '📈' if trade_type.upper() == 'BUY' else '📉'
                signal_color = 'Green' if trade_type.upper() == 'BUY' else 'Red'
                print(f"\n🚨 ACTIVE SIGNAL: {signal_icon} {trade_type.upper()} ({signal_color})")
            else:
                print(f"\n⏸️  NO SIGNAL: Waiting for clear market direction")

        except Exception as e:
            print(f"❌ Error testing signals: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_signals()