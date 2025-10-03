#!/usr/bin/env python3
"""
システム監視・自動復旧ガーディアンサービス
ボットとダッシュボードの安定稼働を保証する包括的監視システム
"""
import logging
import time
import psutil
import subprocess
import requests
import json
import os
import sys
from datetime import datetime, timedelta
import threading
import signal
from pathlib import Path

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - GUARDIAN - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/system_guardian.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class SystemGuardian:
    """システム監視・自動復旧ガーディアン"""

    def __init__(self):
        self.running = False
        self.check_interval = 30  # 30秒間隔チェック
        self.dashboard_url = "http://localhost:8082"
        self.api_url = "http://localhost:8082/api/ticker/DOGE_JPY"
        self.max_memory_mb = 512  # メモリ使用量上限
        self.max_cpu_percent = 90  # CPU使用率上限
        self.failure_counts = {
            'dashboard': 0,
            'api': 0,
            'bot': 0
        }
        self.max_failures = 3  # 連続失敗許容回数
        self.last_restart = {}
        self.min_restart_interval = 300  # 最小再起動間隔（5分）

    def start_monitoring(self):
        """監視開始"""
        logger.info("🛡️ System Guardian starting...")
        self.running = True

        # PM2でダッシュボード起動
        self._ensure_pm2_dashboard()

        # 監視ループ開始
        monitor_thread = threading.Thread(target=self._monitor_loop)
        monitor_thread.daemon = True
        monitor_thread.start()

        logger.info("✅ System Guardian active - 24/7 monitoring enabled")

    def stop_monitoring(self):
        """監視停止"""
        logger.info("Stopping System Guardian...")
        self.running = False

    def _monitor_loop(self):
        """メイン監視ループ"""
        while self.running:
            try:
                # 1. ダッシュボード健康チェック
                self._check_dashboard_health()

                # 2. APIレスポンスチェック
                self._check_api_health()

                # 3. システムリソースチェック
                self._check_system_resources()

                # 4. プロセスチェック
                self._check_processes()

                # 5. ログローテーション
                self._rotate_logs()

                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                time.sleep(60)  # エラー時は1分待機

    def _check_dashboard_health(self):
        """ダッシュボード健康チェック"""
        try:
            response = requests.get(self.dashboard_url, timeout=10)
            if response.status_code == 200:
                self.failure_counts['dashboard'] = 0
                logger.debug("✅ Dashboard healthy")
            else:
                self._handle_dashboard_failure()
        except Exception as e:
            logger.warning(f"Dashboard check failed: {e}")
            self._handle_dashboard_failure()

    def _check_api_health(self):
        """API健康チェック"""
        try:
            response = requests.get(self.api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'current_price' in data:
                    self.failure_counts['api'] = 0
                    logger.debug("✅ API healthy")
                else:
                    self._handle_api_failure()
            else:
                self._handle_api_failure()
        except Exception as e:
            logger.warning(f"API check failed: {e}")
            self._handle_api_failure()

    def _check_system_resources(self):
        """システムリソースチェック"""
        try:
            # メモリ使用量チェック
            memory = psutil.virtual_memory()
            memory_mb = memory.used / 1024 / 1024

            # CPU使用率チェック
            cpu_percent = psutil.cpu_percent(interval=1)

            if memory_mb > self.max_memory_mb:
                logger.warning(f"⚠️ High memory usage: {memory_mb:.1f}MB")
                self._cleanup_resources()

            if cpu_percent > self.max_cpu_percent:
                logger.warning(f"⚠️ High CPU usage: {cpu_percent:.1f}%")
                self._cleanup_resources()

            logger.debug(f"Resources - Memory: {memory_mb:.1f}MB, CPU: {cpu_percent:.1f}%")

        except Exception as e:
            logger.error(f"Resource check failed: {e}")

    def _check_processes(self):
        """プロセス監視"""
        try:
            # PM2プロセス確認
            result = subprocess.run(['pm2', 'list'],
                                  capture_output=True, text=True)

            if 'crypto-dashboard' not in result.stdout:
                logger.warning("🔄 Dashboard process not found in PM2")
                self._restart_dashboard()
            elif 'stopped' in result.stdout:
                logger.warning("🔄 Dashboard process stopped")
                self._restart_dashboard()

        except Exception as e:
            logger.error(f"Process check failed: {e}")

    def _handle_dashboard_failure(self):
        """ダッシュボード障害対応"""
        self.failure_counts['dashboard'] += 1

        if self.failure_counts['dashboard'] >= self.max_failures:
            logger.error(f"🚨 Dashboard failed {self.max_failures} times - restarting")
            self._restart_dashboard()
            self.failure_counts['dashboard'] = 0

    def _handle_api_failure(self):
        """API障害対応"""
        self.failure_counts['api'] += 1

        if self.failure_counts['api'] >= self.max_failures:
            logger.error(f"🚨 API failed {self.max_failures} times - restarting")
            self._restart_dashboard()
            self.failure_counts['api'] = 0

    def _restart_dashboard(self):
        """ダッシュボード再起動"""
        try:
            # 再起動間隔チェック
            if not self._can_restart('dashboard'):
                return

            logger.info("🔄 Restarting dashboard...")

            # PM2でダッシュボード再起動
            subprocess.run(['pm2', 'restart', 'crypto-dashboard'],
                         capture_output=True)

            # 起動確認待ち
            time.sleep(10)

            # 健康チェック
            try:
                response = requests.get(self.dashboard_url, timeout=15)
                if response.status_code == 200:
                    logger.info("✅ Dashboard restart successful")
                    self.last_restart['dashboard'] = datetime.now()
                else:
                    logger.error("❌ Dashboard restart failed - status check")
            except:
                logger.error("❌ Dashboard restart failed - connection")

        except Exception as e:
            logger.error(f"Dashboard restart error: {e}")

    def _ensure_pm2_dashboard(self):
        """PM2ダッシュボード確実起動"""
        try:
            # 既存プロセス停止
            subprocess.run(['pm2', 'delete', 'crypto-dashboard'],
                         capture_output=True)

            # PM2でダッシュボード起動
            cmd = [
                'pm2', 'start', 'final_dashboard.py',
                '--name', 'crypto-dashboard',
                '--interpreter', 'python3',
                '--restart-delay=3000',
                '--max-restarts=10',
                '--log', 'logs/dashboard.log',
                '--error', 'logs/dashboard_error.log'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("✅ Dashboard started with PM2")
                subprocess.run(['pm2', 'save'], capture_output=True)
            else:
                logger.error(f"PM2 start failed: {result.stderr}")

        except Exception as e:
            logger.error(f"PM2 setup error: {e}")

    def _cleanup_resources(self):
        """リソースクリーンアップ"""
        try:
            # ガベージコレクション強制実行
            import gc
            gc.collect()

            # 不要なログファイル削除
            log_dir = Path('logs')
            if log_dir.exists():
                for log_file in log_dir.glob('*.log'):
                    if log_file.stat().st_size > 100 * 1024 * 1024:  # 100MB以上
                        logger.info(f"Rotating large log file: {log_file}")
                        log_file.rename(f"{log_file}.old")
                        log_file.touch()

        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def _rotate_logs(self):
        """ログローテーション"""
        try:
            log_dir = Path('logs')
            if not log_dir.exists():
                log_dir.mkdir()

            # 1日1回ログローテーション
            now = datetime.now()
            for log_file in log_dir.glob('*.log'):
                if log_file.stat().st_size > 50 * 1024 * 1024:  # 50MB以上
                    timestamp = now.strftime('%Y%m%d_%H%M%S')
                    backup_name = f"{log_file.stem}_{timestamp}.log"
                    log_file.rename(log_dir / backup_name)
                    log_file.touch()

        except Exception as e:
            logger.error(f"Log rotation error: {e}")

    def _can_restart(self, service):
        """再起動可能かチェック"""
        if service not in self.last_restart:
            return True

        last = self.last_restart[service]
        now = datetime.now()

        if (now - last).seconds < self.min_restart_interval:
            logger.warning(f"Restart throttled for {service}")
            return False

        return True

def signal_handler(signum, frame):
    """シグナルハンドラ"""
    logger.info("Received termination signal")
    guardian.stop_monitoring()
    sys.exit(0)

if __name__ == "__main__":
    # シグナルハンドラ設定
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # ログディレクトリ作成
    os.makedirs('logs', exist_ok=True)

    # ガーディアン開始
    guardian = SystemGuardian()
    guardian.start_monitoring()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Manual termination")
        guardian.stop_monitoring()