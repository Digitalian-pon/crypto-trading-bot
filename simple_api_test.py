#!/usr/bin/env python3
"""
Simple API Test - Direct position and balance check
"""

import sys
import os
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import User
from services.gmo_api import GMOCoinAPI

def test_api_direct():
    """Test API directly"""
    with app.app_context():
        try:
            user = User.query.filter_by(username='trading_user').first()
            if not user:
                print("ERROR: User not found")
                return

            print(f"=== API Direct Test at {datetime.now()} ===")
            print(f"User: {user.username}")
            print(f"Has API key: {bool(user.api_key)}")
            print(f"Has API secret: {bool(user.api_secret)}")

            api = GMOCoinAPI(user.api_key, user.api_secret)

            # Test positions
            print("\n=== Testing Positions ===")
            positions_response = api.get_positions('DOGE_JPY')
            print(f"Positions response: {positions_response}")

            if 'data' in positions_response and 'list' in positions_response['data']:
                positions = positions_response['data']['list']
                print(f"Found {len(positions)} positions:")
                for i, pos in enumerate(positions):
                    print(f"  Position {i+1}: {pos}")

            # Test margin account
            print("\n=== Testing Margin Account ===")
            try:
                margin_response = api.get_margin_account()
                print(f"Margin response: {margin_response}")
            except Exception as e:
                print(f"Margin account error: {e}")

            # Test account balance
            print("\n=== Testing Account Balance ===")
            try:
                balance_response = api.get_account_balance()
                print(f"Balance response: {balance_response}")
            except Exception as e:
                print(f"Account balance error: {e}")

            # Test current price
            print("\n=== Testing Current Price ===")
            import requests
            try:
                response = requests.get('https://api.coin.z.com/public/v1/ticker?symbol=DOGE_JPY', timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data['status'] == 0:
                        price_data = data['data'][0]
                        print(f"Current DOGE/JPY: ¥{price_data['last']}")
                        print(f"24h Volume: {price_data['volume']}")
                        print(f"24h High: ¥{price_data['high']}")
                        print(f"24h Low: ¥{price_data['low']}")
            except Exception as e:
                print(f"Price fetch error: {e}")

        except Exception as e:
            print(f"Test error: {e}")

if __name__ == "__main__":
    test_api_direct()