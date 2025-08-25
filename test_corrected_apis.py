#!/usr/bin/env python3
"""
Test the corrected position and bulk close APIs
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.gmo_api import GMOCoinAPI
import configparser

def test_corrected_apis():
    print("=== Testing Corrected GMO APIs ===")
    
    # Load API credentials
    config = configparser.ConfigParser()
    config.read('setting.ini')
    
    api_key = config.get('api_credentials', 'api_key')
    api_secret = config.get('api_credentials', 'api_secret')
    
    api = GMOCoinAPI(api_key, api_secret)
    
    print("1. Testing corrected openPositions endpoint...")
    try:
        # Test with DOGE_JPY specifically
        positions = api.get_positions(symbol="DOGE_JPY")
        print(f"DOGE_JPY Positions Response: {positions}")
        
        if positions.get('status') == 0:
            data = positions.get('data', {})
            position_list = data.get('list', [])
            
            if position_list:
                print("POSITIONS FOUND:")
                total_buy_size = 0
                total_sell_size = 0
                
                for pos in position_list:
                    print(f"  Position ID: {pos.get('positionId')}")
                    print(f"  Symbol: {pos.get('symbol')}")
                    print(f"  Side: {pos.get('side')}")
                    print(f"  Size: {pos.get('size')}")
                    print(f"  Price: {pos.get('price')}")
                    print(f"  Timestamp: {pos.get('timestamp')}")
                    print()
                    
                    # Calculate totals
                    side = pos.get('side')
                    size = float(pos.get('size', 0))
                    if side == 'BUY':
                        total_buy_size += size
                    elif side == 'SELL':
                        total_sell_size += size
                
                print(f"SUMMARY:")
                print(f"  Total BUY positions: {total_buy_size}")
                print(f"  Total SELL positions: {total_sell_size}")
                
            else:
                print("No positions found in response")
        else:
            print(f"API Error: Status {positions.get('status')}")
            messages = positions.get('messages', [])
            for msg in messages:
                print(f"  Error: {msg.get('message_string', 'Unknown error')}")
        
    except Exception as e:
        print(f"Error testing positions: {e}")
    
    print("\n2. Testing bulk close functionality...")
    try:
        # Get positions first to see what we have
        positions = api.get_positions(symbol="DOGE_JPY")
        
        if positions.get('status') == 0 and positions.get('data', {}).get('list'):
            position_list = positions['data']['list']
            
            # Calculate sizes for each side
            buy_size = sum(float(p.get('size', 0)) for p in position_list if p.get('side') == 'BUY')
            sell_size = sum(float(p.get('size', 0)) for p in position_list if p.get('side') == 'SELL')
            
            print("BULK CLOSE TEST (DRY RUN):")
            if buy_size > 0:
                print(f"  Would close {buy_size} BUY positions")
                print(f"  Command: api.close_bulk_position('DOGE_JPY', 'BUY', 'MARKET', '{buy_size}')")
            
            if sell_size > 0:
                print(f"  Would close {sell_size} SELL positions")  
                print(f"  Command: api.close_bulk_position('DOGE_JPY', 'SELL', 'MARKET', '{sell_size}')")
                
            # Test convenience method
            print("\nCONVENIENCE METHOD TEST:")
            if sell_size > 0:
                result = api.close_all_positions_by_symbol('DOGE_JPY', 'SELL')
                print(f"close_all_positions_by_symbol result: {result}")
        else:
            print("No positions to test bulk close with")
    
    except Exception as e:
        print(f"Error testing bulk close: {e}")
    
    print("\n3. Current margin account status:")
    margin = api.get_margin_account()
    if margin.get('status') == 0:
        data = margin['data']
        print(f"  Margin used: {data['margin']} JPY")
        print(f"  P&L: {data['profitLoss']} JPY")
        print(f"  Margin ratio: {data['marginRatio']}%")

if __name__ == "__main__":
    test_corrected_apis()