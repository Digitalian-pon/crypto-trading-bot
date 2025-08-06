import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class TechnicalIndicators:
    """
    Technical indicators calculator for crypto trading
    """
    
    @staticmethod
    def calculate_sma(data, window):
        """Simple Moving Average"""
        return data.rolling(window=window).mean()
    
    @staticmethod
    def calculate_ema(data, window):
        """Exponential Moving Average"""
        return data.ewm(span=window, adjust=False).mean()
    
    @staticmethod
    def calculate_rsi(data, window=14):
        """Relative Strength Index"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def calculate_macd(data, fast=12, slow=26, signal=9):
        """MACD indicator"""
        ema_fast = TechnicalIndicators.calculate_ema(data, fast)
        ema_slow = TechnicalIndicators.calculate_ema(data, slow)
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def calculate_bollinger_bands(data, window=20, std=2):
        """Bollinger Bands"""
        sma = TechnicalIndicators.calculate_sma(data, window)
        rolling_std = data.rolling(window=window).std()
        upper_band = sma + (rolling_std * std)
        lower_band = sma - (rolling_std * std)
        
        return upper_band, lower_band, sma
    
    @staticmethod
    def calculate_stochastic(high, low, close, k_window=14, d_window=3):
        """Stochastic Oscillator"""
        lowest_low = low.rolling(window=k_window).min()
        highest_high = high.rolling(window=k_window).max()
        k_percent = ((close - lowest_low) / (highest_high - lowest_low)) * 100
        d_percent = k_percent.rolling(window=d_window).mean()
        
        return k_percent, d_percent
    
    @staticmethod
    def add_all_indicators(df):
        """Add all technical indicators to DataFrame"""
        try:
            # Basic moving averages
            df['sma_20'] = TechnicalIndicators.calculate_sma(df['close'], 20)
            df['ema_12'] = TechnicalIndicators.calculate_ema(df['close'], 12)
            df['ema_26'] = TechnicalIndicators.calculate_ema(df['close'], 26)
            
            # RSI
            df['rsi_14'] = TechnicalIndicators.calculate_rsi(df['close'], 14)
            
            # MACD
            macd_line, signal_line, histogram = TechnicalIndicators.calculate_macd(df['close'])
            df['macd_line'] = macd_line
            df['macd_signal'] = signal_line
            df['macd_histogram'] = histogram
            
            # Bollinger Bands
            bb_upper, bb_lower, bb_middle = TechnicalIndicators.calculate_bollinger_bands(df['close'])
            df['bb_upper'] = bb_upper
            df['bb_lower'] = bb_lower
            df['bb_middle'] = bb_middle
            
            # Stochastic (if high/low columns exist)
            if 'high' in df.columns and 'low' in df.columns:
                stoch_k, stoch_d = TechnicalIndicators.calculate_stochastic(
                    df['high'], df['low'], df['close']
                )
                df['stoch_k'] = stoch_k
                df['stoch_d'] = stoch_d
            
            logger.info("All technical indicators added successfully")
            return df
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators: {e}")
            return df
    
    @staticmethod
    def calculate_all_indicators(df):
        """Alias for add_all_indicators for compatibility"""
        return TechnicalIndicators.add_all_indicators(df)