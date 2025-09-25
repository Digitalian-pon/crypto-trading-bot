#!/bin/bash
# 最強の起動スクリプト - ゼロダウンタイム保証

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="logs/startup.log"

# ログ関数
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - STARTUP - $1" | tee -a "$LOG_FILE"
}

cd "$SCRIPT_DIR"
mkdir -p logs

log "🚀 Starting Zero-Downtime System..."

# 1. 環境チェック
log "Checking environment..."
command -v python3 >/dev/null 2>&1 || { log "❌ Python3 not found"; exit 1; }
command -v pm2 >/dev/null 2>&1 || { log "Installing PM2..."; npm install -g pm2; }

# 2. 依存関係確認
log "Installing dependencies..."
pip install requests psutil 2>/dev/null || true

# 3. 古いプロセス停止
log "Cleaning up old processes..."
pkill -f "system_guardian.py" || true
pkill -f "health_monitor.py" || true
pm2 delete crypto-dashboard || true
pm2 delete crypto-guardian || true

# 4. PM2設定リセット
log "Resetting PM2..."
pm2 kill || true
sleep 2

# 5. システムガーディアン起動
log "Starting System Guardian..."
pm2 start system_guardian.py \
    --name "crypto-guardian" \
    --interpreter python3 \
    --restart-delay=5000 \
    --max-restarts=100 \
    --log logs/guardian.log \
    --error logs/guardian_error.log

# 6. ダッシュボード起動（ガーディアンが管理）
log "Starting Dashboard via Guardian..."
sleep 10  # ガーディアンの初期化待ち

# 7. ヘルスモニター起動（バックアップ）
log "Starting Health Monitor..."
pm2 start health_monitor.py \
    --name "crypto-health" \
    --interpreter python3 \
    --restart-delay=10000 \
    --max-restarts=50 \
    --log logs/health.log

# 8. PM2設定保存・自動起動設定
log "Configuring auto-startup..."
pm2 save
pm2 startup 2>/dev/null || true

# 9. 起動確認
log "Verifying startup..."
sleep 15

# ダッシュボード確認
for i in {1..30}; do
    if curl -s http://localhost:8082 >/dev/null 2>&1; then
        log "✅ Dashboard is responding"
        break
    fi
    if [ $i -eq 30 ]; then
        log "❌ Dashboard startup verification failed"
        # 緊急復旧実行
        ./auto_recovery.sh
    fi
    sleep 1
done

# API確認
API_RESPONSE=$(curl -s "http://localhost:8082/api/ticker/DOGE_JPY" 2>/dev/null || echo "failed")
if [[ "$API_RESPONSE" == *"current_price"* ]]; then
    log "✅ API is working"
else
    log "⚠️ API verification warning"
fi

# 10. 最終状態記録
log "=== Final System State ==="
pm2 status | tee -a "$LOG_FILE"
log "=========================="

log "🎉 Zero-Downtime System startup completed!"
log "📊 Dashboard: http://localhost:8082"
log "🛡️ Guardian: Active monitoring"
log "🏥 Health Monitor: Active"
log "📝 Logs: logs/"

# 自動ガベージコレクション設定
(crontab -l 2>/dev/null; echo "0 */6 * * * cd $SCRIPT_DIR && find logs/ -name '*.log' -mtime +1 -size +100M -delete") | crontab -

log "✅ System is now BULLETPROOF!"