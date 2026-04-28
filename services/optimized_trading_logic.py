"""
v4.0.0 - Simple Trend-Following Strategy

Entry conditions (all must be true):
  - ADX(14) > 25 (strong trend)
  - EMA20 > EMA50 (uptrend) AND MACD histogram > 0 → BUY
  - EMA20 < EMA50 (downtrend) AND MACD histogram < 0 → SELL

Exit conditions (managed by bot):
  - TP +2% (fixed)
  - SL -1% (fixed)
  - No trailing stop, no forced reversal, no time-based exit

24h same-direction reentry block is enforced by the bot, not here.
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class OptimizedTradingLogic:
    ADX_PERIOD = 14
    ADX_THRESHOLD = 25.0

    def __init__(self):
        pass

    @staticmethod
    def _wilder_smooth(series: pd.Series, period: int) -> pd.Series:
        return series.ewm(alpha=1.0 / period, adjust=False).mean()

    @classmethod
    def calculate_adx(cls, df: pd.DataFrame, period: int = ADX_PERIOD) -> pd.DataFrame:
        high = df['high']
        low = df['low']
        close = df['close']

        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
        minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)

        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)

        atr = cls._wilder_smooth(tr, period)
        plus_di = 100.0 * cls._wilder_smooth(plus_dm, period) / atr.replace(0, np.nan)
        minus_di = 100.0 * cls._wilder_smooth(minus_dm, period) / atr.replace(0, np.nan)

        dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = cls._wilder_smooth(dx.fillna(0), period)

        return pd.DataFrame({'adx': adx, 'plus_di': plus_di, 'minus_di': minus_di}, index=df.index)

    def should_trade(self, market_data, historical_df=None, **_kwargs):
        """
        Returns: (should_trade, trade_type, reason, confidence, stop_loss, take_profit)
        stop_loss / take_profit are None — bot applies fixed -1% / +2%.
        """
        if historical_df is None or len(historical_df) < 60:
            return False, None, "Insufficient data", 0.0, None, None

        required_cols = {'high', 'low', 'close', 'ema_20', 'ema_50', 'macd_histogram'}
        if not required_cols.issubset(historical_df.columns):
            missing = required_cols - set(historical_df.columns)
            return False, None, f"Missing columns: {missing}", 0.0, None, None

        try:
            adx_df = self.calculate_adx(historical_df, period=self.ADX_PERIOD)
            adx = float(adx_df['adx'].iloc[-2])
            ema20 = float(historical_df['ema_20'].iloc[-2])
            ema50 = float(historical_df['ema_50'].iloc[-2])
            macd_hist = float(historical_df['macd_histogram'].iloc[-2])
        except (IndexError, ValueError, TypeError) as e:
            return False, None, f"Indicator read error: {e}", 0.0, None, None

        if pd.isna(adx) or pd.isna(ema20) or pd.isna(ema50) or pd.isna(macd_hist):
            return False, None, "Indicator NaN", 0.0, None, None

        logger.info(f"[v4] ADX={adx:.2f} EMA20={ema20:.4f} EMA50={ema50:.4f} MACD_hist={macd_hist:.5f}")

        if adx < self.ADX_THRESHOLD:
            return False, None, f"Weak trend (ADX={adx:.2f} < {self.ADX_THRESHOLD})", 0.0, None, None

        if ema20 > ema50 and macd_hist > 0:
            confidence = min(adx / 50.0, 1.0)
            reason = f"Uptrend: ADX={adx:.1f}, EMA20>EMA50, MACD_hist>0"
            return True, 'BUY', reason, confidence, None, None

        if ema20 < ema50 and macd_hist < 0:
            confidence = min(adx / 50.0, 1.0)
            reason = f"Downtrend: ADX={adx:.1f}, EMA20<EMA50, MACD_hist<0"
            return True, 'SELL', reason, confidence, None, None

        return False, None, "EMA/MACD not aligned", 0.0, None, None
