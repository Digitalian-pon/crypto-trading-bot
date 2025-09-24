import pandas as pd
import numpy as np
import logging
import talib
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
        """Average True Range"""
        return talib.ATR(high.to_numpy(), low.to_numpy(), close.to_numpy(), timeperiod=timeperiod)

    @staticmethod
    def add_all_indicators(df):
        """Add all technical indicators to DataFrame with dynamic adjustments."""
        try:
            config = load_config()

            # Ensure high, low, close columns exist
            if not all(col in df.columns for col in ['high', 'low', 'close']):
                logger.error("DataFrame must contain 'high', 'low', and 'close' columns.")
                return df

            # --- Dynamic Parameter Logic ---
            df['atr'] = TechnicalIndicators.calculate_atr(df['high'], df['low'], df['close'])
            latest_atr = df['atr'].rolling(window=3).mean().iloc[-1]
            
            volatility_threshold = config.getfloat('DynamicParameters', 'volatility_threshold', fallback=50000)

            if latest_atr > volatility_threshold:
                profile = "HighVolatility"
            else:
                profile = "LowVolatility"

            # Load parameters from config based on profile
            rsi_window = config.getint(profile, 'rsi_window')
            ema_window = config.getint(profile, 'ema_window')
            macd_fast = config.getint(profile, 'macd_fast')
            macd_slow = config.getint(profile, 'macd_slow')
            macd_signal = config.getint(profile, 'macd_signal')
            bb_window = config.getint(profile, 'bb_window')
            bb_std = config.getfloat(profile, 'bb_std')

            # Store dynamic params for debugging/logging
            df['dynamic_profile'] = profile.replace("Volatility", "")
            df['dynamic_rsi_window'] = rsi_window

            # --- Indicator Calculations ---
            # EMA
            df[f'ema_{ema_window}'] = TechnicalIndicators.calculate_ema(df['close'], ema_window)
            
            # RSI with dynamic window
            df[f'rsi_{rsi_window}'] = TechnicalIndicators.calculate_rsi(df['close'], rsi_window)
            
            # MACD with dynamic parameters
            macd_line, signal_line, histogram = TechnicalIndicators.calculate_macd(
                df['close'], fast=macd_fast, slow=macd_slow, signal=macd_signal
            )
            df['macd_line'] = macd_line
            df['macd_signal'] = signal_line
            df['macd_histogram'] = histogram
            
            # Bollinger Bands with dynamic parameters
            bb_upper, bb_lower, bb_middle = TechnicalIndicators.calculate_bollinger_bands_ema(
                df['close'], window=bb_window, std=bb_std
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
            
            log_msg = (
                f"Indicators added with profile: {profile}. "
                f"RSI_win: {rsi_window}, "
                f"MACD:({macd_fast},{macd_slow},{macd_signal}), "
                f"BB:({bb_window},{bb_std})"
            )
            logger.info(log_msg)
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