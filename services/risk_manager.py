import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class RiskManager:
    """
    Risk management system for trading bot
    """
    
    def __init__(self):
        self.max_position_size_ratio = 0.05  # Max 5% of balance per trade
        self.stop_loss_ratio = 0.02  # 2% stop loss
        self.take_profit_ratio = 0.04  # 4% take profit
        self.max_daily_loss = 0.10  # Max 10% daily loss
        self.max_open_trades = 3
        
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
    
    def calculate_position_size(self, available_balance, current_price, symbol='DOGE_JPY'):
        """Calculate position size based on available balance and risk rules"""
        try:
            # Calculate maximum position value (JPY) - 残高の5%を使用
            max_position_value = available_balance * self.max_position_size_ratio
            
            # Calculate position size in crypto units
            position_size = max_position_value / current_price
            
            logger.info(f"Position size calculation: balance={available_balance}, max_value={max_position_value}, size={position_size}")
            
            # DOGE取引の場合は最小10単位に調整
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
            
            return position_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 10 if 'DOGE_' in symbol else 0.0001
    
    def should_close_trade(self, trade, current_price, market_indicators=None):
        """Check if a trade should be closed based on risk rules and trend reversal"""
        try:
            entry_price = float(trade.price)
            
            if trade.trade_type.lower() == 'buy':
                # For buy trades
                profit_loss_ratio = (current_price - entry_price) / entry_price
                
                # Check stop loss
                if profit_loss_ratio <= -self.stop_loss_ratio:
                    return True, f"Stop loss triggered: {profit_loss_ratio:.4f}"
                
                # Check take profit
                if profit_loss_ratio >= self.take_profit_ratio:
                    return True, f"Take profit triggered: {profit_loss_ratio:.4f}"
                
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
                
                # Check take profit
                if profit_loss_ratio >= self.take_profit_ratio:
                    return True, f"Take profit triggered: {profit_loss_ratio:.4f}"
                
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