"""
MACD主体トレーディングロジック v3.1.0 (restored)
シンプルなMACD売買戦略 + EMAトレンドフォロー専用モード

方針:
- MACDクロスのみでエントリー判断（他のインジケーターは補助のみ）
- MACDゴールデンクロス → BUY（上昇トレンド時のみ）
- MACDデッドクロス → SELL（下降トレンド時のみ）
- EMAトレンドフィルター: トレンド方向の取引のみ許可
- シンプルな固定TP/SL（利確2%、損切り1.5%）
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class OptimizedTradingLogic:
    """
    MACD主体のシンプルなトレーディングロジック v3.1.0 (restored)

    設計思想:
    - MACDクロスが全て（唯一のエントリーシグナル）
    - EMAトレンドフィルターでトレンド方向の取引のみ許可
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
        self.stop_loss_pct = 0.015    # 1.5%損切り

        # 取引履歴
        self.trade_history = []
        self.recent_trades_limit = 20

        # MACD状態追跡
        self.last_macd_position = None  # 'above' or 'below'

    def should_trade(self, market_data, historical_df=None, skip_price_filter=False, is_tpsl_continuation=False):
        """
        取引判定 - MACD主体版 + EMAトレンドフォロー専用モード

        ルール:
        1. MACDがシグナルを上抜け（Golden Cross）→ BUY（上昇トレンド時のみ）
        2. MACDがシグナルを下抜け（Death Cross）→ SELL（下降トレンド時のみ）
        3. EMAフィルター: 上昇トレンド=BUYのみ、下降トレンド=SELLのみ

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

            logger.info(f"📊 [MACD v3.1.0] Price=¥{current_price:.3f}")
            logger.info(f"   MACD Line: {macd_line:.6f}")
            logger.info(f"   MACD Signal: {macd_signal:.6f}")
            logger.info(f"   MACD Histogram: {macd_histogram:.6f}")

            # === MACDクロス判定（唯一のシグナル） ===
            macd_position = 'above' if macd_line > macd_signal else 'below'

            # クロス検出
            is_golden_cross = False  # MACDがシグナルを上抜け
            is_death_cross = False   # MACDがシグナルを下抜け

            if self.last_macd_position is not None:
                if self.last_macd_position == 'below' and macd_position == 'above':
                    is_golden_cross = True
                    logger.info(f"🟢 MACD GOLDEN CROSS detected!")
                elif self.last_macd_position == 'above' and macd_position == 'below':
                    is_death_cross = True
                    logger.info(f"🔴 MACD DEATH CROSS detected!")

            # 状態を更新
            self.last_macd_position = macd_position

            # === シグナル強度計算 ===
            # ヒストグラムの大きさで信頼度を決定
            histogram_strength = abs(macd_histogram)

            if histogram_strength > 0.05:
                confidence = 2.5  # 強いシグナル
            elif histogram_strength > 0.02:
                confidence = 2.0  # 中程度
            elif histogram_strength > 0.01:
                confidence = 1.5  # 弱め
            else:
                confidence = 1.0  # 最小

            # === EMAトレンド確認（トレンドフォロー専用モード） ===
            # v3.1.0: トレンド方向のみ取引を許可（逆方向は完全禁止）
            ema_trend = 'up' if ema_20 > ema_50 else 'down'
            ema_diff_pct = abs(ema_20 - ema_50) / ema_50 * 100 if ema_50 > 0 else 0

            logger.info(f"   EMA Trend: {ema_trend} (EMA20-EMA50 diff: {ema_diff_pct:.2f}%)")
            logger.info(f"   🎯 TREND-FOLLOW MODE: Only {ema_trend.upper()}TREND trades allowed")

            # === 取引タイミングフィルター ===
            if not skip_price_filter:
                if not self._check_trade_timing():
                    logger.info(f"⏸️ Trade interval too short - waiting...")
                    return False, None, "Trade interval too short", 0.0, None, None

                # 価格変動フィルター（0.5%以上動いたらOK）
                if self.last_trade_price is not None:
                    price_change = abs(current_price - self.last_trade_price) / self.last_trade_price
                    if price_change < 0.005:
                        logger.info(f"⏸️ Price change too small ({price_change*100:.2f}% < 0.5%)")
                        return False, None, f"Price change too small", 0.0, None, None

            # === 売買判定（トレンドフォロー専用モード） ===
            # v3.1.0: トレンド方向のシグナルのみ許可、逆方向は完全ブロック

            # BUY判定: MACDゴールデンクロス
            if is_golden_cross:
                # 【重要】下降トレンド中はBUY完全禁止（閾値なし）
                if ema_trend == 'down':
                    logger.info(f"🚫 Golden Cross BLOCKED - Downtrend active (EMA20 < EMA50)")
                    logger.info(f"   In downtrend, only SELL signals are allowed")
                else:
                    # 上昇トレンド中のみBUY許可
                    take_profit = current_price * (1 + self.take_profit_pct)
                    stop_loss = current_price * (1 - self.stop_loss_pct)

                    logger.info(f"🟢 BUY SIGNAL - MACD Golden Cross + Uptrend confirmed")
                    logger.info(f"   Confidence: {confidence:.2f}")
                    logger.info(f"   TP: ¥{take_profit:.2f} (+{self.take_profit_pct*100:.1f}%)")
                    logger.info(f"   SL: ¥{stop_loss:.2f} (-{self.stop_loss_pct*100:.1f}%)")

                    return True, 'BUY', 'MACD Golden Cross + Uptrend', confidence, stop_loss, take_profit

            # SELL判定: MACDデッドクロス
            if is_death_cross:
                # 【重要】上昇トレンド中はSELL完全禁止（閾値なし）
                if ema_trend == 'up':
                    logger.info(f"🚫 Death Cross BLOCKED - Uptrend active (EMA20 > EMA50)")
                    logger.info(f"   In uptrend, only BUY signals are allowed")
                else:
                    # 下降トレンド中のみSELL許可
                    take_profit = current_price * (1 - self.take_profit_pct)
                    stop_loss = current_price * (1 + self.stop_loss_pct)

                    logger.info(f"🔴 SELL SIGNAL - MACD Death Cross + Downtrend confirmed")
                    logger.info(f"   Confidence: {confidence:.2f}")
                    logger.info(f"   TP: ¥{take_profit:.2f} (-{self.take_profit_pct*100:.1f}%)")
                    logger.info(f"   SL: ¥{stop_loss:.2f} (+{self.stop_loss_pct*100:.1f}%)")

                    return True, 'SELL', 'MACD Death Cross + Downtrend', confidence, stop_loss, take_profit

            # === クロスなし: 継続シグナルチェック（反転シグナル用） ===
            if skip_price_filter:
                # 反転シグナルモード: トレンド方向のシグナルのみ許可
                if macd_position == 'above' and macd_histogram > 0.01:
                    # 上昇トレンド中のみBUY許可
                    if ema_trend == 'up':
                        take_profit = current_price * (1 + self.take_profit_pct)
                        stop_loss = current_price * (1 - self.stop_loss_pct)
                        logger.info(f"🟢 BUY SIGNAL (Reversal mode) - MACD Bullish + Uptrend")
                        return True, 'BUY', 'MACD Bullish (reversal) + Uptrend', confidence, stop_loss, take_profit
                    else:
                        logger.info(f"🚫 BUY blocked in reversal mode - Downtrend active")

                elif macd_position == 'below' and macd_histogram < -0.01:
                    # 下降トレンド中のみSELL許可
                    if ema_trend == 'down':
                        take_profit = current_price * (1 - self.take_profit_pct)
                        stop_loss = current_price * (1 + self.stop_loss_pct)
                        logger.info(f"🔴 SELL SIGNAL (Reversal mode) - MACD Bearish + Downtrend")
                        return True, 'SELL', 'MACD Bearish (reversal) + Downtrend', confidence, stop_loss, take_profit
                    else:
                        logger.info(f"🚫 SELL blocked in reversal mode - Uptrend active")

            # シグナルなし
            logger.info(f"⏸️ No valid signal - waiting...")
            logger.info(f"   MACD position: {macd_position}, EMA trend: {ema_trend}")
            return False, None, "No MACD cross", confidence, None, None

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
