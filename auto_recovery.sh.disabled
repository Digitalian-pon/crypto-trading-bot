#!/bin/bash
# 自動復旧スクリプト - システムダウン時の緊急対応

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="logs/auto_recovery.log"
DASHBOARD_URL="http://localhost:8082"

# ログ関数
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - AUTO_RECOVERY - $1" | tee -a "$LOG_FILE"
}

# エラーハンドラ
error_handler() {
    log "ERROR: Script failed at line $1"
    exit 1
}

trap 'error_handler $LINENO' ERR

# ディレクトリ移動
cd "$SCRIPT_DIR"

# ログディレクトリ作成
mkdir -p logs

log "🔄 Starting emergency recovery sequence..."

# 1. 既存プロセス停止
log "Stopping existing processes..."
pkill -f "final_dashboard.py" || true
pkill -f "fixed_trading_loop.py" || true
pm2 delete crypto-dashboard || true

# 2. PM2デーモン再起動
log "Restarting PM2 daemon..."
pm2 kill || true
sleep 3

# 3. システムリソース確認
log "Checking system resources..."
MEMORY_USAGE=$(free | grep Mem | awk '{print ($3/$2) * 100.0}')
echo "Memory usage: ${MEMORY_USAGE}%"

# 4. 不要プロセス終了（メモリ90%以上の場合）
if (( $(echo "$MEMORY_USAGE > 90" | bc -l) )); then
    log "High memory usage detected - cleaning up..."

    # Python プロセスの中で長時間実行されているものを探して終了
    ps aux | grep python | grep -v grep | awk '{if($10 > 100) print $2}' | head -5 | xargs -r kill -9 || true
fi

# 5. ダッシュボード再起動
log "Starting dashboard with PM2..."
pm2 start final_dashboard.py \
    --name "crypto-dashboard" \
    --interpreter python3 \
    --restart-delay=3000 \
    --max-restarts=20 \
    --log logs/dashboard.log \
    --error logs/dashboard_error.log

# 6. PM2設定保存
pm2 save

# 7. 起動確認（最大30秒待機）
log "Waiting for dashboard startup..."
for i in {1..30}; do
    if curl -s "$DASHBOARD_URL" > /dev/null 2>&1; then
        log "✅ Dashboard is responding on port 8082"
        break
    fi

    if [ $i -eq 30 ]; then
        log "❌ Dashboard startup failed after 30 seconds"
        exit 1
    fi

    sleep 1
done

# 8. API確認
log "Testing API endpoints..."
API_RESPONSE=$(curl -s "${DASHBOARD_URL}/api/ticker/DOGE_JPY" || echo "failed")

if [[ "$API_RESPONSE" != "failed" ]] && [[ "$API_RESPONSE" == *"current_price"* ]]; then
    log "✅ API endpoints are working"
else
    log "⚠️ API endpoints may have issues"
fi

# 9. システム状態記録
log "Recording system state..."
echo "=== System Status ===" >> "$LOG_FILE"
pm2 status >> "$LOG_FILE" 2>&1 || true
echo "====================" >> "$LOG_FILE"

log "🎉 Emergency recovery completed successfully!"
log "📊 Dashboard URL: $DASHBOARD_URL"
log "📝 Logs: $LOG_FILE"

exit 0