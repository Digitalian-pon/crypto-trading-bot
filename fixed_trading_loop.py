import logging
import time
from datetime import datetime
import threading
import pandas as pd
import sys
import traceback
from services.gmo_api import GMOCoinAPI
from services.technical_indicators import TechnicalIndicators
from services.ml_model import TradingModel
from services.risk_manager import RiskManager
from services.data_service import DataService
from services.logger_service import TradeLogger

# ロギング設定を強化
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class FixedTradingBot:
    """
    Fixed version of the automated cryptocurrency trading bot
    """
    
    def __init__(self, user=None, api_key=None, api_secret=None, app=None):
        """
        Initialize the trading bot
        
        :param user: User object with trading settings
        :param api_key: GMO Coin API key
        :param api_secret: GMO Coin API secret
        :param app: Flask app instance for context
        """
        self.user = user
        self.api = GMOCoinAPI(api_key, api_secret)
        self.data_service = DataService(api_key, api_secret)
        self.model = TradingModel()
        self.risk_manager = RiskManager()
        self.running = False
        self.thread = None
        self.interval = 60  # Default check interval in seconds
        self.db_session = None
        self.app = app
    
    def set_db_session(self, session):
        """Set the database session"""
        self.db_session = session
        
    def start(self, interval=None):
        """Start the trading bot in a separate thread"""
        if self.running:
            logger.warning("Trading bot is already running")
            return False
        
        if interval:
            self.interval = interval
        
        # Validate user information
        if not self.user:
            logger.error("Cannot start trading bot: User not provided")
            return False
        
        if not hasattr(self.user, 'api_key') or not self.user.api_key:
            logger.error("Cannot start trading bot: API key not set")
            return False
            
        if not hasattr(self.user, 'settings') or not self.user.settings:
            logger.error("Cannot start trading bot: Trading settings not found")
            return False
            
        if not self.user.settings.trading_enabled:
            logger.error("Cannot start trading bot: Trading is not enabled in settings")
            return False
        
        # Update API credentials and risk manager
        self.api = GMOCoinAPI(self.user.api_key, self.user.api_secret)
        self.data_service = DataService(self.user.api_key, self.user.api_secret)
        self.risk_manager.update_settings(self.user.settings)
        
        # Start the trading thread
        self.running = True
        self.thread = threading.Thread(target=self._trading_loop)
        self.thread.daemon = True
        self.thread.start()
        
        logger.info(f"Trading bot started for user {self.user.username}")
        return True
    
    def stop(self):
        """Stop the trading bot"""
        if not self.running:
            return False
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
            self.thread = None
        
        logger.info(f"Trading bot stopped for user {self.user.username}")
        return True
    
    def _trading_loop(self):
        """Main trading loop that runs in a separate thread"""
        logger.info("Trading loop started")
        
        while self.running:
            try:
                # Execute trading cycle within app context if available
                if self.app:
                    with self.app.app_context():
                        self._execute_trading_cycle()
                else:
                    self._execute_trading_cycle()
                    
                # Sleep until next check
                logger.info(f"Sleeping for {self.interval} seconds until next check")
                time.sleep(self.interval)
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                logger.error(f"Error traceback: {traceback.format_exc()}")
                time.sleep(self.interval)
    
    def _execute_trading_cycle(self):
        """Execute one trading cycle"""
        # Check if user and settings are still available
        if not self.user or not self.user.settings:
            logger.error("User or settings not available, stopping bot")
            self.running = False
            return
        
        if not self.user.settings.trading_enabled:
            logger.info("Trading has been disabled in settings, stopping bot")
            self.running = False
            return
        
        # Get the trading pair from settings
        symbol = self.user.settings.currency_pair
        logger.info(f"Processing currency pair: {symbol}")
        
        # Get market data with indicators
        logger.info(f"Fetching market data with indicators for {symbol}...")
        df = self.data_service.get_data_with_indicators(symbol, interval="1h", limit=100)
        
        if df is None or df.empty:
            logger.error("Failed to get market data, skipping this iteration")
            return
        
        logger.info(f"Successfully retrieved {len(df)} market data points")
        
        # Get active trades
        from models import Trade
        active_trades = []
        
        if self.db_session:
            try:
                user_id = self.user.id
                active_trades = self.db_session.query(Trade).filter_by(
                    user_id=user_id,
                    currency_pair=symbol,
                    status='open'
                ).all()
                
                logger.info(f"Found {len(active_trades)} active trades")
            except Exception as db_e:
                logger.error(f"Database error while querying active trades: {db_e}")
                try:
                    self.db_session.rollback()
                except:
                    pass
        
        # Check current price and existing trades
        current_price = df['close'].iloc[-1]
        logger.info(f"Current {symbol} price: {current_price}")
        
        # Get current market indicators for trend reversal check
        latest_indicators = df.iloc[-1].to_dict()
        
        # Check if any active trades need to be closed
        self._check_active_trades(active_trades, current_price, latest_indicators)
        
        # If no active trades, check for new trade opportunities
        if len(active_trades) == 0:
            logger.info("No active trades found, checking for new trade opportunities")
            self._check_for_new_trade(df, symbol, current_price)
    
    def _check_active_trades(self, active_trades, current_price, market_indicators=None):
        """Check if any active trades need to be closed"""
        if not active_trades:
            return
        
        logger.info(f"Checking {len(active_trades)} active trades for exit conditions")
        
        # Check for major trend reversal that requires closing all positions
        major_reversal = self._check_major_trend_reversal(active_trades, market_indicators)
        if major_reversal:
            logger.warning(f"Major trend reversal detected: {major_reversal}")
            logger.warning("Initiating emergency close of all positions!")
            for trade in active_trades:
                self._close_trade(trade, current_price, f"Emergency close: {major_reversal}")
            return
        
        # Check individual trades
        for trade in active_trades:
            should_close, reason = self.risk_manager.should_close_trade(trade, current_price, market_indicators)
            
            if should_close:
                logger.info(f"Closing trade {trade.id} due to: {reason}")
                self._close_trade(trade, current_price, reason)
            else:
                # Log current trade status
                entry_price = float(trade.price)
                if trade.trade_type.lower() == 'buy':
                    pl_ratio = (current_price - entry_price) / entry_price * 100
                else:
                    pl_ratio = (entry_price - current_price) / entry_price * 100
                
                logger.info(f"Trade {trade.id} ({trade.trade_type.upper()}) still open: Entry={entry_price}, Current={current_price}, P/L={pl_ratio:.2f}%")
    
    def _close_trade(self, trade, current_price, reason):
        """Close a trade and record the result"""
        logger.info(f"Closing trade {trade.id} at price {current_price}, reason: {reason}")
        
        try:
            # Calculate profit/loss
            pl = self.risk_manager.calculate_profit_loss(trade, current_price)
            
            # Execute the close order on the exchange
            close_side = "SELL" if trade.trade_type.upper() == "BUY" else "BUY"
            
            # Format size according to currency pair requirements
            if 'DOGE_' in trade.currency_pair:
                size = max(10, int(trade.amount))
                size_str = f"{size}"
            elif 'XRP_' in trade.currency_pair:
                size = max(10, int(trade.amount))
                size_str = f"{size}"
            elif 'BTC_' in trade.currency_pair:
                size = max(0.0001, round(trade.amount, 8))
                size_str = f"{size:.8f}"
            elif 'ETH_' in trade.currency_pair:
                size = max(0.001, round(trade.amount, 8))
                size_str = f"{size:.8f}"
            else:
                size = max(1, round(trade.amount, 4))
                size_str = f"{size:.4f}"
            
            result = self.api.place_order(
                symbol=trade.currency_pair,
                side=close_side,
                execution_type="MARKET",
                size=size_str
            )
            
            if 'data' in result:
                # Update trade in database
                trade.status = 'closed'
                trade.closing_price = current_price
                trade.profit_loss = pl['amount']
                trade.closed_at = datetime.utcnow()
                
                if self.db_session:
                    self.db_session.commit()
                
                logger.info(f"Trade {trade.id} closed successfully with P/L: {pl['amount']} ({pl['percentage']:.2f}%)")
            else:
                logger.error(f"Failed to close trade {trade.id}: {result}")
                
        except Exception as e:
            if self.db_session:
                try:
                    self.db_session.rollback()
                except:
                    pass
            logger.error(f"Error closing trade {trade.id}: {e}")
    
    def _check_for_new_trade(self, df, symbol, current_price):
        """Check if we should open a new trade"""
        logger.info(f"Checking for new trade opportunities for {symbol} at price {current_price}")
        
        # Get prediction from the ML model
        prediction = self.model.predict(df)
        
        if not prediction:
            # Fallback prediction based on technical indicators
            logger.warning("Using fallback prediction based on technical indicators")
            last_row = df.iloc[-1].to_dict()
            
            rsi = last_row.get('rsi_14', 50)
            macd_line = last_row.get('macd_line', 0)
            macd_signal = last_row.get('macd_signal', 0)
            macd_crossover = macd_line > macd_signal
            
            price = last_row.get('close', 0)
            bb_lower = last_row.get('bb_lower', price * 0.97)
            bb_upper = last_row.get('bb_upper', price * 1.03)
            
            # Buy signal logic
            buy_signal = (rsi < 35) or macd_crossover or (price < bb_lower * 1.02)
            # Sell signal logic
            sell_signal = (rsi > 65) or (not macd_crossover) or (price > bb_upper * 0.98)
            
            pred_value = 1 if buy_signal and not sell_signal else 0
            prob_value = 0.75 if (buy_signal and not sell_signal) or (sell_signal and not buy_signal) else 0.60
            
            prediction = {
                'prediction': pred_value,
                'probability': prob_value,
                'features': last_row
            }
        
        logger.info(f"Model prediction: {prediction['prediction']}, probability: {prediction['probability']:.4f}")
        
        # Evaluate market conditions
        last_row = df.iloc[-1].to_dict()
        market_eval = self.risk_manager.evaluate_market_conditions(last_row)
        
        logger.info(f"Market evaluation: trend={market_eval['market_trend']}, risk_score={market_eval['risk_score']}")
        
        # Determine if we should trade
        should_trade = False
        trade_type = None
        trade_reason = ""
        
        # Lower probability threshold to 0.55 for more trading opportunities
        if prediction['prediction'] == 1 and prediction['probability'] > 0.55:
            # Model predicts price will go up
            if market_eval['market_trend'] != 'bearish' or market_eval['trend_strength'] < 0.7:
                should_trade = True
                trade_type = 'buy'
                trade_reason = f"Bullish signal with {prediction['probability']:.2f} probability"
        elif prediction['prediction'] == 0 and prediction['probability'] > 0.55:
            # Model predicts price will go down
            if market_eval['market_trend'] != 'bullish' or market_eval['trend_strength'] < 0.7:
                should_trade = True
                trade_type = 'sell'
                trade_reason = f"Bearish signal with {prediction['probability']:.2f} probability"
        elif market_eval['trend_strength'] > 0.6:
            # Strong trend without clear ML signal
            should_trade = True
            if market_eval['market_trend'] == 'bullish':
                trade_type = 'buy'
                trade_reason = f"Strong bullish trend. Strength: {market_eval['trend_strength']:.2f}"
            elif market_eval['market_trend'] == 'bearish':
                trade_type = 'sell'
                trade_reason = f"Strong bearish trend. Strength: {market_eval['trend_strength']:.2f}"
        
        if should_trade and trade_type:
            logger.info(f"Decision to trade: {trade_type} because {trade_reason}")
            self._execute_trade(symbol, trade_type, current_price, last_row)
        else:
            logger.info("No trade opportunity at this time")
    
    def _execute_trade(self, symbol, trade_type, current_price, indicators_data):
        """Execute a new trade"""
        logger.info(f"Executing {trade_type} trade for {symbol} at {current_price}")
        
        try:
            # Get available balance
            balance_response = self.api.get_account_balance()
            
            available_balance = 0
            if 'data' in balance_response:
                for asset in balance_response['data']:
                    if asset['symbol'] == 'JPY':
                        available_balance = float(asset['available'])
                        break
                        
                logger.info(f"Available JPY balance for trading: {available_balance}")
            
            if available_balance <= 0:
                logger.error("No available balance for trading")
                return
            
            # Calculate position size
            position_size = self.risk_manager.calculate_position_size(available_balance, current_price)
            
            # Format size according to currency pair requirements
            if 'DOGE_' in symbol:
                position_size_rounded = max(10, int(position_size))
                position_size_str = f"{position_size_rounded}"
            elif 'XRP_' in symbol:
                position_size_rounded = max(10, int(position_size))
                position_size_str = f"{position_size_rounded}"
            elif 'BTC_' in symbol:
                position_size_rounded = max(0.0001, round(position_size, 8))
                position_size_str = f"{position_size_rounded:.8f}"
            elif 'ETH_' in symbol:
                position_size_rounded = max(0.001, round(position_size, 8))
                position_size_str = f"{position_size_rounded:.8f}"
            else:
                position_size_rounded = max(1, round(position_size, 4))
                position_size_str = f"{position_size_rounded:.4f}"
            
            # Execute the order
            result = self.api.place_order(
                symbol=symbol,
                side=trade_type.upper(),
                execution_type="MARKET",
                size=position_size_str
            )
            
            if 'data' in result:
                # Create new trade record
                from models import Trade
                new_trade = Trade()
                new_trade.user_id = self.user.id
                new_trade.currency_pair = symbol
                new_trade.trade_type = trade_type.lower()
                new_trade.amount = position_size_rounded
                new_trade.price = current_price
                new_trade.status = 'open'
                new_trade.indicators_data = indicators_data
                
                if self.db_session:
                    self.db_session.add(new_trade)
                    self.db_session.commit()
                
                logger.info(f"New {trade_type} trade executed: {position_size_rounded} {symbol} at {current_price}")
            else:
                logger.error(f"Failed to execute {trade_type} trade. API response: {result}")
                
        except Exception as e:
            logger.error(f"Error executing {trade_type} trade: {e}")
            if self.db_session:
                try:
                    self.db_session.rollback()
                except:
                    pass
    
    def _check_major_trend_reversal(self, active_trades, market_indicators):
        """Check for major trend reversal that requires closing all positions"""
        if not market_indicators or not active_trades:
            return None
            
        try:
            # Analyze the majority position direction
            buy_trades = sum(1 for trade in active_trades if trade.trade_type.lower() == 'buy')
            sell_trades = len(active_trades) - buy_trades
            
            # If we have mostly BUY positions
            if buy_trades > sell_trades:
                # Check for strong bearish reversal signals
                rsi = market_indicators.get('rsi_14', 50)
                macd_line = market_indicators.get('macd_line', 0)
                macd_signal = market_indicators.get('macd_signal', 0)
                close = market_indicators.get('close', 0)
                ema_12 = market_indicators.get('ema_12', close)
                ema_26 = market_indicators.get('ema_26', close)
                
                # Extremely strong bearish signals for emergency close
                if rsi > 80:  # Extreme overbought
                    return "Extreme RSI overbought (>80) - emergency close all BUY positions"
                
                # Death cross with strong momentum
                if ema_12 < ema_26 and (ema_26 - ema_12) / ema_26 > 0.02:  # 2% gap
                    return "Strong death cross pattern - emergency close all BUY positions"
                
                # MACD with very strong bearish momentum
                if macd_line < macd_signal and (macd_signal - macd_line) > 1.0:
                    return "Extreme MACD bearish divergence - emergency close all BUY positions"
            
            # If we have mostly SELL positions
            elif sell_trades > buy_trades:
                # Check for strong bullish reversal signals
                rsi = market_indicators.get('rsi_14', 50)
                macd_line = market_indicators.get('macd_line', 0)
                macd_signal = market_indicators.get('macd_signal', 0)
                close = market_indicators.get('close', 0)
                ema_12 = market_indicators.get('ema_12', close)
                ema_26 = market_indicators.get('ema_26', close)
                
                # Extremely strong bullish signals for emergency close
                if rsi < 20:  # Extreme oversold
                    return "Extreme RSI oversold (<20) - emergency close all SELL positions"
                
                # Golden cross with strong momentum
                if ema_12 > ema_26 and (ema_12 - ema_26) / ema_26 > 0.02:  # 2% gap
                    return "Strong golden cross pattern - emergency close all SELL positions"
                
                # MACD with very strong bullish momentum
                if macd_line > macd_signal and (macd_line - macd_signal) > 1.0:
                    return "Extreme MACD bullish divergence - emergency close all SELL positions"
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking major trend reversal: {e}")
            return None