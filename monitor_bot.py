#!/usr/bin/env python3
"""
暗号通貨トレーディングボット監視スクリプト
ボットの状態確認と再起動を行います
"""

import os
import sys
import time
import logging
import requests
import subprocess
from datetime import datetime, timedelta

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('monitor.log')
    ]
)
logger = logging.getLogger(__name__)

class BotMonitor:
    def __init__(self):
        # Railway URL (本番環境)
        self.railway_url = "https://web-production-1f4ce.up.railway.app"
        # ローカル開発URL
        self.local_url = "http://localhost:5000"
        # 現在使用するURL
        self.base_url = self.railway_url
        
    def check_bot_status(self):
        """ボットの稼働状況を確認"""
        try:
            # ダッシュボードへのアクセスを試行
            response = requests.get(f"{self.base_url}/", timeout=30)
            
            if response.status_code == 200:
                logger.info("✅ ダッシュボードにアクセス可能")
                
                # API経由でデータ取得を試行
                api_response = requests.get(f"{self.base_url}/api/ticker/DOGE_JPY", timeout=15)
                
                if api_response.status_code == 200:
                    data = api_response.json()
                    if 'data' in data and data['data']:
                        price = data['data'][0]['last']
                        logger.info(f"✅ API正常動作中 - DOGE/JPY価格: {price}")
                        return True
                    else:
                        logger.warning("⚠️ APIレスポンスにデータがありません")
                        return False
                else:
                    logger.error(f"❌ API接続エラー - Status: {api_response.status_code}")
                    return False
            else:
                logger.error(f"❌ ダッシュボードアクセスエラー - Status: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("❌ 接続タイムアウト - サーバーが応答していません")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("❌ 接続エラー - サーバーにアクセスできません")
            return False
        except Exception as e:
            logger.error(f"❌ 予期しないエラー: {e}")
            return False
    
    def check_trading_activity(self):
        """取引活動の確認"""
        try:
            # ログファイルが存在するかチェック
            log_file = "logs/trading_bot.log"
            if not os.path.exists(log_file):
                logger.warning("⚠️ 取引ログファイルが見つかりません")
                return "no_log"
            
            # 最新のログエントリを確認
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if not lines:
                    logger.warning("⚠️ ログファイルが空です")
                    return "empty_log"
                
                # 最新の10行をチェック
                recent_lines = lines[-10:]
                now = datetime.now()
                
                for line in reversed(recent_lines):
                    if "Trading loop" in line or "Checking for new trade" in line:
                        try:
                            # ログの時刻を解析
                            timestamp_str = line.split(' - ')[0]
                            log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                            
                            # 10分以内のログがあるかチェック
                            if now - log_time < timedelta(minutes=10):
                                logger.info("✅ 最近の取引活動を確認")
                                return "active"
                        except:
                            continue
                
                logger.warning("⚠️ 最近の取引活動が見つかりません")
                return "inactive"
                
        except Exception as e:
            logger.error(f"❌ 取引活動確認エラー: {e}")
            return "error"
    
    def get_system_info(self):
        """システム情報を取得"""
        info = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "url": self.base_url,
            "status": "unknown"
        }
        
        try:
            # プロセス確認
            if sys.platform == "win32":
                # Windows
                result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe'], 
                                      capture_output=True, text=True)
                if 'python.exe' in result.stdout:
                    info["processes"] = "Python processes running"
                else:
                    info["processes"] = "No Python processes found"
            else:
                # Linux/Unix
                result = subprocess.run(['pgrep', '-f', 'python'], capture_output=True, text=True)
                if result.stdout.strip():
                    info["processes"] = f"Python PIDs: {result.stdout.strip()}"
                else:
                    info["processes"] = "No Python processes found"
                    
        except Exception as e:
            info["processes"] = f"Process check error: {e}"
        
        return info
    
    def restart_local_bot(self):
        """ローカルボットの再起動（開発環境用）"""
        try:
            logger.info("🔄 ローカルボットを再起動中...")
            
            # 既存のプロセスを終了
            if sys.platform == "win32":
                subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], capture_output=True)
            else:
                subprocess.run(['pkill', '-f', 'python main.py'], capture_output=True)
            
            time.sleep(3)
            
            # 新しいプロセスを開始
            if os.path.exists('main.py'):
                subprocess.Popen([sys.executable, 'main.py'])
                logger.info("✅ ローカルボット再起動完了")
                return True
            else:
                logger.error("❌ main.pyが見つかりません")
                return False
                
        except Exception as e:
            logger.error(f"❌ ローカルボット再起動エラー: {e}")
            return False
    
    def monitor_loop(self, interval=300):  # 5分間隔でチェック
        """監視ループ"""
        logger.info(f"🚀 ボット監視開始 - チェック間隔: {interval}秒")
        
        consecutive_failures = 0
        max_failures = 3
        
        while True:
            try:
                logger.info("=" * 50)
                logger.info("📊 ボット状態チェック開始")
                
                # システム情報を取得
                sys_info = self.get_system_info()
                logger.info(f"🖥️  システム: {sys_info['timestamp']}")
                
                # ボット状態チェック
                is_healthy = self.check_bot_status()
                
                if is_healthy:
                    logger.info("✅ ボットは正常に動作しています")
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    logger.error(f"❌ ボット異常検出 ({consecutive_failures}/{max_failures})")
                    
                    # 連続失敗回数が上限に達した場合の対処
                    if consecutive_failures >= max_failures:
                        logger.error("🚨 連続異常検出 - 対処が必要です")
                        
                        # ローカル環境の場合は再起動を試行
                        if self.base_url == self.local_url:
                            logger.info("🔄 ローカルボット自動再起動を実行")
                            if self.restart_local_bot():
                                consecutive_failures = 0
                                logger.info("✅ 自動再起動完了")
                            else:
                                logger.error("❌ 自動再起動失敗")
                        else:
                            logger.error("⚠️ Railway環境のため手動対応が必要です")
                
                # 取引活動チェック
                activity_status = self.check_trading_activity()
                logger.info(f"📈 取引活動: {activity_status}")
                
                logger.info(f"⏰ {interval}秒後に再チェック")
                time.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("👋 監視を終了します")
                break
            except Exception as e:
                logger.error(f"❌ 監視ループエラー: {e}")
                time.sleep(60)  # エラー時は1分待機

