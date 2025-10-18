# GMO Coin Advanced Trading Bot - Final Version

🎯 **完全自動取引システム** - 24時間稼働中のDOGE/JPY取引ボット

## 🎯 クイックスタート

### 1. **ダッシュボードアクセス**
```
http://localhost:8082/
```
**メインダッシュボード**: `final_dashboard.py` ⭐ **推奨・最新版**

### 2. **アプリケーション起動**
```bash
python main.py          # メインアプリ (ポート5000)
python final_dashboard.py  # ダッシュボード (ポート8082)
```

## 📊 現在の稼働状況

- **取引通貨**: DOGE/JPY (5分足)
- **取引方式**: レバレッジ取引対応
- **監視間隔**: 30秒間隔更新
- **自動取引**: 24時間稼働中
- **API接続**: GMO Coin API連携済み

## 🚀 最新機能 (Final Version)

### 🔧 技術的改善
- **SMA → EMA変更**: より敏感で応答性の高い指数移動平均に変更
- **動的通貨ペア選択**: BTC/ETH/XRP/DOGE_JPYから選択可能
- **時間足設定**: 1m/5m/15m/30m/1h/4h/1dから選択可能
- **設定画面**: Web UIから通貨ペアと時間足を動的変更

### 📊 アルゴリズム詳細

#### **多層意思決定システム**
1. **機械学習予測**: Random Forest分類器による価格方向予測
2. **テクニカル分析**: EMAベース重み付きシグナル統合
3. **リスク管理**: 厳格な損切り・利確・ポジション管理

## 主な機能

- **🔄 動的通貨ペア**: BTC_JPY, ETH_JPY, XRP_JPY, DOGE_JPY対応
- **⏰ 複数時間足**: 1分足〜日足まで選択可能
- **🤖 機械学習**: Random Forestによる価格予測
- **📈 EMAベース分析**: 高応答性の指数移動平均
- **🛡️ リスク管理**: 2%損切り・4%利確の自動執行
- **📱 リアルタイム監視**: 30秒間隔の価格・シグナル更新

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

[trading]
default_symbol = DOGE_JPY
default_timeframe = 1h
available_symbols = BTC_JPY,ETH_JPY,XRP_JPY,DOGE_JPY
available_timeframes = 1m,5m,15m,30m,1h,4h,1d
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

- `GET /` - メインダッシュボード（動的通貨ペア対応）
- `GET /dashboard` - ダッシュボード表示
- `GET /settings` - 通貨ペア・時間足設定画面
- `GET /api/ticker/<symbol>` - 指定通貨の現在価格取得
- `GET /api/trading-analysis/<symbol>` - リアルタイム取引分析
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

## 24時間稼働監視

### ボット監視・確認方法

#### 基本的な状態確認
```bash
# 現在の状態を確認
python monitor_bot.py status

# 継続監視（5分間隔）
python monitor_bot.py monitor

# カスタム間隔で監視（秒単位）
python monitor_bot.py monitor 300
```

#### 稼働状況チェック項目
- ✅ **Webダッシュボード**: https://web-production-1f4ce.up.railway.app
- ✅ **API応答**: `/api/ticker/DOGE_JPY` エンドポイント
- ✅ **取引ログ**: `logs/trading_bot.log` の最新エントリ
- ✅ **プロセス確認**: Pythonプロセスの実行状態

### ボット再起動方法

#### 手動再起動
```bash
# 完全再起動（推奨）
python restart_bot.py restart

# 停止のみ
python restart_bot.py stop

# 開始のみ
python restart_bot.py start

# プロセス状態確認
python restart_bot.py status

# 強制終了
python restart_bot.py kill
```

#### Railway環境での対処法
1. **Railway Dashboard**でアプリケーションを確認
2. **Deploy**タブで最新のデプロイ状況を確認
3. 問題がある場合は**Redeploy**を実行

### 異常検出時の対応手順

#### 1. 状態確認
```bash
python monitor_bot.py status
```

#### 2. ログ確認
```bash
# 取引ログ確認
tail -f logs/trading_bot.log

# エラーログ確認
tail -f monitor.log
```

