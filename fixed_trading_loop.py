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
        
        # Get the trading pair and timeframe from settings
        symbol = self.user.settings.currency_pair
        timeframe = getattr(self.user.settings, 'timeframe', '5m')  # デフォルト5分足
        logger.info(f"Processing currency pair: {symbol}, timeframe: {timeframe}")
        
        # Get market data with indicators
        logger.info(f"Fetching market data with indicators for {symbol} ({timeframe})...")
        df = self.data_service.get_data_with_indicators(symbol, interval=timeframe, limit=100)
        
        if df is None or df.empty:
            logger.error("Failed to get market data, skipping this iteration")
            return
        
        logger.info(f"Successfully retrieved {len(df)} market data points")
        
        # Get active trades
        from models import Trade
        active_trades = []
        
        # First check for exchange positions and sync with database
        exchange_positions = self._get_exchange_positions(symbol)
        if exchange_positions:
            logger.info(f"Found {len(exchange_positions)} positions on exchange")
            self._sync_exchange_positions(exchange_positions, symbol)
        
        if self.db_session:
            try:
                user_id = self.user.id
                active_trades = self.db_session.query(Trade).filter_by(
                    user_id=user_id,
                    currency_pair=symbol,
                    status='open'
                ).all()
                
                logger.info(f"Found {len(active_trades)} active trades in database")
            except Exception as db_e:
                logger.error(f"Database error while querying active trades: {db_e}")
                try:
                    self.db_session.rollback()
                except:
                    pass
                    
        # If no DB trades but exchange positions exist, use exchange data for closing
        if len(active_trades) == 0 and exchange_positions:
            logger.info("Using exchange positions for trade management")
            self._check_exchange_positions_for_closing(exchange_positions, current_price, latest_indicators)
        
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
        
        # JPY残高のみの場合、BUY取引のみ実行可能
        # Lower probability threshold to 0.45 for more trading opportunities
        if prediction['prediction'] == 1 and prediction['probability'] > 0.45:
            # Model predicts price will go up - BUY signal
            if market_eval['market_trend'] != 'bearish' or market_eval['trend_strength'] < 0.7:
                should_trade = True
                trade_type = 'buy'
                trade_reason = f"Bullish signal with {prediction['probability']:.2f} probability - Buying DOGE with JPY"
        elif prediction['prediction'] == 0 and prediction['probability'] > 0.45:
            # Model predicts price will go down - 通常ならSELLだが、JPY残高のためスキップ
            logger.info(f"Bearish signal detected ({prediction['probability']:.2f} probability) but only JPY available - cannot SELL")
            should_trade = False
            trade_reason = "Bearish signal but insufficient DOGE holdings for SELL"
        elif market_eval['trend_strength'] > 0.5:  # 閾値を下げて取引機会を増加
            # Strong trend without clear ML signal
            if market_eval['market_trend'] == 'bullish':
                should_trade = True
                trade_type = 'buy'
                trade_reason = f"Strong bullish trend detected. Strength: {market_eval['trend_strength']:.2f} - Buying DOGE"
            elif market_eval['market_trend'] == 'bearish':
                logger.info(f"Bearish trend detected (strength: {market_eval['trend_strength']:.2f}) but only JPY available - skipping SELL")
                should_trade = False
                trade_reason = "Bearish trend but insufficient DOGE holdings"
        
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
            
            # Calculate position size (BUY注文用)
            position_size = self.risk_manager.calculate_position_size(available_balance, current_price, symbol)
            logger.info(f"Calculated position size for {symbol}: {position_size}")
            
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
    
    def _get_exchange_positions(self, symbol):
        """Get current positions from the exchange"""
        try:
            response = self.api.get_positions(symbol=symbol)
            if response.get('status') == 0 and response.get('data'):
                positions = response['data'].get('list', [])
                logger.info(f"Retrieved {len(positions)} positions from exchange for {symbol}")
                return positions
            else:
                logger.info(f"No positions found on exchange: {response}")
                return []
        except Exception as e:
            logger.error(f"Error getting exchange positions: {e}")
            return []
    
    def _sync_exchange_positions(self, exchange_positions, symbol):
        """Sync exchange positions with database"""
        if not self.db_session:
            return
            
        try:
            from models import Trade
            from datetime import datetime
            
            for position in exchange_positions:
                position_id = position.get('positionId')
                side = position.get('side', '').lower()  # 'BUY' or 'SELL'
                size = float(position.get('size', 0))
                price = float(position.get('price', 0))
                
                # Check if this position already exists in database
                existing_trade = self.db_session.query(Trade).filter_by(
                    exchange_position_id=position_id,
                    currency_pair=symbol
                ).first()
                
                if not existing_trade:
                    # Create new trade record
                    new_trade = Trade()
                    new_trade.user_id = self.user.id
                    new_trade.currency_pair = symbol
                    new_trade.trade_type = side
                    new_trade.amount = size
                    new_trade.price = price
                    new_trade.status = 'open'
                    new_trade.exchange_position_id = position_id
                    new_trade.created_at = datetime.utcnow()
                    
                    self.db_session.add(new_trade)
                    logger.info(f"Synced new {side.upper()} position: {size} {symbol} at {price}")
            
            self.db_session.commit()
            logger.info("Exchange positions synced with database")
            
        except Exception as e:
            logger.error(f"Error syncing exchange positions: {e}")
            if self.db_session:
                try:
                    self.db_session.rollback()
                except:
                    pass
    
    def _check_exchange_positions_for_closing(self, exchange_positions, current_price, market_indicators):
        """Check exchange positions for closing without database dependency"""
        logger.info(f"Checking {len(exchange_positions)} exchange positions for closing")
        
        for position in exchange_positions:
            side = position.get('side', '').lower()
            size = float(position.get('size', 0))
            entry_price = float(position.get('price', 0))
            position_id = position.get('positionId')
            
            # Calculate current P/L
            if side == 'buy':
                pl_ratio = (current_price - entry_price) / entry_price * 100
            else:
                pl_ratio = (entry_price - current_price) / entry_price * 100
            
            logger.info(f"Position {position_id} ({side.upper()}): Entry={entry_price}, Current={current_price}, P/L={pl_ratio:.2f}%")
            
            # Check for opposite signals
            should_close, reason = self._should_close_exchange_position(position, current_price, market_indicators)
            
            if should_close:
                logger.info(f"Closing exchange position {position_id} due to: {reason}")
                self._close_exchange_position(position, current_price, reason)
    
    def _should_close_exchange_position(self, position, current_price, market_indicators):
        """Determine if an exchange position should be closed"""
        if not market_indicators:
            return False, "No market data"
            
        side = position.get('side', '').lower()
        entry_price = float(position.get('price', 0))
        
        # Get indicators
        rsi = market_indicators.get('rsi_14', 50)
        macd_line = market_indicators.get('macd_line', 0)
        macd_signal = market_indicators.get('macd_signal', 0)
        ema_12 = market_indicators.get('ema_12', current_price)
        ema_26 = market_indicators.get('ema_26', current_price)
        bb_upper = market_indicators.get('bb_upper', current_price * 1.02)
        bb_lower = market_indicators.get('bb_lower', current_price * 0.98)
        bb_middle = market_indicators.get('bb_middle', current_price)
        
        # Stop loss and take profit checks
        if side == 'buy':
            pl_ratio = (current_price - entry_price) / entry_price
            if pl_ratio <= -0.03:  # 3% loss
                return True, "Stop loss triggered (3% loss)"
            if pl_ratio >= 0.05:  # 5% profit
                return True, "Take profit triggered (5% profit)"
        else:  # sell
            pl_ratio = (entry_price - current_price) / entry_price
            if pl_ratio <= -0.03:  # 3% loss
                return True, "Stop loss triggered (3% loss)"
            if pl_ratio >= 0.05:  # 5% profit
                return True, "Take profit triggered (5% profit)"
        
        # Opposite signal detection
        if side == 'buy':
            # Check for strong sell signals to close buy position
            bearish_signals = 0
            
            if rsi > 70:  # Overbought
                bearish_signals += 1
            if macd_line < macd_signal and abs(macd_line - macd_signal) > 0.1:  # MACD bearish
                bearish_signals += 1
            if ema_12 < ema_26 and (ema_26 - ema_12) / ema_26 > 0.01:  # Death cross
                bearish_signals += 1
            if current_price < bb_middle and current_price < bb_lower * 1.01:  # Below BB middle
                bearish_signals += 1
                
            if bearish_signals >= 2:
                return True, f"Strong bearish reversal detected ({bearish_signals}/4 signals)"
                
        else:  # sell position
            # Check for strong buy signals to close sell position
            bullish_signals = 0
            
            if rsi < 30:  # Oversold
                bullish_signals += 1
            if macd_line > macd_signal and abs(macd_line - macd_signal) > 0.1:  # MACD bullish
                bullish_signals += 1
            if ema_12 > ema_26 and (ema_12 - ema_26) / ema_26 > 0.01:  # Golden cross
                bullish_signals += 1
            if current_price > bb_middle and current_price > bb_upper * 0.99:  # Above BB middle
                bullish_signals += 1
                
            if bullish_signals >= 2:
                return True, f"Strong bullish reversal detected ({bullish_signals}/4 signals)"
        
        return False, "No close signal detected"
    
    def _close_exchange_position(self, position, current_price, reason):
        """Close an exchange position using individual close API"""
        try:
            symbol = position.get('symbol')
            side = position.get('side')  # The current position side
            size = position.get('size')
            position_id = position.get('positionId')
            
            logger.info(f"Closing position {position_id}: {size} {symbol} {side} at {current_price}")
            
            # Use individual position close with opposite side
            close_side = "SELL" if side == "BUY" else "BUY"
            result = self.api.close_position(
                symbol=symbol,
                side=close_side,
                execution_type="MARKET",
                position_id=position_id,
                size=str(size)
            )
            
            if result.get('status') == 0:
                logger.info(f"Position {position_id} closed successfully: {result}")
                # Update database if trade exists
                if self.db_session:
                    try:
                        from models import Trade
                        db_trade = self.db_session.query(Trade).filter_by(
                            exchange_position_id=position_id
                        ).first()
                        if db_trade:
                            db_trade.status = 'closed'
                            db_trade.closing_price = current_price
                            db_trade.closed_at = datetime.utcnow()
                            self.db_session.commit()
                    except Exception as db_e:
                        logger.error(f"Error updating database after close: {db_e}")
            else:
                logger.error(f"Failed to close position {position_id}: {result}")
                
        except Exception as e:
            logger.error(f"Error closing exchange position: {e}")