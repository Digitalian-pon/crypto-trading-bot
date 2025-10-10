import pandas as pd
import numpy as np
import logging
# import talib  # Not required - using pandas/numpy implementations
from config import load_config

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
        """Bollinger Bands with SMA (legacy)"""
        sma = TechnicalIndicators.calculate_sma(data, window)
        rolling_std = data.rolling(window=window).std()
        upper_band = sma + (rolling_std * std)
        lower_band = sma - (rolling_std * std)
        
        return upper_band, lower_band, sma
    
    @staticmethod
    def calculate_bollinger_bands_ema(data, window=20, std=2):
        """Bollinger Bands with EMA for more responsive middle band"""
        ema = TechnicalIndicators.calculate_ema(data, window)
        rolling_std = data.rolling(window=window).std()
        upper_band = ema + (rolling_std * std)
        lower_band = ema - (rolling_std * std)
        
        return upper_band, lower_band, ema
    
    @staticmethod
    def calculate_stochastic(high, low, close, k_window=14, d_window=3):
        """Stochastic Oscillator"""
        lowest_low = low.rolling(window=k_window).min()
        highest_high = high.rolling(window=k_window).max()
        k_percent = ((close - lowest_low) / (highest_high - lowest_low)) * 100
        d_percent = k_percent.rolling(window=d_window).mean()
        
        return k_percent, d_percent

    @staticmethod
    def calculate_atr(high, low, close, timeperiod=14):
        """Average True Range using pandas/numpy"""
        high_low = high - low
        high_close = abs(high - close.shift())
        low_close = abs(low - close.shift())

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=timeperiod).mean()
        return atr

    @staticmethod
    def calculate_market_regime(df):
        """Calculate market regime: trending, ranging, or volatile"""
        if len(df) < 50:
            return 'ranging'

        # ATR-based volatility
        atr = TechnicalIndicators.calculate_atr(df['high'], df['low'], df['close'], timeperiod=14)
        atr_pct = (atr / df['close']) * 100

        # Trend strength using ADX concept
        high_low_range = df['high'].rolling(20).max() - df['low'].rolling(20).min()
        close_range = df['close'].iloc[-1] - df['close'].iloc[-20] if len(df) >= 20 else 0
        trend_strength = abs(close_range) / high_low_range.iloc[-1] if high_low_range.iloc[-1] > 0 else 0

        volatility_score = atr_pct.iloc[-1]

        if volatility_score > 3.0:
            return 'volatile'
        elif trend_strength > 0.6:
            return 'trending'
        else:
            return 'ranging'

    @staticmethod
    def get_adaptive_parameters(df):
        """Get adaptive parameters based on market regime by reading from config."""
        regime = TechnicalIndicators.calculate_market_regime(df)
        config = load_config()
        
        # Capitalize to match section names in setting.ini (e.g., "Volatile")
        section = regime.capitalize()
        
        if section not in config:
            logger.warning(f"'{section}' section not found in setting.ini. Falling back to 'Trending'.")
            section = 'Trending'

        params = {
            'rsi_window': config.getint(section, 'rsi_window', fallback=14),
            'bb_window': config.getint(section, 'bb_window', fallback=20),
            'bb_std': config.getfloat(section, 'bb_std', fallback=2.0),
            'macd_fast': config.getint(section, 'macd_fast', fallback=12),
            'macd_slow': config.getint(section, 'macd_slow', fallback=26),
            'macd_signal': config.getint(section, 'macd_signal', fallback=9),
            'regime': regime
        }
        return params

    @staticmethod
    def add_all_indicators(df):
        """Add all technical indicators to DataFrame with adaptive parameters"""
        try:
            if not all(col in df.columns for col in ['high', 'low', 'close']):
                logger.error("DataFrame must contain 'high', 'low', and 'close' columns for adaptive indicators.")
                return df

            # Get adaptive parameters based on market regime
            params = TechnicalIndicators.get_adaptive_parameters(df)

            # Basic moving averages with adaptive periods
            df['ema_20'] = TechnicalIndicators.calculate_ema(df['close'], 20)  # Keep for compatibility
            df['ema_50'] = TechnicalIndicators.calculate_ema(df['close'], 50)  # Add for trend confirmation
            df['ema_12'] = TechnicalIndicators.calculate_ema(df['close'], params['macd_fast'])
            df['ema_26'] = TechnicalIndicators.calculate_ema(df['close'], params['macd_slow'])
            # RSI with adaptive period
            df['rsi'] = TechnicalIndicators.calculate_rsi(df['close'], window=params['rsi_window'])

            # MACD with adaptive parameters
            macd_line, signal_line, histogram = TechnicalIndicators.calculate_macd(
                df['close'],
                fast=params['macd_fast'],
                slow=params['macd_slow'],
                signal=params['macd_signal']
            )
            df['macd_line'] = macd_line
            df['macd_signal'] = signal_line
            df['macd_histogram'] = histogram

            # Bollinger Bands with adaptive parameters
            bb_upper, bb_lower, bb_middle = TechnicalIndicators.calculate_bollinger_bands_ema(
                df['close'],
                window=params['bb_window'],
                std=params['bb_std']
            )
            df['bb_upper'] = bb_upper
            df['bb_lower'] = bb_lower
            df['bb_middle'] = bb_middle

            # Stochastic (remains with fixed params for now)
            stoch_k, stoch_d = TechnicalIndicators.calculate_stochastic(
                df['high'], df['low'], df['close']
            )
            df['stoch_k'] = stoch_k
            df['stoch_d'] = stoch_d
            
            # Store market regime info for logging and analysis
            df['market_regime'] = params['regime']
            
            logger.info(f"Indicators added with adaptive parameters (Regime: {params['regime']})")
            return df
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return df
    
    @staticmethod
    def calculate_all_indicators(df):
        """Alias for add_all_indicators for compatibility"""
        return TechnicalIndicators.add_all_indicators(df)
