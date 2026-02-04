"""
MACD専用トレーディングロジック v3.8.0
純粋なMACDクロス売買戦略（ヒストグラム強度フィルター付き）

方針:
- MACDゴールデンクロス → BUY
- MACDデッドクロス → SELL
- EMA、SMA、RSI等は使用しない（MACD純粋戦略）
- MACDヒストグラム閾値で弱いクロスは無視（往復ビンタ防止）
- シンプルな固定TP/SL（利確2%、損切り1.5%）

v3.8.0変更点（2026-02-04）:
- 🎯 MACD専用戦略を維持（ユーザー要望）
- 🎯 EMAフィルター削除（MACDのみで判断）
- 🛡️ MACDヒストグラム閾値（|histogram| < 0.02は弱いクロス）
- 🛡️ クールダウン期間90分（連続損失防止）
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class OptimizedTradingLogic:
    """
    MACD主体のシンプルなトレーディングロジック v3.0.0

    設計思想:
    - MACDクロスが全て（唯一のエントリーシグナル）
    - 複雑なレジーム判定は廃止
    - シンプルな固定TP/SL
    """

    def __init__(self, config=None):
        """初期化"""
        self.config = config or {}
        self.last_trade_time = None
        self.last_trade_price = None
        self.last_exit_price = None
        self.min_trade_interval = 300  # 5分

        # シンプルなTP/SL設定（固定%）
        self.take_profit_pct = 0.02   # 2%利確
        self.stop_loss_pct = 0.015    # 1.5%損切り（v3.4.0: 2.0%→1.5%に強化：早めの損切り）

        # 取引履歴
        self.trade_history = []
        self.recent_trades_limit = 20

        # MACD状態追跡
        self.last_macd_position = None  # 'above' or 'below'

        # v3.8.0: 損切り後クールダウン機能（連続損失防止）
        self.last_loss_time = None      # 最後の損切り時刻
        self.last_loss_side = None      # 最後の損切りポジション（BUY/SELL）
        self.cooldown_after_loss = 5400  # 損切り後90分間は同方向エントリー禁止

        # v3.8.0: MACDヒストグラム閾値（弱いクロスを無視）
        self.min_histogram_for_cross = 0.02  # クロス時の最小ヒストグラム強度

    def should_trade(self, market_data, historical_df=None, skip_price_filter=False, is_tpsl_continuation=False):
        """
        取引判定 - MACD専用版 v3.8.0

        ルール（シンプル）:
        1. MACDライン > シグナルライン（ゴールデンクロス）→ BUY
        2. MACDライン < シグナルライン（デッドクロス）→ SELL
        3. ヒストグラムが0.02未満は弱いクロスとして無視（往復ビンタ防止）
        4. EMA、SMA、RSI等は使用しない

        Returns:
            (should_trade, trade_type, reason, confidence, stop_loss, take_profit)
        """
        try:
            # === 基本データ取得（MACDのみ） ===
            current_price = market_data.get('close', 0)
            macd_line = market_data.get('macd_line', 0)
            macd_signal = market_data.get('macd_signal', 0)
            macd_histogram = market_data.get('macd_histogram', 0)

            logger.info(f"📊 [MACD ONLY v3.8.0] Price=¥{current_price:.3f}")
            logger.info(f"   MACD Line: {macd_line:.6f}")
            logger.info(f"   MACD Signal: {macd_signal:.6f}")
            logger.info(f"   MACD Histogram: {macd_histogram:.6f}")

            # === MACDクロス判定（唯一のシグナル） ===
            macd_position = 'above' if macd_line > macd_signal else 'below'

            # クロス検出
            is_golden_cross = False  # MACDがシグナルを上抜け → BUY
            is_death_cross = False   # MACDがシグナルを下抜け → SELL

            if self.last_macd_position is not None:
                if self.last_macd_position == 'below' and macd_position == 'above':
                    is_golden_cross = True
                    logger.info(f"🟢 MACD GOLDEN CROSS detected! (Line crossed above Signal)")
                elif self.last_macd_position == 'above' and macd_position == 'below':
                    is_death_cross = True
                    logger.info(f"🔴 MACD DEATH CROSS detected! (Line crossed below Signal)")

            # 状態を更新
            self.last_macd_position = macd_position

            # === シグナル強度計算 ===
            histogram_strength = abs(macd_histogram)
            if histogram_strength > 0.05:
                confidence = 2.5
            elif histogram_strength > 0.02:
                confidence = 2.0
            elif histogram_strength > 0.01:
                confidence = 1.5
            else:
                confidence = 1.0

            logger.info(f"   MACD Position: {macd_position.upper()} (Line {'>' if macd_position == 'above' else '<'} Signal)")
            logger.info(f"   Confidence: {confidence:.1f}")

            # === 取引タイミングフィルター ===
            if not skip_price_filter:
                if not self._check_trade_timing():
                    logger.info(f"⏸️ Trade interval too short - waiting...")
                    return False, None, "Trade interval too short", 0.0, None, None

                # 価格変動フィルター（0.3%以上）
                if self.last_trade_price is not None:
                    price_change = abs(current_price - self.last_trade_price) / self.last_trade_price
                    if price_change < 0.003:
                        logger.info(f"⏸️ Price change too small ({price_change*100:.2f}% < 0.3%)")
                        return False, None, f"Price change too small", 0.0, None, None

            # === v3.8.0: 弱いクロスのフィルタリング（MACDヒストグラムのみ） ===
            histogram_strength = abs(macd_histogram)
            is_weak_cross = histogram_strength < self.min_histogram_for_cross
            logger.info(f"   Histogram Strength: {histogram_strength:.4f} (Threshold: {self.min_histogram_for_cross})")

            # === BUY判定: MACDゴールデンクロス ===
            if is_golden_cross:
                # v3.6.0: 弱いクロスチェック
                if is_weak_cross:
                    logger.info(f"🚫 BUY BLOCKED - Weak cross (histogram {histogram_strength:.4f} < {self.min_histogram_for_cross})")
                    logger.info(f"   騙しシグナルの可能性が高いため無視")
                # クールダウンチェック
                elif self._is_in_cooldown('BUY'):
                    logger.info(f"🚫 BUY BLOCKED - In cooldown after recent BUY stop loss")
                else:
                    take_profit = current_price * (1 + self.take_profit_pct)
                    stop_loss = current_price * (1 - self.stop_loss_pct)

                    logger.info(f"🟢 BUY SIGNAL - MACD Golden Cross (Strong)")
                    logger.info(f"   Histogram strength: {histogram_strength:.4f} >= {self.min_histogram_for_cross}")
                    logger.info(f"   TP: ¥{take_profit:.2f} (+{self.take_profit_pct*100:.1f}%)")
                    logger.info(f"   SL: ¥{stop_loss:.2f} (-{self.stop_loss_pct*100:.1f}%)")

                    return True, 'BUY', 'MACD Golden Cross', confidence, stop_loss, take_profit

            # === SELL判定: MACDデッドクロス ===
            if is_death_cross:
                # v3.6.0: 弱いクロスチェック
                if is_weak_cross:
                    logger.info(f"🚫 SELL BLOCKED - Weak cross (histogram {histogram_strength:.4f} < {self.min_histogram_for_cross})")
                    logger.info(f"   騙しシグナルの可能性が高いため無視")
                # クールダウンチェック
                elif self._is_in_cooldown('SELL'):
                    logger.info(f"🚫 SELL BLOCKED - In cooldown after recent SELL stop loss")
                else:
                    take_profit = current_price * (1 - self.take_profit_pct)
                    stop_loss = current_price * (1 + self.stop_loss_pct)

                    logger.info(f"🔴 SELL SIGNAL - MACD Death Cross (Strong)")
                    logger.info(f"   Histogram strength: {histogram_strength:.4f} >= {self.min_histogram_for_cross}")
                    logger.info(f"   TP: ¥{take_profit:.2f} (-{self.take_profit_pct*100:.1f}%)")
                    logger.info(f"   SL: ¥{stop_loss:.2f} (+{self.stop_loss_pct*100:.1f}%)")

                    return True, 'SELL', 'MACD Death Cross', confidence, stop_loss, take_profit

            # === クロスなし: 継続シグナルチェック ===
            # v3.8.0: 継続シグナルの閾値（強いヒストグラムのみ）
            histogram_threshold = 0.02 if not skip_price_filter else 0.015

            logger.info(f"   📈 No cross - checking continuation (threshold: {histogram_threshold})")

            # BUY継続シグナル: MACD above + 強いヒストグラム
            if macd_position == 'above' and macd_histogram > histogram_threshold:
                if self._is_in_cooldown('BUY'):
                    logger.info(f"🚫 BUY blocked - In cooldown")
                else:
                    take_profit = current_price * (1 + self.take_profit_pct)
                    stop_loss = current_price * (1 - self.stop_loss_pct)
                    signal_type = "Reversal" if skip_price_filter else "Continuation"
                    logger.info(f"🟢 BUY SIGNAL ({signal_type}) - MACD Bullish")
                    logger.info(f"   Histogram: {macd_histogram:.4f} > {histogram_threshold}")
                    return True, 'BUY', f'MACD Bullish ({signal_type})', confidence, stop_loss, take_profit

            # SELL継続シグナル: MACD below + 強いヒストグラム
            elif macd_position == 'below' and macd_histogram < -histogram_threshold:
                if self._is_in_cooldown('SELL'):
                    logger.info(f"🚫 SELL blocked - In cooldown")
                else:
                    take_profit = current_price * (1 - self.take_profit_pct)
                    stop_loss = current_price * (1 + self.stop_loss_pct)
                    signal_type = "Reversal" if skip_price_filter else "Continuation"
                    logger.info(f"🔴 SELL SIGNAL ({signal_type}) - MACD Bearish")
                    logger.info(f"   Histogram: {macd_histogram:.4f} < -{histogram_threshold}")
                    return True, 'SELL', f'MACD Bearish ({signal_type})', confidence, stop_loss, take_profit

            # シグナルなし
            logger.info(f"⏸️ No valid signal - waiting for MACD cross...")
            logger.info(f"   MACD position: {macd_position}, Histogram: {macd_histogram:.4f}")
            logger.info(f"   Required: Golden Cross (BUY) or Death Cross (SELL)")
            return False, None, "No valid signal (waiting for MACD cross)", confidence, None, None

        except Exception as e:
            logger.error(f"Error in MACD trading logic: {e}", exc_info=True)
            return False, None, f"Error: {str(e)}", 0.0, None, None

    def _check_trade_timing(self):
        """取引タイミングチェック"""
        if not self.last_trade_time:
            return True

        elapsed = (datetime.now(timezone.utc) - self.last_trade_time).total_seconds()
        return elapsed >= self.min_trade_interval

    def _is_in_cooldown(self, trade_type):
        """
        v3.3.0: 損切り後クールダウンチェック
        損切り後30分間は同方向のエントリーを禁止（連続損失防止）
        """
        if not self.last_loss_time or not self.last_loss_side:
            return False

        # 同方向のみチェック
        if self.last_loss_side != trade_type:
            return False

        elapsed = (datetime.now(timezone.utc) - self.last_loss_time).total_seconds()
        remaining = self.cooldown_after_loss - elapsed

        if remaining > 0:
            logger.info(f"   ⏳ Cooldown remaining: {remaining/60:.1f} minutes for {trade_type}")
            return True

        return False

    def record_stop_loss(self, side):
        """
        v3.3.0: 損切り記録（クールダウン用）
        """
        self.last_loss_time = datetime.now(timezone.utc)
        self.last_loss_side = side
        logger.info(f"📝 Stop loss recorded: {side} - Cooldown started for 30 minutes")

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
