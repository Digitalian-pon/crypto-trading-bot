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
    def calculate_market_regime(df):
        """Calculate market regime: trending, ranging, or volatile"""
        if len(df) < 50:
            return 'ranging', 0.5

        # ATR-based volatility
        atr = TechnicalIndicators.calculate_atr(df['high'], df['low'], df['close'], 14)
        atr_pct = (atr / df['close']) * 100

        # Trend strength using ADX concept
        high_low_range = df['high'].rolling(20).max() - df['low'].rolling(20).min()
        close_range = df['close'].iloc[-1] - df['close'].iloc[-20] if len(df) >= 20 else 0
        trend_strength = abs(close_range) / high_low_range.iloc[-1] if high_low_range.iloc[-1] > 0 else 0

        volatility_score = atr_pct.iloc[-1]

        if volatility_score > 3.0:  # High volatility
            return 'volatile', volatility_score / 5.0
        elif trend_strength > 0.6:  # Strong trend
            return 'trending', trend_strength
        else:
            return 'ranging', 0.5

    @staticmethod
    def calculate_atr(high, low, close, period=14):
        """Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    @staticmethod
    def get_adaptive_parameters(df):
        """Get adaptive parameters based on market regime"""
        regime, strength = TechnicalIndicators.calculate_market_regime(df)

        if regime == 'volatile':
            # Volatile market: wider bands, longer periods
            return {
                'rsi_period': 21,  # Slower RSI
                'bb_period': 30,   # Wider BB
                'bb_std': 2.5,     # Wider bands
                'ema_fast': 15,
                'ema_slow': 35,
                'macd_fast': 15,
                'macd_slow': 35,
                'regime': regime
            }
        elif regime == 'trending':
            # Trending market: standard parameters
            return {
                'rsi_period': 14,
                'bb_period': 20,
                'bb_std': 2.0,
                'ema_fast': 12,
                'ema_slow': 26,
                'macd_fast': 12,
                'macd_slow': 26,
                'regime': regime
            }
        else:  # ranging
            # Ranging market: tighter bands, shorter periods
            return {
                'rsi_period': 9,   # Faster RSI
                'bb_period': 15,   # Tighter BB
                'bb_std': 1.5,     # Narrower bands
                'ema_fast': 8,
                'ema_slow': 21,
                'macd_fast': 8,
                'macd_slow': 21,
                'regime': regime
            }

    @staticmethod
    def add_all_indicators(df):
        """Add all technical indicators to DataFrame with adaptive parameters"""
        try:
            # Get adaptive parameters based on market regime
            params = TechnicalIndicators.get_adaptive_parameters(df)

            # Basic moving averages with adaptive periods
            df['ema_20'] = TechnicalIndicators.calculate_ema(df['close'], 20)  # Keep for compatibility
            df['ema_50'] = TechnicalIndicators.calculate_ema(df['close'], 50)  # Add for trend confirmation
            df['ema_12'] = TechnicalIndicators.calculate_ema(df['close'], params['ema_fast'])
            df['ema_26'] = TechnicalIndicators.calculate_ema(df['close'], params['ema_slow'])

            # RSI with adaptive period
            df['rsi_14'] = TechnicalIndicators.calculate_rsi(df['close'], params['rsi_period'])

            # MACD with adaptive parameters
            macd_line, signal_line, histogram = TechnicalIndicators.calculate_macd(
                df['close'],
                fast=params['macd_fast'],
                slow=params['macd_slow'],
                signal=9
            )
            df['macd_line'] = macd_line
            df['macd_signal'] = signal_line
            df['macd_histogram'] = histogram

            # Bollinger Bands with adaptive parameters
            bb_upper, bb_lower, bb_middle = TechnicalIndicators.calculate_bollinger_bands_ema(
                df['close'],
                window=params['bb_period'],
                std=params['bb_std']
            )
            df['bb_upper'] = bb_upper
            df['bb_lower'] = bb_lower
            df['bb_middle'] = bb_middle

            # Store market regime info
            df['market_regime'] = params['regime']
            
            # Stochastic (if high/low columns exist)
            if 'high' in df.columns and 'low' in df.columns:
                stoch_k, stoch_d = TechnicalIndicators.calculate_stochastic(
                    df['high'], df['low'], df['close']
                )
                df['stoch_k'] = stoch_k
                df['stoch_d'] = stoch_d
            
            logger.info(f"Technical indicators added with adaptive parameters (regime: {params['regime']})")
            return df
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators: {e}")
            return df
    
    @staticmethod
    def calculate_all_indicators(df):
        """Alias for add_all_indicators for compatibility"""
        return TechnicalIndicators.add_all_indicators(df)