# GMO Coin 24時間自動トレーディングボット - プロジェクト完了記録

## 🎯 プロジェクト概要
- **作成日**: 2025年8月7日
- **ユーザー**: thuyo (thuyoshi1@gmail.com) 
- **目的**: GMO CoinでのDOGE/JPY自動取引システム構築
- **状態**: ✅ 完全稼働中

## 🌐 稼働中システム情報
- **URL**: https://web-production-1f4ce.up.railway.app
- **ホスティング**: Railway (無料24時間稼働)
- **GitHub**: https://github.com/Digitalian-pon/crypto-trading-bot
- **監視通貨**: DOGE/JPY
- **更新間隔**: 30秒自動更新

## 💰 アカウント情報
- **残高**: 779 JPY + BTC(0.0000209) + ETH(0.00957046) + XRP(0.419271) + その他
- **API認証**: GMO Coin API連携済み
- **API Key**: FXhblJAz9Ql0G3pCo5p/+S9zkFw6r2VC (32文字)
- **API Secret**: /YiZoJlRybHnKAO78go6Jt9LKQOS/EwEEe47UyEl6YbXo7XA84fL+Q/k3AEJeCBo (64文字)

## 📊 技術仕様
### 売買判断ロジック:
- **RSI**: < 35 (買い), > 65 (売り) - 信頼度 0.8
- **MACD**: ライン>シグナル&正値 (買い), ライン<シグナル&負値 (売り) - 信頼度 0.6
- **ボリンジャーバンド**: 下限付近 (買い), 上限付近 (売り) - 信頼度 0.7
- **実行条件**: 信頼度合計 0.8以上

### リスク管理:
- **最大投資額**: 残高の5%
- **損切り**: 2%下落で実行
- **利確**: 4%上昇で実行
- **最短取引間隔**: 30分

## 🛠️ システム構成
### ファイル構造:
```
crypto-trading-bot/
├── app.py                 # Flaskメインアプリ
├── main.py               # エントリーポイント
├── config.py             # 設定管理
├── models.py             # データベースモデル
├── services/
│   ├── gmo_api.py           # GMO Coin API
│   ├── technical_indicators.py  # テクニカル指標
│   ├── simple_trading_logic.py  # 売買判断ロジック
│   ├── risk_manager.py         # リスク管理
│   ├── notification_service.py # アラート機能
│   └── data_service.py         # データ取得
├── templates/
│   ├── simple_dashboard.html   # メインダッシュボード
│   └── simple_settings.html    # 設定画面
└── logs/ # 取引ログ保存場所
```

### 主要機能:
- ✅ リアルタイム価格監視
- ✅ 技術指標分析 (RSI, MACD, ボリンジャーバンド)
- ✅ 自動売買シグナル検出
- ✅ ウェブダッシュボード (PC/スマホ対応)
- ✅ 取引履歴記録
- ✅ エラーハンドリング

## 🚨 重要な設定
### 環境変数 (Railway設定済み):
```
GMO_API_KEY = FXhblJAz9Ql0G3pCo5p/+S9zkFw6r2VC
GMO_API_SECRET = /YiZoJlRybHnKAO78go6Jt9LKQOS/EwEEe47UyEl6YbXo7XA84fL+Q/k3AEJeCBo
```

## 📱 操作方法
### ダッシュボード確認:
1. https://web-production-1f4ce.up.railway.app にアクセス
2. リアルタイム価格・シグナル確認
3. 30秒ごと自動更新

### 設定変更:
1. /settings ページで設定調整
2. リスク管理パラメータ変更
3. 自動取引ON/OFF切り替え

## 🔄 呼び出し方法
次回このプロジェクトについて質問する際は以下のように呼び出してください:

**"GMO Coinトレーディングボットの件"** または 
**"DOGE/JPY自動取引システムの件"** または
**"crypto trading bot project"**

## 📞 サポート対応履歴
- さくらVPS問題 → Railway無料ホスティングに移行
- API認証エラー → 修正完了
- ダッシュボード表示問題 → JavaScript修正完了
- 循環インポートエラー → 動的インポートで解決
- リアルタイム分析表示 → 実装完了

## 🎯 今後の改善案
- より多くの通貨ペア対応
- メール/LINE通知機能
- 詳細な取引履歴分析
- バックテスト機能
- ポートフォリオ管理

---
**最終更新**: 2025年8月7日
**ステータス**: 24時間稼働中 ✅