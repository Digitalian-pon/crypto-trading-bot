"""
取引履歴を詳細に分析するスクリプト
"""

import sys
from services.gmo_api import GMOCoinAPI
from config import load_config
import logging
from datetime import datetime

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def main():
    """取引履歴分析メイン"""
    try:
        # 設定読み込み
        config = load_config()
        api_key = config.get('api_credentials', 'api_key')
        api_secret = config.get('api_credentials', 'api_secret')

        # API初期化
        api = GMOCoinAPI(api_key, api_secret)
        symbol = 'DOGE_JPY'

        print("\n" + "="*80)
        print(f"📊 取引履歴詳細分析: {symbol}")
        print("="*80 + "\n")

        # 取引履歴取得（最新50件）
        print("📜 取引履歴取得中...")
        executions = api.get_latest_executions(symbol=symbol, count=50)

        if not executions or 'data' not in executions:
            print("❌ 取引履歴取得失敗")
            return

        trades_list = executions.get('list', [])
        print(f"✅ 取引履歴取得成功: {len(trades_list)}件\n")

        # 取引をグループ化（ポジションのオープン/クローズ）
        print("="*80)
        print("📊 取引履歴（詳細）")
        print("="*80)

        buy_positions = []
        sell_positions = []

        for i, trade in enumerate(trades_list[:20], 1):  # 最新20件
            timestamp = trade.get('timestamp', '')
            side = trade.get('side', '')
            price = float(trade.get('price', 0))
            size = float(trade.get('size', 0))
            fee = float(trade.get('fee', 0))

            # タイムスタンプをフォーマット
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime('%m/%d %H:%M:%S')
            else:
                time_str = "N/A"

            # 損益計算の準備
            if side == 'BUY':
                buy_positions.append({'price': price, 'size': size, 'time': time_str})
                pl_str = ""
            else:  # SELL
                # 直前のBUYポジションと比較
                if buy_positions:
                    last_buy = buy_positions[-1]
                    profit = size * (price - last_buy['price'])
                    net_profit = profit - 2.0  # 往復手数料
                    pl_str = f" → 損益: ¥{profit:.1f}, 純利益: ¥{net_profit:.1f}"
                    buy_positions.pop()
                else:
                    pl_str = " → (対応するBUYなし)"

            print(f"{i:2d}. {time_str} | {side:4s} {size:3.0f} @ ¥{price:.2f} (手数料¥{fee:.0f}){pl_str}")

        # 統計情報
        print("\n" + "="*80)
        print("📈 統計情報")
        print("="*80)

        # 決済された取引のみ分析
        closed_trades = []
        temp_buy = None

        for trade in reversed(trades_list):  # 古い順に処理
            side = trade.get('side', '')
            price = float(trade.get('price', 0))
            size = float(trade.get('size', 0))

            if side == 'BUY' and temp_buy is None:
                temp_buy = {'price': price, 'size': size}
            elif side == 'SELL' and temp_buy is not None:
                profit = size * (price - temp_buy['price'])
                closed_trades.append(profit)
                temp_buy = None

        if closed_trades:
            wins = sum(1 for p in closed_trades if p > 0)
            losses = sum(1 for p in closed_trades if p < 0)
            total = len(closed_trades)
            win_rate = wins / total * 100
            total_profit = sum(closed_trades)
            total_fees = total * 2.0  # 往復手数料
            net_profit = total_profit - total_fees

            print(f"決済取引数: {total}件")
            print(f"勝率: {win_rate:.1f}% ({wins}勝 {losses}敗)")
            print(f"総利益: ¥{total_profit:.1f}")
            print(f"総手数料: -¥{total_fees:.1f}")
            print(f"純損益: ¥{net_profit:.1f}")
            print(f"平均損益: ¥{total_profit/total:.2f}/回")
            print(f"平均純損益: ¥{net_profit/total:.2f}/回")
        else:
            print("決済された取引がありません")

        # 現在のポジション
        print("\n" + "="*80)
        print("📊 現在のポジション")
        print("="*80)

        positions = api.get_positions(symbol=symbol)
        if positions:
            for pos in positions:
                side = pos.get('side')
                size = pos.get('size')
                entry_price = float(pos.get('price', 0))
                print(f"{side} {size} DOGE @ ¥{entry_price:.2f}")
        else:
            print("ポジションなし")

        # 残高
        print("\n" + "="*80)
        print("💰 残高")
        print("="*80)

        balance = api.get_account_balance()
        if 'data' in balance:
            for asset in balance['data']:
                if asset['symbol'] == 'JPY':
                    print(f"JPY: ¥{float(asset['available']):.0f}")

        print("\n" + "="*80)
        print("✅ 分析完了")
        print("="*80 + "\n")

    except Exception as e:
        logger.error(f"分析エラー: {e}", exc_info=True)

if __name__ == "__main__":
    main()
