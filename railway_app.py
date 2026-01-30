"""
Railway用統合アプリケーション - 最適化版
- 最適化されたDOGE_JPYレバレッジ取引ボットとダッシュボードを同時起動
- 24時間稼働対応
- 市場レジーム検出、動的SL/TP、ATRベースリスク管理
- 空売り（SELL）とロング（BUY）の両方に対応

VERSION: 2.6.0 - 5min Timeframe Switch (2026-01-14)
Changes:
⚡ **5分足トレードに変更** - 短期スキャルピング戦略で素早い利確を狙う

【修正内容】
- タイムフレーム: 4hour → 5min（短期トレードに変更）
- 5分足データを直接使用（リサンプリング不要）
- インジケーター: MACD + RSI + Bollinger Bands（短期向け）
- チェック間隔: 300秒（5分）- 5分足1本ごとに判断

【変更の理由】
- v2.5.1（4時間足）では損失が継続（¥730 → ¥212、-71%）
- 4時間足戦略と5分チェック間隔のミスマッチ
- 手数料負けを防ぐため、より明確なシグナルでエントリー
- 5分足で素早い利確を狙い、損失を最小化

【期待される効果】
- ✅ 短期トレンドを素早く捉える
- ✅ 利確¥3.0を達成しやすい（5分足での変動を活用）
- ✅ 明確なシグナルでエントリー精度向上
- ✅ 損失を早期に切る（-0.8%損切り）
- ✅ 残高回復を目指す（¥212 → ¥300以上）
"""

import os
import sys
import threading
import logging
from datetime import datetime
import shutil
import glob

# バージョン情報
VERSION = "3.2.1"
BUILD_DATE = "2026-01-30"
COMMIT_HASH = "lower-histogram-threshold"

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
            logger.info("Features: MACD + EMA Trend Following, Dynamic SL/TP")
            logger.info("🎯 MACD TREND-FOLLOW STRATEGY (v3.2.1):")
            logger.info("   - 📈 エントリー: MACDクロス OR 継続シグナル")
            logger.info("   - 🟢 BUY: 上昇トレンド中のみ（EMA20 > EMA50）")
            logger.info("   - 🔴 SELL: 下降トレンド中のみ（EMA20 < EMA50）")
            logger.info("   - 📊 継続シグナル: ヒストグラム > 0.015 でエントリー")
            logger.info("   - 💰 利確: +2%")
            logger.info("   - 🚨 損切り: -1.5%")
            logger.info("   - 🎯 閾値緩和でより多くの取引機会を確保")
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
    logger.info("Timeframe: 5min (short-term scalping)")
    logger.info("Check Interval: 300s (5min)")
    logger.info("Primary Indicator: MACD + EMA Trend Following")
    logger.info("Strategy: TREND-FOLLOW + CONTINUATION SIGNAL 🎯")
    logger.info("Entry: MACD Cross OR Continuation (histogram > 0.02)")
    logger.info("BUY = Uptrend only | SELL = Downtrend only")
    logger.info("="*60)

    # 取引ボットをバックグラウンドスレッドで起動
    bot_thread = threading.Thread(target=run_trading_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ Trading bot thread started")

    # ダッシュボードをメインスレッドで起動（Railwayのヘルスチェック用）
    run_dashboard()
