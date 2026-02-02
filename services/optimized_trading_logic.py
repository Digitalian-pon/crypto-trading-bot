"""
MACD主体トレーディングロジック v3.4.0
シンプルなMACD売買戦略

方針:
- MACDクロス または 継続シグナルでエントリー判断
- MACDゴールデンクロス or Bullish継続 → BUY（上昇トレンド中のみ）
- MACDデッドクロス or Bearish継続 → SELL（下降トレンド中のみ）
- シンプルな固定TP/SL（利確2%、損切り1.5%）

v3.4.0変更点:
- 🎯 価格 vs EMA フィルター追加: 価格 > EMA20 のみBUY許可
- 🎯 MACDヒストグラム方向確認: 増加中のみBUY、減少中のみSELL
- 🎯 損切り強化: 2.0% → 1.5%（早めの損切りで損失最小化）
- 🎯 クールダウン延長: 30分 → 60分（連続損失防止強化）
- EMAの遅れによる誤エントリーを防止

v3.3.1変更点:
- MACDヒストグラム閾値を大幅緩和: 0.015 → 0.008（低ボラ対応）
- 14時間シグナルなしの問題を解決
- 反転時閾値も緩和: 0.008 → 0.005

v3.3.0変更点:
- 損切りラインを緩和: 1.5% → 2.0%（短期ノイズ対策）
- 価格変動フィルターを緩和: 0.5% → 0.3%（機会損失削減）
- 損切り後クールダウン機能追加（連続損失防止）
- EMA5フィルター追加（短期反発でのSELL防止）
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
        self.last_macd_histogram = None  # v3.4.0: ヒストグラム方向追跡

        # v3.4.0: 損切り後クールダウン機能強化（連続損失防止）
        self.last_loss_time = None      # 最後の損切り時刻
        self.last_loss_side = None      # 最後の損切りポジション（BUY/SELL）
        self.cooldown_after_loss = 3600  # 損切り後60分間は同方向エントリー禁止（30分→60分）

    def should_trade(self, market_data, historical_df=None, skip_price_filter=False, is_tpsl_continuation=False):
        """
        取引判定 - MACD主体版

        ルール:
        1. MACDがシグナルを上抜け → BUY
        2. MACDがシグナルを下抜け → SELL
        3. EMAで軽くフィルター（強いトレンドの逆張りを防ぐのみ）

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

            logger.info(f"📊 [MACD v3.0] Price=¥{current_price:.3f}")
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
            # v3.3.0: EMA5追加（短期反発検出）
            # v3.4.0: 価格 vs EMA フィルター追加
            ema_5 = market_data.get('ema_5', current_price)
            ema_trend = 'up' if ema_20 > ema_50 else 'down'
            ema_diff_pct = abs(ema_20 - ema_50) / ema_50 * 100 if ema_50 > 0 else 0

            # v3.4.0: 価格 vs EMA フィルター（EMAの遅れ対策）
            price_above_ema20 = current_price > ema_20
            price_below_ema20 = current_price < ema_20

            # v3.4.0: MACDヒストグラム方向チェック
            histogram_increasing = True  # デフォルト
            histogram_decreasing = True  # デフォルト
            if self.last_macd_histogram is not None:
                histogram_increasing = macd_histogram > self.last_macd_histogram
                histogram_decreasing = macd_histogram < self.last_macd_histogram
            self.last_macd_histogram = macd_histogram  # 更新

            # v3.3.0: 短期反発検出（EMA5とEMA20の関係）
            short_term_bounce = (ema_trend == 'down' and ema_5 > ema_20)  # 下降トレンド中の短期反発
            short_term_pullback = (ema_trend == 'up' and ema_5 < ema_20)  # 上昇トレンド中の短期調整

            logger.info(f"   EMA Trend: {ema_trend} (EMA20-EMA50 diff: {ema_diff_pct:.2f}%)")
            logger.info(f"   EMA5: ¥{ema_5:.3f}, Short-term bounce: {short_term_bounce}")
            logger.info(f"   🎯 v3.4.0 Price vs EMA: Price {'>' if price_above_ema20 else '<'} EMA20")
            logger.info(f"   🎯 v3.4.0 Histogram direction: {'↑' if histogram_increasing else '↓'}")
            logger.info(f"   🎯 TREND-FOLLOW MODE: Only {ema_trend.upper()}TREND trades allowed")

            # === 取引タイミングフィルター ===
            if not skip_price_filter:
                if not self._check_trade_timing():
                    logger.info(f"⏸️ Trade interval too short - waiting...")
                    return False, None, "Trade interval too short", 0.0, None, None

                # 価格変動フィルター（0.3%以上動いたらOK）- v3.3.0: 0.5%→0.3%に緩和
                if self.last_trade_price is not None:
                    price_change = abs(current_price - self.last_trade_price) / self.last_trade_price
                    if price_change < 0.003:
                        logger.info(f"⏸️ Price change too small ({price_change*100:.2f}% < 0.3%)")
                        return False, None, f"Price change too small", 0.0, None, None

            # === 売買判定（トレンドフォロー専用モード） ===
            # v3.1.0: トレンド方向のシグナルのみ許可、逆方向は完全ブロック

            # BUY判定: MACDゴールデンクロス
            if is_golden_cross:
                # 【重要】下降トレンド中はBUY完全禁止（閾値なし）
                if ema_trend == 'down':
                    logger.info(f"🚫 Golden Cross BLOCKED - Downtrend active (EMA20 < EMA50)")
                    logger.info(f"   In downtrend, only SELL signals are allowed")
                # v3.3.0: 損切り後クールダウン中は同方向エントリー禁止
                elif self._is_in_cooldown('BUY'):
                    logger.info(f"🚫 BUY BLOCKED - In cooldown after recent BUY stop loss")
                # v3.4.0: 価格がEMA20を下回っている場合はBUY禁止
                elif price_below_ema20:
                    logger.info(f"🚫 BUY BLOCKED - Price below EMA20 (EMA lag detection)")
                    logger.info(f"   Price ¥{current_price:.3f} < EMA20 ¥{ema_20:.3f}")
                # v3.4.0: ヒストグラムが減少中はBUY禁止
                elif not histogram_increasing and self.last_macd_histogram is not None:
                    logger.info(f"🚫 BUY BLOCKED - MACD histogram decreasing (momentum fading)")
                else:
                    # 上昇トレンド中 + 価格 > EMA20 + ヒストグラム増加中のみBUY許可
                    take_profit = current_price * (1 + self.take_profit_pct)
                    stop_loss = current_price * (1 - self.stop_loss_pct)

                    logger.info(f"🟢 BUY SIGNAL - MACD Golden Cross + Uptrend + Price>EMA20 confirmed")
                    logger.info(f"   Confidence: {confidence:.2f}")
                    logger.info(f"   TP: ¥{take_profit:.2f} (+{self.take_profit_pct*100:.1f}%)")
                    logger.info(f"   SL: ¥{stop_loss:.2f} (-{self.stop_loss_pct*100:.1f}%)")

                    return True, 'BUY', 'MACD Golden Cross + Uptrend + Price>EMA20', confidence, stop_loss, take_profit

            # SELL判定: MACDデッドクロス
            if is_death_cross:
                # 【重要】上昇トレンド中はSELL完全禁止（閾値なし）
                if ema_trend == 'up':
                    logger.info(f"🚫 Death Cross BLOCKED - Uptrend active (EMA20 > EMA50)")
                    logger.info(f"   In uptrend, only BUY signals are allowed")
                # v3.3.0: 短期反発中はSELLを控える（損切り後の連続損失防止）
                elif short_term_bounce:
                    logger.info(f"🚫 Death Cross BLOCKED - Short-term bounce detected (EMA5 > EMA20)")
                    logger.info(f"   Wait for bounce to end before SELL")
                # v3.3.0: 損切り後クールダウン中は同方向エントリー禁止
                elif self._is_in_cooldown('SELL'):
                    logger.info(f"🚫 SELL BLOCKED - In cooldown after recent SELL stop loss")
                # v3.4.0: 価格がEMA20を上回っている場合はSELL禁止
                elif price_above_ema20:
                    logger.info(f"🚫 SELL BLOCKED - Price above EMA20 (EMA lag detection)")
                    logger.info(f"   Price ¥{current_price:.3f} > EMA20 ¥{ema_20:.3f}")
                # v3.4.0: ヒストグラムが増加中はSELL禁止
                elif not histogram_decreasing and self.last_macd_histogram is not None:
                    logger.info(f"🚫 SELL BLOCKED - MACD histogram increasing (momentum rising)")
                else:
                    # 下降トレンド中 + 価格 < EMA20 + ヒストグラム減少中のみSELL許可
                    take_profit = current_price * (1 - self.take_profit_pct)
                    stop_loss = current_price * (1 + self.stop_loss_pct)

                    logger.info(f"🔴 SELL SIGNAL - MACD Death Cross + Downtrend + Price<EMA20 confirmed")
                    logger.info(f"   Confidence: {confidence:.2f}")
                    logger.info(f"   TP: ¥{take_profit:.2f} (-{self.take_profit_pct*100:.1f}%)")
                    logger.info(f"   SL: ¥{stop_loss:.2f} (+{self.stop_loss_pct*100:.1f}%)")

                    return True, 'SELL', 'MACD Death Cross + Downtrend + Price<EMA20', confidence, stop_loss, take_profit

            # === クロスなし: 継続シグナルチェック ===
            # v3.3.1: 閾値を大幅緩和（0.015→0.008）- 低ボラティリティ対応
            # 14時間シグナルなしの問題を解決
            histogram_threshold = 0.008 if not skip_price_filter else 0.005

            logger.info(f"   📈 Checking continuation signal (threshold: {histogram_threshold})")

            # BUY継続シグナル: MACD above + 強いヒストグラム + 上昇トレンド
            if macd_position == 'above' and macd_histogram > histogram_threshold:
                if ema_trend == 'down':
                    logger.info(f"🚫 BUY blocked - Downtrend active (EMA20 < EMA50)")
                elif self._is_in_cooldown('BUY'):
                    logger.info(f"🚫 BUY blocked - In cooldown after recent BUY stop loss")
                # v3.4.0: 価格がEMA20を下回っている場合はBUY禁止
                elif price_below_ema20:
                    logger.info(f"🚫 BUY blocked - Price below EMA20 (¥{current_price:.3f} < ¥{ema_20:.3f})")
                # v3.4.0: ヒストグラムが減少中はBUY禁止
                elif not histogram_increasing and self.last_macd_histogram is not None:
                    logger.info(f"🚫 BUY blocked - Histogram decreasing (momentum fading)")
                else:
                    take_profit = current_price * (1 + self.take_profit_pct)
                    stop_loss = current_price * (1 - self.stop_loss_pct)
                    signal_type = "Reversal" if skip_price_filter else "Continuation"
                    logger.info(f"🟢 BUY SIGNAL ({signal_type}) - MACD Bullish + Uptrend + Price>EMA20")
                    logger.info(f"   Histogram: {macd_histogram:.4f} > {histogram_threshold}")
                    return True, 'BUY', f'MACD Bullish ({signal_type}) + Uptrend + Price>EMA20', confidence, stop_loss, take_profit

            # SELL継続シグナル: MACD below + 強いヒストグラム + 下降トレンド
            elif macd_position == 'below' and macd_histogram < -histogram_threshold:
                if ema_trend == 'up':
                    logger.info(f"🚫 SELL blocked - Uptrend active (EMA20 > EMA50)")
                elif short_term_bounce:
                    logger.info(f"🚫 SELL blocked - Short-term bounce detected (EMA5 > EMA20)")
                elif self._is_in_cooldown('SELL'):
                    logger.info(f"🚫 SELL blocked - In cooldown after recent SELL stop loss")
                # v3.4.0: 価格がEMA20を上回っている場合はSELL禁止
                elif price_above_ema20:
                    logger.info(f"🚫 SELL blocked - Price above EMA20 (¥{current_price:.3f} > ¥{ema_20:.3f})")
                # v3.4.0: ヒストグラムが増加中はSELL禁止
                elif not histogram_decreasing and self.last_macd_histogram is not None:
                    logger.info(f"🚫 SELL blocked - Histogram increasing (momentum rising)")
                else:
                    take_profit = current_price * (1 - self.take_profit_pct)
                    stop_loss = current_price * (1 + self.stop_loss_pct)
                    signal_type = "Reversal" if skip_price_filter else "Continuation"
                    logger.info(f"🔴 SELL SIGNAL ({signal_type}) - MACD Bearish + Downtrend + Price<EMA20")
                    logger.info(f"   Histogram: {macd_histogram:.4f} < -{histogram_threshold}")
                    return True, 'SELL', f'MACD Bearish ({signal_type}) + Downtrend + Price<EMA20', confidence, stop_loss, take_profit

            # シグナルなし
            logger.info(f"⏸️ No valid signal - waiting...")
            logger.info(f"   MACD position: {macd_position}, Histogram: {macd_histogram:.4f}")
            logger.info(f"   EMA trend: {ema_trend}, Required histogram: >{histogram_threshold} or <-{histogram_threshold}")
            return False, None, "No valid signal (waiting for stronger MACD)", confidence, None, None

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
