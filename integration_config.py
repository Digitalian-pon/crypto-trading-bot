"""
Integration Configuration - Unified settings management for the enhanced trading system
統合設定 - 強化取引システムの統一設定管理
"""

import os
import configparser
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class AITradingConfig:
    """
    Configuration data class for AI trading system
    AI取引システム設定データクラス
    """
    # Original ai.py parameters
    product_code: str = 'DOGE_JPY'
    use_percent: float = 0.05  # 5% position sizing
    duration: str = '5m'
    past_period: int = 100
    stop_limit_percent: float = 0.03  # 3% stop loss
    trade_interval: int = 60  # seconds between trades
    
    # GitHub project parameters
    currency_pair: str = 'DOGE_JPY'
    timeframe: str = '5m'
    trading_enabled: bool = False
    risk_level: str = 'medium'
    stop_loss_percentage: float = 3.0
    take_profit_percentage: float = 5.0
    
    # Enhanced AI parameters
    ml_probability_threshold: float = 0.6
    signal_confidence_threshold: float = 0.65
    optimization_interval: int = 24 * 60 * 60  # 24 hours
    max_daily_loss: float = 10.0  # 10% daily loss limit
    max_consecutive_losses: int = 5
    
    # API credentials
    api_key: str = ''
    api_secret: str = ''
    
    # Notification settings
    gmail_sender: str = ''
    gmail_password: str = ''
    gmail_receiver: str = ''
    
    # Paper trading
    paper_trade: bool = False
    paper_balance: float = 100000.0

