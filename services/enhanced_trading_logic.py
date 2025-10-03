import logging
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class EnhancedTradingLogic:
    """
    強化されたトレーディングロジック - トレンドフィルター付き
    下降トレンド中の騙しシグナルを排除
    """

    def __init__(self):
        self.last_trade_time = None
        self.min_trade_interval = 0

    def should_trade(self, market_data):
        """
        トレンドフィルター付き取引判定
        """
        try:
            current_price = market_data.get('close', 0)
            rsi = market_data.get('rsi_14', 50)
            macd_line = market_data.get('macd_line', 0)
            macd_signal = market_data.get('macd_signal', 0)
            bb_upper = market_data.get('bb_upper', current_price * 1.02)
            bb_lower = market_data.get('bb_lower', current_price * 0.98)
            bb_middle = market_data.get('bb_middle', current_price)
            ema_20 = market_data.get('ema_20', current_price)
            ema_50 = market_data.get('ema_50', current_price)  # 長期トレンド用

            # === 1. トレンド分析（最重要） ===
            trend_analysis = self._analyze_market_trend(market_data)
            trend_direction = trend_analysis['direction']
            trend_strength = trend_analysis['strength']

            logger.info(f"Trend Analysis - Direction: {trend_direction}, Strength: {trend_strength:.3f}")

            signals = []

            # === 2. RSIシグナル（補助的・重み削減） ===
            if trend_direction == 'STRONG_DOWN':
                # 強い下降トレンド中でも極端なRSIは逆張り許可
                if rsi < 20:  # 極端な売られすぎは反転期待
                    signals.append(('BUY', 'RSI Extreme Oversold - Reversal Expected', 0.5))
                    logger.info(f"Contrarian RSI Buy: {rsi:.2f} < 20 (reversal expected in downtrend)")
                elif rsi > 70:
                    signals.append(('SELL', 'RSI Overbought + Strong Downtrend', 0.6))
                    logger.info(f"Enhanced RSI Sell: {rsi:.2f} > 70 (strong downtrend)")
            elif trend_direction == 'STRONG_UP':
                # 強い上昇トレンド中でも極端なRSIは逆張り許可
                if rsi < 30:
                    signals.append(('BUY', 'RSI Oversold + Strong Uptrend', 0.6))
                    logger.info(f"Enhanced RSI Buy: {rsi:.2f} < 30 (strong uptrend)")
                elif rsi > 80:  # 極端な買われすぎは反転期待
                    signals.append(('SELL', 'RSI Extreme Overbought - Reversal Expected', 0.5))
                    logger.info(f"Contrarian RSI Sell: {rsi:.2f} > 80 (reversal expected in uptrend)")
            else:
                # 中立・弱いトレンド時は閾値緩和
                if rsi < 30:  # 緩和: 25 → 30
                    signals.append(('BUY', 'RSI Oversold', 0.5))
                    logger.info(f"RSI Buy: {rsi:.2f} < 30")
                elif rsi > 70:  # 緩和: 75 → 70
                    signals.append(('SELL', 'RSI Overbought', 0.5))
                    logger.info(f"RSI Sell: {rsi:.2f} > 70")

            # === 3. 最優先MACDシグナル（重み大幅増加） ===
            macd_diff = abs(macd_line - macd_signal)

            if macd_line > macd_signal:
                # MACDクロスオーバー - 最優先買いシグナル
                if macd_line > 0:
                    # ポジティブゾーンでのクロスオーバー - 非常に強い
                    if macd_diff > 0.5:
                        signals.append(('BUY', 'MACD Strong Bullish Crossover', 1.5))
                        logger.info(f"🔥 PRIORITY MACD Buy: Strong positive crossover (diff: {macd_diff:.3f})")
                    else:
                        signals.append(('BUY', 'MACD Bullish Crossover', 1.2))
                        logger.info(f"⚡ PRIORITY MACD Buy: Positive crossover (diff: {macd_diff:.3f})")
                else:
                    # ネガティブゾーンからの転換 - 強い
                    signals.append(('BUY', 'MACD Bullish Reversal', 1.0))
                    logger.info(f"📈 PRIORITY MACD Buy: Reversal from negative (diff: {macd_diff:.3f})")

            elif macd_line < macd_signal:
                # MACDクロスアンダー - 最優先売りシグナル
                if macd_line < 0:
                    # ネガティブゾーンでのクロスアンダー - 非常に強い
                    if macd_diff > 0.5:
                        signals.append(('SELL', 'MACD Strong Bearish Crossunder', 1.5))
                        logger.info(f"🔥 PRIORITY MACD Sell: Strong negative crossunder (diff: {macd_diff:.3f})")
                    else:
                        signals.append(('SELL', 'MACD Bearish Crossunder', 1.2))
                        logger.info(f"⚡ PRIORITY MACD Sell: Negative crossunder (diff: {macd_diff:.3f})")
                else:
                    # ポジティブゾーンからの転換 - 強い
                    signals.append(('SELL', 'MACD Bearish Reversal', 1.0))
                    logger.info(f"📉 PRIORITY MACD Sell: Reversal from positive (diff: {macd_diff:.3f})")

            # === 4. Bollinger Bandsシグナル（補助的・重み削減） ===
            bb_position = (current_price - bb_lower) / (bb_upper - bb_lower)

            if current_price < bb_lower * 1.01:  # BB下限近く
                if trend_direction in ['UP', 'STRONG_UP']:
                    signals.append(('BUY', 'BB Bounce + Uptrend', 0.5))
                    logger.info(f"BB Buy: Lower band + uptrend")
                elif trend_direction == 'NEUTRAL':
                    signals.append(('BUY', 'BB Bounce Neutral', 0.4))
                    logger.info(f"Weak BB Buy: Lower band + neutral")
                else:
                    logger.info(f"BB Buy IGNORED: Lower band but downtrend")

            elif current_price > bb_upper * 0.99:  # BB上限近く
                if trend_direction in ['DOWN', 'STRONG_DOWN']:
                    signals.append(('SELL', 'BB Reversal + Downtrend', 0.5))
                    logger.info(f"BB Sell: Upper band + downtrend")
                elif trend_direction == 'NEUTRAL':
                    signals.append(('SELL', 'BB Reversal Neutral', 0.4))
                    logger.info(f"Weak BB Sell: Upper band + neutral")

            # === 5. EMAトレンド確認（補助的・重み削減） ===
            if current_price > ema_20 * 1.015 and ema_20 > ema_50:
                signals.append(('BUY', 'EMA Bullish Alignment', 0.4))
                logger.info("EMA Buy: Price above EMA20 > EMA50")
            elif current_price < ema_20 * 0.985 and ema_20 < ema_50:
                signals.append(('SELL', 'EMA Bearish Alignment', 0.4))
                logger.info("EMA Sell: Price below EMA20 < EMA50")

            # === 6. シグナル統合・判定 ===
            buy_signals = [s for s in signals if s[0] == 'BUY']
            sell_signals = [s for s in signals if s[0] == 'SELL']

            buy_strength = sum([s[2] for s in buy_signals])
            sell_strength = sum([s[2] for s in sell_signals])

            # トレンド強度に応じた閾値調整（緩和版）
            if abs(trend_strength) > 0.02:  # 強いトレンド
                min_signal_strength = 0.8  # 緩和: 1.2 → 0.8
            elif abs(trend_strength) > 0.01:  # 中程度トレンド
                min_signal_strength = 0.6  # 緩和: 0.9 → 0.6
            else:  # 弱いトレンド
                min_signal_strength = 0.4  # 緩和: 0.6 → 0.4

            logger.info(f"Enhanced Signal Analysis:")
            logger.info(f"  Buy Strength: {buy_strength:.2f}")
            logger.info(f"  Sell Strength: {sell_strength:.2f}")
            logger.info(f"  Required Threshold: {min_signal_strength:.2f}")
            logger.info(f"  Buy Signals: {[f'{s[1]}({s[2]})' for s in buy_signals]}")
            logger.info(f"  Sell Signals: {[f'{s[1]}({s[2]})' for s in sell_signals]}")

            # 最終判定
            if buy_strength >= min_signal_strength and buy_strength > sell_strength:
                reasons = [s[1] for s in buy_signals]
                return True, 'BUY', f"Enhanced Buy: {', '.join(reasons)}", buy_strength
            elif sell_strength >= min_signal_strength and sell_strength > buy_strength:
                reasons = [s[1] for s in sell_signals]
                return True, 'SELL', f"Enhanced Sell: {', '.join(reasons)}", sell_strength

            # シグナル不足
            logger.info(f"No strong signal - Buy: {buy_strength:.2f}, Sell: {sell_strength:.2f}, Required: {min_signal_strength:.2f}")
            return False, None, "No clear enhanced signal", max(buy_strength, sell_strength)

        except Exception as e:
            logger.error(f"Error in enhanced trading decision: {e}")
            return False, None, f"Error: {str(e)}", 0.0

    def _analyze_market_trend(self, market_data):
        """
        市場トレンド分析 - 過去20期間の価格動向
        """
        try:
            # 簡易的なトレンド計算（実際は過去データの配列が必要）
            current_price = market_data.get('close', 0)
            ema_20 = market_data.get('ema_20', current_price)
            ema_50 = market_data.get('ema_50', current_price)

            # EMAベースのトレンド強度
            price_ema_diff = (current_price - ema_20) / ema_20
            ema_trend = (ema_20 - ema_50) / ema_50

            # 総合トレンド強度
            trend_strength = (price_ema_diff + ema_trend) / 2

            # トレンド方向判定
            if trend_strength > 0.02:
                direction = 'STRONG_UP'
            elif trend_strength > 0.005:
                direction = 'UP'
            elif trend_strength < -0.02:
                direction = 'STRONG_DOWN'
            elif trend_strength < -0.005:
                direction = 'DOWN'
            else:
                direction = 'NEUTRAL'

            return {
                'direction': direction,
                'strength': trend_strength,
                'price_ema_diff': price_ema_diff,
                'ema_trend': ema_trend
            }

        except Exception as e:
            logger.error(f"Trend analysis error: {e}")
            return {
                'direction': 'NEUTRAL',
                'strength': 0.0,
                'price_ema_diff': 0.0,
                'ema_trend': 0.0
            }

    def check_trade_timing(self):
        """取引タイミングチェック"""
        if not self.last_trade_time:
            return True
        time_since_last = (datetime.now() - self.last_trade_time).total_seconds()
        return time_since_last >= self.min_trade_interval

    def record_trade(self):
        """取引記録"""
        self.last_trade_time = datetime.now()