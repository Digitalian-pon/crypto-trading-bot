import logging
from datetime import datetime
import json
import os

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Notification service for trading alerts
    """
    
    def __init__(self):
        self.alerts_file = 'logs/alerts.json'
        self.max_alerts = 50
        
        # Create alerts directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
    
    def send_alert(self, alert_type, message, price=None, symbol=None):
        """
        Send alert notification
        
        :param alert_type: Type of alert ('trade', 'price', 'error', 'info')
        :param message: Alert message
        :param price: Current price (optional)
        :param symbol: Trading symbol (optional)
        """
        try:
            alert = {
                'timestamp': datetime.now().isoformat(),
                'type': alert_type,
                'message': message,
                'price': price,
                'symbol': symbol
            }
            
            # Load existing alerts
            alerts = self.load_alerts()
            
            # Add new alert at beginning
            alerts.insert(0, alert)
            
            # Keep only recent alerts
            alerts = alerts[:self.max_alerts]
            
            # Save alerts
            self.save_alerts(alerts)
            
            # Log the alert
            logger.info(f"Alert sent: {alert_type} - {message}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
            return False
    
    def load_alerts(self):
        """Load alerts from file"""
        try:
            if os.path.exists(self.alerts_file):
                with open(self.alerts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Error loading alerts: {e}")
            return []
    
    def save_alerts(self, alerts):
        """Save alerts to file"""
        try:
            with open(self.alerts_file, 'w', encoding='utf-8') as f:
                json.dump(alerts, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving alerts: {e}")
            return False
    
    def get_recent_alerts(self, limit=10):
        """Get recent alerts"""
        try:
            alerts = self.load_alerts()
            return alerts[:limit]
        except Exception as e:
            logger.error(f"Error getting recent alerts: {e}")
            return []
    
    def clear_alerts(self):
        """Clear all alerts"""
        try:
            self.save_alerts([])
            return True
        except Exception as e:
            logger.error(f"Error clearing alerts: {e}")
            return False
    
    # Predefined alert types
    def alert_trade_executed(self, trade_type, symbol, price, amount):
        """Alert for executed trade"""
        message = f"{trade_type.upper()}注文実行: {amount} {symbol} @ ¥{price}"
        self.send_alert('trade', message, price, symbol)
    
    def alert_price_change(self, symbol, price, change_percent):
        """Alert for significant price change"""
        direction = "上昇" if change_percent > 0 else "下降"
        message = f"{symbol} 価格{direction}: ¥{price} ({change_percent:+.2f}%)"
        self.send_alert('price', message, price, symbol)
    
    def alert_error(self, error_message):
        """Alert for system error"""
        self.send_alert('error', f"システムエラー: {error_message}")
    
    def alert_system_status(self, status):
        """Alert for system status change"""
        self.send_alert('info', f"システム状態: {status}")