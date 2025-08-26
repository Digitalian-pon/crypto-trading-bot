#!/usr/bin/env python3
"""
Test to understand the actual position status through available APIs
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.gmo_api import GMOCoinAPI
import configparser

def test_actual_positions():
    print("=== Testing Available Position Information ===")
    
    # Load API credentials
    config = configparser.ConfigParser()
    config.read('setting.ini')
    
    api_key = config.get('api_credentials', 'api_key')
    api_secret = config.get('api_credentials', 'api_secret')
    
    api = GMOCoinAPI(api_key, api_secret)
    
    print("1. Margin Account Status:")
    margin = api.get_margin_account()
    if margin.get('status') == 0:
        data = margin['data']
        print(f"  Actual P&L: {data['actualProfitLoss']} JPY")
        print(f"  Unrealized P&L: {data['profitLoss']} JPY") 
        print(f"  Margin Used: {data['margin']} JPY")
        print(f"  Margin Ratio: {data['marginRatio']}%")
        print(f"  Available: {data['availableAmount']} JPY")
        
        # If margin is used, there are positions
        if float(data['margin']) > 0:
            print("  STATUS: POSITIONS DETECTED (margin in use)")
        else:
            print("  STATUS: NO POSITIONS (no margin used)")
    
    print("\n2. Account Assets:")
    balance = api.get_account_balance()
    if balance.get('status') == 0:
        relevant_assets = []
        for asset in balance['data']:
            if asset['symbol'] in ['JPY', 'DOGE'] or float(asset['amount']) > 0:
                relevant_assets.append(asset)
        
        for asset in relevant_assets:
            print(f"  {asset['symbol']}: {asset['amount']} (rate: {asset['conversionRate']})")
    
    print("\n3. Recent Executions (to understand position activity):")
    executions = api.get_execution_history(symbol='DOGE_JPY', count=5)
    if executions.get('status') == 0 and executions.get('data'):
        print("  Recent DOGE_JPY executions found:")
        for exec in executions['data']:
            print(f"    {exec.get('timestamp')}: {exec.get('side')} {exec.get('size')} @ {exec.get('price')}")
    else:
        print("  No recent executions found")
    
    print("\n=== ANALYSIS ===")
    if margin.get('status') == 0:
        margin_used = float(margin['data']['margin'])
        pnl = float(margin['data']['profitLoss'])
        
        if margin_used > 0:
            print(f"✓ ACTIVE POSITIONS CONFIRMED")
            print(f"  - Margin in use: {margin_used} JPY")
            print(f"  - Current P&L: {pnl} JPY ({'PROFIT' if pnl > 0 else 'LOSS'})")
            print(f"  - Position size estimate: ~{margin_used/0.04:.0f} JPY worth")
        else:
            print("✗ NO ACTIVE POSITIONS")
            print("  - No margin being used")

if __name__ == "__main__":
    test_actual_positions()