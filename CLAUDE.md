# GMO Coin 24時間自動トレーディングボット - プロジェクト完了記録

## 🎯 プロジェクト概要
- **作成日**: 2025年8月7日
- **ユーザー**: thuyo (thuyoshi1@gmail.com)
- **目的**: GMO CoinでのDOGE/JPYレバレッジ取引システム構築
- **状態**: ✅ 完全稼働中（DOGEレバレッジ取引・トレンドフォロー戦略）

## 🌐 稼働中システム情報
- **ローカルダッシュボード**: http://localhost:8082 ✅ **正常稼働中**
- **GitHub**: https://github.com/Digitalian-pon/crypto-trading-bot
- **監視通貨**: **DOGE/JPY** (レバレッジ取引)
- **時間足**: 5分足（短期トレード）
- **更新間隔**: 60秒間隔でシグナルチェック

## 💰 アカウント情報
- **残高**: 1,050 JPY + 0.00002090 BTC
- **API認証**: GMO Coin API連携済み
- **API Key**: FXhblJAz9Ql0G3pCo5p/+S9zkFw6r2VC (32文字)
- **API Secret**: /YiZoJlRybHnKAO78go6Jt9LKQOS/EwEEe47UyEl6YbXo7XA84fL+Q/k3AEJeCBo (64文字)

## 📊 技術仕様
### レバレッジ取引システム:
- **取引タイプ**: レバレッジ取引（空売り対応）
- **BUY取引**: ロングポジション（価格上昇で利益）
- **SELL取引**: ショートポジション（価格下降で利益=空売り）
- **ポジション管理**: 自動損切り・利確・反転シグナル決済

### 売買判断ロジック（トレンドフォロー戦略）:
- **RSI**: トレンド方向のみ - 下降中は戻り売り、上昇中は押し目買い
- **MACD**: トレンドフィルター付き - トレンド方向のシグナルのみ採用
- **ボリンジャーバンド**: トレンド方向のみ - 逆張り禁止
- **EMA**: 20/50期間でトレンド判定

### リスク管理:
- **投資額**: 残高の95%
- **損切り**: -3%で自動決済
- **利確**: +5%で自動決済
- **最小DOGE取引単位**: 10 DOGE
- **取引間隔**: 60秒

## 🛠️ システム構成
### ファイル構造:
```
crypto-trading-bot/
├── leverage_trading_bot.py  # DOGEレバレッジ取引ボット
├── railway_app.py           # Railway用統合アプリ
├── app.py                   # Flaskメインアプリ
├── config.py                # 設定管理
├── models.py                # データベースモデル
├── services/
│   ├── gmo_api.py                 # GMO Coin API
│   ├── technical_indicators.py    # テクニカル指標
│   ├── enhanced_trading_logic.py  # トレンドフォロー売買ロジック
│   └── data_service.py            # データ取得
└── final_dashboard.py       # ダッシュボード
```

### 主要機能:
- ✅ DOGE/JPYレバレッジ取引（BUY/SELL両方向）
- ✅ 5分足短期トレンド分析
- ✅ トレンドフォロー戦略（落ちるナイフ回避）
- ✅ 自動損切り・利確システム
- ✅ リアルタイム価格監視
- ✅ 技術指標分析 (RSI, MACD, ボリンジャーバンド, EMA)
- ✅ ウェブダッシュボード (PC/スマホ対応)
- ✅ PM2自動復旧機能
- ✅ Railway対応（ボット+ダッシュボード同時起動）

## 🚨 重要な設定
### 環境変数:
```
GMO_API_KEY = FXhblJAz9Ql0G3pCo5p/+S9zkFw6r2VC
GMO_API_SECRET = /YiZoJlRybHnKAO78go6Jt9LKQOS/EwEEe47UyEl6YbXo7XA84fL+Q/k3AEJeCBo
```

## 📱 操作方法
### ダッシュボード確認:
1. http://localhost:8082 にアクセス
2. リアルタイム価格・シグナル確認
3. 60秒ごと自動更新

### PM2管理:
```bash
pm2 status                      # 状態確認
pm2 logs doge-leverage-bot     # ログ確認
pm2 restart doge-leverage-bot  # 再起動
pm2 stop doge-leverage-bot     # 停止
```