def main():
    """メイン関数"""
    monitor = BotMonitor()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "status":
            # 単発チェック
            logger.info("📊 ボット状態を確認中...")
            is_healthy = monitor.check_bot_status()
            activity = monitor.check_trading_activity()
            sys_info = monitor.get_system_info()
            
            print("\n" + "="*50)
            print("📊 CRYPTO TRADING BOT STATUS")
            print("="*50)
            print(f"🌐 URL: {monitor.base_url}")
            print(f"⏰ チェック時刻: {sys_info['timestamp']}")
            print(f"🤖 ボット状態: {'✅ 正常' if is_healthy else '❌ 異常'}")
            print(f"📈 取引活動: {activity}")
            print(f"🖥️  プロセス: {sys_info.get('processes', 'Unknown')}")
            print("="*50)
            
        elif command == "restart":
            # 再起動実行
            if monitor.restart_local_bot():
                print("✅ ボット再起動完了")
            else:
                print("❌ ボット再起動失敗")
                
        elif command == "monitor":
            # 監視モード（デフォルト5分間隔）
            interval = 300
            if len(sys.argv) > 2:
                try:
                    interval = int(sys.argv[2])
                except ValueError:
                    logger.warning("無効な間隔指定。デフォルト300秒を使用します")
            
            monitor.monitor_loop(interval)
            
        else:
            print("使用方法:")
            print("  python monitor_bot.py status    # 現在の状態を確認")
            print("  python monitor_bot.py restart   # ボットを再起動")
            print("  python monitor_bot.py monitor [間隔秒] # 継続監視")
    else:
        # 引数なしの場合は状態チェック
        monitor.monitor_loop()

if __name__ == "__main__":
    main()