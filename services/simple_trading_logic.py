import logging
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

class SimpleTradingLogic:
    """
    Simplified trading logic with clear signals
    """
    
    def __init__(self):
        self.last_trade_time = None
        self.min_trade_interval = 0  # No cooldown - allow immediate trading
        
    def should_trade(self, market_data):
        """
        Simple trading decision based on clear technical indicators
        
        :param market_data: Dictionary with price and indicator data
        :return: tuple (should_trade, trade_type, reason, confidence)
        """
        try:
            # Current price and indicators
            current_price = market_data.get('close', 0)
            rsi = market_data.get('rsi_14', 50)
            macd_line = market_data.get('macd_line', 0)
            macd_signal = market_data.get('macd_signal', 0)
            bb_upper = market_data.get('bb_upper', current_price * 1.02)
            bb_lower = market_data.get('bb_lower', current_price * 0.98)
            bb_middle = market_data.get('bb_middle', current_price)
            
            # Calculate signals
            signals = []
            
            # 1. RSI Signals (Strong weight)
            if rsi < 35:
                signals.append(('BUY', 'RSI Oversold', 0.8))
                logger.info(f"RSI Buy Signal: {rsi:.2f} < 35 (oversold)")
            elif rsi > 65:
                signals.append(('SELL', 'RSI Overbought', 0.8))
                logger.info(f"RSI Sell Signal: {rsi:.2f} > 65 (overbought)")
            
            # 2. MACD Signals (Medium weight)
            if macd_line > macd_signal and macd_line > 0:
                signals.append(('BUY', 'MACD Bullish', 0.6))
                logger.info("MACD Buy Signal: Line > Signal and positive")
            elif macd_line < macd_signal and macd_line < 0:
                signals.append(('SELL', 'MACD Bearish', 0.6))
                logger.info("MACD Sell Signal: Line < Signal and negative")
            
            # 3. Bollinger Band Signals (Medium weight)
            if current_price < bb_lower * 1.005:  # Near lower band
                signals.append(('BUY', 'BB Bounce', 0.7))
                logger.info(f"BB Buy Signal: Price {current_price} near lower band {bb_lower}")
            elif current_price > bb_upper * 0.995:  # Near upper band
                signals.append(('SELL', 'BB Reversal', 0.7))
                logger.info(f"BB Sell Signal: Price {current_price} near upper band {bb_upper}")
            
            # 4. Moving Average Signal - Changed to EMA for better responsiveness
            ema_20 = market_data.get('ema_20', current_price)
            if current_price > ema_20 * 1.01:
                signals.append(('BUY', 'Above EMA', 0.5))
            elif current_price < ema_20 * 0.99:
                signals.append(('SELL', 'Below EMA', 0.5))
            
            # Evaluate signals
            buy_signals = [s for s in signals if s[0] == 'BUY']
            sell_signals = [s for s in signals if s[0] == 'SELL']
            
            buy_strength = sum([s[2] for s in buy_signals])
            sell_strength = sum([s[2] for s in sell_signals])
            
            logger.info(f"Signal Analysis - Buy strength: {buy_strength:.2f}, Sell strength: {sell_strength:.2f}")
            logger.info(f"Buy signals: {[f'{s[1]}({s[2]})' for s in buy_signals]}")
            logger.info(f"Sell signals: {[f'{s[1]}({s[2]})' for s in sell_signals]}")
            
            # Decision making
            min_signal_strength = 0.8  # Lower threshold for more trades
            
            if buy_strength >= min_signal_strength and buy_strength > sell_strength:
                reasons = [s[1] for s in buy_signals]
                return True, 'BUY', f"Buy signals: {', '.join(reasons)}", buy_strength
                
            elif sell_strength >= min_signal_strength and sell_strength > buy_strength:
                reasons = [s[1] for s in sell_signals]
                return True, 'SELL', f"Sell signals: {', '.join(reasons)}", sell_strength
            
            # No strong signal
            logger.info(f"No strong trading signal. Buy: {buy_strength:.2f}, Sell: {sell_strength:.2f}, Min required: {min_signal_strength}")
            return False, None, "No clear signal", max(buy_strength, sell_strength)
            
        except Exception as e:
            logger.error(f"Error in trading decision: {e}")
            return False, None, f"Error: {str(e)}", 0.0
    
    def check_trade_timing(self):
        """Check if enough time has passed since last trade"""
        if not self.last_trade_time:
            return True
        
        time_since_last = (datetime.now() - self.last_trade_time).total_seconds()
        return time_since_last >= self.min_trade_interval
    
    def record_trade(self):
        """Record the time of the last trade"""
        self.last_trade_time = datetime.now()
    
    def get_market_summary(self, market_data):
        """Get a summary of current market conditions"""
        try:
            current_price = market_data.get('close', 0)
            rsi = market_data.get('rsi_14', 50)
            macd_line = market_data.get('macd_line', 0)
            macd_signal = market_data.get('macd_signal', 0)
            
            # Determine market condition
            if rsi > 70:
                condition = "Overbought"
            elif rsi < 30:
                condition = "Oversold"
            elif macd_line > macd_signal:
                condition = "Bullish"
            elif macd_line < macd_signal:
                condition = "Bearish"
            else:
                condition = "Neutral"
            
            return {
                'condition': condition,
                'price': current_price,
                'rsi': rsi,
                'macd_signal_strength': abs(macd_line - macd_signal),
                'volatility': 'High' if rsi > 65 or rsi < 35 else 'Normal'
            }
            
        except Exception as e:
            logger.error(f"Error getting market summary: {e}")
            return {'condition': 'Error', 'price': 0}