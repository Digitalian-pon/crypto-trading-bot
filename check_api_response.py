"""
GMO Coin APIのレスポンスを確認
"""

import sys
from services.gmo_api import GMOCoinAPI
from config import load_config
import json

def main():
    config = load_config()
    api_key = config.get('api_credentials', 'api_key')
    api_secret = config.get('api_credentials', 'api_secret')
    api = GMOCoinAPI(api_key, api_secret)

    print("="*80)
    print("📊 GMO Coin API レスポンス確認")
    print("="*80 + "\n")

    # 1. 取引履歴
    print("1. /v1/latestExecutions レスポンス:")
    print("-" * 80)
    response = api.get_latest_executions(symbol='DOGE_JPY', count=10)
    print(json.dumps(response, indent=2, ensure_ascii=False))

    print("\n2. 現在のポジション:")
    print("-" * 80)
    positions = api.get_positions(symbol='DOGE_JPY')
    print(json.dumps(positions, indent=2, ensure_ascii=False))

    print("\n3. 残高:")
    print("-" * 80)
    balance = api.get_account_balance()
    if 'data' in balance:
        for asset in balance['data']:
            if asset['symbol'] == 'JPY':
                print(f"JPY: {asset}")

if __name__ == "__main__":
    main()