## 🔄 呼び出し方法
次回このプロジェクトについて質問する際は以下のように呼び出してください:

**"GMO Coinトレーディングボットの件"** または
**"DOGE/JPYレバレッジ取引システムの件"** または
**"crypto trading bot project"**

## 🔄 BTC現物取引への完全移行 (2025年10月12日)
### 問題概要：
- **DOGEレバレッジ取引で大損失**: 29円でSELL → 33円で強制決済 = -13%損失（9件全て）
- **問題の根本原因**:
  - DOGEのボラティリティが高すぎる（30分足でも激しい変動）
  - レバレッジ取引で証拠金維持率低下 → 強制ロスカット
  - トレンドフォロー戦略の限界（短期逆張りで大損失）

### 実施した完全移行：

#### 1. **新規現物取引ボット作成** (`simple_spot_bot.py`)
```python
class SimpleSpotTradingBot:
    """
    シンプルな現物取引ボット - BTC/JPYのみ
    レバレッジなし、ポジション管理なし
    """

    def execute_buy(self, current_price, jpy_balance):
        """BUY実行 - JPYでBTC購入"""
        max_jpy = jpy_balance * 0.95
        btc_amount = max_jpy / current_price
        btc_amount = round(btc_amount, 4)  # 最小0.0001 BTC

    def execute_sell(self, btc_balance):
        """SELL実行 - BTC全額売却"""
        btc_amount = btc_balance * 0.95
        btc_amount = round(btc_amount, 4)
```

#### 2. **設定ファイル更新** (`setting.ini`)
```ini
[trading]
default_symbol = BTC    # DOGE_JPY → BTC_JPY → BTC (現物)
default_timeframe = 30m  # 5m → 30m
```

#### 3. **データベース更新**
```sql
UPDATE trading_settings SET currency_pair = 'BTC', timeframe = '30m'
```

#### 4. **旧ボット削除・新ボット起動**
```bash
pm2 stop trading-bot         # 旧レバレッジボット停止
pm2 delete trading-bot       # 削除
pm2 start simple_spot_bot.py --name btc-spot-bot --interpreter python3
pm2 save                     # 保存
```

### 動作確認結果：
- ✅ BTC/JPY 30分足データ取得成功 (45本)
- ✅ テクニカル指標計算成功 (RSI=42.07, MACD=-37171/-13126)
- ✅ トレンドフォローシグナル検出 (SELL signal, confidence 1.50)
- ✅ 残高確認成功 (JPY: 1,050円, BTC: 0.00002090)
- ✅ PM2監視下で正常稼働中

### 現物取引のメリット：
1. **強制ロスカットなし**: 現物なのでBTCを保有し続けられる
2. **ボラティリティ削減**: BTCはDOGEより価格安定
3. **リスク管理改善**: レバレッジなしで安全
4. **シンプルな取引**: BUY/SELL のみ、ポジション管理不要

### 技術詳細：
- **新規ファイル**: `simple_spot_bot.py` (209行)
- **修正ファイル**: `setting.ini`, database, `final_dashboard.py`
- **GitHubコミット**:
  - c6040aa - 🔄 Complete migration to BTC spot trading
  - 11ab097 - 🖥️ Update dashboard to display BTC/JPY spot trading
- **PM2プロセス**: btc-spot-bot (online)
- **ダッシュボード**: dashboard (online, port 8082)

#### 5. **正しいシンボルへの修正** (2025年10月15日)
**重大発見**: BTC_JPY はレバレッジ取引専用シンボルだった！

**GMO Coin APIの仕様**:
- ✅ **BTC** = 現物取引（スポット）シンボル
- ❌ **BTC_JPY** = レバレッジ取引専用シンボル
- 最小単位: 0.0001 BTC（両方同じ）

**修正内容**:
```ini
# setting.ini
default_symbol = BTC  # BTC_JPY → BTC

# database
UPDATE trading_settings SET currency_pair = 'BTC'
```

```python
# final_dashboard.py - シンボル修正
api.get_positions('BTC')  # BTC_JPY → BTC
get_data_with_indicators('BTC', interval='30m')
requests.get('https://api.coin.z.com/public/v1/ticker?symbol=BTC')
```

