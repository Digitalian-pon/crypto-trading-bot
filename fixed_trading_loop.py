import logging
import time
from datetime import datetime
import threading
import pandas as pd
import sys
import traceback
from services.gmo_api import GMOCoinAPI
from services.technical_indicators import TechnicalIndicators
from services.enhanced_trading_logic import EnhancedTradingLogic as SimpleTradingLogic
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
        self.trading_logic = SimpleTradingLogic()
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
        
        # First check for exchange positions and sync with database (ALWAYS sync)
        exchange_positions = self._get_exchange_positions(symbol)
        logger.info(f"Found {len(exchange_positions)} positions on exchange")
        # Always run sync to handle orphaned positions, even if exchange_positions is empty
        self._sync_exchange_positions(exchange_positions, symbol)
        
        if self.db_session and self.app:
            try:
                with self.app.app_context():
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
                    if self.app:
                        with self.app.app_context():
                            self.db_session.rollback()
                    else:
                        self.db_session.rollback()
                except:
                    pass
                    
        # Check current price and existing trades
        current_price = df['close'].iloc[-1]
        logger.info(f"Current {symbol} price: {current_price}")

        # Get current market indicators for trend reversal check
        latest_indicators = df.iloc[-1].to_dict()

        # If no DB trades but exchange positions exist, use exchange data for closing
        if len(active_trades) == 0 and exchange_positions:
            logger.info("Using exchange positions for trade management")
            self._check_exchange_positions_for_closing(exchange_positions, current_price, latest_indicators)
        
        # Check if any active trades need to be closed
        self._check_active_trades(active_trades, current_price, latest_indicators)
        
        # Exchange position check to prevent multiple orders
        exchange_positions = self._get_exchange_positions(symbol)
        has_exchange_position = len(exchange_positions) > 0

        # If no active trades in DB but exchange has position, sync first
        if len(active_trades) == 0 and has_exchange_position:
            logger.warning("No DB trades but exchange has positions - using exchange position management")
            # Use exchange positions instead of DB for trade management
            active_trades = []

        # 【修正版】シグナルベース決済を優先し、ポジション状態を確認
        logger.info("🔄 Starting position state machine control...")

        # ポジション存在時も、まずシグナルベースの決済チェックを実行
        if has_exchange_position:
            logger.info(f"🚨 POSITION STATE: {len(exchange_positions)} positions exist")

            # シグナルベースの逆シグナル決済チェック（_check_for_new_trade内で実行）
            logger.info("🔍 Checking for opposite signal closure...")
            self._check_for_new_trade(df, symbol, current_price)

            # 決済後のポジション状態を再確認
            exchange_positions = self._get_exchange_positions(symbol)
            has_exchange_position = len(exchange_positions) > 0

            # まだポジションが残っている場合は、損切り・利確チェックも実行
            if has_exchange_position:
                logger.info(f"📊 Still have {len(exchange_positions)} positions after signal check - checking SL/TP...")
                self._check_existing_positions_for_closure_only(exchange_positions, current_price, latest_indicators)
            else:
                logger.info("✅ All positions closed by signal - ready for new trades")
        else:
            # ポジション0個の場合は通常通り新規注文チェック
            logger.info("✅ POSITION STATE: No positions - checking for new trade opportunities")
            self._check_for_new_trade(df, symbol, current_price)

        # Only open new trades if no active trades AND no exchange positions
        if len(active_trades) == 0 and not has_exchange_position:
            logger.info("No active trades found - new trade opportunities checked above")
        elif len(active_trades) == 0 and has_exchange_position:
            logger.info(f"No DB trades but {len(exchange_positions)} exchange positions exist - opposite signal closure checked above")
        else:
            logger.info(f"Have {len(active_trades)} active trades - opposite signal closure checked above")
    
    def _check_active_trades(self, active_trades, current_price, market_indicators=None):
        """Check if any active trades need to be closed"""
        if not active_trades:
            return
        
        logger.info(f"Checking {len(active_trades)} active trades for exit conditions")
        
        # Check for major trend reversal that requires selective position closing
        major_reversal = self._check_major_trend_reversal(active_trades, market_indicators)
        if major_reversal:
            logger.warning(f"Major trend reversal detected: {major_reversal}")

            # RSI過売り（強気転換）の場合：SELLポジションのみ決済、BUYポジションは保持
            if "emergency close all SELL positions" in major_reversal:
                logger.warning("RSI oversold condition - closing only SELL positions, keeping BUY positions!")
                for trade in active_trades:
                    if trade.trade_type.lower() == 'sell':  # SELLポジションのみ決済
                        logger.info(f"Closing SELL position: Trade {trade.id}")
                        self._close_trade(trade, current_price, f"Emergency close: {major_reversal}")
                    else:
                        logger.info(f"Keeping BUY position: Trade {trade.id} (favorable market condition)")
            else:
                # その他の緊急事態では全ポジション決済
                logger.warning("General emergency condition - closing all positions!")
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
                
                if self.db_session and self.app:
                    with self.app.app_context():
                        self.db_session.commit()
                
                logger.info(f"Trade {trade.id} closed successfully with P/L: {pl['amount']} ({pl['percentage']:.2f}%)")
            else:
                logger.error(f"Failed to close trade {trade.id}: {result}")
                
        except Exception as e:
            if self.db_session and self.app:
                try:
                    with self.app.app_context():
                        self.db_session.rollback()
                except:
                    pass
            logger.error(f"Error closing trade {trade.id}: {e}")
    
    def _check_for_new_trade(self, df, symbol, current_price):
        """Check if we should open a new trade"""
        logger.info(f"Checking for new trade opportunities for {symbol} at price {current_price}")
        
        # Get trading signal from SimpleTradingLogic (same as dashboard)
        last_row = df.iloc[-1].to_dict()
        should_trade, trade_type, reason, confidence = self.trading_logic.should_trade(last_row)

        logger.info(f"Trading signal: should_trade={should_trade}, type={trade_type}, reason='{reason}', confidence={confidence:.4f}")
        
        # Evaluate market conditions
        last_row = df.iloc[-1].to_dict()
        market_eval = self.risk_manager.evaluate_market_conditions(last_row)
        
        logger.info(f"Market evaluation: trend={market_eval['market_trend']}, risk_score={market_eval['risk_score']}")
        
        # Check available balances to determine possible trade types
        balance_response = self.api.get_account_balance()
        available_jpy = 0
        available_doge = 0

        if 'data' in balance_response:
            for asset in balance_response['data']:
                if asset['symbol'] == 'JPY':
                    available_jpy = float(asset['available'])
                elif asset['symbol'] == 'DOGE':
                    available_doge = float(asset['available'])

        logger.info(f"Available balances - JPY: {available_jpy}, DOGE: {available_doge}")

        # Use SimpleTradingLogic result and check balance constraints
        final_should_trade = False
        final_trade_type = None
        final_trade_reason = ""

        if should_trade and trade_type:
            if trade_type.upper() == 'BUY':
                if available_jpy > 100:  # Minimum JPY required for trade
                    if market_eval['market_trend'] != 'bearish' or market_eval['trend_strength'] < 0.7:
                        final_should_trade = True
                        final_trade_type = 'buy'
                        final_trade_reason = f"{reason} - Buying DOGE with JPY (confidence: {confidence:.2f})"
                else:
                    logger.info(f"Buy signal detected but insufficient JPY balance ({available_jpy})")
            elif trade_type.upper() == 'SELL':
                if available_doge >= 10:  # Minimum DOGE required for SELL order
                    if market_eval['market_trend'] != 'bullish' or market_eval['trend_strength'] < 0.7:
                        final_should_trade = True
                        final_trade_type = 'sell'
                        final_trade_reason = f"{reason} - Selling DOGE for JPY (confidence: {confidence:.2f})"
                else:
                    logger.info(f"Sell signal detected but insufficient DOGE balance ({available_doge})")
        elif market_eval['trend_strength'] > 0.5:  # 閾値を下げて取引機会を増加
            # Strong trend without clear SimpleTradingLogic signal
            if market_eval['market_trend'] == 'bullish' and available_jpy > 100:
                final_should_trade = True
                final_trade_type = 'buy'
                final_trade_reason = f"Strong bullish trend detected. Strength: {market_eval['trend_strength']:.2f} - Buying DOGE"
            elif market_eval['market_trend'] == 'bearish' and available_doge >= 10:
                final_should_trade = True
                final_trade_type = 'sell'
                final_trade_reason = f"Strong bearish trend detected. Strength: {market_eval['trend_strength']:.2f} - Selling DOGE"

        # 【重要】逆シグナル検出による一括決済チェック
        self._check_opposite_signal_closure(symbol, current_price, should_trade, trade_type, reason)

        if final_should_trade and final_trade_type:
            logger.info(f"Decision to trade: {final_trade_type} because {final_trade_reason}")
            self._execute_trade(symbol, final_trade_type, current_price, last_row)
        else:
            logger.info("No trade opportunity at this time")

    def _execute_trade(self, symbol, trade_type, current_price, indicators_data):
        """Execute a new trade"""
        logger.info(f"Executing {trade_type} trade for {symbol} at {current_price}")
        
        try:
            # Get available balance
            balance_response = self.api.get_account_balance()

            available_jpy = 0
            available_doge = 0
            if 'data' in balance_response:
                for asset in balance_response['data']:
                    if asset['symbol'] == 'JPY':
                        available_jpy = float(asset['available'])
                    elif asset['symbol'] == 'DOGE':
                        available_doge = float(asset['available'])

                logger.info(f"Available balance for trading - JPY: {available_jpy}, DOGE: {available_doge}")

            # Calculate optimal position size using enhanced risk management
            confidence = indicators_data.get('signal_confidence', 0.8)  # Default confidence
            position_size = self.risk_manager.calculate_position_size(
                available_balance=available_jpy,
                current_price=current_price,
                symbol=symbol,
                market_indicators=indicators_data,
                confidence=confidence
            )

            if trade_type.lower() == 'buy':
                if available_jpy <= 100:
                    logger.error("Insufficient JPY balance for BUY trade")
                    return
                logger.info(f"Enhanced BUY order: {position_size:.2f} DOGE (optimized for market conditions)")
            else:  # SELL trade
                if available_jpy <= 100:  # For leverage SELL, need JPY as margin
                    logger.error("Insufficient JPY balance for leverage SELL trade")
                    return
                logger.info(f"Enhanced SELL order: {position_size:.2f} DOGE (optimized for market conditions)")

            logger.info(f"Calculated position size for {symbol}: {position_size}")

            # Format size according to currency pair requirements
            if 'DOGE_' in symbol:
                position_size_rounded = max(10, int(position_size))  # 最低10DOGE、ただし計算値を優先
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

                # Initialize trailing stop price attribute if enabled
                if self.risk_manager.trailing_stop_enabled:
                    new_trade.trailing_stop_price = None
                
                if self.db_session and self.app:
                    with self.app.app_context():
                        self.db_session.add(new_trade)
                        self.db_session.commit()
                
                logger.info(f"New {trade_type} trade executed: {position_size_rounded} {symbol} at {current_price}")
            else:
                logger.error(f"Failed to execute {trade_type} trade. API response: {result}")
                
        except Exception as e:
            logger.error(f"Error executing {trade_type} trade: {e}")
            if self.db_session and self.app:
                try:
                    with self.app.app_context():
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
                
                # Extremely strong bullish signals for emergency close of SELL positions
                if rsi < 20:  # Extreme oversold - 強気転換でSELLポジションを決済
                    return "Extreme RSI oversold (<20) - emergency close all SELL positions (keep BUY positions)"
                
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
            positions = self.api.get_positions(symbol=symbol)
            logger.info(f"Retrieved {len(positions)} positions from exchange for {symbol}")
            return positions
        except Exception as e:
            logger.error(f"Error getting exchange positions: {e}")
            return []
    
    def _sync_exchange_positions(self, exchange_positions, symbol):
        """Bi-directional sync between exchange positions and database"""
        if not self.db_session:
            return
            
        try:
            from models import Trade
            from datetime import datetime
            
            # Get current exchange position IDs
            exchange_position_ids = set()
            for position in exchange_positions:
                position_id = position.get('positionId')
                exchange_position_ids.add(position_id)
                
                side = position.get('side', '').lower()  # 'BUY' or 'SELL'
                size = float(position.get('size', 0))
                price = float(position.get('price', 0))
                
                # Check if this position already exists in database
                if self.app:
                    with self.app.app_context():
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

            # CRITICAL FIX: Remove orphaned positions from database
            # Get all database trades for this user and symbol
            if self.app:
                with self.app.app_context():
                    db_trades = self.db_session.query(Trade).filter_by(
                        user_id=self.user.id,
                        currency_pair=symbol,
                        status='open'
                    ).all()

                    orphaned_count = 0
                    for trade in db_trades:
                        if trade.exchange_position_id and trade.exchange_position_id not in exchange_position_ids:
                            # This trade exists in DB but not on exchange - mark as closed
                            logger.info(f"Removing orphaned position: Trade {trade.id} (Position ID: {trade.exchange_position_id})")
                            trade.status = 'closed'
                            trade.closing_price = trade.price  # Use entry price as close approximation
                            trade.closed_at = datetime.utcnow()
                            orphaned_count += 1

                    if orphaned_count > 0:
                        logger.info(f"Cleaned up {orphaned_count} orphaned positions from database")

                    self.db_session.commit()
                    logger.info("Bi-directional exchange-database sync completed")
            
        except Exception as e:
            logger.error(f"Error syncing exchange positions: {e}")
            if self.db_session and self.app:
                try:
                    with self.app.app_context():
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
            if current_price > bb_upper * 0.98:  # Price near upper BB (overbought reversal)
                bearish_signals += 1

            if bearish_signals >= 2:
                return True, f"Strong bearish reversal detected ({bearish_signals}/4 signals)"
                
        else:  # sell position
            # Check for strong buy signals to close sell position
            bullish_signals = 0

            if rsi < 35:  # Oversold
                bullish_signals += 1
            if macd_line > macd_signal and abs(macd_line - macd_signal) > 0.05:  # MACD bullish
                bullish_signals += 1
            if ema_12 > ema_26 and (ema_12 - ema_26) / ema_26 > 0.005:  # Golden cross
                bullish_signals += 1
            if current_price < bb_lower * 1.02:  # Price near lower BB (oversold bounce)
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
                if self.db_session and self.app:
                    try:
                        from models import Trade
                        with self.app.app_context():
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

    def _check_existing_positions_for_closure_only(self, positions, current_price, market_indicators):
        """既存ポジション決済のみを実行（新規注文は一切行わない）"""
        logger.info(f"🔍 Checking {len(positions)} existing positions for closure only")

        for position in positions:
            side = position.get('side')
            size = position.get('size')
            entry_price = float(position.get('price', 0))
            position_id = position.get('positionId')

            # Calculate P/L
            if side == 'BUY':
                pl_ratio = (current_price - entry_price) / entry_price
            else:
                pl_ratio = (entry_price - current_price) / entry_price

            logger.info(f"📊 Position {position_id} ({side}): Entry={entry_price}, Current={current_price}, P/L={pl_ratio:.4f}")

            # Check closure conditions
            should_close, reason = self._should_close_position_strict(position, current_price, market_indicators)

            if should_close:
                logger.info(f"🔄 Closing position {position_id}: {reason}")
                success = self._close_exchange_position_sync(position, current_price, reason)
                if success:
                    logger.info(f"✅ Position {position_id} closed successfully")
                else:
                    logger.error(f"❌ Failed to close position {position_id}")
            else:
                logger.info(f"📌 Position {position_id} remains open: {reason}")

    def _should_close_position_strict(self, position, current_price, market_indicators):
        """厳格なポジション決済判定（利確・損切り・反転シグナル）"""
        side = position.get('side')
        entry_price = float(position.get('price', 0))

        # Calculate profit/loss ratio
        if side == 'BUY':
            pl_ratio = (current_price - entry_price) / entry_price
        else:
            pl_ratio = (entry_price - current_price) / entry_price

        # Stop loss check (3% loss)
        if pl_ratio <= -0.03:
            return True, f"Stop loss triggered: {pl_ratio:.4f}"

        # Take profit check (5% profit)
        if pl_ratio >= 0.05:
            return True, f"Take profit triggered: {pl_ratio:.4f}"

        # Market reversal check
        if market_indicators:
            rsi = market_indicators.get('rsi_14', 50)
            macd_line = market_indicators.get('macd_line', 0)
            macd_signal = market_indicators.get('macd_signal', 0)

            reversal_signals = 0

            if side == 'BUY':
                # Strong bearish signals to close BUY position
                if rsi > 75:  # Extremely overbought
                    reversal_signals += 1
                if macd_line < macd_signal and abs(macd_line - macd_signal) > 0.5:
                    reversal_signals += 1

                if reversal_signals >= 2:
                    return True, f"Strong bearish reversal detected ({reversal_signals}/2 signals)"

            else:  # SELL position
                # Strong bullish signals to close SELL position
                if rsi < 25:  # Extremely oversold
                    reversal_signals += 1
                if macd_line > macd_signal and abs(macd_line - macd_signal) > 0.5:
                    reversal_signals += 1

                if reversal_signals >= 2:
                    return True, f"Strong bullish reversal detected ({reversal_signals}/2 signals)"

        return False, "No closure condition met"

    def _close_exchange_position_sync(self, position, current_price, reason):
        """個別ポジション決済（同期処理・成功確認付き）"""
        try:
            symbol = position.get('symbol')
            side = position.get('side')  # The current position side
            size = position.get('size')
            position_id = position.get('positionId')

            logger.info(f"🔄 Closing position {position_id}: {size} {symbol} {side} at {current_price}")

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
                logger.info(f"✅ Position {position_id} API call successful: {result}")

                # Update database if trade exists
                if self.db_session and self.app:
                    try:
                        from models import Trade
                        with self.app.app_context():
                            db_trade = self.db_session.query(Trade).filter_by(
                                exchange_position_id=position_id
                            ).first()
                            if db_trade:
                                db_trade.status = 'closed'
                                db_trade.closing_price = current_price
                                db_trade.closed_at = datetime.utcnow()
                                self.db_session.commit()
                                logger.info(f"📊 Database updated for position {position_id}")
                    except Exception as db_e:
                        logger.error(f"Database update error: {db_e}")

                return True
            else:
                logger.error(f"❌ Failed to close position {position_id}: {result}")
                return False

        except Exception as e:
            logger.error(f"Error in sync close position: {e}")
            return False

    def _check_for_new_trade(self, df, symbol, current_price):
        """Check for new trading opportunities and execute opposite signal closure"""
        try:
            # Get market data from Simple Trading Logic
            if df is None or df.empty:
                logger.warning("No market data available for trading decision")
                return

            # Convert DataFrame to dictionary for the last row (latest data)
            latest_data = df.iloc[-1].to_dict()

            # Use Simple Trading Logic for signal generation
            should_trade, trade_type, reason, confidence = self.trading_logic.should_trade(latest_data)

            logger.info(f"Signal Analysis - Should trade: {should_trade}, Type: {trade_type}, Reason: {reason}, Confidence: {confidence:.2f}")

            # CRITICAL: Check for opposite signal closure FIRST (同期処理)
            logger.info(f"🔍 Calling _check_opposite_signal_closure with: symbol={symbol}, should_trade={should_trade}, trade_type={trade_type}")
            opposite_closure_completed = self._check_opposite_signal_closure(symbol, current_price, should_trade, trade_type, reason)

            # 【重要】新規注文前のポジション完全確認
            if should_trade and confidence >= 0.8:
                logger.info(f"🎯 Strong signal detected for {trade_type} (confidence: {confidence:.2f})")

                # 決済処理が実行された場合、追加の待機時間
                if opposite_closure_completed:
                    logger.info("⏳ Opposite positions were closed, waiting for settlement confirmation...")
                    import time
                    time.sleep(3)  # 決済処理完全完了待機

                # 【最重要】新規注文前の最終ポジション確認
                logger.info("🔍 Final position verification before new trade...")
                final_positions = self.api.get_positions(symbol=symbol)

                if final_positions:
                    logger.info(f"📊 Current positions count: {len(final_positions)}")

                    # 反対ポジションまたは同方向ポジションの存在確認
                    conflicting_positions = []
                    same_direction_positions = []

                    for pos in final_positions:
                        pos_side = pos.get('side')
                        pos_id = pos.get('positionId')

                        if pos_side == trade_type.upper():
                            same_direction_positions.append(pos_id)
                        else:
                            conflicting_positions.append(pos_id)

                    # 反対ポジションが残っている場合は新規注文中止
                    if conflicting_positions:
                        logger.warning(f"❌ Conflicting positions detected: {conflicting_positions}")
                        logger.warning(f"Cannot place {trade_type} order while opposite positions exist")
                        return

                    # 同方向ポジションが既にある場合も新規注文中止（重複防止）
                    if same_direction_positions:
                        logger.info(f"⚠️ Same direction positions already exist: {same_direction_positions}")
                        logger.info(f"Skipping new {trade_type} order to avoid position duplication")
                        return

                    logger.info("✅ No conflicting positions found - proceeding with new trade")

                else:
                    logger.info("📭 No positions found - safe to place new trade")

                # 取引タイミング確認
                if not self.trading_logic.check_trade_timing():
                    logger.info("⏰ Trade timing restriction active - skipping new trade")
                    return

                # 【最終段階】新規注文実行
                logger.info(f"🚀 Executing new {trade_type} trade...")
                if self._place_new_trade(symbol, trade_type, current_price, reason, confidence):
                    self.trading_logic.record_trade()
                    logger.info(f"✅ New {trade_type} trade placed successfully")
                else:
                    logger.error(f"❌ Failed to place new {trade_type} trade")
            else:
                logger.info(f"📊 Signal strength insufficient for new trade - Confidence: {confidence:.2f}, Required: 0.8")

        except Exception as e:
            logger.error(f"Error checking for new trade: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _place_new_trade(self, symbol, trade_type, current_price, reason, confidence):
        """Place a new trade with enhanced verification and logging"""
        try:
            logger.info(f"🎯 === STARTING NEW TRADE PLACEMENT ===")
            logger.info(f"📋 Trade Details: {trade_type.upper()} {symbol} at {current_price}")
            logger.info(f"📊 Signal: {reason} (Confidence: {confidence:.2f})")

            # Get available balance for trade sizing
            balance_info = self.api.get_account_balance()

            if 'data' not in balance_info:
                logger.error(f"❌ Failed to get account balance: {balance_info}")
                return False

            available_jpy = 0
            available_doge = 0

            for asset in balance_info['data']:
                if asset['symbol'] == 'JPY':
                    available_jpy = float(asset['available'])
                elif asset['symbol'] == 'DOGE':
                    available_doge = float(asset['available'])

            logger.info(f"💰 Available balances - JPY: {available_jpy}, DOGE: {available_doge}")

            # Calculate trade size based on 95% of available balance
            if trade_type.upper() == 'BUY':
                # For BUY orders, use 95% of JPY balance
                max_jpy = available_jpy * 0.95
                max_doge_quantity = int(max_jpy / current_price)
                # Round DOWN to nearest 10 DOGE (GMO requirement)
                rounded_doge = (max_doge_quantity // 10) * 10
                trade_size = max(10, rounded_doge)
                logger.info(f"🔢 BUY order calculation: max_jpy={max_jpy:.2f}, price={current_price}, max_doge_quantity={max_doge_quantity}, rounded_doge={rounded_doge}, trade_size={trade_size}")

                if max_jpy < 100:  # Need at least 100 JPY
                    logger.warning(f"❌ Insufficient JPY balance for BUY order: {available_jpy}")
                    return False

            else:  # SELL (レバレッジショートポジション)
                # For leverage SELL orders, use JPY balance as margin
                max_jpy = available_jpy * 0.95
                max_doge_quantity = int(max_jpy / current_price)
                # Round DOWN to nearest 10 DOGE (GMO requirement)
                rounded_doge = (max_doge_quantity // 10) * 10
                trade_size = max(10, rounded_doge)
                logger.info(f"🔢 SELL order calculation (leverage): max_jpy={max_jpy:.2f}, price={current_price}, max_doge_quantity={max_doge_quantity}, rounded_doge={rounded_doge}, trade_size={trade_size}")

                if max_jpy < 100:  # Need at least 100 JPY as margin
                    logger.warning(f"❌ Insufficient JPY balance for leverage SELL order: {available_jpy}")
                    return False

            # 【最重要】注文実行前の3段階ポジション確認
            logger.info("🔍 TRIPLE POSITION CHECK before order execution...")

            for check_round in range(3):
                logger.info(f"🔍 Position check round {check_round + 1}/3...")
                pre_positions = self.api.get_positions(symbol=symbol)

                if pre_positions:
                    logger.error(f"❌ ABORT ROUND {check_round + 1}: {len(pre_positions)} positions detected!")
                    for pos in pre_positions:
                        logger.error(f"   Position: {pos.get('side')} {pos.get('size')} @ {pos.get('price')} (ID: {pos.get('positionId')})")
                    return False

                # Wait between checks
                if check_round < 2:
                    import time
                    time.sleep(1)

            logger.info("✅ TRIPLE CHECK PASSED: No positions detected in any round - safe to proceed")

            logger.info(f"🚀 EXECUTING {trade_type.upper()} ORDER: {trade_size} DOGE at {current_price} JPY")

            # Place the order
            result = self.api.place_order(
                symbol=symbol,
                side=trade_type.upper(),
                execution_type="MARKET",
                size=str(trade_size)
            )

            if 'data' in result:
                logger.info(f"✅ {trade_type.upper()} ORDER SUCCESSFUL!")
                logger.info(f"📋 Order details: {result['data']}")

                # 注文後のポジション確認
                import time
                time.sleep(2)  # 注文反映待機
                new_positions = self.api.get_positions(symbol=symbol)

                if new_positions:
                    logger.info(f"✅ Post-order verification: {len(new_positions)} positions now exist")
                    for pos in new_positions:
                        logger.info(f"   New Position: {pos.get('side')} {pos.get('size')} @ {pos.get('price')} (ID: {pos.get('positionId')})")

                logger.info(f"🎯 === NEW TRADE PLACEMENT COMPLETED ===")
                return True
            else:
                logger.error(f"❌ Failed to place {trade_type} order: {result}")
                logger.info(f"🚫 === NEW TRADE PLACEMENT FAILED ===")
                return False

        except Exception as e:
            logger.error(f"❌ Error placing new trade: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.info(f"🚫 === NEW TRADE PLACEMENT ERROR ===")
            return False

    def _check_opposite_signal_closure(self, symbol, current_price, should_trade, trade_type, reason):
        """
        SimpleTradingLogicからの逆シグナル検出による一括決済（同期処理）
        BUYシグナル出現時 → 全SELLポジション決済
        SELLシグナル出現時 → 全BUYポジション決済
        """
        logger.info(f"🔄 _check_opposite_signal_closure called: should_trade={should_trade}, trade_type={trade_type}, reason={reason}")

        if not should_trade or not trade_type:
            logger.info(f"🚫 Early return: should_trade={should_trade}, trade_type={trade_type}")
            return False  # 決済なしを返す

        try:
            # 取引所のポジション一覧を取得 (get_positionsはリストを返す)
            positions = self.api.get_positions(symbol=symbol)
            logger.info(f"📋 Initial positions check - positions count: {len(positions)}")

            if not positions:
                logger.info("📭 No positions found on exchange")
                return False

            # GMO API returns positions as a list
            positions_to_close = []
            all_positions = positions
            initial_position_count = len(all_positions)

            # 逆シグナル検出ロジック
            if trade_type.upper() == 'BUY':
                # BUYシグナル → SELLポジションを全て決済
                for position in all_positions:
                    if position.get('symbol') == symbol and position.get('side') == 'SELL':
                        positions_to_close.append(position)
                        logger.info(f"📌 Found SELL position to close: {position.get('positionId')}")

                if positions_to_close:
                    logger.info(f"🔄 BUYシグナル検出！SELLポジション {len(positions_to_close)}件を同期決済開始")
                    logger.info(f"決済理由: {reason}")

            elif trade_type.upper() == 'SELL':
                # SELLシグナル → BUYポジションを全て決済
                for position in all_positions:
                    if position.get('symbol') == symbol and position.get('side') == 'BUY':
                        positions_to_close.append(position)
                        logger.info(f"📌 Found BUY position to close: {position.get('positionId')}")

                if positions_to_close:
                    logger.info(f"🔄 SELLシグナル検出！BUYポジション {len(positions_to_close)}件を同期決済開始")
                    logger.info(f"決済理由: {reason}")

            # 決済がない場合は早期リターン
            if not positions_to_close:
                logger.info("📭 No opposite positions to close")
                return False

            # 【重要】同期決済実行と完了確認
            closed_positions = 0
            for position in positions_to_close:
                position_id = position.get('positionId')
                logger.info(f"💥 Closing position: {position_id}")

                success = self._close_exchange_position_sync(position, current_price, f"逆シグナル決済: {reason}")
                if success:
                    closed_positions += 1
                    logger.info(f"✅ Position {position_id} successfully closed ({closed_positions}/{len(positions_to_close)})")
                else:
                    logger.error(f"❌ Failed to close position {position_id}")

            # 決済完了確認（最大3回リトライ）
            import time
            for attempt in range(3):
                logger.info(f"🔍 Verifying closure completion (attempt {attempt + 1}/3)...")
                time.sleep(2)  # API処理完了待機

                remaining_positions = self.api.get_positions(symbol=symbol)
                if remaining_positions:
                    # 決済対象の反対ポジションが残っているかチェック
                    remaining_opposite = []
                    for pos in remaining_positions:
                        if trade_type.upper() == 'BUY' and pos.get('side') == 'SELL':
                            remaining_opposite.append(pos.get('positionId'))
                        elif trade_type.upper() == 'SELL' and pos.get('side') == 'BUY':
                            remaining_opposite.append(pos.get('positionId'))

                    if not remaining_opposite:
                        logger.info(f"✅ All opposite positions successfully closed! Remaining total positions: {len(remaining_positions)}")
                        return True  # 決済完了
                    else:
                        logger.warning(f"⚠️ {len(remaining_opposite)} opposite positions still remain: {remaining_opposite}")
                else:
                    logger.info("📭 No positions remaining")
                    return True

            logger.error(f"❌ Failed to complete opposite signal closure after 3 attempts")
            return False

        except Exception as e:
            logger.error(f"逆シグナル決済チェック中にエラーが発生: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False