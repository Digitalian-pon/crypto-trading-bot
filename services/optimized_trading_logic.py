"""
MACD単体トレーディングロジック v3.12.0
MACDクロスのみエントリー + トレーリングストップ決済

方針:
- エントリー: MACDクロスの瞬間のみ（ゴールデンクロス→BUY、デッドクロス→SELL）
- ポジションベースエントリー: 無効化（v3.12.0 - 低品質シグナルによる損失防止）
- クロス保持: フィルターで拒否されてもクロス状態を保持（次回再試行）
- EMA: 参考情報としてログに表示するのみ（取引判断には使用しない）
- 決済: トレーリングストップ + MACDクロス確認（bot側で処理）
- 決済時のMACDクロス → 即座に反対注文（トレンド転換を捉える）
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class OptimizedTradingLogic:
    """
    MACD主体トレーディングロジック v3.8.0

    設計思想:
    - エントリー1: MACDクロス（高confidence） - クロスの瞬間
    - エントリー2: MACDポジション（中confidence） - Line > Signal → BUY、Line < Signal → SELL
    - クロス保持: フィルター拒否時もクロスを消滅させない
    - EMAはconfidence調整のみ（ブロックしない）
    - 決済: トレーリングストップ + MACDクロス確認 → 反対注文
    """

    def __init__(self, config=None):
        """初期化 v3.11.0 - EMA削除・MACD単体化"""
        self.config = config or {}
        self.last_trade_time = None
        self.last_trade_price = None
        self.last_exit_price = None
        self.min_trade_interval = 60  # 1分（チェック間隔に合わせる）

        # シンプルなTP/SL設定（固定%）- リスクリワード比 2:1
        self.take_profit_pct = 0.03   # 3%利確
        self.stop_loss_pct = 0.010    # 1.0%損切り

        # 取引履歴
        self.trade_history = []
        self.recent_trades_limit = 20

        # MACD状態追跡
        self.last_macd_position = None  # 'above' or 'below'
        self.pending_cross = None       # フィルター拒否されたクロスを保持

    def should_trade(self, market_data, historical_df=None, skip_price_filter=False, is_tpsl_continuation=False):
        """
        取引判定 - v3.7.0 MACDクロスベースエントリー（クロス保持機能付き）

        ルール:
        1. MACDゴールデンクロス（below→above遷移）→ BUY
        2. MACDデッドクロス（above→below遷移）→ SELL
        3. クロスなし → 取引なし
        4. フィルターで拒否 → クロスを保持し次回再試行（消滅させない）
        5. EMAトレンド: confidence調整のみ（ブロックしない）

        Returns:
            (should_trade, trade_type, reason, confidence, stop_loss, take_profit)
        """
        try:
            # === 基本データ取得 ===
            current_price = market_data.get('close', 0)
            macd_line = market_data.get('macd_line', 0)
            macd_signal = market_data.get('macd_signal', 0)
            macd_histogram = market_data.get('macd_histogram', 0)
            ema_20 = market_data.get('ema_20', current_price)
            ema_50 = market_data.get('ema_50', current_price)

            logger.info(f"📊 [MACD v3.8.0 Cross+Position] Price=¥{current_price:.3f}")
            logger.info(f"   MACD Line: {macd_line:.6f}, Signal: {macd_signal:.6f}, Hist: {macd_histogram:.6f}")

            # === MACDポジション判定 ===
            macd_position = 'above' if macd_line > macd_signal else 'below'

            # === クロス検出 ===
            is_golden_cross = False
            is_death_cross = False
            is_entry_startup = False

            # ★ FIX v3.12.2: Bot再起動後の初回サイクル - 過去データからクロスを検出
            if self.last_macd_position is None:
                is_entry_startup = True
                # 過去のローソク足からMACDの前回状態を復元
                if historical_df is not None and len(historical_df) >= 3 and 'macd_line' in historical_df.columns and 'macd_signal' in historical_df.columns:
                    prev_row = historical_df.iloc[-2]
                    prev_macd_line = prev_row.get('macd_line', 0)
                    prev_macd_signal = prev_row.get('macd_signal', 0)
                    prev_position = 'above' if prev_macd_line > prev_macd_signal else 'below'
                    self.last_macd_position = prev_position
                    logger.info(f"🔄 [STARTUP] MACD state restored from previous candle: {prev_position} (current: {macd_position})")
                    # 前回と今回が異なればクロス発生
                    if prev_position == 'below' and macd_position == 'above':
                        is_golden_cross = True
                        is_entry_startup = False
                        logger.info(f"🟢 [STARTUP] GOLDEN CROSS detected from historical data!")
                    elif prev_position == 'above' and macd_position == 'below':
                        is_death_cross = True
                        is_entry_startup = False
                        logger.info(f"🔴 [STARTUP] DEATH CROSS detected from historical data!")
                    else:
                        logger.info(f"🔄 [STARTUP] No cross at startup (both {macd_position})")
                else:
                    self.last_macd_position = macd_position
                    logger.info(f"🔄 [STARTUP] MACD entry state initialized: {macd_position} (no historical data)")
            else:
                # 1. 新しいクロスを検出
                if self.last_macd_position == 'below' and macd_position == 'above':
                    is_golden_cross = True
                    self.pending_cross = None  # 新クロスで古いpendingをクリア
                    logger.info(f"🟢 MACD GOLDEN CROSS detected!")
                elif self.last_macd_position == 'above' and macd_position == 'below':
                    is_death_cross = True
                    self.pending_cross = None
                    logger.info(f"🔴 MACD DEATH CROSS detected!")

            # 2. 保留中のクロスがあれば復元（起動時は除く）
            if not is_entry_startup and not is_golden_cross and not is_death_cross and self.pending_cross is not None:
                # 保留中のクロスがまだ有効か確認（MACDの方向が変わっていないこと）
                if self.pending_cross == 'golden' and macd_position == 'above':
                    is_golden_cross = True
                    logger.info(f"🟢 PENDING Golden Cross RESTORED (filter blocked last time)")
                elif self.pending_cross == 'death' and macd_position == 'below':
                    is_death_cross = True
                    logger.info(f"🔴 PENDING Death Cross RESTORED (filter blocked last time)")
                else:
                    # MACDが反転した → 保留クロスは無効
                    logger.info(f"   Pending cross '{self.pending_cross}' expired (MACD reversed)")
                    self.pending_cross = None

            # 状態を更新（常に最新の状態を追跡）
            self.last_macd_position = macd_position

            # === ヒストグラム強度・EMAトレンド（クロス/ポジション両方で使用） ===
            histogram_strength = abs(macd_histogram)
            ema_trend = 'up' if ema_20 > ema_50 else 'down'
            ema_diff_pct = abs(ema_20 - ema_50) / ema_50 * 100 if ema_50 > 0 else 0
            logger.info(f"   EMA Trend: {ema_trend} ({ema_diff_pct:.2f}%), Hist strength: {histogram_strength:.6f}")

            # === クロスなし → 待機（v3.12.0: ポジションベースエントリー無効化） ===
            if not is_golden_cross and not is_death_cross:
                logger.info(f"   No MACD cross - waiting for cross signal (position-based DISABLED v3.12.0)")
                return False, None, "No MACD cross - waiting", 0.0, None, None

            # === シグナル強度計算（クロスベースエントリー用） ===
            if histogram_strength > 0.03:
                confidence = 2.5
            elif histogram_strength > 0.01:
                confidence = 2.0
            elif histogram_strength > 0.005:
                confidence = 1.5
            else:
                confidence = 1.0

            # === 取引タイミングフィルター ===
            if not skip_price_filter:
                if not self._check_trade_timing():
                    # クロスを保留状態にする（消滅させない）
                    cross_type = 'golden' if is_golden_cross else 'death'
                    self.pending_cross = cross_type
                    logger.info(f"   ⏳ Cross PENDING (trade interval too short) - will retry next cycle")
                    return False, None, "Trade interval too short (cross pending)", 0.0, None, None

                if self.last_trade_price is not None:
                    price_change = abs(current_price - self.last_trade_price) / self.last_trade_price
                    if price_change < 0.003:
                        cross_type = 'golden' if is_golden_cross else 'death'
                        self.pending_cross = cross_type
                        logger.info(f"   ⏳ Cross PENDING (price change too small: {price_change*100:.2f}%) - will retry")
                        return False, None, "Price change too small (cross pending)", 0.0, None, None

            # === クロスが実行される → pending をクリア ===
            self.pending_cross = None

            # === 売買判定（MACDクロスのみ - v3.11.0 EMA削除） ===
            if is_golden_cross:
                reason = f'MACD Golden Cross (EMA: {ema_trend} {ema_diff_pct:.2f}%)'
                stop_loss = current_price * (1 - self.stop_loss_pct)
                take_profit = current_price * (1 + self.take_profit_pct)
                logger.info(f"🟢 BUY SIGNAL: {reason} (confidence={confidence:.2f})")
                return True, 'BUY', reason, confidence, stop_loss, take_profit

            elif is_death_cross:
                reason = f'MACD Death Cross (EMA: {ema_trend} {ema_diff_pct:.2f}%)'
                stop_loss = current_price * (1 + self.stop_loss_pct)
                take_profit = current_price * (1 - self.take_profit_pct)
                logger.info(f"🔴 SELL SIGNAL: {reason} (confidence={confidence:.2f})")
                return True, 'SELL', reason, confidence, stop_loss, take_profit

            return False, None, "No signal", 0.0, None, None

        except Exception as e:
            logger.error(f"Error in MACD trading logic: {e}", exc_info=True)
            return False, None, f"Error: {str(e)}", 0.0, None, None

    def _check_trade_timing(self):
        """取引タイミングチェック"""
        if not self.last_trade_time:
            return True

        elapsed = (datetime.now(timezone.utc) - self.last_trade_time).total_seconds()
        return elapsed >= self.min_trade_interval

    def record_stop_loss(self, side):
        """損切り記録"""
        logger.info(f"📝 Stop loss recorded: {side}")

    def record_trade(self, trade_type, price, result=None, is_exit=False):
        """取引記録"""
        self.last_trade_time = datetime.now(timezone.utc)

        if is_exit:
            self.last_exit_price = price
            logger.info(f"💰 Exit recorded: ¥{price:.2f}")
        else:
            self.last_trade_price = price
            logger.info(f"📝 Entry recorded: ¥{price:.2f}")

        # ファイルログ
        try:
            with open('bot_execution_log.txt', 'a') as f:
                action = "EXIT" if is_exit else "ENTRY"
                f.write(f"TRADE_{action}: {trade_type.upper()} @ ¥{price:.2f}\n")
        except:
            pass

        trade_record = {
            'timestamp': self.last_trade_time,
            'type': trade_type,
            'price': price,
            'result': result,
            'is_exit': is_exit
        }

        self.trade_history.append(trade_record)

        if len(self.trade_history) > self.recent_trades_limit:
            self.trade_history = self.trade_history[-self.recent_trades_limit:]

    def get_performance_stats(self):
        """パフォーマンス統計"""
        if not self.trade_history:
            return None

        results = [t['result'] for t in self.trade_history if t.get('result')]

        if not results:
            return None

        wins = sum(1 for r in results if r > 0)
        losses = sum(1 for r in results if r < 0)
        total_pnl = sum(results)

        return {
            'total_trades': len(results),
            'wins': wins,
            'losses': losses,
            'win_rate': wins / len(results) if results else 0,
            'total_pnl': total_pnl,
            'avg_pnl': total_pnl / len(results) if results else 0
        }

    # === 互換性のためのダミーメソッド ===
    def _calculate_atr_from_data(self, df, period=14):
        """ATR計算（互換性用）"""
        try:
            if df is None or len(df) < period:
                return 0.0

            high = df['high'].tail(period)
            low = df['low'].tail(period)
            close = df['close'].tail(period)

            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())

            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.mean()

            return atr if not pd.isna(atr) else 0.0
        except:
            return 0.0

    def _detect_market_regime(self, market_data, historical_df):
        """市場レジーム検出（互換性用 - 常にTRENDINGを返す）"""
        return 'TRENDING'

    # レジームパラメータ（互換性用）
    regime_params = {
        'TRENDING': {
            'stop_loss_atr_mult': 1.5,
            'take_profit_atr_mult': 3.0,
        },
        'RANGING': {
            'stop_loss_atr_mult': 1.5,
            'take_profit_atr_mult': 3.0,
        },
        'VOLATILE': {
            'stop_loss_atr_mult': 2.0,
            'take_profit_atr_mult': 4.0,
        }
    }
