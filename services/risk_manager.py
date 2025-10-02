import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Risk management system for trading bot
    """
    
    def __init__(self):
        self.max_position_size_ratio = 0.15  # Max 15% of balance per trade (増加: 5% → 15%)
        self.stop_loss_ratio = 0.03  # 3% stop loss (緩和: 2% → 3%)
        self.take_profit_ratio = 0.025  # 2.5% take profit (早期利確: 4% → 2.5%)
        self.max_daily_loss = 0.15  # Max 15% daily loss (緩和: 10% → 15%)
        self.max_open_trades = 5  # 最大5ポジション (増加: 3 → 5)

        # Dynamic profit-taking parameters
        self.min_take_profit = 0.015  # 1.5% minimum profit
        self.max_take_profit = 0.05   # 5% maximum profit (調整: 8% → 5%)
        self.volatility_multiplier = 2.0  # Volatility adjustment factor

        # Trailing stop parameters (早期開始)
        self.trailing_stop_enabled = True
        self.trailing_start_profit = 0.015  # Start trailing at 1.5% profit (早期化: 2% → 1.5%)
        self.trailing_distance = 0.01      # 1% trailing distance
        
    def update_settings(self, settings):
        """Update risk settings from user settings"""
        try:
            if hasattr(settings, 'max_position_size_ratio'):
                self.max_position_size_ratio = settings.max_position_size_ratio
            if hasattr(settings, 'stop_loss_ratio'):
                self.stop_loss_ratio = settings.stop_loss_ratio
            if hasattr(settings, 'take_profit_ratio'):
                self.take_profit_ratio = settings.take_profit_ratio
            if hasattr(settings, 'max_daily_loss'):
                self.max_daily_loss = settings.max_daily_loss
            if hasattr(settings, 'max_open_trades'):
                self.max_open_trades = settings.max_open_trades
                
            logger.info("Risk manager settings updated")
        except Exception as e:
            logger.error(f"Error updating risk settings: {e}")
    
    def calculate_position_size(self, available_balance, current_price, symbol='DOGE_JPY', market_indicators=None, confidence=1.0):
        """Calculate optimal position size based on balance, risk, volatility, and signal confidence"""
        try:
            # Base position size calculation with volatility adjustment
            volatility_score = 0.5  # Default medium volatility
            if market_indicators:
                volatility_score = self._calculate_volatility_score(market_indicators)

            # Adjust position size ratio based on volatility and confidence
            base_ratio = self.max_position_size_ratio

            # Volatility adjustment (緩和版 - ボラティリティによる削減を抑制)
            if volatility_score > 0.7:  # High volatility - reduce position size
                volatility_multiplier = 0.75  # 75% of normal size (緩和: 50% → 75%)
                logger.info(f"High volatility ({volatility_score:.3f}) - slightly reducing position size")
            elif volatility_score < 0.3:  # Low volatility - can increase position size
                volatility_multiplier = 1.5  # 150% of normal size
                logger.info(f"Low volatility ({volatility_score:.3f}) - increasing position size")
            else:  # Medium volatility
                volatility_multiplier = 1.2  # 通常より大きく (増加: 1.0 → 1.2)
                logger.info(f"Medium volatility ({volatility_score:.3f}) - slightly increased position size")

            # Confidence adjustment (0.5 - 1.5 multiplier)
            confidence_multiplier = 0.5 + confidence
            logger.info(f"Signal confidence {confidence:.3f} - confidence multiplier: {confidence_multiplier:.3f}")

            # Calculate adjusted position ratio (with limits)
            adjusted_ratio = base_ratio * volatility_multiplier * confidence_multiplier
            adjusted_ratio = min(max(adjusted_ratio, 0.01), 0.8)  # Limits: 1% - 80% of balance

            # Calculate position value and size
            max_position_value = available_balance * adjusted_ratio
            position_size = max_position_value / current_price

            logger.info(f"Enhanced position calculation:")
            logger.info(f"  Available balance: {available_balance:.2f}")
            logger.info(f"  Base ratio: {base_ratio:.3f}")
            logger.info(f"  Volatility multiplier: {volatility_multiplier:.3f}")
            logger.info(f"  Confidence multiplier: {confidence_multiplier:.3f}")
            logger.info(f"  Adjusted ratio: {adjusted_ratio:.3f}")
            logger.info(f"  Max position value: {max_position_value:.2f}")
            logger.info(f"  Raw position size: {position_size:.6f}")

            # Apply symbol-specific minimum requirements
            if 'DOGE_' in symbol:
                position_size = max(int(position_size), 10)  # DOGE最小10単位
                logger.info(f"DOGE position adjusted to: {position_size} units")
            elif 'XRP_' in symbol:
                position_size = max(int(position_size), 10)  # XRP最小10単位
            elif 'BTC_' in symbol:
                position_size = max(position_size, 0.0001)  # BTC最小0.0001
            elif 'ETH_' in symbol:
                position_size = max(position_size, 0.001)   # ETH最小0.001
            else:
                position_size = max(position_size, 1)       # その他最小1単位

            # Safety check - never exceed 80% of balance
            max_safe_value = available_balance * 0.8
            if position_size * current_price > max_safe_value:
                position_size = max_safe_value / current_price
                if 'DOGE_' in symbol or 'XRP_' in symbol:
                    position_size = int(position_size)
                logger.warning(f"Position size capped for safety: {position_size}")

            return position_size

        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 10 if 'DOGE_' in symbol else 0.0001
    
    def should_close_trade(self, trade, current_price, market_indicators=None):
        """Check if a trade should be closed based on dynamic risk rules and trend reversal"""
        try:
            entry_price = float(trade.price)

            # Calculate dynamic take profit based on market volatility
            dynamic_take_profit = self._calculate_dynamic_take_profit(market_indicators)

            if trade.trade_type.lower() == 'buy':
                # For buy trades
                profit_loss_ratio = (current_price - entry_price) / entry_price

                # Check stop loss
                if profit_loss_ratio <= -self.stop_loss_ratio:
                    return True, f"Stop loss triggered: {profit_loss_ratio:.4f}"

                # Check trailing stop
                if self.trailing_stop_enabled and hasattr(trade, 'trailing_stop_price'):
                    if current_price <= trade.trailing_stop_price:
                        return True, f"Trailing stop triggered at {trade.trailing_stop_price:.4f}"

                # Check dynamic take profit
                if profit_loss_ratio >= dynamic_take_profit:
                    return True, f"Dynamic take profit triggered: {profit_loss_ratio:.4f} (target: {dynamic_take_profit:.4f})"

                # Update trailing stop if profitable
                if self.trailing_stop_enabled and profit_loss_ratio >= self.trailing_start_profit:
                    new_trailing_stop = current_price * (1 - self.trailing_distance)
                    if not hasattr(trade, 'trailing_stop_price') or new_trailing_stop > trade.trailing_stop_price:
                        trade.trailing_stop_price = new_trailing_stop
                        logger.info(f"Updated trailing stop for trade {trade.id}: {new_trailing_stop:.4f}")

                # Check trend reversal for buy positions
                if market_indicators:
                    trend_reversal = self._check_trend_reversal_for_buy(market_indicators)
                    if trend_reversal:
                        return True, f"Trend reversal detected for BUY position: {trend_reversal}"

            else:  # sell trades
                # For sell trades
                profit_loss_ratio = (entry_price - current_price) / entry_price

                # Check stop loss
                if profit_loss_ratio <= -self.stop_loss_ratio:
                    return True, f"Stop loss triggered: {profit_loss_ratio:.4f}"

                # Check trailing stop
                if self.trailing_stop_enabled and hasattr(trade, 'trailing_stop_price'):
                    if current_price >= trade.trailing_stop_price:
                        return True, f"Trailing stop triggered at {trade.trailing_stop_price:.4f}"

                # Check dynamic take profit
                if profit_loss_ratio >= dynamic_take_profit:
                    return True, f"Dynamic take profit triggered: {profit_loss_ratio:.4f} (target: {dynamic_take_profit:.4f})"

                # Update trailing stop if profitable
                if self.trailing_stop_enabled and profit_loss_ratio >= self.trailing_start_profit:
                    new_trailing_stop = current_price * (1 + self.trailing_distance)
                    if not hasattr(trade, 'trailing_stop_price') or new_trailing_stop < trade.trailing_stop_price:
                        trade.trailing_stop_price = new_trailing_stop
                        logger.info(f"Updated trailing stop for trade {trade.id}: {new_trailing_stop:.4f}")

                # Check trend reversal for sell positions
                if market_indicators:
                    trend_reversal = self._check_trend_reversal_for_sell(market_indicators)
                    if trend_reversal:
                        return True, f"Trend reversal detected for SELL position: {trend_reversal}"

            return False, "No exit condition met"

        except Exception as e:
            logger.error(f"Error checking trade exit conditions: {e}")
            return False, "Error in exit check"
    
    def calculate_profit_loss(self, trade, current_price):
        """Calculate profit/loss for a trade"""
        try:
            entry_price = float(trade.price)
            amount = float(trade.amount)
            
            if trade.trade_type.lower() == 'buy':
                # For buy trades: profit when price goes up
                pl_amount = (current_price - entry_price) * amount
                pl_percentage = (current_price - entry_price) / entry_price * 100
            else:
                # For sell trades: profit when price goes down
                pl_amount = (entry_price - current_price) * amount
                pl_percentage = (entry_price - current_price) / entry_price * 100
            
            return {
                'amount': pl_amount,
                'percentage': pl_percentage
            }
            
        except Exception as e:
            logger.error(f"Error calculating profit/loss: {e}")
            return {'amount': 0, 'percentage': 0}
    
    def evaluate_market_conditions(self, indicators):
        """Evaluate current market conditions and risk"""
        try:
            # Initialize scores
            trend_score = 0
            volatility_score = 0
            momentum_score = 0
            
            # RSI analysis
            rsi = indicators.get('rsi_14', 50)
            if rsi > 70:
                trend_score -= 1  # Overbought
            elif rsi < 30:
                trend_score += 1  # Oversold
            
            # MACD analysis
            macd_line = indicators.get('macd_line', 0)
            macd_signal = indicators.get('macd_signal', 0)
            if macd_line > macd_signal:
                momentum_score += 1
            else:
                momentum_score -= 1
            
            # Bollinger Bands analysis
            close = indicators.get('close', 0)
            bb_upper = indicators.get('bb_upper', close * 1.02)
            bb_lower = indicators.get('bb_lower', close * 0.98)
            bb_middle = indicators.get('bb_middle', close)
            
            # Price position within bands
            if close > bb_upper:
                volatility_score += 2  # High volatility, overbought
            elif close < bb_lower:
                volatility_score += 2  # High volatility, oversold
            elif abs(close - bb_middle) / bb_middle < 0.01:
                volatility_score -= 1  # Low volatility
            
            # Moving average trend
            sma_20 = indicators.get('sma_20', close)
            ema_12 = indicators.get('ema_12', close)
            ema_26 = indicators.get('ema_26', close)
            
            if ema_12 > ema_26 and close > sma_20:
                trend_score += 2  # Strong uptrend
            elif ema_12 < ema_26 and close < sma_20:
                trend_score -= 2  # Strong downtrend
            
            # Determine overall market trend
            total_score = trend_score + momentum_score
            
            if total_score >= 2:
                market_trend = 'bullish'
                trend_strength = min(abs(total_score) / 4.0, 1.0)
            elif total_score <= -2:
                market_trend = 'bearish'
                trend_strength = min(abs(total_score) / 4.0, 1.0)
            else:
                market_trend = 'neutral'
                trend_strength = 0.3
            
            # Risk score (0-10, higher = more risky)
            risk_score = min(abs(volatility_score) + 2, 10)
            
            return {
                'market_trend': market_trend,
                'trend_strength': trend_strength,
                'risk_score': risk_score,
                'volatility': abs(volatility_score)
            }
            
        except Exception as e:
            logger.error(f"Error evaluating market conditions: {e}")
            return {
                'market_trend': 'neutral',
                'trend_strength': 0.5,
                'risk_score': 5,
                'volatility': 1
            }
    
    def _check_trend_reversal_for_buy(self, indicators):
        """Check if trend is reversing against BUY position (turning bearish)"""
        try:
            # RSI overbought condition (strong reversal signal)
            rsi = indicators.get('rsi_14', 50)
            if rsi > 75:  # Strong overbought
                return "RSI extremely overbought (>75)"
            
            # MACD bearish crossover
            macd_line = indicators.get('macd_line', 0)
            macd_signal = indicators.get('macd_signal', 0)
            macd_histogram = indicators.get('macd_histogram', 0)
            
            # Strong bearish MACD signal
            if macd_line < macd_signal and macd_histogram < -0.5:
                return "Strong MACD bearish crossover"
            
            # Price breaking below key moving averages
            close = indicators.get('close', 0)
            ema_12 = indicators.get('ema_12', close)
            ema_26 = indicators.get('ema_26', close)
            sma_20 = indicators.get('sma_20', close)
            
            # Death cross pattern (fast MA below slow MA) + price below both
            if ema_12 < ema_26 and close < sma_20 and close < ema_12:
                return "Death cross pattern with price breakdown"
            
            # Bollinger Band squeeze with downward breakout
            bb_upper = indicators.get('bb_upper', close * 1.02)
            bb_lower = indicators.get('bb_lower', close * 0.98)
            bb_middle = indicators.get('bb_middle', close)
            
            # Price falling below middle band with momentum
            if close < bb_middle * 0.995 and macd_line < macd_signal:
                return "Bollinger Band middle break with bearish momentum"
            
            # Multiple weak signals combined
            weak_signals = 0
            if rsi > 65:  # Moderately overbought
                weak_signals += 1
            if macd_line < macd_signal:  # MACD bearish
                weak_signals += 1
            if close < ema_12:  # Price below fast MA
                weak_signals += 1
            if close < sma_20:  # Price below SMA
                weak_signals += 1
            
            if weak_signals >= 3:
                return f"Multiple bearish signals ({weak_signals}/4)"
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking trend reversal for buy: {e}")
            return None
    
    def _check_trend_reversal_for_sell(self, indicators):
        """Check if trend is reversing against SELL position (turning bullish)"""
        try:
            # RSI oversold condition (strong reversal signal)
            rsi = indicators.get('rsi_14', 50)
            if rsi < 25:  # Strong oversold
                return "RSI extremely oversold (<25)"
            
            # MACD bullish crossover
            macd_line = indicators.get('macd_line', 0)
            macd_signal = indicators.get('macd_signal', 0)
            macd_histogram = indicators.get('macd_histogram', 0)
            
            # Strong bullish MACD signal
            if macd_line > macd_signal and macd_histogram > 0.5:
                return "Strong MACD bullish crossover"
            
            # Price breaking above key moving averages
            close = indicators.get('close', 0)
            ema_12 = indicators.get('ema_12', close)
            ema_26 = indicators.get('ema_26', close)
            sma_20 = indicators.get('sma_20', close)
            
            # Golden cross pattern (fast MA above slow MA) + price above both
            if ema_12 > ema_26 and close > sma_20 and close > ema_12:
                return "Golden cross pattern with price breakout"
            
            # Bollinger Band squeeze with upward breakout
            bb_upper = indicators.get('bb_upper', close * 1.02)
            bb_lower = indicators.get('bb_lower', close * 0.98)
            bb_middle = indicators.get('bb_middle', close)
            
            # Price rising above middle band with momentum
            if close > bb_middle * 1.005 and macd_line > macd_signal:
                return "Bollinger Band middle break with bullish momentum"
            
            # Multiple weak signals combined
            weak_signals = 0
            if rsi < 35:  # Moderately oversold
                weak_signals += 1
            if macd_line > macd_signal:  # MACD bullish
                weak_signals += 1
            if close > ema_12:  # Price above fast MA
                weak_signals += 1
            if close > sma_20:  # Price above SMA
                weak_signals += 1
            
            if weak_signals >= 3:
                return f"Multiple bullish signals ({weak_signals}/4)"
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking trend reversal for sell: {e}")
            return None

    def _calculate_dynamic_take_profit(self, market_indicators):
        """Calculate dynamic take profit based on market volatility and conditions"""
        try:
            if not market_indicators:
                return self.take_profit_ratio

            # Calculate market volatility using various indicators
            volatility_score = self._calculate_volatility_score(market_indicators)

            # Adjust take profit based on volatility
            if volatility_score > 0.7:  # High volatility
                dynamic_tp = self.min_take_profit  # Quick profits in volatile markets
                logger.info(f"High volatility detected ({volatility_score:.3f}) - using quick take profit: {dynamic_tp:.3f}")
            elif volatility_score < 0.3:  # Low volatility
                dynamic_tp = self.max_take_profit  # Let profits run in stable markets
                logger.info(f"Low volatility detected ({volatility_score:.3f}) - using extended take profit: {dynamic_tp:.3f}")
            else:  # Medium volatility
                # Linear interpolation between min and max
                dynamic_tp = self.min_take_profit + (self.max_take_profit - self.min_take_profit) * (1 - volatility_score)
                logger.info(f"Medium volatility detected ({volatility_score:.3f}) - using adaptive take profit: {dynamic_tp:.3f}")

            return min(max(dynamic_tp, self.min_take_profit), self.max_take_profit)

        except Exception as e:
            logger.error(f"Error calculating dynamic take profit: {e}")
            return self.take_profit_ratio

    def _calculate_volatility_score(self, indicators):
        """Calculate a volatility score from 0-1 based on market indicators"""
        try:
            volatility_factors = []

            # RSI volatility - extreme values indicate high volatility
            rsi = indicators.get('rsi_14', 50)
            rsi_volatility = max(abs(rsi - 50) / 50, 0)  # Distance from neutral (50)
            volatility_factors.append(min(rsi_volatility, 1))

            # Bollinger Band width - wider bands indicate higher volatility
            bb_upper = indicators.get('bb_upper', 0)
            bb_lower = indicators.get('bb_lower', 0)
            close = indicators.get('close', 0)
            if bb_upper > 0 and bb_lower > 0 and close > 0:
                bb_width = (bb_upper - bb_lower) / close
                bb_volatility = min(bb_width * 50, 1)  # Normalize BB width
                volatility_factors.append(bb_volatility)

            # MACD histogram volatility - larger values indicate momentum changes
            macd_histogram = indicators.get('macd_histogram', 0)
            macd_volatility = min(abs(macd_histogram) * 10, 1)  # Normalize MACD histogram
            volatility_factors.append(macd_volatility)

            # Price movement relative to moving averages
            ema_12 = indicators.get('ema_12', close)
            ema_26 = indicators.get('ema_26', close)
            if ema_26 > 0:
                ma_divergence = abs(ema_12 - ema_26) / ema_26
                ma_volatility = min(ma_divergence * 100, 1)  # Normalize MA divergence
                volatility_factors.append(ma_volatility)

            # Average volatility score
            if volatility_factors:
                avg_volatility = sum(volatility_factors) / len(volatility_factors)
                return min(max(avg_volatility, 0), 1)
            else:
                return 0.5  # Default medium volatility

        except Exception as e:
            logger.error(f"Error calculating volatility score: {e}")
            return 0.5  # Default medium volatility