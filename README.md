# 暗号通貨自動取引システム

GMO Coin APIを活用したAI駆動の暗号通貨自動取引システムです。複数のテクニカル指標を分析し、リスク管理機能を備えた自動取引を実行します。

## 主な機能

### 🤖 AI駆動の取引決定
- 複数のテクニカル指標（RSI、MACD、ボリンジャーバンド、SMA、EMA）による分析
- 機械学習アルゴリジムによる売買シグナル生成
- リアルタイム市場データ処理

### 📊 高度なデータ可視化
- Google Chartsを使用したインタラクティブなチャート
- 複数の時間軸（5分、15分、30分、1時間、4時間、1日）
- テクニカル指標の切り替え表示機能
- リアルタイム価格更新

### 🛡️ リスク管理
- ストップロス機能（パーセンテージベース）
- ポジションサイズ計算
- 取引履歴とパフェーマンス追跡

### 🔐 セキュアな認証
- Flask-Loginによるユーザー認証
- GMO Coin API資格情報の安全な保存
- PostgreSQLデータベースによる永続化

### 🎯 対応通貨ペア
- BTC/JPY
- ETH/JPY  
- LTC/JPY
- XRP/JPY
- DOGE/JPY

## 技術スタック

- **バックエンド**: Python, Flask, SQLAlchemy
- **データベース**: PostgreSQL
- **機械学習**: scikit-learn, pandas, numpy
- **フロントエンド**: Bootstrap, Google Charts
- **API**: GMO Coin API
- **認証**: Flask-Login

## アーキテクチャ

```
├── app.py                   # メインアプリケーション
├── models.py               # データベースモデル
├── routes/                 # ルート定義
│   ├── auth.py            # 認証関連
│   ├── dashboard.py       # ダッシュボード
│   ├── api.py             # API エンドポイント
│   └── settings.py        # 設定画面
├── services/              # ビジネスロジック
│   ├── trading_bot.py     # 取引ボット
│   ├── data_service.py    # データ取得サービス
│   ├── gmo_api.py         # GMO API クライアント
│   └── logger_service.py  # ログサービス
├── static/                # 静的ファイル
└── templates/             # HTMLテンプレート
```

## セットアップ

### 必要な環境変数

```bash
DATABASE_URL=postgresql://user:password@host:port/database
GMO_API_KEY=your_gmo_api_key
GMO_API_SECRET=your_gmo_api_secret
SESSION_SECRET=your_session_secret
```

### インストール

1. 依存関係のインストール
```bash
pip install -r requirements.txt
```

2. データベースの初期化
```bash
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

3. アプリケーションの起動
```bash
gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
```

## 機能詳細

### 自動取引機能
- 1分間隔での市場データ監視
- テクニカル指標による売買シグナル生成
- 自動注文実行とポジション管理

### チャート機能
- リアルタイム価格表示
- 複数のテクニカル指標のオーバーレイ表示
- 時間軸とインジケーターの動的切り替え

### ログ機能
- 全取引の詳細ログ
- APIエラー監視
- パフォーマンス統計

## 安全性とリスク管理

- 環境変数による機密情報管理
- ストップロス機能による損失制限
- ポジションサイズの自動計算
- 取引履歴の完全記録

## ライセンス

プライベートプロジェクト - 無断転用禁止

## 注意事項

このシステムは教育・研究目的で開発されています。実際の取引には十分な検証とリスク管理を行ってください。
暗号通貨取引には高いリスクが伴います。