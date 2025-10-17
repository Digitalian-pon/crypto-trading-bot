"""
Railway用統合アプリケーション
- BTC現物取引ボットとダッシュボードを同時起動
- 24時間稼働対応
"""

import os
import sys
import threading
import logging
from datetime import datetime

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def run_trading_bot():
    """取引ボットを実行"""
    try:
        logger.info("Starting DOGE_JPY Leverage Trading Bot...")
        from leverage_trading_bot import LeverageTradingBot

        bot = LeverageTradingBot()
        bot.run()
    except Exception as e:
        logger.error(f"Trading bot error: {e}", exc_info=True)

def run_dashboard():
    """ダッシュボードを実行"""
    try:
        logger.info("Starting DOGE_JPY Leverage Dashboard Server...")
        import socketserver
        import http.server
        from final_dashboard import FinalDashboardHandler

        port = int(os.environ.get('PORT', 8080))
        host = os.environ.get('HOST', '0.0.0.0')

        logger.info(f"Dashboard starting on {host}:{port}")

        with socketserver.TCPServer((host, port), FinalDashboardHandler) as httpd:
            logger.info("DOGE_JPY Leverage dashboard server started successfully")
            httpd.serve_forever()
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)

if __name__ == "__main__":
    logger.info("="*60)
    logger.info("Railway Deployment - DOGE_JPY Leverage Trading System")
    logger.info(f"Started at: {datetime.now()}")
    logger.info("="*60)

    # 取引ボットをバックグラウンドスレッドで起動
    bot_thread = threading.Thread(target=run_trading_bot, daemon=True)
    bot_thread.start()
    logger.info("Trading bot thread started")

    # ダッシュボードをメインスレッドで起動（Railwayのヘルスチェック用）
    run_dashboard()
