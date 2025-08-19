import os
import configparser
import logging

logger = logging.getLogger(__name__)

def load_config():
    """
    Load configuration from setting.ini file
    """
    config = configparser.ConfigParser()
    
    # Check if setting.ini exists
    if os.path.exists('setting.ini'):
        config.read('setting.ini')
        logger.info("Loaded configuration from setting.ini")
    else:
        logger.warning("setting.ini not found, using default values")
        
        # Create default sections
        config['api_credentials'] = {
            'api_key': '',
            'api_secret': ''
        }
        config['application'] = {
            'debug': 'True',
            'secret_key': 'your_secret_key_here'
        }
        config['database'] = {
            'database_uri': 'sqlite:///instance/crypto_trader.db'
        }
        config['trading'] = {
            'default_symbol': 'DOGE_JPY',
            'default_timeframe': '1h',
            'available_symbols': 'BTC_JPY,ETH_JPY,XRP_JPY,DOGE_JPY',
            'available_timeframes': '1m,5m,15m,30m,1h,4h,1d'
        }
        
        # Save default config
        with open('setting.ini', 'w') as configfile:
            config.write(configfile)
        
        logger.info("Created default setting.ini file")
    
    return config

def save_api_credentials(api_key, api_secret):
    """
    Save API credentials to setting.ini
    """
    config = configparser.ConfigParser()
    
    # Load existing config if available
    if os.path.exists('setting.ini'):
        config.read('setting.ini')
    
    # Make sure the section exists
    if 'api_credentials' not in config:
        config['api_credentials'] = {}
    
    # Update credentials
    config['api_credentials']['api_key'] = api_key
    config['api_credentials']['api_secret'] = api_secret
    
    # Save the config
    with open('setting.ini', 'w') as configfile:
        config.write(configfile)
    
    logger.info("API credentials saved to setting.ini")
    return True

def save_trading_settings(symbol, timeframe):
    """
    Save trading settings to setting.ini
    """
    config = configparser.ConfigParser()
    
    # Load existing config if available
    if os.path.exists('setting.ini'):
        config.read('setting.ini')
    
    # Make sure the section exists
    if 'trading' not in config:
        config['trading'] = {}
    
    # Update trading settings
    config['trading']['default_symbol'] = symbol
    config['trading']['default_timeframe'] = timeframe
    
    # Save the config
    with open('setting.ini', 'w') as configfile:
        config.write(configfile)
    
    logger.info(f"Trading settings saved: {symbol}, {timeframe}")
    return True

def get_available_symbols():
    """
    Get list of available trading symbols
    """
    try:
        config = load_config()
        if 'trading' in config:
            symbols_str = config['trading'].get('available_symbols', 'DOGE_JPY')
        else:
            symbols_str = 'DOGE_JPY'
        return symbols_str.split(',')
    except Exception as e:
        logger.warning(f"Error getting available symbols: {e}")
        return ['DOGE_JPY']

def get_available_timeframes():
    """
    Get list of available timeframes
    """
    try:
        config = load_config()
        if 'trading' in config:
            timeframes_str = config['trading'].get('available_timeframes', '1h')
        else:
            timeframes_str = '1h'
        return timeframes_str.split(',')
    except Exception as e:
        logger.warning(f"Error getting available timeframes: {e}")
        return ['1h']

def get_default_symbol():
    """
    Get default trading symbol
    """
    try:
        config = load_config()
        if 'trading' in config:
            return config['trading'].get('default_symbol', 'DOGE_JPY')
        else:
            return 'DOGE_JPY'
    except Exception as e:
        logger.warning(f"Error getting default symbol: {e}")
        return 'DOGE_JPY'

def get_default_timeframe():
    """
    Get default timeframe
    """
    try:
        config = load_config()
        if 'trading' in config:
            return config['trading'].get('default_timeframe', '1h')
        else:
            return '1h'
    except Exception as e:
        logger.warning(f"Error getting default timeframe: {e}")
        return '1h'