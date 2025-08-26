#!/usr/bin/env python3
"""
Test script to verify trend reversal detection functionality
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.risk_manager import RiskManager
from services.gmo_api import GMOCoinAPI
from services.data_service import DataService
from config import load_config

def test_trend_reversal():
    print("Testing trend reversal detection...")
    
    # Load config and initialize services
    config = load_config()
    api_key = config['api_credentials'].get('api_key', '')
    api_secret = config['api_credentials'].get('api_secret', '')
    
    if not api_key or not api_secret:
        print("API credentials not found!")
        return
    
    # Initialize services
    data_service = DataService(api_key, api_secret)
    risk_manager = RiskManager()
    
    # Get current market data
    print("Fetching current DOGE/JPY market data...")
    df = data_service.get_data_with_indicators('DOGE_JPY', interval="1h", limit=5)
    
    if df is None or df.empty:
        print("Failed to get market data")
        return
    
    # Get latest indicators
    latest = df.iloc[-1].to_dict()
    
    print("\n=== CURRENT MARKET CONDITIONS ===")
    print(f"Price: {latest.get('close', 0):.3f} JPY")
    print(f"RSI(14): {latest.get('rsi_14', 50):.2f}")
    print(f"MACD Line: {latest.get('macd_line', 0):.4f}")
    print(f"MACD Signal: {latest.get('macd_signal', 0):.4f}")
    print(f"MACD Histogram: {latest.get('macd_histogram', 0):.4f}")
    print(f"EMA(12): {latest.get('ema_12', 0):.3f}")
    print(f"EMA(26): {latest.get('ema_26', 0):.3f}")
    print(f"SMA(20): {latest.get('sma_20', 0):.3f}")
    print(f"BB Upper: {latest.get('bb_upper', 0):.3f}")
    print(f"BB Middle: {latest.get('bb_middle', 0):.3f}")
    print(f"BB Lower: {latest.get('bb_lower', 0):.3f}")
    
    # Test trend reversal for BUY positions
    print("\n=== TREND REVERSAL TEST FOR BUY POSITIONS ===")
    buy_reversal = risk_manager._check_trend_reversal_for_buy(latest)
    if buy_reversal:
        print(f"🚨 BEARISH REVERSAL DETECTED: {buy_reversal}")
    else:
        print("✅ No bearish reversal signals detected")
    
    # Test trend reversal for SELL positions
    print("\n=== TREND REVERSAL TEST FOR SELL POSITIONS ===")
    sell_reversal = risk_manager._check_trend_reversal_for_sell(latest)
    if sell_reversal:
        print(f"🚨 BULLISH REVERSAL DETECTED: {sell_reversal}")
    else:
        print("✅ No bullish reversal signals detected")
    
    # Test market evaluation
    print("\n=== MARKET EVALUATION ===")
    market_eval = risk_manager.evaluate_market_conditions(latest)
    print(f"Market Trend: {market_eval['market_trend']}")
    print(f"Trend Strength: {market_eval['trend_strength']:.2f}")
    print(f"Risk Score: {market_eval['risk_score']}")
    print(f"Volatility: {market_eval['volatility']}")
    
    print("\n=== TEST COMPLETED ===")

if __name__ == "__main__":
    test_trend_reversal()