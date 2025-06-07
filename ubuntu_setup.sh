#!/bin/bash

# Ubuntu 24.04 用のトレーディングボット設定スクリプト
# さくらのVPS 512MBプラン (月額671円) での完全セットアップ

echo "=== Ubuntu 24.04 暗号通貨トレーディングボット セットアップ ==="

# 1. システム更新
echo "1. システム更新中..."
sudo apt update && sudo apt upgrade -y

# 2. 必要なパッケージをインストール
echo "2. 必要なパッケージのインストール..."
sudo apt install -y python3 python3-pip python3-venv git postgresql postgresql-contrib \
    nginx curl wget build-essential libssl-dev libffi-dev python3-dev

# 3. PostgreSQL設定
echo "3. PostgreSQLの設定..."
sudo systemctl enable postgresql
sudo systemctl start postgresql

# PostgreSQLユーザーとデータベース作成
sudo -u postgres psql << 'EOF'
CREATE USER trading_user WITH PASSWORD 'trading_secure_pass_2024';
CREATE DATABASE trading_db OWNER trading_user;
GRANT ALL PRIVILEGES ON DATABASE trading_db TO trading_user;
\q
EOF

# 4. Python仮想環境作成（512MB用に軽量化）
echo "4. Python仮想環境の作成..."
cd /home/ubuntu
python3 -m venv trading_env
source trading_env/bin/activate

# メモリ使用量を抑制する設定
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

# 5. GitHubからプロジェクトクローン
echo "5. プロジェクトのクローン..."
git clone https://github.com/Digitalian-pon/crypto-trading-bot.git
cd crypto-trading-bot

# 6. Python依存関係インストール
echo "6. Python依存関係のインストール..."
../trading_env/bin/pip install --upgrade pip
../trading_env/bin/pip install gunicorn flask flask-sqlalchemy flask-login flask-wtf \
    psycopg2-binary requests pandas numpy scikit-learn

# 7. 環境変数ファイル作成
echo "7. 環境変数の設定..."
cat > .env << 'EOF'
GMO_API_KEY=your_gmo_api_key_here
GMO_API_SECRET=your_gmo_api_secret_here
DATABASE_URL=postgresql://trading_user:trading_secure_pass_2024@localhost/trading_db
SESSION_SECRET=ubuntu_trading_session_secret_2024
EOF

echo "重要: .env ファイルの GMO_API_KEY と GMO_API_SECRET を実際の値に変更してください"

# 8. systemdサービスファイル作成（メインアプリ）
echo "8. systemdサービスの設定..."
sudo tee /etc/systemd/system/trading-bot.service > /dev/null << 'EOF'
[Unit]
Description=Crypto Trading Bot
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/crypto-trading-bot
Environment=PATH=/home/ubuntu/trading_env/bin
EnvironmentFile=/home/ubuntu/crypto-trading-bot/.env
ExecStart=/home/ubuntu/trading_env/bin/gunicorn --bind 0.0.0.0:5000 --workers 1 --max-requests 1000 --timeout 120 main:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 9. Webhookサーバーサービス作成
sudo tee /etc/systemd/system/webhook-service.service > /dev/null << 'EOF'
[Unit]
Description=GitHub Webhook Server for Crypto Trading Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/crypto-trading-bot
Environment=PATH=/home/ubuntu/trading_env/bin
ExecStart=/home/ubuntu/trading_env/bin/python webhook_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 10. ログディレクトリとファイル作成
echo "9. ログディレクトリの設定..."
sudo mkdir -p /var/log
sudo touch /var/log/webhook.log
sudo chown ubuntu:ubuntu /var/log/webhook.log

# 11. sudoers設定（パスワードなしでサービス再起動）
echo "10. sudo権限の設定..."
echo "ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart trading-bot.service" | sudo tee /etc/sudoers.d/webhook-restart

# 12. ファイアウォール設定
echo "11. ファイアウォールの設定..."
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 5000/tcp    # トレーディングボット
sudo ufw allow 8080/tcp    # Webhook
sudo ufw --force enable

# 13. サービス有効化・開始
echo "12. サービスの開始..."
sudo systemctl daemon-reload
sudo systemctl enable trading-bot.service
sudo systemctl enable webhook-service.service
sudo systemctl start trading-bot.service
sudo systemctl start webhook-service.service

# 14. サービス状態確認
echo "13. サービス状態の確認..."
sleep 5

echo ""
echo "=== トレーディングボットサービス状態 ==="
sudo systemctl status trading-bot.service --no-pager -l

echo ""
echo "=== Webhookサービス状態 ==="
sudo systemctl status webhook-service.service --no-pager -l

# 15. セットアップ完了メッセージ
echo ""
echo "========================================="
echo "    Ubuntu セットアップ完了！"
echo "========================================="
echo ""
echo "次の手順を実行してください："
echo ""
echo "1. 環境変数の設定："
echo "   nano /home/ubuntu/crypto-trading-bot/.env"
echo "   GMO_API_KEY と GMO_API_SECRET を実際の値に変更"
echo ""
echo "2. サービス再起動："
echo "   sudo systemctl restart trading-bot.service"
echo ""
echo "3. GitHubのWebhook設定："
echo "   - Settings > Webhooks > Add webhook"
echo "   - Payload URL: http://49.212.131.248:8080/webhook"
echo "   - Content type: application/json"
echo "   - Secret: crypto_trading_bot_webhook_secret_2024"
echo ""
echo "4. アクセス確認："
echo "   http://49.212.131.248:5000"
echo ""
echo "ログ確認コマンド："
echo "sudo journalctl -u trading-bot.service -f"
echo "sudo tail -f /var/log/webhook.log"
echo ""
echo "サービス管理："
echo "sudo systemctl start/stop/restart trading-bot.service"
echo "sudo systemctl start/stop/restart webhook-service.service"