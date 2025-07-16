# GMO Coin Trading Dashboard　（更新２）

リアルタイム暗号通貨取引ダッシュボード - DOGE/JPY専用

## 概要

GMOコインAPIを使用したリアルタイム取引監視システムです。実際のポジション、残高、取引履歴を表示し、自動的な売買シグナルを生成します。

## 主な機能

- **リアルタイム価格表示**: DOGE/JPYの現在価格を30秒間隔で更新
- **口座残高監視**: 利用可能金額と証拠金余力をリアルタイム表示
- **ポジション管理**: 保有ポジションの詳細と含み損益を計算
- **取引履歴**: 最新の取引記録を表示
- **自動売買シグナル**: 技術的指標に基づく売買判断

## 技術スタック

- **Backend**: Python 3.9+ with Flask
- **API**: GMO Coin Private/Public API
- **Database**: SQLite (PostgreSQL対応)
- **Frontend**: HTML/CSS/JavaScript
- **Charts**: Google Charts
- **Deployment**: Gunicorn (VPS対応)

## インストール方法

### 必要な依存関係

```bash
pip install -r requirements.txt
```

### 設定ファイル

`setting.ini`を作成し、GMOコインのAPIキーを設定してください：

```ini
[api_credentials]
api_key = YOUR_API_KEY
api_secret = YOUR_API_SECRET

[application]
debug = True
secret_key = your_secret_key_here

[database]
database_uri = sqlite:///crypto_trader.db
```

## 使用方法

### 開発環境

```bash
python3 main.py
```

### 本番環境 (VPS)

```bash
gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
```

## VPSデプロイメント

### 自動デプロイ

```bash
# VPS上で実行
bash DIRECT_VPS_SETUP.sh
```

### 手動デプロイ

```bash
# 依存関係のインストール
pip3 install requests

# ダッシュボードの起動
python3 vps_real_api_dashboard.py
```

## API仕様

### エンドポイント

- `GET /` - メインダッシュボード
- `GET /dashboard` - ダッシュボード表示
- `GET /api/data` - JSON形式のデータ取得
- `GET /api/ticker` - 現在価格取得
- `GET /api/balance` - 口座残高取得

### レスポンス例

```json
{
  "current_price": 30.223,
  "volume": "17532145",
  "balance": {
    "available": 813.0,
    "transferable": 813.0
  },
  "positions": [
    {
      "symbol": "DOGE_JPY",
      "side": "BUY",
      "size": "20",
      "price": "30.407"
    }
  ],
  "total_pnl": -3.68,
  "timestamp": "2025-07-14T08:45:00"
}
```

## セキュリティ

- APIキーは環境変数または設定ファイルで管理
- HTTPS対応 (本番環境推奨)
- セッション管理とCSRF保護
- 入力値検証

## 監視機能

- リアルタイム価格監視
- ポジション変動アラート
- 利益/損失しきい値通知
- システムヘルスチェック

## トラブルシューティング

### よくある問題

1. **APIキーエラー**: `setting.ini`の設定を確認
2. **接続エラー**: ネットワーク接続とファイアウォール設定を確認
3. **ポート5000が使用中**: `pkill -f python3`で既存プロセスを終了

### ログ確認

```bash
tail -f api_dashboard.log
```

## 開発者向け情報

### プロジェクト構造

```
├── main.py              # メインアプリケーション
├── app.py               # Flask設定
├── models.py            # データモデル
├── config.py            # 設定管理
├── vps_real_api_dashboard.py  # VPS用ダッシュボード
├── setting.ini          # 設定ファイル
├── templates/           # HTMLテンプレート
├── static/             # CSS/JS/画像
└── requirements.txt    # 依存関係
```

### 開発環境セットアップ

```bash
# 仮想環境作成
python3 -m venv venv
source venv/bin/activate

# 依存関係インストール
pip install -r requirements.txt

# 開発サーバー起動
python3 main.py
```

## ライセンス

MIT License

## 作者

- 開発者: Crypto Trading System Team
- 連絡先: support@cryptotrading.com

## 更新履歴

- 2025-07-14: 初期リリース - GMO Coin API統合
- 2025-07-14: VPS対応版リリース
- 2025-07-14: リアルタイム監視機能追加

## 注意事項

- 本システムは教育・学習目的で作成されています
- 実際の取引は自己責任で行ってください
- GMOコインの利用規約を遵守してください
