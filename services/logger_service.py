import logging
import os
from datetime import datetime
import json

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/trading_bot.log'),
        logging.StreamHandler()
    ]
)

class TradeLogger:
    """
    Enhanced logging service for trading operations
    """
    
    @staticmethod
    def log_trade_execution(trade, is_bot=True):
        """Log trade execution"""
        try:
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'event': 'trade_execution',
                'trade_id': trade.id if hasattr(trade, 'id') else None,
                'currency_pair': trade.currency_pair,
                'trade_type': trade.trade_type,
                'amount': str(trade.amount),
                'price': str(trade.price),
                'is_bot': is_bot
            }
            
            logger = logging.getLogger('trade_execution')
            logger.info(f"Trade executed: {json.dumps(log_data)}")
            
            # Save to separate trade log file
            with open('logs/trades.log', 'a') as f:
                f.write(f"{json.dumps(log_data)}\n")
                
        except Exception as e:
            logger = logging.getLogger('trade_logger')
            logger.error(f"Error logging trade execution: {e}")
    
    @staticmethod
    def log_trade_close(trade, closing_price, profit_loss, reason):
        """Log trade closure"""
        try:
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'event': 'trade_close',
                'trade_id': trade.id if hasattr(trade, 'id') else None,
                'currency_pair': trade.currency_pair,
                'entry_price': str(trade.price),
                'closing_price': str(closing_price),
                'profit_loss': str(profit_loss),
                'reason': reason
            }
            
            logger = logging.getLogger('trade_close')
            logger.info(f"Trade closed: {json.dumps(log_data)}")
            
            # Save to separate trade log file
            with open('logs/trades.log', 'a') as f:
                f.write(f"{json.dumps(log_data)}\n")
                
        except Exception as e:
            logger = logging.getLogger('trade_logger')
            logger.error(f"Error logging trade close: {e}")
    
    @staticmethod
    def log_api_error(error_message, endpoint=None, params=None):
        """Log API errors"""
        try:
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'event': 'api_error',
                'error_message': error_message,
                'endpoint': endpoint,
                'params': params
            }
            
            logger = logging.getLogger('api_error')
            logger.error(f"API Error: {json.dumps(log_data)}")
            
            # Save to separate error log file
            with open('logs/errors.log', 'a') as f:
                f.write(f"{json.dumps(log_data)}\n")
                
        except Exception as e:
            logger = logging.getLogger('trade_logger')
            logger.error(f"Error logging API error: {e}")
    
    @staticmethod
    def log_strategy_signal(currency_pair, signal_type, probability, indicators):
        """Log trading strategy signals"""
        try:
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'event': 'strategy_signal',
                'currency_pair': currency_pair,
                'signal_type': signal_type,
                'probability': probability,
                'indicators': {
                    'rsi': indicators.get('rsi_14', None),
                    'macd_line': indicators.get('macd_line', None),
                    'macd_signal': indicators.get('macd_signal', None),
                    'close_price': indicators.get('close', None)
                }
            }
            
            logger = logging.getLogger('strategy_signal')
            logger.info(f"Strategy signal: {json.dumps(log_data)}")
            
            # Save to separate signals log file
            with open('logs/signals.log', 'a') as f:
                f.write(f"{json.dumps(log_data)}\n")
                
        except Exception as e:
            logger = logging.getLogger('trade_logger')
            logger.error(f"Error logging strategy signal: {e}")
    
    @staticmethod
    def log_market_data(currency_pair, price_data):
        """Log market data updates"""
        try:
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'event': 'market_data',
                'currency_pair': currency_pair,
                'price_data': price_data
            }
            
            logger = logging.getLogger('market_data')
            logger.debug(f"Market data: {json.dumps(log_data)}")
            
        except Exception as e:
            logger = logging.getLogger('trade_logger')
            logger.error(f"Error logging market data: {e}")
    
    @staticmethod
    def get_recent_trades(limit=10):
        """Get recent trade logs"""
        try:
            if not os.path.exists('logs/trades.log'):
                return []
            
            trades = []
            with open('logs/trades.log', 'r') as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    try:
                        trades.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
            
            return trades[::-1]  # Reverse to get newest first
            
        except Exception as e:
            logger = logging.getLogger('trade_logger')
            logger.error(f"Error getting recent trades: {e}")
            return []
    
    @staticmethod
    def get_recent_errors(limit=10):
        """Get recent error logs"""
        try:
            if not os.path.exists('logs/errors.log'):
                return []
            
            errors = []
            with open('logs/errors.log', 'r') as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    try:
                        errors.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
            
            return errors[::-1]  # Reverse to get newest first
            
        except Exception as e:
            logger = logging.getLogger('trade_logger')
            logger.error(f"Error getting recent errors: {e}")
            return []