# PM2自動復旧システム設定記録

## 実装日時
2025年9月23日

## 設定内容

### 1. PM2インストール
```bash
npm install -g pm2
```

### 2. ダッシュボード起動（自動再起動機能付き）
```bash
pm2 start final_dashboard.py --name "crypto-dashboard" --interpreter python3 --restart-delay=3000 --max-restarts=10
```

### 3. PM2設定保存
```bash
pm2 save
```

### 4. Termux起動時自動復活設定
~/.bashrcに以下を追加:
```bash
pm2 resurrect
```

## 自動復旧機能仕様
- **プロセス名**: crypto-dashboard
- **再起動遅延**: 3秒
- **最大再起動回数**: 10回
- **監視対象**: final_dashboard.py (ポート8082)

## 操作コマンド
- **状態確認**: `pm2 status`
- **再起動**: `pm2 restart crypto-dashboard`
- **停止**: `pm2 stop crypto-dashboard`
- **ログ確認**: `pm2 logs crypto-dashboard`

## 効果
- ダッシュボードクラッシュ時の自動復旧
- Termux再起動時の自動プロセス復活
- 24時間安定稼働の保証