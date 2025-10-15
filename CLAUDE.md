# GMO Coin 24時間自動トレーディングボット - プロジェクト完了記録

## 🎯 プロジェクト概要
- **作成日**: 2025年8月7日
- **ユーザー**: thuyo (thuyoshi1@gmail.com)
- **目的**: GMO CoinでのBTC/JPY現物取引システム構築（旧: DOGE/JPYレバレッジ取引）
- **状態**: ✅ 完全稼働中（BTC現物取引・トレンドフォロー戦略）

## 🌐 稼働中システム情報
- **ローカルダッシュボード**: http://localhost:8082 ✅ **正常稼働中**
- **GitHub**: https://github.com/Digitalian-pon/crypto-trading-bot
- **監視通貨**: **BTC/JPY** (現物取引)
- **時間足**: 30分足（長期トレンド重視）
- **更新間隔**: 60秒間隔でシグナルチェック

## 💰 アカウント情報
- **残高**: 1,050 JPY + 0.00002090 BTC
- **API認証**: GMO Coin API連携済み
- **API Key**: FXhblJAz9Ql0G3pCo5p/+S9zkFw6r2VC (32文字)
- **API Secret**: /YiZoJlRybHnKAO78go6Jt9LKQOS/EwEEe47UyEl6YbXo7XA84fL+Q/k3AEJeCBo (64文字)

## 📊 技術仕様
### 現物取引システム:
- **取引タイプ**: 現物取引のみ（レバレッジなし）
- **BUY取引**: JPY残高でBTC購入
- **SELL取引**: BTC残高を全額売却
- **ポジション管理**: なし（現物なので強制ロスカットなし）

### 売買判断ロジック（トレンドフォロー戦略）:
- **RSI**: トレンド方向のみ - 下降中は戻り売り、上昇中は押し目買い
- **MACD**: トレンドフィルター付き - トレンド方向のシグナルのみ採用
- **ボリンジャーバンド**: トレンド方向のみ - 逆張り禁止
- **EMA**: 20/50期間でトレンド判定

### リスク管理:
- **投資額**: 残高の95%
- **最小BTC取引単位**: 0.0001 BTC
- **最小JPY残高**: 100円
- **取引間隔**: 60秒

## 🛠️ システム構成
### ファイル構造:
```
crypto-trading-bot/
├── simple_spot_bot.py    # 現物取引専用ボット
├── app.py                # Flaskメインアプリ
├── config.py             # 設定管理
├── models.py             # データベースモデル
├── services/
│   ├── gmo_api.py                 # GMO Coin API
│   ├── technical_indicators.py    # テクニカル指標
│   ├── enhanced_trading_logic.py  # トレンドフォロー売買ロジック
│   └── data_service.py            # データ取得
└── final_dashboard.py    # ダッシュボード
```

### 主要機能:
- ✅ BTC/JPY現物取引
- ✅ 30分足長期トレンド分析
- ✅ トレンドフォロー戦略（落ちるナイフ回避）
- ✅ リアルタイム価格監視
- ✅ 技術指標分析 (RSI, MACD, ボリンジャーバンド, EMA)
- ✅ ウェブダッシュボード (PC/スマホ対応)
- ✅ PM2自動復旧機能

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
pm2 status                    # 状態確認
pm2 logs btc-spot-bot        # ログ確認
pm2 restart btc-spot-bot     # 再起動
pm2 stop btc-spot-bot        # 停止
```

## 🔄 呼び出し方法
次回このプロジェクトについて質問する際は以下のように呼び出してください:

**"GMO Coinトレーディングボットの件"** または
**"BTC/JPY現物取引システムの件"** または
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
default_symbol = BTC_JPY    # DOGE_JPY → BTC_JPY
default_timeframe = 30m      # 5m → 30m
```

#### 3. **データベース更新**
```sql
UPDATE trading_settings SET currency_pair = 'BTC_JPY', timeframe = '30m'
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

#### 5. **ダッシュボード完全対応** (2025年10月15日追加)
**問題**: ダッシュボードが DOGE_JPY のまま表示されていた
**原因**: `final_dashboard.py` 内に DOGE_JPY がハードコードされていた（5箇所）

**修正内容**:
```python
# Line 58: ポジション取得
self.api_positions = api.get_positions('BTC_JPY')  # DOGE_JPY → BTC_JPY

# Line 77: マーケットデータ取得
market_data_response = self.data_service.get_data_with_indicators('BTC_JPY', interval='30m')  # DOGE_JPY/5m → BTC_JPY/30m

# Line 116: ティッカーAPI
response = requests.get('https://api.coin.z.com/public/v1/ticker?symbol=BTC_JPY', timeout=5)  # DOGE_JPY → BTC_JPY

# Line 303: HTMLタイトル
<title>BTC/JPY取引ダッシュボード</title>  # DOGE/JPY → BTC/JPY

# Line 373-374: ヘッダーと価格表示
<h1>🪙 BTC/JPY 現物取引ダッシュボード</h1>
<div class="price">¥{self.current_price:,.0f}</div>  # 小数点3桁 → カンマ区切り整数
```

**動作確認結果**:
- ✅ ダッシュボード正常起動 (port 8082)
- ✅ BTC/JPY 価格正常表示 (~17,000,000円)
- ✅ 30分足データ取得・表示
- ✅ トレンドフォローシグナル正常表示
- ✅ テクニカル指標 (RSI, MACD, BB) 正常表示

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
- **2025年10月15日**: ダッシュボードBTC/JPY表示完全修正 ✅

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

**最終更新**: 2025年10月15日
**ステータス**: 24時間完全稼働中 ✅ (BTC現物取引)
**ボット**: btc-spot-bot (PM2監視下)
**ダッシュボード**: http://localhost:8082/ ✅ **BTC/JPY正常表示中**
**取引方式**: 現物取引（レバレッジなし）
**シンボル**: 🪙 BTC/JPY
**時間足**: ⏱️ 30分足（長期トレンド重視）
**アルゴリズム**: 🎯 完全トレンドフォロー（落ちるナイフ回避・押し目買い・戻り売り）
**インジケーター**: ✅ RSI, MACD, BB, EMA全て正常計算・シグナル発動
**自動復旧**: 🛡️ PM2によるクラッシュ時自動再起動・Termux復活対応
**GitHubコミット**:
- c6040aa - BTC現物取引への完全移行
- 11ab097 - ダッシュボードBTC/JPY表示完全対応
