#!/bin/bash

# VPS側のWebhook自動更新システム設定スクリプト

echo "=== Webhook自動更新システムのセットアップ開始 ==="

# 1. sudoアクセスの確認
if [ "$EUID" -eq 0 ]; then
    echo "rootユーザーでは実行しないでください。通常ユーザーで実行してください。"
    exit 1
fi

# 2. 必要なディレクトリの確認
echo "1. ディレクトリ構造の確認..."
REPO_DIR="/home/ubuntu/crypto-trading-bot"
if [ ! -d "$REPO_DIR" ]; then
    echo "エラー: $REPO_DIR が見つかりません"
    echo "先にGitリポジトリをクローンしてください："
    echo "git clone https://github.com/Digitalian-pon/crypto-trading-bot.git"
    exit 1
fi

# 3. Webhook サーバーファイルをコピー
echo "2. Webhookサーバーの設定..."
if [ -f "./webhook_server.py" ]; then
    cp ./webhook_server.py "$REPO_DIR/"
    chmod +x "$REPO_DIR/webhook_server.py"
    echo "webhook_server.py をコピーしました"
else
    echo "エラー: webhook_server.py が見つかりません"
    exit 1
fi

# 4. systemdサービスファイルの設置
echo "3. systemdサービスの設定..."
if [ -f "./webhook-service.service" ]; then
    sudo cp ./webhook-service.service /etc/systemd/system/
    echo "systemdサービスファイルをコピーしました"
else
    echo "エラー: webhook-service.service が見つかりません"
    exit 1
fi

# 5. ログディレクトリの作成
echo "4. ログディレクトリの設定..."
sudo touch /var/log/webhook.log
sudo chown ubuntu:ubuntu /var/log/webhook.log

# 6. sudoers設定（パスワードなしでsystemctl restart）
echo "5. sudo権限の設定..."
echo "ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart trading-bot.service" | sudo tee /etc/sudoers.d/webhook-restart

# 7. ファイアウォール設定
echo "6. ファイアウォールの設定..."
sudo ufw allow 8080 comment "Webhook server"

# 8. systemdサービスの有効化・開始
echo "7. Webhookサービスの開始..."
sudo systemctl daemon-reload
sudo systemctl enable webhook-service.service
sudo systemctl start webhook-service.service

# 9. サービス状態の確認
echo "8. サービス状態の確認..."
sleep 3
if sudo systemctl is-active --quiet webhook-service.service; then
    echo "✓ Webhookサービスが正常に起動しました"
else
    echo "✗ Webhookサービスの起動に失敗しました"
    sudo systemctl status webhook-service.service
    exit 1
fi

# 10. セットアップ完了
echo ""
echo "=== セットアップ完了 ==="
echo "Webhookサーバーがポート8080で起動しています"
echo ""
echo "次の手順："
echo "1. GitHubリポジトリの設定 > Webhooks に移動"
echo "2. 以下の設定でWebhookを追加："
echo "   - Payload URL: http://あなたのVPS_IP:8080/webhook"
echo "   - Content type: application/json"
echo "   - Secret: crypto_trading_bot_webhook_secret_2024"
echo "   - Events: Just the push event"
echo "   - Active: チェック"
echo ""
echo "設定後、GitHubにコードをpushすると自動でVPSが更新されます"
echo ""
echo "ログ確認コマンド："
echo "sudo tail -f /var/log/webhook.log"
echo ""
echo "サービス管理コマンド："
echo "sudo systemctl status webhook-service.service"
echo "sudo systemctl restart webhook-service.service"