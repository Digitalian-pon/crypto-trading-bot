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