class IntegratedConfigManager:
    """
    Integrated Configuration Manager
    統合設定マネージャー
    """
    
    def __init__(self, config_file: str = 'enhanced_settings.ini'):
        """
        Initialize integrated config manager
        
        Args:
            config_file: Configuration file path
        """
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.ai_config = AITradingConfig()
        
        # Load configuration from multiple sources
        self._load_configuration()
        
        logger.info(f'Integrated config manager initialized with {config_file}')

    def _load_configuration(self):
        """Load configuration from all sources"""
        try:
            # 1. Load from enhanced_settings.ini (primary)
            self._load_from_enhanced_settings()
            
            # 2. Load from original setting.ini (backup)
            self._load_from_original_settings()
            
            # 3. Load from environment variables (override)
            self._load_from_environment()
            
            # 4. Apply user database settings if available
            self._load_from_database()
            
            # 5. Validate and normalize settings
            self._validate_and_normalize()
            
            logger.info('Configuration loaded from all sources')
            
        except Exception as e:
            logger.error(f'Configuration loading error: {str(e)}')
            self._create_default_configuration()

    def _load_from_enhanced_settings(self):
        """Load from enhanced_settings.ini"""
        try:
            if os.path.exists(self.config_file):
                self.config.read(self.config_file)
                logger.info(f'Loaded enhanced settings from {self.config_file}')
                
                # Map enhanced settings to AI config
                if 'ai_trading' in self.config:
                    section = self.config['ai_trading']
                    self.ai_config.product_code = section.get('product_code', self.ai_config.product_code)
                    self.ai_config.use_percent = section.getfloat('use_percent', self.ai_config.use_percent)
                    self.ai_config.duration = section.get('duration', self.ai_config.duration)
                    self.ai_config.past_period = section.getint('past_period', self.ai_config.past_period)
                    self.ai_config.stop_limit_percent = section.getfloat('stop_limit_percent', self.ai_config.stop_limit_percent)
                    self.ai_config.trade_interval = section.getint('trade_interval', self.ai_config.trade_interval)
                
                if 'github_trading' in self.config:
                    section = self.config['github_trading']
                    self.ai_config.currency_pair = section.get('currency_pair', self.ai_config.currency_pair)
                    self.ai_config.timeframe = section.get('timeframe', self.ai_config.timeframe)
                    self.ai_config.trading_enabled = section.getboolean('trading_enabled', self.ai_config.trading_enabled)
                    self.ai_config.risk_level = section.get('risk_level', self.ai_config.risk_level)
                    self.ai_config.stop_loss_percentage = section.getfloat('stop_loss_percentage', self.ai_config.stop_loss_percentage)
                    self.ai_config.take_profit_percentage = section.getfloat('take_profit_percentage', self.ai_config.take_profit_percentage)
                
                if 'enhanced_ai' in self.config:
                    section = self.config['enhanced_ai']
                    self.ai_config.ml_probability_threshold = section.getfloat('ml_probability_threshold', self.ai_config.ml_probability_threshold)
                    self.ai_config.signal_confidence_threshold = section.getfloat('signal_confidence_threshold', self.ai_config.signal_confidence_threshold)
                    self.ai_config.optimization_interval = section.getint('optimization_interval', self.ai_config.optimization_interval)
                    self.ai_config.max_daily_loss = section.getfloat('max_daily_loss', self.ai_config.max_daily_loss)
                    self.ai_config.max_consecutive_losses = section.getint('max_consecutive_losses', self.ai_config.max_consecutive_losses)
                
                if 'api_credentials' in self.config:
                    section = self.config['api_credentials']
                    self.ai_config.api_key = section.get('api_key', self.ai_config.api_key)
                    self.ai_config.api_secret = section.get('api_secret', self.ai_config.api_secret)
                
                if 'notifications' in self.config:
                    section = self.config['notifications']
                    self.ai_config.gmail_sender = section.get('gmail_sender', self.ai_config.gmail_sender)
                    self.ai_config.gmail_password = section.get('gmail_password', self.ai_config.gmail_password)
                    self.ai_config.gmail_receiver = section.get('gmail_receiver', self.ai_config.gmail_receiver)
                
                if 'paper_trading' in self.config:
                    section = self.config['paper_trading']
                    self.ai_config.paper_trade = section.getboolean('paper_trade', self.ai_config.paper_trade)
                    self.ai_config.paper_balance = section.getfloat('paper_balance', self.ai_config.paper_balance)
                    
        except Exception as e:
            logger.warning(f'Error loading enhanced settings: {str(e)}')

    def _load_from_original_settings(self):
        """Load from original setting.ini as backup"""
        try:
            original_config_file = 'setting.ini'
            if os.path.exists(original_config_file):
                original_config = configparser.ConfigParser()
                original_config.read(original_config_file)
                logger.info(f'Loaded original settings from {original_config_file}')
                
                # Fill in missing API credentials
                if 'api_credentials' in original_config and not self.ai_config.api_key:
                    section = original_config['api_credentials']
                    self.ai_config.api_key = section.get('api_key', '')
                    self.ai_config.api_secret = section.get('api_secret', '')
                
                # Fill in missing trading settings
                if 'trading' in original_config:
                    section = original_config['trading']
                    if not self.ai_config.currency_pair or self.ai_config.currency_pair == 'DOGE_JPY':
                        self.ai_config.currency_pair = section.get('default_symbol', self.ai_config.currency_pair)
                        self.ai_config.product_code = self.ai_config.currency_pair
                    if not self.ai_config.timeframe or self.ai_config.timeframe == '5m':
                        self.ai_config.timeframe = section.get('default_timeframe', self.ai_config.timeframe)
                        self.ai_config.duration = self.ai_config.timeframe
                        
        except Exception as e:
            logger.warning(f'Error loading original settings: {str(e)}')

    def _load_from_environment(self):
        """Load from environment variables (highest priority)"""
        try:
            # API credentials from environment
            if os.environ.get('GMO_API_KEY'):
                self.ai_config.api_key = os.environ['GMO_API_KEY']
            if os.environ.get('GMO_API_SECRET'):
                self.ai_config.api_secret = os.environ['GMO_API_SECRET']
            
            # Trading settings from environment
            if os.environ.get('TRADING_ENABLED'):
                self.ai_config.trading_enabled = os.environ['TRADING_ENABLED'].lower() == 'true'
            if os.environ.get('CURRENCY_PAIR'):
                self.ai_config.currency_pair = os.environ['CURRENCY_PAIR']
                self.ai_config.product_code = self.ai_config.currency_pair
            if os.environ.get('TIMEFRAME'):
                self.ai_config.timeframe = os.environ['TIMEFRAME']
                self.ai_config.duration = self.ai_config.timeframe
            
            # Paper trading from environment
            if os.environ.get('PAPER_TRADE'):
                self.ai_config.paper_trade = os.environ['PAPER_TRADE'].lower() == 'true'
            
            # Gmail settings from environment
            if os.environ.get('GMAIL_SENDER'):
                self.ai_config.gmail_sender = os.environ['GMAIL_SENDER']
            if os.environ.get('GMAIL_PASSWORD'):
                self.ai_config.gmail_password = os.environ['GMAIL_PASSWORD']
            if os.environ.get('GMAIL_RECEIVER'):
                self.ai_config.gmail_receiver = os.environ['GMAIL_RECEIVER']
                
            logger.info('Environment variables loaded')
            
        except Exception as e:
            logger.warning(f'Error loading environment variables: {str(e)}')

    def _load_from_database(self):
        """Load user settings from database if available"""
        try:
            # Import here to avoid circular imports
            from models import User, TradingSettings, db
            
            # Try to get the first user with settings
            user = User.query.filter(User.settings.isnot(None)).first()
            
            if user and user.settings:
                settings = user.settings
                
                # Update config with database settings
                self.ai_config.currency_pair = settings.currency_pair
                self.ai_config.product_code = settings.currency_pair
                self.ai_config.timeframe = settings.timeframe
                self.ai_config.duration = settings.timeframe
                self.ai_config.trading_enabled = settings.trading_enabled
                self.ai_config.risk_level = settings.risk_level
                self.ai_config.stop_loss_percentage = settings.stop_loss_percentage
                self.ai_config.take_profit_percentage = settings.take_profit_percentage
                self.ai_config.stop_limit_percent = settings.stop_loss_percentage / 100
                
                # Update API credentials if available
                if user.api_key:
                    self.ai_config.api_key = user.api_key
                if user.api_secret:
                    self.ai_config.api_secret = user.api_secret
                
                logger.info(f'Database settings loaded for user {user.username}')
                
        except Exception as e:
            logger.info(f'Database settings not available: {str(e)}')

    def _validate_and_normalize(self):
        """Validate and normalize configuration values"""
        try:
            # Ensure consistency between similar settings
            self.ai_config.product_code = self.ai_config.currency_pair
            self.ai_config.duration = self.ai_config.timeframe
            self.ai_config.stop_limit_percent = self.ai_config.stop_loss_percentage / 100
            
            # Validate percentage ranges
            self.ai_config.use_percent = max(0.01, min(0.2, self.ai_config.use_percent))  # 1-20%
            self.ai_config.stop_loss_percentage = max(0.5, min(10.0, self.ai_config.stop_loss_percentage))  # 0.5-10%
            self.ai_config.take_profit_percentage = max(1.0, min(20.0, self.ai_config.take_profit_percentage))  # 1-20%
            self.ai_config.ml_probability_threshold = max(0.5, min(1.0, self.ai_config.ml_probability_threshold))  # 50-100%
            self.ai_config.signal_confidence_threshold = max(0.5, min(1.0, self.ai_config.signal_confidence_threshold))  # 50-100%
            
            # Validate numeric ranges
            self.ai_config.trade_interval = max(30, min(3600, self.ai_config.trade_interval))  # 30s-1h
            self.ai_config.past_period = max(50, min(1000, self.ai_config.past_period))  # 50-1000 periods
            self.ai_config.max_consecutive_losses = max(3, min(20, self.ai_config.max_consecutive_losses))  # 3-20 losses
            
            # Validate timeframe
            valid_timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
            if self.ai_config.timeframe not in valid_timeframes:
                self.ai_config.timeframe = '5m'
                self.ai_config.duration = '5m'
            
            # Validate currency pair
            valid_pairs = ['DOGE_JPY', 'BTC_JPY', 'ETH_JPY', 'XRP_JPY', 'LTC_JPY', 'BCH_JPY']
            if self.ai_config.currency_pair not in valid_pairs:
                self.ai_config.currency_pair = 'DOGE_JPY'
                self.ai_config.product_code = 'DOGE_JPY'
            
            # Validate risk level
            valid_risk_levels = ['low', 'medium', 'high']
            if self.ai_config.risk_level not in valid_risk_levels:
                self.ai_config.risk_level = 'medium'
            
            logger.info('Configuration validated and normalized')
            
        except Exception as e:
            logger.error(f'Configuration validation error: {str(e)}')

    def _create_default_configuration(self):
        """Create default configuration file"""
        try:
            # Create default configuration
            default_config = configparser.ConfigParser()
            
            # AI Trading section (original ai.py parameters)
            default_config['ai_trading'] = {
                'product_code': 'DOGE_JPY',
                'use_percent': '0.05',
                'duration': '5m',
                'past_period': '100',
                'stop_limit_percent': '0.03',
                'trade_interval': '60'
            }
            
            # GitHub Trading section (GitHub project parameters)
            default_config['github_trading'] = {
                'currency_pair': 'DOGE_JPY',
                'timeframe': '5m',
                'trading_enabled': 'False',
                'risk_level': 'medium',
                'stop_loss_percentage': '3.0',
                'take_profit_percentage': '5.0'
            }
            
            # Enhanced AI section (new enhanced features)
            default_config['enhanced_ai'] = {
                'ml_probability_threshold': '0.6',
                'signal_confidence_threshold': '0.65',
                'optimization_interval': '86400',
                'max_daily_loss': '10.0',
                'max_consecutive_losses': '5'
            }
            
            # API credentials section
            default_config['api_credentials'] = {
                'api_key': '',
                'api_secret': ''
            }
            
            # Notifications section
            default_config['notifications'] = {
                'gmail_sender': '',
                'gmail_password': '',
                'gmail_receiver': ''
            }
            
            # Paper trading section
            default_config['paper_trading'] = {
                'paper_trade': 'False',
                'paper_balance': '100000.0'
            }
            
            # Write default configuration
            with open(self.config_file, 'w') as f:
                default_config.write(f)
            
            # Update instance config
            self.config = default_config
            
            logger.info(f'Default configuration created: {self.config_file}')
            
        except Exception as e:
            logger.error(f'Error creating default configuration: {str(e)}')

    def save_configuration(self):
        """Save current configuration to file"""
        try:
            # Update config sections with current AI config values
            if 'ai_trading' not in self.config:
                self.config.add_section('ai_trading')
            self.config['ai_trading'] = {
                'product_code': self.ai_config.product_code,
                'use_percent': str(self.ai_config.use_percent),
                'duration': self.ai_config.duration,
                'past_period': str(self.ai_config.past_period),
                'stop_limit_percent': str(self.ai_config.stop_limit_percent),
                'trade_interval': str(self.ai_config.trade_interval)
            }
            
            if 'github_trading' not in self.config:
                self.config.add_section('github_trading')
            self.config['github_trading'] = {
                'currency_pair': self.ai_config.currency_pair,
                'timeframe': self.ai_config.timeframe,
                'trading_enabled': str(self.ai_config.trading_enabled),
                'risk_level': self.ai_config.risk_level,
                'stop_loss_percentage': str(self.ai_config.stop_loss_percentage),
                'take_profit_percentage': str(self.ai_config.take_profit_percentage)
            }
            
            if 'enhanced_ai' not in self.config:
                self.config.add_section('enhanced_ai')
            self.config['enhanced_ai'] = {
                'ml_probability_threshold': str(self.ai_config.ml_probability_threshold),
                'signal_confidence_threshold': str(self.ai_config.signal_confidence_threshold),
                'optimization_interval': str(self.ai_config.optimization_interval),
                'max_daily_loss': str(self.ai_config.max_daily_loss),
                'max_consecutive_losses': str(self.ai_config.max_consecutive_losses)
            }
            
            if 'api_credentials' not in self.config:
                self.config.add_section('api_credentials')
            self.config['api_credentials'] = {
                'api_key': self.ai_config.api_key,
                'api_secret': self.ai_config.api_secret
            }
            
            if 'notifications' not in self.config:
                self.config.add_section('notifications')
            self.config['notifications'] = {
                'gmail_sender': self.ai_config.gmail_sender,
                'gmail_password': self.ai_config.gmail_password,
                'gmail_receiver': self.ai_config.gmail_receiver
            }
            
            if 'paper_trading' not in self.config:
                self.config.add_section('paper_trading')
            self.config['paper_trading'] = {
                'paper_trade': str(self.ai_config.paper_trade),
                'paper_balance': str(self.ai_config.paper_balance)
            }
            
            # Write to file
            with open(self.config_file, 'w') as f:
                self.config.write(f)
            
            logger.info(f'Configuration saved to {self.config_file}')
            
        except Exception as e:
            logger.error(f'Error saving configuration: {str(e)}')

    def update_setting(self, section: str, key: str, value: Any):
        """Update a specific setting"""
        try:
            # Update in config parser
            if section not in self.config:
                self.config.add_section(section)
            self.config[section][key] = str(value)
            
            # Update in AI config dataclass
            if hasattr(self.ai_config, key):
                setattr(self.ai_config, key, value)
            
            # Save to file
            self.save_configuration()
            
            logger.info(f'Setting updated: {section}.{key} = {value}')
            
        except Exception as e:
            logger.error(f'Error updating setting {section}.{key}: {str(e)}')

    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        """Get a specific setting value"""
        try:
            if section in self.config and key in self.config[section]:
                return self.config[section][key]
            else:
                return getattr(self.ai_config, key, default)
                
        except Exception as e:
            logger.error(f'Error getting setting {section}.{key}: {str(e)}')
            return default

    def get_ai_config(self) -> AITradingConfig:
        """Get the AI trading configuration"""
        return self.ai_config

    def sync_with_database(self, user_id: int):
        """Sync configuration with database user settings"""
        try:
            from models import User, TradingSettings, db
            
            user = User.query.get(user_id)
            if not user:
                logger.warning(f'User {user_id} not found for config sync')
                return
            
            # Update user API credentials
            if self.ai_config.api_key:
                user.api_key = self.ai_config.api_key
            if self.ai_config.api_secret:
                user.api_secret = self.ai_config.api_secret
            
            # Update or create trading settings
            if user.settings:
                settings = user.settings
            else:
                settings = TradingSettings(user_id=user_id)
                db.session.add(settings)
            
            settings.currency_pair = self.ai_config.currency_pair
            settings.timeframe = self.ai_config.timeframe
            settings.trading_enabled = self.ai_config.trading_enabled
            settings.risk_level = self.ai_config.risk_level
            settings.stop_loss_percentage = self.ai_config.stop_loss_percentage
            settings.take_profit_percentage = self.ai_config.take_profit_percentage
            settings.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            logger.info(f'Configuration synced with database for user {user_id}')
            
        except Exception as e:
            logger.error(f'Error syncing with database: {str(e)}')

    def export_settings(self) -> Dict[str, Any]:
        """Export settings as dictionary"""
        try:
            return {
                'ai_trading': {
                    'product_code': self.ai_config.product_code,
                    'use_percent': self.ai_config.use_percent,
                    'duration': self.ai_config.duration,
                    'past_period': self.ai_config.past_period,
                    'stop_limit_percent': self.ai_config.stop_limit_percent,
                    'trade_interval': self.ai_config.trade_interval
                },
                'github_trading': {
                    'currency_pair': self.ai_config.currency_pair,
                    'timeframe': self.ai_config.timeframe,
                    'trading_enabled': self.ai_config.trading_enabled,
                    'risk_level': self.ai_config.risk_level,
                    'stop_loss_percentage': self.ai_config.stop_loss_percentage,
                    'take_profit_percentage': self.ai_config.take_profit_percentage
                },
                'enhanced_ai': {
                    'ml_probability_threshold': self.ai_config.ml_probability_threshold,
                    'signal_confidence_threshold': self.ai_config.signal_confidence_threshold,
                    'optimization_interval': self.ai_config.optimization_interval,
                    'max_daily_loss': self.ai_config.max_daily_loss,
                    'max_consecutive_losses': self.ai_config.max_consecutive_losses
                },
                'paper_trading': {
                    'paper_trade': self.ai_config.paper_trade,
                    'paper_balance': self.ai_config.paper_balance
                },
                'export_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f'Error exporting settings: {str(e)}')
            return {}

    def import_settings(self, settings: Dict[str, Any]):
        """Import settings from dictionary"""
        try:
            # Import AI trading settings
            if 'ai_trading' in settings:
                ai_settings = settings['ai_trading']
                self.ai_config.product_code = ai_settings.get('product_code', self.ai_config.product_code)
                self.ai_config.use_percent = ai_settings.get('use_percent', self.ai_config.use_percent)
                self.ai_config.duration = ai_settings.get('duration', self.ai_config.duration)
                self.ai_config.past_period = ai_settings.get('past_period', self.ai_config.past_period)
                self.ai_config.stop_limit_percent = ai_settings.get('stop_limit_percent', self.ai_config.stop_limit_percent)
                self.ai_config.trade_interval = ai_settings.get('trade_interval', self.ai_config.trade_interval)
            
            # Import GitHub trading settings
            if 'github_trading' in settings:
                github_settings = settings['github_trading']
                self.ai_config.currency_pair = github_settings.get('currency_pair', self.ai_config.currency_pair)
                self.ai_config.timeframe = github_settings.get('timeframe', self.ai_config.timeframe)
                self.ai_config.trading_enabled = github_settings.get('trading_enabled', self.ai_config.trading_enabled)
                self.ai_config.risk_level = github_settings.get('risk_level', self.ai_config.risk_level)
                self.ai_config.stop_loss_percentage = github_settings.get('stop_loss_percentage', self.ai_config.stop_loss_percentage)
                self.ai_config.take_profit_percentage = github_settings.get('take_profit_percentage', self.ai_config.take_profit_percentage)
            
            # Import enhanced AI settings
            if 'enhanced_ai' in settings:
                enhanced_settings = settings['enhanced_ai']
                self.ai_config.ml_probability_threshold = enhanced_settings.get('ml_probability_threshold', self.ai_config.ml_probability_threshold)
                self.ai_config.signal_confidence_threshold = enhanced_settings.get('signal_confidence_threshold', self.ai_config.signal_confidence_threshold)
                self.ai_config.optimization_interval = enhanced_settings.get('optimization_interval', self.ai_config.optimization_interval)
                self.ai_config.max_daily_loss = enhanced_settings.get('max_daily_loss', self.ai_config.max_daily_loss)
                self.ai_config.max_consecutive_losses = enhanced_settings.get('max_consecutive_losses', self.ai_config.max_consecutive_losses)
            
            # Import paper trading settings
            if 'paper_trading' in settings:
                paper_settings = settings['paper_trading']
                self.ai_config.paper_trade = paper_settings.get('paper_trade', self.ai_config.paper_trade)
                self.ai_config.paper_balance = paper_settings.get('paper_balance', self.ai_config.paper_balance)
            
            # Validate and save
            self._validate_and_normalize()
            self.save_configuration()
            
            logger.info('Settings imported successfully')
            
        except Exception as e:
            logger.error(f'Error importing settings: {str(e)}')

# Global configuration instance
_config_manager = None

def get_integrated_config() -> IntegratedConfigManager:
    """Get the global integrated configuration manager"""
    global _config_manager
    if _config_manager is None:
        _config_manager = IntegratedConfigManager()
    return _config_manager

def get_ai_config() -> AITradingConfig:
    """Get the AI trading configuration"""
    return get_integrated_config().get_ai_config()