#### 3. 再起動実行
```bash
# 自動再起動
python restart_bot.py restart
```

#### 4. Railway環境でのトラブル
- Railway Dashboard: https://railway.app/dashboard
- プロジェクト: web-production-1f4ce
- 手動Redeploy実行

## トラブルシューティング

### よくある問題と解決法

1. **APIキーエラー**
   - `setting.ini`の設定を確認
   - Railway環境変数の確認（`GMO_API_KEY`, `GMO_API_SECRET`）

2. **接続エラー**
   - ネットワーク接続とファイアウォール設定を確認
   - GMO Coin APIのサービス状況を確認

3. **ボットが停止している**
   - `python restart_bot.py restart`で再起動
   - `python monitor_bot.py status`で状態確認

4. **取引が実行されない**
   - 残高不足の確認
   - 取引条件（RSI、MACDなど）の確認
   - `logs/trading_bot.log`でエラー内容を確認

5. **Railway環境でのトラブル**
   - Build失敗: 依存関係を確認
   - メモリ不足: プランのアップグレードを検討
   - 接続タイムアウト: サーバー負荷を確認

### ログファイル一覧
- `logs/trading_bot.log` - メイン取引ログ
- `monitor.log` - 監視ログ
- `restart.log` - 再起動ログ

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

## 🧠 アルゴリズム詳細説明

### **EMAベースの技術分析システム**

#### **1. 指数移動平均 (EMA) 指標**
- **EMA 20**: メイントレンド判定 (SMAより応答性向上)
- **EMA 12/26**: MACD計算用高速/低速ライン
- **ボリンジャーバンド**: EMA20ベースでより敏感な反応

#### **2. 売買シグナル条件（改良版）**

**🟢 買いシグナル（重み付き判定）:**
- RSI < 35 (売られ過ぎ) - 重み: 0.8
- MACD線 > シグナル線 かつ MACD線 > 0 - 重み: 0.6
- 価格 < 下部BBバンド × 1.005 - 重み: 0.7
- 価格 > EMA20 × 1.01 - 重み: 0.5

**🔴 売りシグナル（重み付き判定）:**
- RSI > 65 (買われ過ぎ) - 重み: 0.8
- MACD線 < シグナル線 かつ MACD線 < 0 - 重み: 0.6
- 価格 > 上部BBバンド × 0.995 - 重み: 0.7
- 価格 < EMA20 × 0.99 - 重み: 0.5

**実行条件**: 合計重み ≥ 0.8

#### **3. Random Forest機械学習統合**
- **予測対象**: 次期価格の上昇/下降方向
- **特徴量**: 全テクニカル指標値
- **閾値**: 55%以上の確率でシグナル採用
- **最適化**: グリッドサーチによる日次ハイパーパラメータ調整

#### **4. 動的設定システム**
- **通貨ペア**: Web UI内で瞬時切り替え
- **時間足**: 1分〜日足まで設定変更
- **設定保存**: `setting.ini`に永続保存

### **リスク管理（強化版）**
- **ポジションサイズ**: 残高の5%まで
- **損切り**: 2%下落で即座実行
- **利確**: 4%上昇で自動決済
- **最大損失**: 日次10%制限
- **緊急決済**: RSI極値(20未満/80超)で全ポジション決済

## ライセンス

MIT License

## 作者

- 開発者: Crypto Trading System Team
- 連絡先: support@cryptotrading.com

## 更新履歴

- 2025-07-14: 初期リリース - GMO Coin API統合
- 2025-07-14: VPS対応版リリース
- 2025-07-14: リアルタイム監視機能追加
- **2025-08-19: 更新３ - EMA移行・動的設定対応**
  - SMA → EMA変更で応答性向上
  - 動的通貨ペア選択機能追加
  - 時間足設定機能追加
  - Web UI設定画面実装

## 注意事項

- 本システムは教育・学習目的で作成されています
- 実際の取引は自己責任で行ってください
- GMOコインの利用規約を遵守してください
# Railway Deploy Trigger Sat Oct 18 19:55:00 JST 2025
# DOGE_JPY Leverage Trading System - Debugging API calls
# Latest: Detailed logging to identify Railway API issues

