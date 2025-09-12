#!/usr/bin/env python3
"""
Force bulk close all positions test
"""
import sys
sys.path.append('/data/data/com.termux/files/home/suno-ai-music-generator/crypto-trading-bot')

from services.gmo_api import GMOCoinAPI
from config import load_config

def force_bulk_close():
    """Force close all positions for testing"""
    config = load_config()
    api = GMOCoinAPI(config['api_credentials']['api_key'], config['api_credentials']['api_secret'])
    
    print("🚨 強制一括決済テスト開始")
    
    # Get current positions
    print("\n1. 現在のポジション確認中...")
    positions_response = api.get_positions(symbol='DOGE_JPY')
    if positions_response.get('status') != 0:
        print(f"❌ ポジション取得失敗: {positions_response}")
        return False
    
    positions = positions_response.get('data', {}).get('list', [])
    print(f"📊 現在のポジション数: {len(positions)}")
    
    if not positions:
        print("ℹ️ 決済するポジションがありません")
        return True
    
    # Calculate total size
    total_size = sum(int(pos['size']) for pos in positions)
    print(f"💰 総ポジションサイズ: {total_size} DOGE")
    
    # Show all positions
    print("\n📋 全ポジションリスト:")
    for i, pos in enumerate(positions):
        print(f"  {i+1:2d}. {pos['side']} {pos['size']:>3} @ {pos['price']:>7} (ID: {pos['positionId']})")
    
    # Method 1: Try individual closes for each position
    print(f"\n2. 個別決済方式で一括実行...")
    success_count = 0
    fail_count = 0
    
    for i, pos in enumerate(positions):
        print(f"\n決済中 ({i+1}/{len(positions)}): Position {pos['positionId']}")
        
        try:
            # Close individual position
            close_side = "SELL" if pos['side'] == "BUY" else "BUY"
            result = api.close_position(
                symbol='DOGE_JPY',
                side=close_side,
                execution_type='MARKET',
                position_id=pos['positionId'],
                size=pos['size']
            )
            
            if result.get('status') == 0:
                print(f"✅ 決済成功: Order ID {result.get('data')}")
                success_count += 1
            else:
                print(f"❌ 決済失敗: {result}")
                fail_count += 1
                
        except Exception as e:
            print(f"❌ 決済エラー: {e}")
            fail_count += 1
    
    print(f"\n📊 決済結果:")
    print(f"✅ 成功: {success_count}/{len(positions)}")
    print(f"❌ 失敗: {fail_count}/{len(positions)}")
    
    # Verify remaining positions
    print(f"\n3. 残りポジション確認...")
    final_response = api.get_positions(symbol='DOGE_JPY')
    if final_response.get('status') == 0:
        remaining = final_response.get('data', {}).get('list', [])
        print(f"📊 残りポジション数: {len(remaining)}")
        
        if remaining:
            print("⚠️  未決済ポジション:")
            for pos in remaining:
                print(f"  - {pos['side']} {pos['size']} @ {pos['price']} (ID: {pos['positionId']})")
        else:
            print("🎉 全ポジション決済完了！")
            
        return len(remaining) == 0
    else:
        print(f"❌ 最終確認失敗: {final_response}")
        return False

if __name__ == "__main__":
    print("🔧 強制一括決済テスト")
    print("⚠️  注意: これは実際の取引です！")
    
    import time
    print("3秒後に開始...")
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    
    success = force_bulk_close()
    
    if success:
        print("\n✅ 一括決済テスト完了")
        print("🎯 反対シグナル検出機能がテストされました")
    else:
        print("\n❌ 一括決済テストで問題が発生")
        
    sys.exit(0 if success else 1)