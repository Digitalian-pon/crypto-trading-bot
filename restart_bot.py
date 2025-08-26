#!/usr/bin/env python3
"""
暗号通貨トレーディングボット再起動スクリプト
ボットを安全に停止・再起動します
"""

import os
import sys
import time
import logging
import subprocess
import psutil
from datetime import datetime

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('restart.log')
    ]
)
logger = logging.getLogger(__name__)

class BotRestarter:
    def __init__(self):
        self.project_dir = os.getcwd()
        self.main_file = os.path.join(self.project_dir, 'main.py')
        
    def find_bot_processes(self):
        """実行中のボットプロセスを検索"""
        processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        cmdline = proc.info['cmdline'] or []
                        cmdline_str = ' '.join(cmdline)
                        
                        # main.pyまたはapp.pyを実行しているプロセスを検索
                        if any(keyword in cmdline_str for keyword in ['main.py', 'app.py', 'crypto-trading-bot']):
                            processes.append({
                                'pid': proc.info['pid'],
                                'name': proc.info['name'],
                                'cmdline': cmdline_str
                            })
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                    
        except Exception as e:
            logger.error(f"プロセス検索エラー: {e}")
            
        return processes
    
    def stop_bot_processes(self):
        """ボットプロセスを停止"""
        logger.info("🛑 実行中のボットプロセスを検索中...")
        
        processes = self.find_bot_processes()
        
        if not processes:
            logger.info("ℹ️  実行中のボットプロセスが見つかりません")
            return True
        
        logger.info(f"📋 {len(processes)}個のプロセスが見つかりました")
        
        # プロセスを停止
        stopped_count = 0
        for proc_info in processes:
            try:
                pid = proc_info['pid']
                logger.info(f"🔄 PID {pid} を停止中: {proc_info['cmdline']}")
                
                proc = psutil.Process(pid)
                
                # まず穏やかに終了を試行
                proc.terminate()
                
                # 最大10秒待機
                try:
                    proc.wait(timeout=10)
                    logger.info(f"✅ PID {pid} が正常に停止しました")
                    stopped_count += 1
                except psutil.TimeoutExpired:
                    # 強制終了
                    logger.warning(f"⚠️ PID {pid} を強制終了します")
                    proc.kill()
                    stopped_count += 1
                    
            except psutil.NoSuchProcess:
                logger.info(f"ℹ️  PID {pid} は既に終了しています")
                stopped_count += 1
            except Exception as e:
                logger.error(f"❌ PID {pid} 停止エラー: {e}")
        
        logger.info(f"✅ {stopped_count}/{len(processes)} プロセスが停止しました")
        return stopped_count == len(processes)
    
    def start_bot(self):
        """ボットを開始"""
        if not os.path.exists(self.main_file):
            logger.error(f"❌ {self.main_file} が見つかりません")
            return False
        
        try:
            logger.info("🚀 新しいボットプロセスを開始中...")
            
            # 新しいプロセスでボットを開始
            if sys.platform == "win32":
                # Windows
                process = subprocess.Popen(
                    [sys.executable, 'main.py'],
                    cwd=self.project_dir,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                # Linux/macOS
                process = subprocess.Popen(
                    [sys.executable, 'main.py'],
                    cwd=self.project_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
            
            # 少し待ってプロセスが正常に開始されたか確認
            time.sleep(3)
            
            if process.poll() is None:
                logger.info(f"✅ 新しいボットプロセスが開始されました (PID: {process.pid})")
                return True
            else:
                logger.error("❌ ボットプロセスの開始に失敗しました")
                return False
                
        except Exception as e:
            logger.error(f"❌ ボット開始エラー: {e}")
            return False
    
    def restart(self):
        """ボット再起動メイン処理"""
        logger.info("=" * 60)
        logger.info("🔄 CRYPTO TRADING BOT RESTART")
        logger.info(f"⏰ 開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        # 1. 既存プロセス停止
        if not self.stop_bot_processes():
            logger.error("❌ プロセス停止に失敗しました")
            return False
        
        # 2. 少し待機
        logger.info("⏳ 3秒間待機中...")
        time.sleep(3)
        
        # 3. 新しいプロセス開始
        if not self.start_bot():
            logger.error("❌ ボット開始に失敗しました")
            return False
        
        logger.info("=" * 60)
        logger.info("✅ RESTART COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        return True
    
    def status(self):
        """現在のボット状態を表示"""
        logger.info("📊 ボットプロセス状態:")
        
        processes = self.find_bot_processes()
        
        if not processes:
            print("❌ ボットプロセスが見つかりません")
            return False
        
        print(f"✅ {len(processes)}個のボットプロセスが実行中:")
        for i, proc_info in enumerate(processes, 1):
            print(f"  {i}. PID: {proc_info['pid']}")
            print(f"     コマンド: {proc_info['cmdline']}")
        
        return True
    
    def force_kill(self):
        """強制終了"""
        logger.warning("⚠️ 全てのPythonプロセスを強制終了します")
        
        if sys.platform == "win32":
            # Windows
            subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], capture_output=True)
            subprocess.run(['taskkill', '/F', '/IM', 'pythonw.exe'], capture_output=True)
        else:
            # Linux/macOS
            subprocess.run(['pkill', '-f', 'python'], capture_output=True)
        
        logger.info("✅ 強制終了完了")

def main():
    """メイン関数"""
    restarter = BotRestarter()
    
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python restart_bot.py restart    # ボットを再起動")
        print("  python restart_bot.py stop       # ボットを停止")
        print("  python restart_bot.py start      # ボットを開始")
        print("  python restart_bot.py status     # 現在の状態を確認")
        print("  python restart_bot.py kill       # 強制終了")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "restart":
        success = restarter.restart()
        sys.exit(0 if success else 1)
        
    elif command == "stop":
        success = restarter.stop_bot_processes()
        if success:
            print("✅ ボット停止完了")
        else:
            print("❌ ボット停止に問題が発生しました")
        sys.exit(0 if success else 1)
        
    elif command == "start":
        success = restarter.start_bot()
        if success:
            print("✅ ボット開始完了")
        else:
            print("❌ ボット開始に失敗しました")
        sys.exit(0 if success else 1)
        
    elif command == "status":
        restarter.status()
        
    elif command == "kill":
        restarter.force_kill()
        
    else:
        print(f"❌ 不明なコマンド: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()