#### 6. **エンドポイント修正** (2025年10月15日)
**問題**: レバレッジ取引用エンドポイントを使用していた

**削除したエンドポイント**:
- ❌ `/v1/openPositions` - ポジション一覧（現物には不要）
- ❌ `/v1/account/margin` - 証拠金情報（現物には不要）

**使用するエンドポイント**:
- ✅ `/v1/account/assets` - 残高取得（JPY, BTC）
- ✅ `/v1/order` - 注文（現物/レバレッジ共通）
- ✅ `/v1/ticker` - 価格情報（symbol=BTC）

**ダッシュボードUI変更**:
```python
# Before (レバレッジ用)
self.api_positions = api.get_positions('BTC')
self.balance_info = api.get_margin_account()

# After (現物用)
self.api_positions = []  # 現物にポジションなし
balance_response = api.get_account_balance()  # /v1/account/assets
self.balance_info = {'jpy': JPY残高, 'btc': BTC残高}
```

**残高表示**:
- JPY残高: 1,094円
- BTC残高: 0.00002090 BTC
- BTC評価額: 355円
- 総資産（JPY換算）: 1,449円

**動作確認結果**:
- ✅ BTC現物シンボルで正常動作
- ✅ /v1/account/assets で残高取得成功
- ✅ ポジション・証拠金の概念を完全削除
- ✅ 現物取引専用ダッシュボードに変更完了
- ✅ http://localhost:8082 で正常表示

---

#### 7. **取引履歴表示修正** (2025年10月16日)
**問題**: ダッシュボードに取引履歴が表示されない

**原因**:
1. `/v1/executions` エンドポイントは `orderId` または `executionId` パラメータが必須
2. `symbol` だけでは使用できない → エラー: Invalid request parameter

**修正内容**:
```python
# services/gmo_api.py
def get_latest_executions(self, symbol=None, page=1, count=100):
    """過去1日の約定履歴取得"""
    endpoint = "/v1/latestExecutions"  # /v1/executions → /v1/latestExecutions
    params = {"page": page, "count": count}
    if symbol:
        params["symbol"] = symbol
    return self._private_request("GET", endpoint, params)
```

**レバレッジボット干渉問題の修正**:
```python
# app.py - 旧レバレッジボットの自動起動を無効化
# Trading bot auto-start DISABLED - Using separate PM2 process (btc-spot-bot)
# from fixed_trading_loop import FixedTradingBot as TradingBot  # コメントアウト
```

**ポート設定の柔軟化**:
```python
# final_dashboard.py
PORT = int(os.environ.get('PORT', 8082))  # ハードコード → 環境変数対応
HOST = os.environ.get('HOST', '0.0.0.0')
```

**動作確認結果**:
- ✅ `/v1/latestExecutions?symbol=BTC&page=1&count=10` - HTTP 200成功
- ✅ 取引履歴取得成功: SELL 0.00002 BTC @ ¥16,817,427（手数料¥1）
- ✅ ダッシュボードに取引履歴が正常表示
- ✅ レバレッジボットの干渉を完全排除

---

## 📞 サポート対応履歴（抜粋）
- **2025年8月22日**: 実取引機能修正
- **2025年8月25日**: レバレッジ取引API完全対応
- **2025年9月12日**: 決済ロジック完全修復
- **2025年9月15日**: トレーディングボット自動取引実行成功確認
- **2025年10月8日**: ログ肥大化問題修正
- **2025年10月9日**: 時間足変更・talib依存関係削除
- **2025年10月11日**: 完全トレンドフォロー戦略実装
- **2025年10月12日**: BTC現物取引への完全移行 ✅
- **2025年10月15日**: 正しいシンボル修正（BTC_JPY→BTC）+ エンドポイント完全修正 ✅
- **2025年10月16日**: 取引履歴表示修正 + レバレッジボット干渉排除 ✅

## 🎯 トレンドフォロー戦略（2025年10月11日実装）
### トレンドフォロー統合マトリクス

