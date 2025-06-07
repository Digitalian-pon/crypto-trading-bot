# VPS セットアップガイド - さくらのVPS + CentOS Stream 9

## 概要
このガイドでは、さくらのVPS（月額685円）にCentOS Stream 9を使用して、暗号通貨トレーディングボットを24時間稼働させる方法を説明します。

## 1. さくらのVPS契約

### 契約手順
1. [さくらのVPS](https://vps.sakura.ad.jp/) にアクセス
2. **512MBプラン（月額671円）** を選択
3. 契約時設定：
   - **OS**: CentOS Stream 9
   - **管理ユーザー**: centos
   - **認証方式**: SSH公開鍵 または パスワード

### 契約完了後
- IPアドレスが発行されます
- SSH接続情報を控えておく

## 2. VPSへの接続

### SSH接続
```bash
ssh centos@あなたのVPS_IP
```

初回接続時はフィンガープリントの確認が表示されるので `yes` を入力。

## 3. 自動セットアップの実行

### セットアップスクリプトのダウンロード・実行
```bash
# GitHubからプロジェクトをクローン
git clone https://github.com/Digitalian-pon/crypto-trading-bot.git
cd crypto-trading-bot

# セットアップスクリプトを実行可能にして実行
chmod +x centos_setup.sh
./centos_setup.sh
```

セットアップには5-10分程度かかります。

## 4. 環境変数の設定

### GMO Coin APIキーの設定
```bash
nano /home/centos/crypto-trading-bot/.env
```

以下の値を実際のAPIキーに変更：
```
GMO_API_KEY=あなたの実際のAPIキー
GMO_API_SECRET=あなたの実際のAPIシークレット
DATABASE_URL=postgresql://trading_user:trading_secure_pass_2024@localhost/trading_db
SESSION_SECRET=centos_trading_session_secret_2024
```

### サービス再起動
```bash
sudo systemctl restart trading-bot.service
sudo systemctl restart webhook-service.service
```

## 5. GitHub Webhook設定

### GitHub側の設定
1. リポジトリページで **Settings** > **Webhooks** > **Add webhook**
2. 設定項目：
   - **Payload URL**: `http://あなたのVPS_IP:8080/webhook`
   - **Content type**: `application/json`
   - **Secret**: `crypto_trading_bot_webhook_secret_2024`
   - **Events**: `Just the push event`
   - **Active**: チェック

### 動作確認
GitHubにコードをpushすると、VPSが自動で更新されます。

## 6. アクセス確認

### Webインターフェース
ブラウザで以下にアクセス：
```
http://あなたのVPS_IP:5000
```

ダッシュボードが表示されれば成功です。

## 7. ログ確認・管理

### サービス状態確認
```bash
# トレーディングボット状態
sudo systemctl status trading-bot.service

# Webhook サーバー状態
sudo systemctl status webhook-service.service
```

### ログ確認
```bash
# トレーディングボットログ
sudo journalctl -u trading-bot.service -f

# Webhookログ
sudo tail -f /var/log/webhook.log
```

### サービス管理
```bash
# サービス再起動
sudo systemctl restart trading-bot.service
sudo systemctl restart webhook-service.service

# サービス停止
sudo systemctl stop trading-bot.service

# サービス開始
sudo systemctl start trading-bot.service
```

## 8. トラブルシューティング

### よくある問題

**Q: サービスが起動しない**
```bash
# エラーログを確認
sudo journalctl -u trading-bot.service -n 50

# 設定ファイルを確認
nano /home/centos/crypto-trading-bot/.env
```

**Q: Webページにアクセスできない**
```bash
# ファイアウォール確認
sudo firewall-cmd --list-all

# ポート5000が開いているか確認
sudo ss -tlnp | grep 5000
```

**Q: GitHubからの自動更新が動作しない**
```bash
# Webhookログを確認
sudo tail -f /var/log/webhook.log

# ポート8080が開いているか確認
sudo ss -tlnp | grep 8080
```

## 9. セキュリティ設定（推奨）

### SSH設定強化
```bash
sudo nano /etc/ssh/sshd_config
```

以下を設定：
```
PermitRootLogin no
PasswordAuthentication no  # 公開鍵認証のみ
Port 2222  # デフォルトポート変更
```

### 定期更新設定
```bash
# 自動セキュリティ更新を有効化
sudo dnf install -y dnf-automatic
sudo systemctl enable --now dnf-automatic.timer
```

## 10. 費用とメンテナンス

### 月額費用
- **VPS**: 671円/月
- **電気代**: VPS側なので不要
- **合計**: 671円/月

### メンテナンス
- 月1回程度のシステム更新推奨
- トレードログの定期確認

## サポート

問題が発生した場合は、以下のログ情報を確認してください：
1. システムログ: `sudo journalctl -xe`
2. アプリケーションログ: `sudo journalctl -u trading-bot.service -f`
3. Webhookログ: `sudo tail -f /var/log/webhook.log`