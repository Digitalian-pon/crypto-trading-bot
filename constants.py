"""
Constants for AI trading system
AI取引システム用定数
"""

# Trading signals
BUY = 'BUY'
SELL = 'SELL'
HOLD = 'HOLD'

# Time durations
DURATION_1M = '1m'
DURATION_5M = '5m'
DURATION_15M = '15m'
DURATION_30M = '30m'
DURATION_1H = '1h'
DURATION_4H = '4h'
DURATION_1D = '1d'

# Trading parameters
DEFAULT_STOP_LOSS = 0.03  # 3%
DEFAULT_TAKE_PROFIT = 0.05  # 5%
DEFAULT_POSITION_SIZE = 0.05  # 5%

# Technical indicator periods
DEFAULT_EMA_FAST = 12
DEFAULT_EMA_SLOW = 26
DEFAULT_RSI_PERIOD = 14
DEFAULT_MACD_FAST = 12
DEFAULT_MACD_SLOW = 26
DEFAULT_MACD_SIGNAL = 9

# Risk management
MAX_DAILY_LOSS = 0.1  # 10%
MAX_CONSECUTIVE_LOSSES = 5
MIN_CONFIDENCE_THRESHOLD = 0.6

# Currency pairs
CURRENCY_PAIRS = [
    'DOGE_JPY',
    'BTC_JPY', 
    'ETH_JPY',
    'XRP_JPY',
    'LTC_JPY',
    'BCH_JPY'
]

# Default currency pair
DEFAULT_CURRENCY_PAIR = 'DOGE_JPY'

# Timeframes
TIMEFRAMES = [
    DURATION_1M,
    DURATION_5M,
    DURATION_15M,
    DURATION_30M,
    DURATION_1H,
    DURATION_4H,
    DURATION_1D
]

# Default timeframe
DEFAULT_TIMEFRAME = DURATION_5M