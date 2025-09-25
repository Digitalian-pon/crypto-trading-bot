#!/usr/bin/env python3
"""
軽量ヘルスモニター - リソース効率重視の監視サービス
"""
import requests
import subprocess
import time
import json
import logging
from datetime import datetime

# 軽量ログ設定
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - HEALTH - %(message)s')
logger = logging.getLogger(__name__)

class HealthMonitor:
    def __init__(self):
        self.dashboard_url = "http://localhost:8082"
        self.api_url = "http://localhost:8082/api/ticker/DOGE_JPY"
        self.check_interval = 60  # 1分間隔

    def run_continuous_check(self):
        """継続的ヘルスチェック"""
        logger.info("🏥 Health Monitor started")

        while True:
            try:
                # ダッシュボードチェック
                dashboard_ok = self._check_dashboard()

                # APIチェック
                api_ok = self._check_api()

                # PM2プロセスチェック
                pm2_ok = self._check_pm2_status()

                # 総合判定
                if dashboard_ok and api_ok and pm2_ok:
                    logger.info("✅ All systems healthy")
                else:
                    logger.warning("⚠️ System issues detected")
                    if not dashboard_ok:
                        self._emergency_restart()

                time.sleep(self.check_interval)

            except KeyboardInterrupt:
                logger.info("Health monitor stopped")
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(30)

    def _check_dashboard(self):
        """ダッシュボード確認"""
        try:
            response = requests.get(self.dashboard_url, timeout=10)
            return response.status_code == 200
        except:
            return False

    def _check_api(self):
        """API確認"""
        try:
            response = requests.get(self.api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return 'current_price' in data
            return False
        except:
            return False

    def _check_pm2_status(self):
        """PM2状態確認"""
        try:
            result = subprocess.run(['pm2', 'jlist'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                processes = json.loads(result.stdout)
                for proc in processes:
                    if proc['name'] == 'crypto-dashboard':
                        return proc['pm2_env']['status'] == 'online'
            return False
        except:
            return False

    def _emergency_restart(self):
        """緊急再起動"""
        logger.warning("🚨 Initiating emergency restart...")
        try:
            subprocess.run(['./auto_recovery.sh'], check=True)
            logger.info("✅ Emergency restart completed")
        except Exception as e:
            logger.error(f"Emergency restart failed: {e}")

if __name__ == "__main__":
    monitor = HealthMonitor()
    monitor.run_continuous_check()