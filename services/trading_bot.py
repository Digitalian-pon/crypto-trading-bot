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
from models import Trade, TradingSettings

# ロギング設定を強化
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # トレーディングボットのログを詳細に出力

class TradingBot:
    """
    Automated cryptocurrency trading bot
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
        """
        Set the database session
        
        :param session: SQLAlchemy session
        """
        self.db_session = session
    
    def update_user(self, user):
        """
        Update the user and their settings
        
        :param user: User object with trading settings
        """
        self.user = user
        if user and user.settings:
            self.risk_manager.update_settings(user.settings)
    
    def get_settings(self):
        """
        Get the current trading settings
        
        :return: TradingSettings object
        """
        if self.user and self.user.settings:
            return self.user.settings
        return None
    
    def start(self, interval=None):
        """
        Start the trading bot in a separate thread
        
        :param interval: Check interval in seconds
        """
        if self.running:
            logger.warning("Trading bot is already running")
            return False
        
        if interval:
            self.interval = interval
        
        # ユーザー情報の検証
        if not self.user:
            logger.error("Cannot start trading bot: User not provided")
            return False
            
        # API認証情報の検証
        if not hasattr(self.user, 'api_key') or not hasattr(self.user, 'api_secret') or not self.user.api_key or not self.user.api_secret:
            logger.error("Cannot start trading bot: API credentials not set")
            return False
        
        # 設定の検証
        if not hasattr(self.user, 'settings') or not self.user.settings:
            logger.error("Cannot start trading bot: Trading settings not found")
            return False
            
        if not hasattr(self.user.settings, 'trading_enabled') or not self.user.settings.trading_enabled:
            logger.error("Cannot start trading bot: Trading is not enabled in settings")
            return False
        
        # ユーザー情報のログ（機密情報は含めない）
        username = getattr(self.user, 'username', 'unknown')
        currency_pair = getattr(self.user.settings, 'currency_pair', 'unknown') if self.user.settings else 'unknown'
        
        logger.info(f"Starting trading bot for user: {username}, currency: {currency_pair}")
        
        # Update API credentials
        self.api = GMOCoinAPI(self.user.api_key, self.user.api_secret)
        self.data_service = DataService(self.user.api_key, self.user.api_secret)
        
        # Update risk manager with user settings
        self.risk_manager.update_settings(self.user.settings)
        
        # Start the trading thread
        self.running = True
        self.thread = threading.Thread(target=self._trading_loop)
        self.thread.daemon = True
        self.thread.start()
        
        logger.info(f"Trading bot started for user {username}")
        return True
    
    def stop(self):
        """
        Stop the trading bot
        """
        if not self.running:
            logger.warning("Trading bot is not running")
            return False
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
            self.thread = None
        
        # ユーザー名の安全な取得
        username = getattr(self.user, 'username', 'unknown') if self.user else 'unknown'
        logger.info(f"Trading bot stopped for user {username}")
        return True
    
    def _trading_loop(self):
        """
        Main trading loop that runs in a separate thread
        """
        logger.info("Trading loop started")
        
        # 最適化スケジュール設定（1日1回）
        last_optimization_time = None
        optimization_interval = 24 * 60 * 60  # 24時間（秒単位）
        
        while self.running:
            # Ensure we're operating within Flask app context
            if self.app:
                with self.app.app_context():
                    self._execute_trading_cycle()
            else:
                self._execute_trading_cycle()
    
    def _execute_trading_cycle(self):
        """Execute one trading cycle"""
        try:
            # Check if user or settings are available
            if not self.user:
                logger.error("User is not available, stopping bot")
                self.running = False
                return
                
            if not hasattr(self.user, 'settings') or not self.user.settings:
                logger.error("User settings are not available, stopping bot")
                self.running = False
                return
            
            # Check if trading is still enabled
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
                    time.sleep(self.interval)
                    continue
                
                logger.info(f"Successfully retrieved {len(df)} market data points")
                
                # 定期的なモデル最適化処理
                now = time.time()
                if last_optimization_time is None or (now - last_optimization_time) >= optimization_interval:
                    logger.info("Scheduled model parameter optimization...")
                    optimized_params = self.model.optimize_parameters(df)
                    if optimized_params:
                        logger.info(f"Model parameters optimized successfully: {optimized_params['model_params']}")
                        logger.info(f"Top features: {optimized_params['top_features']}")
                        # 最適化時刻を更新
                        last_optimization_time = now
                    else:
                        logger.warning("Model parameter optimization failed or was skipped")
                
                # Get the current active trades for this user and symbol
                active_trades = None
                if self.db_session:
                    try:
                        # セッションの状態をリフレッシュし、新しいクエリを準備
                        self.db_session.commit()  # 以前のトランザクションがあれば完了させる
                        
                        user_id = self.user.id
                        active_trades = self.db_session.query(Trade).filter_by(
                            user_id=user_id,
                            currency_pair=symbol,
                            status='open'
                        ).all()
                        
                        logger.info(f"Found {len(active_trades) if active_trades else 0} active trades")
                    except Exception as db_e:
                        logger.error(f"Database error while querying active trades: {db_e}")
                        # セッションがエラー状態になっている可能性があるのでロールバック
                        self.db_session.rollback()
                else:
                    logger.error("Database session is not available")
                
                # Check if we have any active trades that need to be closed
                current_price = df['close'].iloc[-1]
                logger.info(f"Current {symbol} price: {current_price}")
                self._check_active_trades(active_trades, current_price)
                
                # If there are no active trades, check if we should open a new one
                if not active_trades or len(active_trades) == 0:
                    logger.info("No active trades found, checking for new trade opportunities")
                    self._check_for_new_trade(df, symbol, current_price)
                
                # Sleep until next check
                logger.info(f"Sleeping for {self.interval} seconds until next check")
                time.sleep(self.interval)
                
            except Exception as e:
                import traceback
                logger.error(f"Error in trading loop: {e}")
                logger.error(f"Error traceback: {traceback.format_exc()}")
                logger.info(f"Will retry after {self.interval} seconds")
                time.sleep(self.interval)
    
    def _check_active_trades(self, active_trades, current_price):
        """
        Check if any active trades need to be closed
        
        :param active_trades: List of active Trade objects
        :param current_price: Current price of the trading pair
        """
        if not active_trades:
            return
        
        for trade in active_trades:
            should_close, reason = self.risk_manager.should_close_trade(trade, current_price)
            
            if should_close:
                self._close_trade(trade, current_price, reason)
    
    def _close_trade(self, trade, current_price, reason):
        """
        Close a trade and record the result
        
        :param trade: Trade object to close
        :param current_price: Current price of the trading pair
        :param reason: Reason for closing the trade
        """
        logger.info(f"Closing trade {trade.id} at price {current_price}, reason: {reason}")
        
        try:
            # Calculate profit/loss
            pl = self.risk_manager.calculate_profit_loss(trade, current_price)
            
            # Execute the close order on the exchange
            close_side = "SELL" if trade.trade_type.upper() == "BUY" else "BUY"
            
            # GMO Coinの小数点桁数制限に対応するためにフォーマット調整
            # 通貨ペアに応じたフォーマット処理
            if 'DOGE_' in trade.currency_pair:
                # DOGEは小数点以下0桁、かつ最小値は10
                size = max(10, int(trade.amount))
                size_str = f"{size}"
            elif 'XRP_' in trade.currency_pair:
                # XRPは小数点以下0桁、かつ最小値は10
                size = max(10, int(trade.amount))
                size_str = f"{size}"
            elif 'BTC_' in trade.currency_pair:
                # BTCは小数点以下8桁、最小値0.0001
                size = max(0.0001, round(trade.amount, 8))
                size_str = f"{size:.8f}"
            elif 'ETH_' in trade.currency_pair:
                # ETHは小数点以下8桁、最小値0.001
                size = max(0.001, round(trade.amount, 8))
                size_str = f"{size:.8f}"
            else:
                # その他の通貨は小数点以下4桁で処理、最小値1
                size = max(1, round(trade.amount, 4))
                size_str = f"{size:.4f}"
            
            logger.info(f"注文数量を調整: {trade.currency_pair}, {trade.amount} → {size_str}")
            
            result = self.api.place_order(
                symbol=trade.currency_pair,
                side=close_side,
                execution_type="MARKET",
                size=size_str  # 文字列として渡して小数点桁数を明示的に制御
            )
            
            # API エラーの場合はログに記録
            if 'error' in result:
                TradeLogger.log_api_error(
                    f"取引クローズエラー: {result.get('error', '不明なエラー')}", 
                    endpoint="place_order", 
                    params={"symbol": trade.currency_pair, "side": close_side, "size": trade.amount}
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
                
                # トレードクローズログを記録
                TradeLogger.log_trade_close(
                    trade=trade, 
                    closing_price=current_price, 
                    profit_loss=pl['amount'], 
                    reason=reason
                )
            else:
                logger.error(f"Failed to close trade {trade.id}: {result}")
        except Exception as e:
            if self.db_session:
                self.db_session.rollback()
            logger.error(f"Error closing trade {trade.id}: {e}")
            
            # エラー情報をログに記録
            TradeLogger.log_api_error(
                f"取引クローズエラー(例外): {str(e)}", 
                endpoint="close_trade", 
                params={"trade_id": trade.id, "price": current_price}
            )
    
    def _check_for_new_trade(self, df, symbol, current_price):
        """
        Check if we should open a new trade
        
        :param df: DataFrame with market data and indicators
        :param symbol: Trading pair symbol
        :param current_price: Current price of the trading pair
        """
        logger.info(f"Checking for new trade opportunities for {symbol} at price {current_price}")
        
        # Get prediction from the ML model
        prediction = self.model.predict(df)
        
        if not prediction:
            logger.warning("Could not get prediction from model, using fallback prediction")
            # 技術指標からフォールバック予測を作成
            last_row = df.iloc[-1].to_dict()
            
            # RSIに基づく判断（70超：売り、30未満：買い）
            rsi = last_row.get('rsi_14', 50)
            
            # MACDに基づく判断
            macd_line = last_row.get('macd_line', 0)
            macd_signal = last_row.get('macd_signal', 0)
            macd_crossover = macd_line > macd_signal
            
            # ボリンジャーバンドに基づく判断
            price = last_row.get('close', 0)
            bb_lower = last_row.get('bb_lower', price * 0.97)
            bb_upper = last_row.get('bb_upper', price * 1.03)
            
            # 買いシグナル: RSIが30未満 or MACDがシグナルラインを上抜け or 価格がボリンジャー下限に近い
            buy_signal = (rsi < 30) or macd_crossover or (price < bb_lower * 1.01)
            
            # 売りシグナル: RSIが70超 or MACDがシグナルラインを下抜け or 価格がボリンジャー上限に近い
            sell_signal = (rsi > 70) or (not macd_crossover) or (price > bb_upper * 0.99)
            
            # 最終判断（買いシグナルと売りシグナルの強度を比較）
            pred_value = 1 if buy_signal and not sell_signal else 0
            prob_value = 0.75 if (buy_signal and not sell_signal) or (sell_signal and not buy_signal) else 0.60
            
            prediction = {
                'prediction': pred_value,
                'probability': prob_value,
                'features': last_row
            }
            
            logger.info(f"Using fallback prediction based on technical indicators")
                
        logger.info(f"Model prediction: {prediction['prediction']}, probability: {prediction['probability']:.4f}")
        
        # Evaluate market conditions
        last_row = df.iloc[-1].to_dict()
        market_eval = self.risk_manager.evaluate_market_conditions(last_row)
        
        logger.info(f"Market evaluation: trend={market_eval['market_trend']}, risk_score={market_eval['risk_score']}")
        
        # Determine if we should trade based on prediction and market conditions
        should_trade = False
        trade_type = None
        trade_reason = ""
        
        # トレード条件を大幅に緩和（確率閾値を0.55に下げる）
        if prediction['prediction'] == 1 and prediction['probability'] > 0.55:
            # Model predicts price will go up
            logger.info("Model indicates BULLISH signal")
            if market_eval['market_trend'] != 'bearish' or market_eval['trend_strength'] < 0.7:
                should_trade = True
                trade_type = 'buy'
                trade_reason = f"Bullish signal with {prediction['probability']:.2f} probability, market trend: {market_eval['market_trend']}"
            else:
                logger.info(f"Not trading despite bullish signal because: market_trend={market_eval['market_trend']}, trend_strength={market_eval['trend_strength']:.2f}")
        elif prediction['prediction'] == 0 and prediction['probability'] > 0.55:
            # Model predicts price will go down
            logger.info("Model indicates BEARISH signal")
            if market_eval['market_trend'] != 'bullish' or market_eval['trend_strength'] < 0.7:
                should_trade = True
                trade_type = 'sell'
                trade_reason = f"Bearish signal with {prediction['probability']:.2f} probability, market trend: {market_eval['market_trend']}"
            else:
                logger.info(f"Not trading despite bearish signal because: market_trend={market_eval['market_trend']}, trend_strength={market_eval['trend_strength']:.2f}")
        else:
            # 予測が明確でない場合、テクニカル指標のみに基づいて判断（条件緩和）
            if market_eval['trend_strength'] > 0.6:  # 閾値を0.7→0.6に緩和
                should_trade = True
                # 市場トレンドに従ってトレードタイプを決定
                if market_eval['market_trend'] == 'bullish':
                    trade_type = 'buy'
                    trade_reason = f"Strong bullish trend detected. Strength: {market_eval['trend_strength']:.2f}"
                elif market_eval['market_trend'] == 'bearish':
                    trade_type = 'sell'
                    trade_reason = f"Strong bearish trend detected. Strength: {market_eval['trend_strength']:.2f}"
            # トレンドが中程度の場合でもトレードを実行
            elif market_eval['trend_strength'] > 0.4 and market_eval['risk_score'] < 7:
                should_trade = True
                if market_eval['market_trend'] == 'bullish':
                    trade_type = 'buy'
                    trade_reason = f"Moderate bullish trend with low risk. Strength: {market_eval['trend_strength']:.2f}"
                elif market_eval['market_trend'] == 'bearish':
                    trade_type = 'sell'
                    trade_reason = f"Moderate bearish trend with low risk. Strength: {market_eval['trend_strength']:.2f}"
                
            logger.info(f"ML signal analysis: Prediction: {prediction['prediction']}, probability: {prediction['probability']:.2f}, trend_strength: {market_eval['trend_strength']:.2f}")
        
        if should_trade and trade_type:
            logger.info(f"Decision to trade: {trade_type} because {trade_reason}")
            self._execute_trade(symbol, trade_type, current_price, last_row)
        else:
            logger.info("No trade opportunity at this time")
    
    def _execute_trade(self, symbol, trade_type, current_price, indicators_data):
        """
        Execute a new trade
        
        :param symbol: Trading pair symbol
        :param trade_type: Type of trade ('buy' or 'sell')
        :param current_price: Current price of the trading pair
        :param indicators_data: Technical indicators data at trade time
        """
        logger.info(f"Executing {trade_type} trade for {symbol} at {current_price}")
        
        try:
            # Check if user is available
            if not self.user:
                logger.error("User is not available for trade execution")
                return
                
            # Log API credentials availability (without showing the credentials)
            logger.info(f"API credentials available: {bool(self.user.api_key and self.user.api_secret)}")
            
            # Get available balance
            logger.info("Requesting account balance from GMO API...")
            balance_response = self.api.get_account_balance()
            logger.debug(f"Balance response: {balance_response}")
            
            available_balance = 0
            
            if 'data' in balance_response:
                for asset in balance_response['data']:
                    logger.info(f"Found asset: {asset['symbol']} with available balance: {asset['available']}")
                    if asset['symbol'] == 'JPY':
                        available_balance = float(asset['available'])
                        break
                        
                logger.info(f"Available JPY balance for trading: {available_balance}")
            else:
                logger.error(f"Failed to get balance data. Response: {balance_response}")
            
            if available_balance <= 0:
                logger.error("No available balance for trading")
                return
            
            # Calculate position size
            logger.info(f"Calculating position size based on balance: {available_balance} and price: {current_price}")
            position_size = self.risk_manager.calculate_position_size(
                available_balance,
                current_price
            )
            logger.info(f"Calculated position size: {position_size}")
            
            # Ensure minimum position size
            minimum_size = 0.0001  # Minimum BTC amount for GMO Coin
            if position_size < minimum_size:
                logger.info(f"Adjusting position size to minimum: {minimum_size}")
                position_size = minimum_size
            
            # Log details before execution
            logger.info(f"Executing order: {symbol}, {trade_type.upper()}, MARKET, size={position_size}")
            
            # ストラテジーに基づく取引シグナルを記録
            # 予測データを初期化（実際のML予測がある場合は上書きされる）
            prediction = {
                'probability': 0.7,  # デフォルトの信頼度
                'signal': trade_type,
                'confidence': 'medium'
            }
            
            # 確率値を予測データがあれば使用、なければデフォルト値を設定
            if 'probability' in prediction:
                signal_probability = prediction['probability']
            else:
                signal_probability = 0.7
                
            TradeLogger.log_strategy_signal(
                currency_pair=symbol,
                signal_type=trade_type,
                probability=signal_probability,
                indicators=indicators_data
            )
            
            # Execute the order
            # GMO Coinの小数点桁数制限に対応するためにフォーマット調整
            # 通貨ペアに応じたフォーマット処理
            if 'DOGE_' in symbol:
                # DOGEは小数点以下0桁、かつ最小値は10
                position_size_rounded = max(10, int(position_size))
                position_size_str = f"{position_size_rounded}"
            elif 'XRP_' in symbol:
                # XRPは小数点以下0桁、かつ最小値は10
                position_size_rounded = max(10, int(position_size))
                position_size_str = f"{position_size_rounded}"
            elif 'BTC_' in symbol:
                # BTCは小数点以下8桁、最小値0.0001
                position_size_rounded = max(0.0001, round(position_size, 8))
                position_size_str = f"{position_size_rounded:.8f}"
            elif 'ETH_' in symbol:
                # ETHは小数点以下8桁、最小値0.001
                position_size_rounded = max(0.001, round(position_size, 8))
                position_size_str = f"{position_size_rounded:.8f}"
            else:
                # その他の通貨は小数点以下4桁で処理、最小値1
                position_size_rounded = max(1, round(position_size, 4))
                position_size_str = f"{position_size_rounded:.4f}"
            
            logger.info(f"注文数量を調整: {symbol}, {position_size} → {position_size_str}")
            
            result = self.api.place_order(
                symbol=symbol,
                side=trade_type.upper(),
                execution_type="MARKET",
                size=position_size_str  # 文字列として渡して小数点桁数を明示的に制御
            )
            
            logger.info(f"Order execution result: {result}")
            
            if 'data' in result:
                logger.info("Order successfully placed, creating database record")
                # Create new trade record
                new_trade = Trade()
                new_trade.user_id = self.user.id
                new_trade.currency_pair = symbol
                new_trade.trade_type = trade_type.lower()
                new_trade.amount = position_size
                new_trade.price = current_price
                new_trade.status = 'open'
                new_trade.indicators_data = indicators_data
                
                if self.db_session:
                    logger.info("Adding trade to database session")
                    self.db_session.add(new_trade)
                    self.db_session.commit()
                    logger.info(f"Trade successfully saved to database with ID: {new_trade.id}")
                    
                    # トレード実行ログを記録
                    TradeLogger.log_trade_execution(new_trade, is_bot=True)
                else:
                    logger.error("Database session not available, trade not saved to database")
                
                logger.info(f"New {trade_type} trade executed: {position_size} {symbol} at {current_price}")
            else:
                logger.error(f"Failed to execute {trade_type} trade. API response: {result}")
                
                # API エラーの場合はログに記録
                TradeLogger.log_api_error(
                    f"取引実行エラー: {result.get('error', '不明なエラー')}", 
                    endpoint="place_order", 
                    params={"symbol": symbol, "side": trade_type.upper(), "size": position_size}
                )
        except Exception as e:
            import traceback
            logger.error(f"Error executing {trade_type} trade: {e}")
            logger.error(f"Error traceback: {traceback.format_exc()}")
            if self.db_session:
                logger.info("Rolling back database transaction")
                self.db_session.rollback()
