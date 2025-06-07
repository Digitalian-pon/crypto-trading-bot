#!/bin/bash

# CentOS Stream 9 用のトレーディングボット設定スクリプト
# さくらのVPS 512MBプラン (月額671円) での完全セットアップ

echo "=== CentOS Stream 9 暗号通貨トレーディングボット セットアップ ==="

# 1. システム更新
echo "1. システム更新中..."
sudo dnf update -y

# 2. EPEL リポジトリ追加
echo "2. EPELリポジトリの追加..."
sudo dnf install -y epel-release

# 3. 必要なパッケージをインストール
echo "3. 必要なパッケージのインストール..."
sudo dnf install -y python3 python3-pip python3-devel git postgresql postgresql-server postgresql-contrib \
    nginx curl wget gcc gcc-c++ make openssl-devel libffi-devel

# 4. PostgreSQL初期化・設定
echo "4. PostgreSQLの設定..."
sudo postgresql-setup --initdb
sudo systemctl enable postgresql
sudo systemctl start postgresql

# PostgreSQLユーザーとデータベース作成
sudo -u postgres psql << 'EOF'
CREATE USER trading_user WITH PASSWORD 'trading_secure_pass_2024';
CREATE DATABASE trading_db OWNER trading_user;
GRANT ALL PRIVILEGES ON DATABASE trading_db TO trading_user;
\q
EOF

# 5. Python仮想環境作成（512MB用に軽量化）
echo "5. Python仮想環境の作成..."
cd /home/centos
python3 -m venv trading_env
source trading_env/bin/activate

# メモリ使用量を抑制する設定
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

# 6. GitHubからプロジェクトクローン
echo "6. プロジェクトのクローン..."
git clone https://github.com/Digitalian-pon/crypto-trading-bot.git
cd crypto-trading-bot

# 7. Python依存関係インストール
echo "7. Python依存関係のインストール..."
../trading_env/bin/pip install --upgrade pip
../trading_env/bin/pip install gunicorn flask flask-sqlalchemy flask-login flask-wtf \
    psycopg2-binary requests pandas numpy scikit-learn

# 8. 環境変数ファイル作成
echo "8. 環境変数の設定..."
cat > .env << 'EOF'
GMO_API_KEY=your_gmo_api_key_here
GMO_API_SECRET=your_gmo_api_secret_here
DATABASE_URL=postgresql://trading_user:trading_secure_pass_2024@localhost/trading_db
SESSION_SECRET=centos_trading_session_secret_2024
EOF

echo "重要: .env ファイルの GMO_API_KEY と GMO_API_SECRET を実際の値に変更してください"

# 9. systemdサービスファイル作成（メインアプリ）
echo "9. systemdサービスの設定..."
sudo tee /etc/systemd/system/trading-bot.service > /dev/null << 'EOF'
[Unit]
Description=Crypto Trading Bot
After=network.target postgresql.service

[Service]
Type=simple
User=centos
WorkingDirectory=/home/centos/crypto-trading-bot
Environment=PATH=/home/centos/trading_env/bin
EnvironmentFile=/home/centos/crypto-trading-bot/.env
ExecStart=/home/centos/trading_env/bin/gunicorn --bind 0.0.0.0:5000 --workers 1 --max-requests 1000 --timeout 120 main:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 10. Webhookサーバーサービス作成
sudo tee /etc/systemd/system/webhook-service.service > /dev/null << 'EOF'
[Unit]
Description=GitHub Webhook Server for Crypto Trading Bot
After=network.target

[Service]
Type=simple
User=centos
WorkingDirectory=/home/centos/crypto-trading-bot
Environment=PATH=/home/centos/trading_env/bin
ExecStart=/home/centos/trading_env/bin/python webhook_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 11. ログディレクトリとファイル作成
echo "10. ログディレクトリの設定..."
sudo mkdir -p /var/log
sudo touch /var/log/webhook.log
sudo chown centos:centos /var/log/webhook.log

# 12. sudoers設定（パスワードなしでサービス再起動）
echo "11. sudo権限の設定..."
echo "centos ALL=(ALL) NOPASSWD: /bin/systemctl restart trading-bot.service" | sudo tee /etc/sudoers.d/webhook-restart

# 13. SELinux設定（必要に応じて）
echo "12. SELinux設定..."
sudo setsebool -P httpd_can_network_connect 1

# 14. ファイアウォール設定
echo "13. ファイアウォールの設定..."
sudo firewall-cmd --permanent --add-port=5000/tcp   # トレーディングボット
sudo firewall-cmd --permanent --add-port=8080/tcp   # Webhook
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload

# 15. サービス有効化・開始
echo "14. サービスの開始..."
sudo systemctl daemon-reload
sudo systemctl enable trading-bot.service
sudo systemctl enable webhook-service.service
sudo systemctl start trading-bot.service
sudo systemctl start webhook-service.service

# 16. サービス状態確認
echo "15. サービス状態の確認..."
sleep 5

echo ""
echo "=== トレーディングボットサービス状態 ==="
sudo systemctl status trading-bot.service --no-pager -l

echo ""
echo "=== Webhookサービス状態 ==="
sudo systemctl status webhook-service.service --no-pager -l

# 17. セットアップ完了メッセージ
echo ""
echo "========================================="
echo "    CentOS セットアップ完了！"
echo "========================================="
echo ""
echo "次の手順を実行してください："
echo ""
echo "1. 環境変数の設定："
echo "   nano /home/centos/crypto-trading-bot/.env"
echo "   GMO_API_KEY と GMO_API_SECRET を実際の値に変更"
echo ""
echo "2. サービス再起動："
echo "   sudo systemctl restart trading-bot.service"
echo ""
echo "3. GitHubのWebhook設定："
echo "   - Settings > Webhooks > Add webhook"
echo "   - Payload URL: http://あなたのVPS_IP:8080/webhook"
echo "   - Content type: application/json"
echo "   - Secret: crypto_trading_bot_webhook_secret_2024"
echo ""
echo "4. アクセス確認："
echo "   http://あなたのVPS_IP:5000"
echo ""
echo "ログ確認コマンド："
echo "sudo journalctl -u trading-bot.service -f"
echo "sudo tail -f /var/log/webhook.log"
echo ""
echo "サービス管理："
echo "sudo systemctl start/stop/restart trading-bot.service"
echo "sudo systemctl start/stop/restart webhook-service.service"