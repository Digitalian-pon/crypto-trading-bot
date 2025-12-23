"""
Railway用統合アプリケーション - 最適化版
- 最適化されたDOGE_JPYレバレッジ取引ボットとダッシュボードを同時起動
- 24時間稼働対応
- 市場レジーム検出、動的SL/TP、ATRベースリスク管理
- 空売り（SELL）とロング（BUY）の両方に対応

VERSION: 2.1.0 - Fee Erosion Fix (2025-12-23)
Changes:
- TP/SL決済後の継続チェック無効化
- 価格距離フィルター追加（1.5%）
- 信頼度閾値引き上げ
- チェック間隔延長（300秒）
"""

import os
import sys
import threading
import logging
from datetime import datetime
import shutil
import glob

# バージョン情報
VERSION = "2.1.0"
BUILD_DATE = "2025-12-23"
COMMIT_HASH = "8171d54"

# キャッシュクリア: Railway環境で古いバイトコードが使われるのを防ぐ
def clear_python_cache():
    """Pythonキャッシュファイル（__pycache__、.pyc）を削除"""
    try:
        # __pycache__ ディレクトリを削除
        for pycache_dir in glob.glob('**/__pycache__', recursive=True):
            shutil.rmtree(pycache_dir, ignore_errors=True)
            print(f"[CACHE] Removed: {pycache_dir}")

        # .pyc ファイルを削除
        for pyc_file in glob.glob('**/*.pyc', recursive=True):
            os.remove(pyc_file)
            print(f"[CACHE] Removed: {pyc_file}")

        print("[CACHE] ✅ Python cache cleared successfully")
    except Exception as e:
        print(f"[CACHE] ⚠️ Cache clear warning: {e}")

# 起動時にキャッシュクリア
clear_python_cache()

# Railway環境: 環境変数を強制的にハードコード値で設定
# これによりRailway環境でも確実にAPI認証が動作する
os.environ['GMO_API_KEY'] = 'FXhblJAz9Ql0G3pCo5p/+S9zkFw6r2VC'
os.environ['GMO_API_SECRET'] = '/YiZoJlRybHnKAO78go6Jt9LKQOS/EwEEe47UyEl6YbXo7XA84fL+Q/k3AEJeCBo'

print("[RAILWAY] ========================================")
print(f"[RAILWAY] VERSION: {VERSION}")
print(f"[RAILWAY] BUILD_DATE: {BUILD_DATE}")
print(f"[RAILWAY] COMMIT: {COMMIT_HASH}")
print("[RAILWAY] ========================================")
print("[RAILWAY] API Credentials Configuration")
print("[RAILWAY] ========================================")
print(f"[RAILWAY] GMO_API_KEY: {os.environ.get('GMO_API_KEY', 'NOT SET')[:10]}... (length: {len(os.environ.get('GMO_API_KEY', ''))})")
print(f"[RAILWAY] GMO_API_SECRET: {os.environ.get('GMO_API_SECRET', 'NOT SET')[:10]}... (length: {len(os.environ.get('GMO_API_SECRET', ''))})")
print("[RAILWAY] ========================================")

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def run_trading_bot():
    """最適化されたDOGE_JPYレバレッジ取引ボットを実行"""
    while True:  # 永続ループ（確実に動作させる）
        try:
            logger.info("="*70)
            logger.info("🤖 TRADING BOT STARTING...")
            logger.info(f"📌 VERSION: {VERSION} ({BUILD_DATE}) - COMMIT: {COMMIT_HASH}")
            logger.info("="*70)
            logger.info("Features: Market Regime Detection, Dynamic SL/TP, ATR-based Risk Management")
            logger.info("🆕 NEW FEATURES:")
            logger.info("   - TP/SL決済後の継続チェック無効化（クールダウン期間）")
            logger.info("   - 価格距離フィルター（決済価格から1.5%以上動くまで待機）")
            logger.info("   - 信頼度閾値引き上げ（高品質シグナルのみ）")
            logger.info("   - チェック間隔延長（300秒=5分）")
            logger.info("="*70)
            from optimized_leverage_bot import OptimizedLeverageTradingBot

            bot = OptimizedLeverageTradingBot()
            logger.info("✅ Bot instance created successfully")
            bot.run()  # これは無限ループ
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ CRITICAL BOT ERROR: {e}", exc_info=True)
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error details: {str(e)}")
            # エラー時も継続稼働するため、60秒待って再起動
            import time
            logger.info("⏳ Waiting 60 seconds before restart...")
            time.sleep(60)
            logger.info("🔄 Attempting to restart trading bot...")
            # ループが続くので自動的に再起動される

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
    logger.info("🚀 Railway Deployment - Optimized DOGE_JPY Trading System")
    logger.info(f"Started at: {datetime.now()}")
    logger.info("Trading Pair: DOGE_JPY")
    logger.info("Trading Type: Leverage (Long & Short)")
    logger.info("Timeframe: 1hour")
    logger.info("Check Interval: 180s (3min)")
    logger.info("Optimizations: Market Regime, Dynamic SL/TP, ATR Risk, Trailing Stop")
    logger.info("Profit Target: ¥2.5 | Stop Loss: -0.5% or -¥2")
    logger.info("="*60)

    # 取引ボットをバックグラウンドスレッドで起動
    bot_thread = threading.Thread(target=run_trading_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ Trading bot thread started")

    # ダッシュボードをメインスレッドで起動（Railwayのヘルスチェック用）
    run_dashboard()
