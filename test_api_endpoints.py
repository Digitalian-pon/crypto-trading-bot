#!/usr/bin/env python3
"""
Test GMO Coin API endpoints directly to verify they work correctly
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.gmo_api import GMOCoinAPI

# Set environment variables
os.environ['GMO_API_KEY'] = 'FXhblJAz9Ql0G3pCo5p/+S9zkFw6r2VC'
os.environ['GMO_API_SECRET'] = '/YiZoJlRybHnKAO78go6Jt9LKQOS/EwEEe47UyEl6YbXo7XA84fL+Q/k3AEJeCBo'

def test_endpoints():
    """Test all relevant API endpoints"""

    api = GMOCoinAPI()

    print("=" * 80)
    print("Testing GMO Coin API Endpoints")
    print("=" * 80)

    # Test 1: Public API - Ticker (should work)
    print("\n1. Testing Public API - Ticker (DOGE_JPY)")
    print("-" * 80)
    ticker = api.get_ticker("DOGE_JPY")
    if ticker:
        print(f"✅ SUCCESS: Price = ¥{ticker.get('last', 'N/A')}")
        print(f"   Volume = {ticker.get('volume', 'N/A')}")
    else:
        print("❌ FAILED: Could not get ticker data")

    # Test 2: Private API - Account Balance
    print("\n2. Testing Private API - Account Balance (/v1/account/assets)")
    print("-" * 80)
    balance = api.get_account_balance()
    print(f"Response: {balance}")
    if balance and balance.get('status') == 0:
        print("✅ SUCCESS: Account balance retrieved")
        if balance.get('data'):
            for asset in balance['data']:
                print(f"   {asset.get('symbol')}: {asset.get('amount')} (available: {asset.get('available')})")
    else:
        print(f"❌ FAILED: {balance}")

    # Test 3: Private API - Margin Account Info
    print("\n3. Testing Private API - Margin Account (/v1/account/margin)")
    print("-" * 80)
    margin = api.get_margin_account()
    print(f"Response: {margin}")
    if margin:
        print("✅ SUCCESS: Margin account info retrieved")
        print(f"   Available Amount: {margin.get('availableAmount', 'N/A')}")
        print(f"   Margin Call Status: {margin.get('marginCallStatus', 'N/A')}")
    else:
        print("❌ FAILED: Could not get margin account info")

    # Test 4: Private API - Open Positions
    print("\n4. Testing Private API - Open Positions (/v1/openPositions)")
    print("-" * 80)
    positions = api.get_positions("DOGE_JPY")
    print(f"Response: {positions}")
    if isinstance(positions, list):
        print(f"✅ SUCCESS: Found {len(positions)} open positions")
        for pos in positions:
            print(f"   Position: {pos.get('side')} {pos.get('size')} @ ¥{pos.get('price')}")
            print(f"   Position ID: {pos.get('positionId')}")
            print(f"   Loss Gain: {pos.get('lossGain', 'N/A')}")
    else:
        print(f"❌ FAILED: {positions}")

    # Test 5: Private API - Latest Executions
    print("\n5. Testing Private API - Latest Executions (/v1/latestExecutions)")
    print("-" * 80)
    executions = api.get_latest_executions("DOGE_JPY", count=5)
    print(f"Response: {executions}")
    if executions and executions.get('status') == 0:
        print("✅ SUCCESS: Execution history retrieved")
        if executions.get('data', {}).get('list'):
            for ex in executions['data']['list'][:3]:  # Show first 3
                print(f"   {ex.get('side')} {ex.get('size')} @ ¥{ex.get('price')} - {ex.get('timestamp')}")
    else:
        print(f"❌ FAILED: {executions}")

    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80)

if __name__ == "__main__":
    test_endpoints()
