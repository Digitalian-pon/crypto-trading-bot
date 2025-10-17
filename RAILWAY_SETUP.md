# Railway デプロイメント設定ガイド

## 🚀 Railway環境変数設定

Railwayダッシュボードで以下の環境変数を設定してください:

### 必須環境変数

```
GMO_API_KEY=FXhblJAz9Ql0G3pCo5p/+S9zkFw6r2VC
GMO_API_SECRET=/YiZoJlRybHnKAO78go6Jt9LKQOS/EwEEe47UyEl6YbXo7XA84fL+Q/k3AEJeCBo
PORT=8080
```

## 📋 設定手順

### 1. Railwayダッシュボードにアクセス
https://railway.app/project/web-production-1f4ce

### 2. Variables タブを開く
プロジェクトページで「Variables」または「Environment」タブを選択

### 3. 環境変数を追加

#### GMO_API_KEY
- Key: `GMO_API_KEY`
- Value: `FXhblJAz9Ql0G3pCo5p/+S9zkFw6r2VC`

#### GMO_API_SECRET
- Key: `GMO_API_SECRET`
- Value: `/YiZoJlRybHnKAO78go6Jt9LKQOS/EwEEe47UyEl6YbXo7XA84fL+Q/k3AEJeCBo`

#### PORT
- Key: `PORT`
- Value: `8080`

### 4. デプロイメントを再起動

環境変数を設定したら、「Redeploy」ボタンをクリックしてアプリケーションを再起動してください。

## ✅ 動作確認

デプロイ完了後、以下のURLにアクセスして動作確認:
https://web-production-1f4ce.up.railway.app/

### 正常に動作している場合の表示:
- ✅ DOGE/JPY価格が表示される（¥27.xxx など）
- ✅ 24時間高値/安値が表示される
- ✅ 残高情報が表示される
- ✅ ポジション情報が表示される
- ✅ 取引シグナルが表示される

### 問題がある場合:
- ❌ 価格が ¥0.00 のまま
- ❌ 「システム初期化中」のまま変わらない
- ❌ 残高情報取得エラー

→ 環境変数が正しく設定されているか再確認してください

## 🔧 トラブルシューティング

### ログの確認方法
1. Railwayダッシュボード → Deployments タブ
2. 最新のデプロイメントをクリック
3. Logs を確認

### よくあるエラー

#### "User not found and no environment variables set"
→ 環境変数が設定されていません。上記の手順で設定してください。

#### "API authentication failed"
→ APIキーが正しくない可能性があります。コピー&ペースト時にスペースが入っていないか確認してください。

#### "Connection timeout"
→ Railway側のネットワーク問題の可能性があります。数分待ってから再試行してください。

## 📞 サポート

問題が解決しない場合は、Railwayのログを確認し、エラーメッセージを報告してください。
