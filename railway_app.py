"""
Railway用統合アプリケーション
- DOGE_JPYレバレッジ取引ボットとダッシュボードを同時起動
- 24時間稼働対応
- 空売り（SELL）とロング（BUY）の両方に対応
"""

import os
import sys
import threading
import logging
from datetime import datetime

# Railway環境: 環境変数が未設定の場合はハードコード値を使用
if not os.environ.get('GMO_API_KEY'):
    os.environ['GMO_API_KEY'] = 'FXhblJAz9Ql0G3pCo5p/+S9zkFw6r2VC'
    os.environ['GMO_API_SECRET'] = '/YiZoJlRybHnKAO78go6Jt9LKQOS/EwEEe47UyEl6YbXo7XA84fL+Q/k3AEJeCBo'
    print(f"[RAILWAY] Set hardcoded API credentials")
else:
    print(f"[RAILWAY] Using existing environment variable API credentials")

# Verify credentials are set
print(f"[RAILWAY] GMO_API_KEY length: {len(os.environ.get('GMO_API_KEY', ''))}")
print(f"[RAILWAY] GMO_API_SECRET length: {len(os.environ.get('GMO_API_SECRET', ''))}")

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def run_trading_bot():
    """DOGE_JPYレバレッジ取引ボットを実行"""
    try:
        logger.info("Starting DOGE_JPY Leverage Trading Bot...")
        logger.info("Features: BUY (Long) and SELL (Short) positions")
        from leverage_trading_bot import LeverageTradingBot

        bot = LeverageTradingBot()
        bot.run()
    except Exception as e:
        logger.error(f"Trading bot error: {e}", exc_info=True)
        # エラー時も継続稼働するため、再起動を試みる
        import time
        time.sleep(60)
        logger.info("Attempting to restart trading bot...")
        run_trading_bot()

def run_dashboard():
    """DOGE_JPYレバレッジダッシュボードを実行"""
    try:
        logger.info("Starting DOGE_JPY Leverage Dashboard Server...")
        import socketserver
        import http.server
        from final_dashboard import FinalDashboardHandler

        port = int(os.environ.get('PORT', 8080))
        host = os.environ.get('HOST', '0.0.0.0')

        logger.info(f"Dashboard starting on {host}:{port}")
        logger.info("Dashboard will display: Positions, Balance, Signals, Execution History")

        with socketserver.TCPServer((host, port), FinalDashboardHandler) as httpd:
            logger.info("DOGE_JPY Leverage dashboard server started successfully")
            logger.info("Dashboard URL: http://0.0.0.0:{port}/")
            httpd.serve_forever()
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        # エラー時も継続稼働するため、再起動を試みる
        import time
        time.sleep(30)
        logger.info("Attempting to restart dashboard...")
        run_dashboard()

if __name__ == "__main__":
    logger.info("="*60)
    logger.info("🚀 Railway Deployment - DOGE_JPY Leverage Trading System")
    logger.info(f"Started at: {datetime.now()}")
    logger.info("Trading Pair: DOGE_JPY")
    logger.info("Trading Type: Leverage (Long & Short)")
    logger.info("Timeframe: 5m")
    logger.info("="*60)

    # 取引ボットをバックグラウンドスレッドで起動
    bot_thread = threading.Thread(target=run_trading_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ Trading bot thread started")

    # ダッシュボードをメインスレッドで起動（Railwayのヘルスチェック用）
    run_dashboard()
