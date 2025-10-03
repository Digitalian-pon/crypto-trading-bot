"""
Settings for AI trading system - Compatible with original ai.py
AI取引システム用設定 - 元のai.pyとの互換性
"""

import os
from integration_config import get_ai_config

# Get AI configuration
try:
    ai_config = get_ai_config()
except:
    # Fallback configuration if integration config fails
    class FallbackConfig:
        api_key = ''
        api_secret = ''
        product_code = 'DOGE_JPY'
        currency_pair = 'DOGE_JPY'
        timeframe = '5m'
        duration = '5m'
        trading_enabled = False
        paper_trade = False
        trade_interval = 60
        gmail_sender = ''
        gmail_password = ''
        gmail_receiver = ''
    
    ai_config = FallbackConfig()

# API credentials
api_key = ai_config.api_key or os.environ.get('GMO_API_KEY', '')
api_secret = ai_config.api_secret or os.environ.get('GMO_API_SECRET', '')

# Trading settings
product_code = ai_config.product_code
currency_pair = ai_config.currency_pair
timeframe = ai_config.timeframe
duration = ai_config.duration
trading_enabled = ai_config.trading_enabled

# Paper trading
paper_trade = getattr(ai_config, 'paper_trade', False)

# Trading intervals
trade_interval = getattr(ai_config, 'trade_interval', 60)

# Gmail notification settings
gmail_sender = getattr(ai_config, 'gmail_sender', '')
gmail_password = getattr(ai_config, 'gmail_password', '')
gmail_receiver = getattr(ai_config, 'gmail_receiver', '')

# Risk management
stop_loss_percentage = getattr(ai_config, 'stop_loss_percentage', 3.0)
take_profit_percentage = getattr(ai_config, 'take_profit_percentage', 5.0)
use_percent = getattr(ai_config, 'use_percent', 0.05)

# Debug mode
DEBUG = not trading_enabled