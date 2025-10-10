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
            rsi = market_data.get('rsi', market_data.get('rsi_14', 50))  # Try 'rsi' first, fallback to 'rsi_14'
            macd_line = market_data.get('macd_line', 0)
            macd_signal = market_data.get('macd_signal', 0)
            bb_upper = market_data.get('bb_upper', current_price * 1.02)
            bb_lower = market_data.get('bb_lower', current_price * 0.98)
            bb_middle = market_data.get('bb_middle', current_price)
            ema_20 = market_data.get('ema_20', current_price)
            ema_50 = market_data.get('ema_50', current_price)  # 長期トレンド用

            # Log current indicator values
            logger.info(f"📊 Indicator Values: Price={current_price:.3f}, RSI={rsi:.2f}, MACD={macd_line:.4f}/{macd_signal:.4f}, BB={bb_lower:.3f}/{bb_upper:.3f}, EMA20/50={ema_20:.3f}/{ema_50:.3f}")

            # === 1. トレンド分析（最重要） ===
            trend_analysis = self._analyze_market_trend(market_data)
            trend_direction = trend_analysis['direction']
            trend_strength = trend_analysis['strength']

            logger.info(f"Trend Analysis - Direction: {trend_direction}, Strength: {trend_strength:.3f}")

            signals = []

            # === 2. RSIシグナル（トレンドフォロー重視） ===
            if trend_direction == 'STRONG_DOWN':
                # 強い下降トレンド中は逆張り禁止 - トレンドフォロー徹底
                if rsi > 60:  # 下降中の戻りは売りチャンス
                    signals.append(('SELL', 'RSI Pullback in Downtrend', 0.7))
                    logger.info(f"Trend-Following RSI Sell: {rsi:.2f} > 60 in strong downtrend")
                elif rsi < 20:
                    # 極端な売られすぎでも逆張りしない - ログのみ
                    logger.info(f"RSI Extreme Oversold: {rsi:.2f} < 20, but NO contrarian trade in downtrend (falling knife)")
            elif trend_direction == 'DOWN':
                # 下降トレンド中
                if rsi > 65:
                    signals.append(('SELL', 'RSI Resistance in Downtrend', 0.6))
                    logger.info(f"RSI Sell: {rsi:.2f} > 65 in downtrend")
            elif trend_direction == 'STRONG_UP':
                # 強い上昇トレンド中は押し目買い
                if rsi < 40:  # 上昇中の押し目は買いチャンス
                    signals.append(('BUY', 'RSI Dip in Uptrend', 0.7))
                    logger.info(f"Trend-Following RSI Buy: {rsi:.2f} < 40 in strong uptrend")
                elif rsi > 80:
                    # 極端な買われすぎでも逆張りしない - ログのみ
                    logger.info(f"RSI Extreme Overbought: {rsi:.2f} > 80, but NO contrarian trade in uptrend")
            elif trend_direction == 'UP':
                # 上昇トレンド中
                if rsi < 35:
                    signals.append(('BUY', 'RSI Dip in Uptrend', 0.6))
                    logger.info(f"RSI Buy: {rsi:.2f} < 35 in uptrend")
            else:
                # 中立時のみ逆張り許可
                if rsi < 30:
                    signals.append(('BUY', 'RSI Oversold Neutral', 0.4))
                    logger.info(f"RSI Buy: {rsi:.2f} < 30 (neutral market)")
                elif rsi > 70:
                    signals.append(('SELL', 'RSI Overbought Neutral', 0.4))
                    logger.info(f"RSI Sell: {rsi:.2f} > 70 (neutral market)")

            # === 3. MACDシグナル（トレンドフォロー重視） ===
            macd_diff = abs(macd_line - macd_signal)

            if macd_line > macd_signal:
                # MACDブリッシュクロスオーバー
                if trend_direction in ['UP', 'STRONG_UP', 'NEUTRAL']:
                    # 上昇トレンドまたは中立時のみBUYシグナル
                    if macd_line > 0:
                        # ポジティブゾーンでのクロスオーバー
                        if macd_diff > 0.5:
                            signals.append(('BUY', 'MACD Strong Bullish + Uptrend', 1.5))
                            logger.info(f"🔥 MACD Buy: Strong positive crossover in {trend_direction} (diff: {macd_diff:.3f})")
                        else:
                            signals.append(('BUY', 'MACD Bullish + Uptrend', 1.2))
                            logger.info(f"⚡ MACD Buy: Positive crossover in {trend_direction} (diff: {macd_diff:.3f})")
                    else:
                        # ネガティブゾーンからの転換（反転シグナル）
                        if trend_direction == 'NEUTRAL':
                            signals.append(('BUY', 'MACD Reversal Neutral', 0.9))
                            logger.info(f"📈 MACD Buy: Reversal from negative in neutral market (diff: {macd_diff:.3f})")
                        else:
                            signals.append(('BUY', 'MACD Reversal + Uptrend', 1.0))
                            logger.info(f"📈 MACD Buy: Reversal from negative in {trend_direction} (diff: {macd_diff:.3f})")
                else:
                    # 下降トレンド中のMACDブリッシュは無視（騙しの可能性）
                    logger.info(f"MACD IGNORED: Bullish crossover in downtrend (falling knife risk, diff: {macd_diff:.3f})")

            elif macd_line < macd_signal:
                # MACDベアリッシュクロスアンダー
                if trend_direction in ['DOWN', 'STRONG_DOWN', 'NEUTRAL']:
                    # 下降トレンドまたは中立時のみSELLシグナル
                    if macd_line < 0:
                        # ネガティブゾーンでのクロスアンダー
                        if macd_diff > 0.5:
                            signals.append(('SELL', 'MACD Strong Bearish + Downtrend', 1.5))
                            logger.info(f"🔥 MACD Sell: Strong negative crossunder in {trend_direction} (diff: {macd_diff:.3f})")
                        else:
                            signals.append(('SELL', 'MACD Bearish + Downtrend', 1.2))
                            logger.info(f"⚡ MACD Sell: Negative crossunder in {trend_direction} (diff: {macd_diff:.3f})")
                    else:
                        # ポジティブゾーンからの転換（反転シグナル）
                        if trend_direction == 'NEUTRAL':
                            signals.append(('SELL', 'MACD Reversal Neutral', 0.9))
                            logger.info(f"📉 MACD Sell: Reversal from positive in neutral market (diff: {macd_diff:.3f})")
                        else:
                            signals.append(('SELL', 'MACD Reversal + Downtrend', 1.0))
                            logger.info(f"📉 MACD Sell: Reversal from positive in {trend_direction} (diff: {macd_diff:.3f})")
                else:
                    # 上昇トレンド中のMACDベアリッシュは無視（騙しの可能性）
                    logger.info(f"MACD IGNORED: Bearish crossunder in uptrend (temporary pullback, diff: {macd_diff:.3f})")

            # === 4. Bollinger Bands（トレンドフォロー） ===
            bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5

            if current_price < bb_lower * 1.01:  # BB下限近く
                if trend_direction in ['UP', 'STRONG_UP']:
                    # 上昇トレンド中のBB下限タッチは押し目買いチャンス
                    signals.append(('BUY', 'BB Dip in Uptrend', 0.6))
                    logger.info(f"BB Buy: Lower band bounce in uptrend")
                elif trend_direction == 'NEUTRAL':
                    signals.append(('BUY', 'BB Bounce Neutral', 0.3))
                    logger.info(f"Weak BB Buy: Lower band in neutral market")
                else:
                    # 下降トレンド中のBB下限は落ちるナイフ - 無視
                    logger.info(f"BB IGNORED: Lower band in downtrend (falling knife)")

            elif current_price > bb_upper * 0.99:  # BB上限近く
                if trend_direction in ['DOWN', 'STRONG_DOWN']:
                    # 下降トレンド中のBB上限タッチは戻り売りチャンス
                    signals.append(('SELL', 'BB Rally in Downtrend', 0.6))
                    logger.info(f"BB Sell: Upper band resistance in downtrend")
                elif trend_direction == 'NEUTRAL':
                    signals.append(('SELL', 'BB Reversal Neutral', 0.3))
                    logger.info(f"Weak BB Sell: Upper band in neutral market")
                else:
                    # 上昇トレンド中のBB上限は強さの証 - 無視
                    logger.info(f"BB IGNORED: Upper band in uptrend (strong momentum)")

            # === 5. EMAトレンド確認（トレンド方向のみ） ===
            if ema_20 > ema_50:  # 上昇トレンド配置
                if current_price > ema_20 * 1.01:
                    signals.append(('BUY', 'EMA Bullish Trend', 0.5))
                    logger.info("EMA Buy: Strong bullish alignment")
            elif ema_20 < ema_50:  # 下降トレンド配置
                if current_price < ema_20 * 0.99:
                    signals.append(('SELL', 'EMA Bearish Trend', 0.5))
                    logger.info("EMA Sell: Strong bearish alignment")

            # === 6. シグナル統合・判定 ===
            buy_signals = [s for s in signals if s[0] == 'BUY']
            sell_signals = [s for s in signals if s[0] == 'SELL']

            buy_strength = sum([s[2] for s in buy_signals])
            sell_strength = sum([s[2] for s in sell_signals])

            # トレンド強度に応じた閾値調整（トレンドフォロー重視）
            if abs(trend_strength) > 0.02:  # 強いトレンド
                min_signal_strength = 0.7  # トレンド方向は積極的
            elif abs(trend_strength) > 0.01:  # 中程度トレンド
                min_signal_strength = 0.8  # 中程度は慎重に
            else:  # 弱いトレンド/中立
                min_signal_strength = 0.5  # 中立時は標準的

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