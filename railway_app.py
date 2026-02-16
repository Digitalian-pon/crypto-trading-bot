"""
Railway用統合アプリケーション - 最適化版
- 最適化されたDOGE_JPYレバレッジ取引ボットとダッシュボードを同時起動
- 24時間稼働対応
- MACD Cross + EMAトレンドフォロー専用モード
- 空売り（SELL）とロング（BUY）の両方に対応

VERSION: 3.5.0-cross-entry (2026-02-17)
Changes:
🎯 **v3.5.0** - クロスベースエントリー + EMAソフトフィルター

【v3.5.0の修正内容】
- エントリー: ポジションベース → クロスベースに変更
  - ゴールデンクロス（below→above遷移）の瞬間のみBUY
  - デッドクロス（above→below遷移）の瞬間のみSELL
- EMAフィルター: ハードブロック → confidence調整に変更
  - 順方向: confidence +30%（シグナル強化）
  - 逆方向: confidence -30%（弱めるがブロックしない）
- 決済: トレーリングストップ + MACDクロス確認（v3.4.0維持）

【v3.5.0の主要ルール】
- エントリー: MACDクロスの瞬間のみ（初動を捉える）
- 決済: トレーリングストップ / MACDクロス(確認付き) / SL -1.5%
- EMA: ブロックしない（confidence調整のみ）
"""

import os
import sys
import threading
import logging
from datetime import datetime
import shutil
import glob

# バージョン情報
VERSION = "3.5.0-cross-entry"
BUILD_DATE = "2026-02-17"
COMMIT_HASH = "cross-based-entry-ema-soft"

# 強力なキャッシュクリア: Railway環境で古いバイトコードを完全削除
def clear_python_cache():
    """Pythonキャッシュファイル（__pycache__、.pyc、.pyo）を完全削除"""
    try:
        removed_count = 0

        # __pycache__ ディレクトリを削除
        for pycache_dir in glob.glob('**/__pycache__', recursive=True):
            try:
                shutil.rmtree(pycache_dir, ignore_errors=False)
                print(f"[CACHE] Removed directory: {pycache_dir}")
                removed_count += 1
            except Exception as e:
                print(f"[CACHE] Warning removing {pycache_dir}: {e}")

        # .pyc ファイルを削除
        for pyc_file in glob.glob('**/*.pyc', recursive=True):
            try:
                os.remove(pyc_file)
                print(f"[CACHE] Removed file: {pyc_file}")
                removed_count += 1
            except Exception as e:
                print(f"[CACHE] Warning removing {pyc_file}: {e}")

        # .pyo ファイルも削除（最適化バイトコード）
        for pyo_file in glob.glob('**/*.pyo', recursive=True):
            try:
                os.remove(pyo_file)
                print(f"[CACHE] Removed file: {pyo_file}")
                removed_count += 1
            except Exception as e:
                print(f"[CACHE] Warning removing {pyo_file}: {e}")

        print(f"[CACHE] ✅ Python cache cleared successfully ({removed_count} items)")

        # sys.dont_write_bytecodeを設定して新しいキャッシュ生成を抑制
        sys.dont_write_bytecode = True
        print("[CACHE] ✅ Bytecode generation disabled")

    except Exception as e:
        print(f"[CACHE] ⚠️ Cache clear error: {e}")

# 起動時にキャッシュクリア
print("[CACHE] Starting aggressive cache clear...")
clear_python_cache()

# Railway環境: 環境変数を強制的にハードコード値で設定
# これによりRailway環境でも確実にAPI認証が動作する
os.environ['GMO_API_KEY'] = 'FXhblJAz9Ql0G3pCo5p/+S9zkFw6r2VC'
os.environ['GMO_API_SECRET'] = '/YiZoJlRybHnKAO78go6Jt9LKQOS/EwEEe47UyEl6YbXo7XA84fL+Q/k3AEJeCBo'
os.environ['BOT_VERSION'] = VERSION

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
            logger.info("Features: CROSS-BASED ENTRY + TRAILING STOP (v3.5.0)")
            logger.info("🎯 v3.5.0 CROSS-BASED ENTRY MODE:")
            logger.info("   - 🟢 BUY: MACD Golden Cross (below→above)")
            logger.info("   - 🔴 SELL: MACD Death Cross (above→below)")
            logger.info("   - 📊 EMA: confidence adjustment only (no block)")
            logger.info("   - 📈 TRAILING STOP: +1%→SL=0%, +2%→SL=+1%, +3%→SL=+2%")
            logger.info("   - 🔄 EXIT: MACD Cross + Histogram confirm / Trailing Stop")
            logger.info("   - 🛡️ SL: -1.5% (initial)")
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
    logger.info("🚀 Railway Deployment - DOGE_JPY Trading System v3.3.0-no-filter")
    logger.info(f"Started at: {datetime.now()}")
    logger.info("Trading Pair: DOGE_JPY")
    logger.info("Trading Type: Leverage (Long & Short)")
    logger.info("Timeframe: 15min")
    logger.info("Check Interval: 300s (5min check, 15min candles)")
    logger.info("Primary Indicator: MACD Cross + EMA Trend Filter")
    logger.info("Strategy: CROSS-BASED ENTRY + TRAILING STOP (v3.5.0)")
    logger.info("BUY = MACD Golden Cross | SELL = MACD Death Cross | EMA = confidence only")
    logger.info("EXIT = Trailing Stop (+1%→0%, +2%→+1%, +3%→+2%) | MACD Cross+Confirm | SL -1.5%")
    logger.info("="*60)

    # 取引ボットをバックグラウンドスレッドで起動
    bot_thread = threading.Thread(target=run_trading_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ Trading bot thread started")

    # ダッシュボードをメインスレッドで起動（Railwayのヘルスチェック用）
    run_dashboard()
