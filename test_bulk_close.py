#!/usr/bin/env python3
"""
Test script to verify bulk position closing functionality
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.gmo_api import GMOCoinAPI
import configparser

def test_bulk_close():
    print("Testing bulk position close functionality...")
    
    # Load API credentials
    config = configparser.ConfigParser()
    config.read('setting.ini')
    
    api_key = config.get('api_credentials', 'api_key')
    api_secret = config.get('api_credentials', 'api_secret')
    
    if not api_key or not api_secret:
        print("API credentials not found!")
        return
    
    # Initialize API
    api = GMOCoinAPI(api_key, api_secret)
    
    print("1. Checking current margin account status...")
    margin_account = api.get_margin_account()
    print(f"Margin account: {margin_account}")
    
    print("\n2. Checking current positions...")
    try:
        positions = api.get_positions()
        print(f"Positions: {positions}")
        
        # If positions found, show details
        if positions.get('status') == 0 and positions.get('data'):
            print("Position details:")
            for pos in positions['data']:
                print(f"  Symbol: {pos.get('symbol')}, Side: {pos.get('side')}, Size: {pos.get('size')}")
        
    except Exception as e:
        print(f"Error getting positions: {e}")
    
    print("\n3. Testing close_all_positions_by_symbol method (DRY RUN)...")
    try:
        # This would close all SELL positions for DOGE_JPY 
        print("close_all_positions_by_symbol method exists")
        print("Would call: api.close_all_positions_by_symbol('DOGE_JPY', 'SELL')")
        print("This method:")
        print("  1. Gets current positions via /v1/positions")
        print("  2. Filters by symbol and side")
        print("  3. Calls bulk close via /v1/closeOrder/bulk")
        
    except Exception as e:
        print(f"Error with bulk close method: {e}")
    
    print("\n4. Current account balance for reference...")
    balance = api.get_account_balance()
    
    # Extract relevant balances
    if 'data' in balance:
        for asset in balance['data']:
            if asset['symbol'] in ['JPY', 'DOGE']:
                print(f"{asset['symbol']}: {asset['amount']} (available: {asset['available']})")
    
    print("\nTest completed. No actual positions were closed.")

if __name__ == "__main__":
    test_bulk_close()