| インジケーター | 下降トレンド | 上昇トレンド | 中立 |
|--------------|------------|------------|------|
| **RSI** | 戻り売り（RSI>60）<br>❌ 逆張りBUY禁止 | 押し目買い（RSI<40）<br>❌ 逆張りSELL禁止 | 逆張り許可 |
| **MACD** | ベアリッシュのみ<br>❌ ブリッシュ無視 | ブリッシュのみ<br>❌ ベアリッシュ無視 | 両方向採用 |
| **BB** | 上限で売り<br>❌ 下限無視 | 下限で買い<br>❌ 上限無視 | 両方向採用 |
| **EMA** | EMA<で売り強化 | EMA>で買い強化 | - |

### 期待される効果：
1. **損失削減**: 下降トレンド中の無駄な逆張りBUY排除 → 「落ちるナイフ」回避
2. **収益性向上**: トレンド継続中の押し目買い・戻り売り
3. **安定性向上**: 騙しシグナルの大幅削減
4. **機会損失削減**: トレンド転換時の素早い反転

---

#### 8. **DOGE_JPYレバレッジ取引への復帰** (2025年10月18日)
**ユーザーリクエスト**: BTC現物取引からDOGE_JPYレバレッジ取引に戻す

**実施内容**:
```bash
# BTC現物ボット停止・削除
pm2 stop btc-spot-bot
pm2 delete btc-spot-bot

# DOGEレバレッジボット起動
pm2 start leverage_trading_bot.py --name doge-leverage-bot --interpreter python3
pm2 save
```

**Railway用アプリ更新**:
```python
# railway_app.py - DOGE_JPYレバレッジ取引用に更新
def run_trading_bot():
    """DOGE_JPYレバレッジ取引ボットを実行"""
    from leverage_trading_bot import LeverageTradingBot
    bot = LeverageTradingBot()
    bot.run()
```

**動作確認**:
- ✅ DOGEレバレッジボット正常起動
- ✅ 現在のポジション: SELL 1件（エントリー¥27.41、含み損-1.18%）
- ✅ DOGE_JPY価格: ¥27.73
- ✅ テクニカル指標正常計算中
- ✅ ダッシュボード表示正常（http://localhost:8082）

**GitHubコミット**:
- e54ab7c - 🔄 Revert to DOGE_JPY leverage trading for Railway

---

**最終更新**: 2025年10月18日
**ステータス**: 24時間完全稼働中 ✅ (DOGE_JPYレバレッジ取引)
**ボット**: doge-leverage-bot (PM2監視下)
**ダッシュボード**: http://localhost:8082/ ✅ **DOGEレバレッジ取引 + ポジション・取引履歴表示中**
**取引方式**: レバレッジ取引（BUY/SELL両方向対応・空売り可能）
**シンボル**: 🐕 **DOGE_JPY** (レバレッジ取引専用シンボル)
**時間足**: ⏱️ 5分足（短期トレード）
**アルゴリズム**: 🎯 完全トレンドフォロー（落ちるナイフ回避・押し目買い・戻り売り）
**インジケーター**: ✅ RSI, MACD, BB, EMA全て正常計算・シグナル発動
**自動復旧**: 🛡️ PM2によるクラッシュ時自動再起動・Termux復活対応
**ポジション管理**: ✅ 損切り-3%、利確+5%、反転シグナルで自動決済
**APIエンドポイント**:
- ✅ /v1/account/assets (残高取得)
- ✅ /v1/openPositions (ポジション一覧)
- ✅ /v1/order (注文実行)
- ✅ /v1/closeOrder (ポジション決済)
- ✅ /v1/ticker (価格情報)
- ✅ /v1/latestExecutions (取引履歴・過去1日)
**Railway対応**:
- ✅ railway_app.py でボット+ダッシュボード同時起動
- ✅ 環境変数でAPIキー設定対応
- ✅ エラー時自動再起動機能実装
**GitHubコミット**:
- c6040aa - BTC現物取引への完全移行
- 11ab097 - ダッシュボードBTC/JPY表示完全対応
- 2525585 - シンボル修正（BTC_JPY → BTC）
- ed32d89 - エンドポイント修正（現物取引専用化）
- f16cd9b - 最小取引単位修正（0.0001→0.00001 BTC）
- a7c5715 - 取引履歴表示修正 + レバレッジボット干渉排除
- e54ab7c - 🔄 DOGE_JPYレバレッジ取引への復帰 🆕
