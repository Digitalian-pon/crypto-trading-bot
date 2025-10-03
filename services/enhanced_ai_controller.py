"""
Enhanced AI Controller - Integrating existing ai.py functionality with GitHub project structure
統合版AIコントローラー - 既存ai.pyの機能をGitHubプロジェクト構造に統合
"""

import datetime
import logging
import time
import numpy as np
import pandas as pd
from datetime import timezone, timedelta
import datetime as dt
from typing import Dict, List, Optional, Tuple

# GitHub project imports
from services.gmo_api import GMOCoinAPI
from services.technical_indicators import TechnicalIndicators
from services.ml_model import TradingModel
from services.risk_manager import RiskManager
from services.data_service import DataService
from services.logger_service import TradeLogger

# Original ai.py functionality preservation
import constants
import settings

logger = logging.getLogger(__name__)

class EnhancedAIController:
    """
    Enhanced AI Controller combining original ai.py functionality with GitHub project structure
    統合版AIコントローラー - 元のai.pyとGitHubプロジェクトの機能を統合
    """

    def __init__(self, user, product_code=None, use_percent=None, duration=None, 
                 past_period=None, stop_limit_percent=None, api_client=None):
        """
        Initialize Enhanced AI Controller
        
        Args:
            user: User object from GitHub project
            product_code: Trading pair (e.g., 'DOGE_JPY')
            use_percent: Position sizing percentage
            duration: Timeframe for analysis
            past_period: Historical data period
            stop_limit_percent: Stop loss percentage
            api_client: Optional API client instance
        """
        # User context from GitHub project
        self.user = user
        
        # Original ai.py parameters with fallbacks from user settings
        self.product_code = product_code or (user.settings.currency_pair if user and user.settings else 'DOGE_JPY')
        self.use_percent = use_percent or 0.05  # 5% default
        self.duration = duration or (user.settings.timeframe if user and user.settings else '5m')
        self.past_period = past_period or 100
        self.stop_limit_percent = stop_limit_percent or (user.settings.stop_loss_percentage / 100 if user and user.settings else 0.03)
        
        # Original ai.py performance tracking
        self.start_trade = dt.datetime.now(timezone.utc)
        self.last_trade_time = dt.datetime.now(timezone.utc)
        self.trade_count = 0
        self.win_count = 0
        self.lose_count = 0
        self.total_profit = 0
        self.total_profit_prev = 0
        self.daily_loss = 0
        
        # Paper trading support
        if hasattr(settings, 'paper_trade') and settings.paper_trade:
            self.paper_balance = 100000.0
            self.paper_positions = []
        
        # GitHub project components
        self.api = api_client or GMOCoinAPI(
            user.api_key if user else settings.api_key,
            user.api_secret if user else settings.api_secret
        )
        self.data_service = DataService(
            user.api_key if user else settings.api_key,
            user.api_secret if user else settings.api_secret
        )
        self.ml_model = TradingModel()
        self.risk_manager = RiskManager()
        self.technical_indicators = TechnicalIndicators()
        
        # Enhanced features
        self.optimized_trade_params = None
        self.last_optimization_time = None
        self.optimization_interval = 24 * 60 * 60  # 24 hours
        
        logger.info('Enhanced AI Controller initialized', extra={
            'product_code': self.product_code,
            'duration': self.duration,
            'user_id': user.id if user else None,
            'action': 'init'
        })
        
        # Initialize optimization parameters
        self.update_optimize_params()

    def duration_seconds(self, duration: str) -> int:
        """Convert duration string to seconds (from original ai.py)"""
        duration_map = {
            '1m': 60,
            '5m': 300,
            '1h': 3600,
            '4h': 14400,
            '1d': 86400
        }
        return duration_map.get(duration, 300)  # Default to 5m

    def calc_risk_size(self, balance: float, current_price: float) -> int:
        """
        Calculate position size with risk management (enhanced from original ai.py)
        """
        try:
            # Use GitHub project's risk manager for enhanced calculation
            base_size = self.risk_manager.calculate_position_size(balance, current_price)
            
            # Apply original ai.py risk constraints
            max_size = balance * self.use_percent
            min_size = 0.001  # Minimum position size
            
            # Risk per trade limit
            risk_per_trade = balance * self.stop_limit_percent
            max_risk_size = risk_per_trade / (current_price * self.stop_limit_percent) if current_price > 0 else 0
            
            # Final size determination
            size = min(max_size, max_risk_size, base_size)
            size = max(min_size, size)
            
            return max(1, int(size))  # Ensure minimum 1 unit for crypto
            
        except Exception as e:
            logger.error(f'Risk size calculation error: {str(e)}')
            return 1

    def update_optimize_params(self):
        """
        Update optimization parameters (enhanced from original ai.py)
        """
        try:
            # Check if optimization is needed
            if not self._should_update_params():
                return
                
            # Get market data using GitHub project's data service
            df = self._get_market_data_for_optimization()
            
            if df is None or len(df) < 100:
                logger.warning('Insufficient data for optimization')
                return
            
            # Use ML model for parameter optimization
            optimized_params = self.ml_model.optimize_parameters(df)
            if optimized_params:
                self.optimized_trade_params = optimized_params
                self._cache_params()
                logger.info('Parameters optimized successfully')
            
        except Exception as e:
            logger.error(f'Parameter optimization failed: {str(e)}')

    def _should_update_params(self) -> bool:
        """Check if parameter update is needed"""
        if not self.optimized_trade_params:
            return True
            
        if self.last_optimization_time:
            elapsed = time.time() - self.last_optimization_time
            return elapsed >= self.optimization_interval
            
        return True

    def _cache_params(self):
        """Cache optimization parameters"""
        self.last_optimization_time = time.time()

    def _get_market_data_for_optimization(self) -> Optional[pd.DataFrame]:
        """Get market data for optimization using GitHub project's data service"""
        try:
            timeframe = self.duration
            limit = self._get_limit_for_timeframe(timeframe)
            
            df = self.data_service.get_data_with_indicators(
                self.product_code, 
                interval=timeframe, 
                limit=limit
            )
            return df
            
        except Exception as e:
            logger.error(f'Market data fetch error: {str(e)}')
            return None

    def _get_limit_for_timeframe(self, timeframe: str) -> int:
        """Get appropriate data limit based on timeframe"""
        timeframe_limits = {
            '1m': 1440,   # 24 hours
            '5m': 288,    # 24 hours
            '15m': 96,    # 24 hours
            '30m': 48,    # 24 hours
            '1h': 24,     # 24 hours
            '4h': 6,      # 24 hours
            '1d': 30      # 30 days
        }
        return timeframe_limits.get(timeframe, 288)

    def can_trade(self) -> bool:
        """
        Check if trading is allowed (enhanced from original ai.py)
        """
        try:
            # Original time-based constraint
            current_time = dt.datetime.now(timezone.utc)
            time_since_last_trade = current_time - self.last_trade_time
            
            trade_interval = getattr(settings, 'trade_interval', 60)
            if time_since_last_trade.total_seconds() < trade_interval:
                return False
            
            # GitHub project's risk management check
            if hasattr(self.user, 'settings') and self.user.settings:
                if not self.user.settings.trading_enabled:
                    return False
                    
            # Additional risk checks using risk manager
            return True
            
        except Exception as e:
            logger.error(f'Can trade check failed: {str(e)}')
            return False

    def get_trade_signal(self, df: pd.DataFrame) -> str:
        """
        Get trading signal using combined analysis (enhanced from original ai.py)
        
        Args:
            df: DataFrame with market data and indicators
            
        Returns:
            str: 'BUY', 'SELL', or 'HOLD'
        """
        try:
            if df is None or len(df) < 2:
                return 'HOLD'
            
            # Get ML prediction from GitHub project
            ml_prediction = self.ml_model.predict(df)
            
            # Get technical analysis signal (original ai.py style)
            technical_signal = self._get_technical_signal(df)
            
            # Get risk assessment from GitHub project
            last_row = df.iloc[-1].to_dict()
            market_eval = self.risk_manager.evaluate_market_conditions(last_row)
            
            # Combined decision logic
            final_signal = self._combine_signals(ml_prediction, technical_signal, market_eval)
            
            logger.info(f'Signal analysis - ML: {ml_prediction}, Technical: {technical_signal}, Final: {final_signal}')
            return final_signal
            
        except Exception as e:
            logger.error(f'Signal generation error: {str(e)}')
            return 'HOLD'

    def _get_technical_signal(self, df: pd.DataFrame) -> str:
        """
        Get technical analysis signal (from original ai.py)
        """
        try:
            signal = 'HOLD'
            
            # EMA crossover strategy
            if 'ema_12' in df.columns and 'ema_26' in df.columns:
                if len(df) >= 2:
                    # Golden cross: short EMA crosses above long EMA
                    if (df['ema_12'].iloc[-2] < df['ema_26'].iloc[-2] and 
                        df['ema_12'].iloc[-1] >= df['ema_26'].iloc[-1]):
                        signal = 'BUY'
                    # Death cross: short EMA crosses below long EMA
                    elif (df['ema_12'].iloc[-2] > df['ema_26'].iloc[-2] and 
                          df['ema_12'].iloc[-1] <= df['ema_26'].iloc[-1]):
                        signal = 'SELL'
            
            # RSI strategy
            if 'rsi_14' in df.columns and len(df) >= 2:
                rsi_current = df['rsi_14'].iloc[-1]
                rsi_prev = df['rsi_14'].iloc[-2]
                
                # Recovery from oversold
                if rsi_prev < 30 and rsi_current >= 30:
                    signal = 'BUY'
                # Fall from overbought
                elif rsi_prev > 70 and rsi_current <= 70:
                    signal = 'SELL'
            
            # MACD strategy
            if 'macd_line' in df.columns and 'macd_signal' in df.columns and len(df) >= 2:
                macd_current = df['macd_line'].iloc[-1]
                signal_current = df['macd_signal'].iloc[-1]
                macd_prev = df['macd_line'].iloc[-2]
                signal_prev = df['macd_signal'].iloc[-2]
                
                # MACD crosses above signal line
                if macd_prev < signal_prev and macd_current >= signal_current:
                    signal = 'BUY'
                # MACD crosses below signal line
                elif macd_prev > signal_prev and macd_current <= signal_current:
                    signal = 'SELL'
                    
            return signal
            
        except Exception as e:
            logger.error(f'Technical signal error: {str(e)}')
            return 'HOLD'

    def _combine_signals(self, ml_prediction: Dict, technical_signal: str, market_eval: Dict) -> str:
        """
        Combine ML, technical, and market evaluation signals
        """
        try:
            signal_scores = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
            
            # ML prediction weight
            if ml_prediction:
                pred_value = ml_prediction.get('prediction', 0)
                probability = ml_prediction.get('probability', 0.5)
                
                if pred_value == 1 and probability > 0.6:  # Bullish prediction
                    signal_scores['BUY'] += probability * 2
                elif pred_value == 0 and probability > 0.6:  # Bearish prediction
                    signal_scores['SELL'] += probability * 2
                else:
                    signal_scores['HOLD'] += 1
            
            # Technical signal weight
            if technical_signal == 'BUY':
                signal_scores['BUY'] += 1.5
            elif technical_signal == 'SELL':
                signal_scores['SELL'] += 1.5
            else:
                signal_scores['HOLD'] += 1
            
            # Market evaluation weight
            if market_eval:
                trend = market_eval.get('market_trend', 'neutral')
                strength = market_eval.get('trend_strength', 0.5)
                
                if trend == 'bullish' and strength > 0.7:
                    signal_scores['BUY'] += strength * 1.5
                elif trend == 'bearish' and strength > 0.7:
                    signal_scores['SELL'] += strength * 1.5
                else:
                    signal_scores['HOLD'] += 0.5
            
            # Find highest scoring signal
            best_signal = max(signal_scores, key=signal_scores.get)
            
            # Require minimum confidence
            if signal_scores[best_signal] < 2.0:
                return 'HOLD'
                
            return best_signal
            
        except Exception as e:
            logger.error(f'Signal combination error: {str(e)}')
            return 'HOLD'

    def execute_trade(self, signal: str, current_price: float, df: pd.DataFrame) -> bool:
        """
        Execute trade based on signal (combining original ai.py and GitHub project)
        """
        try:
            if not self.can_trade():
                return False
                
            if signal == 'BUY':
                return self._execute_buy_order(current_price, df)
            elif signal == 'SELL':
                return self._execute_sell_order(current_price, df)
                
            return False
            
        except Exception as e:
            logger.error(f'Trade execution error: {str(e)}')
            return False

    def _execute_buy_order(self, current_price: float, df: pd.DataFrame) -> bool:
        """Execute buy order (enhanced from original ai.py)"""
        try:
            # Get balance
            balance_response = self.api.get_account_balance()
            if 'data' not in balance_response:
                logger.error('Failed to get account balance')
                return False
                
            available_balance = 0
            for asset in balance_response['data']:
                if asset['symbol'] == 'JPY':
                    available_balance = float(asset['available'])
                    break
            
            if available_balance <= 0:
                logger.warning('No available JPY balance for buy order')
                return False
            
            # Calculate position size
            position_size = self.calc_risk_size(available_balance, current_price)
            
            # Format position size for GMO Coin
            position_size_str = self._format_position_size(position_size, self.product_code)
            
            # Execute order
            result = self.api.place_order(
                symbol=self.product_code,
                side='BUY',
                execution_type='MARKET',
                size=position_size_str
            )
            
            if 'data' in result:
                self._record_trade(
                    trade_type='buy',
                    amount=position_size,
                    price=current_price,
                    indicators_data=df.iloc[-1].to_dict() if df is not None else {}
                )
                self.last_trade_time = dt.datetime.now(timezone.utc)
                logger.info(f'Buy order executed: {position_size} {self.product_code} at {current_price}')
                return True
            else:
                logger.error(f'Buy order failed: {result}')
                return False
                
        except Exception as e:
            logger.error(f'Buy order execution error: {str(e)}')
            return False

    def _execute_sell_order(self, current_price: float, df: pd.DataFrame) -> bool:
        """Execute sell order (enhanced from original ai.py)"""
        try:
            # Get positions
            positions = self.api.get_positions(self.product_code)
            
            if not positions or 'data' not in positions or not positions['data'].get('list'):
                logger.warning('No positions to sell')
                return False
            
            # Calculate total sellable amount
            total_amount = 0
            for pos in positions['data']['list']:
                if pos['side'] == 'BUY':  # Can sell buy positions
                    total_amount += float(pos['size'])
            
            if total_amount <= 0:
                logger.warning('No buy positions to sell')
                return False
            
            # Format position size
            position_size_str = self._format_position_size(total_amount, self.product_code)
            
            # Execute sell order
            result = self.api.place_order(
                symbol=self.product_code,
                side='SELL',
                execution_type='MARKET',
                size=position_size_str
            )
            
            if 'data' in result:
                self._record_trade(
                    trade_type='sell',
                    amount=total_amount,
                    price=current_price,
                    indicators_data=df.iloc[-1].to_dict() if df is not None else {}
                )
                self.last_trade_time = dt.datetime.now(timezone.utc)
                logger.info(f'Sell order executed: {total_amount} {self.product_code} at {current_price}')
                return True
            else:
                logger.error(f'Sell order failed: {result}')
                return False
                
        except Exception as e:
            logger.error(f'Sell order execution error: {str(e)}')
            return False

    def _format_position_size(self, size: float, symbol: str) -> str:
        """Format position size according to GMO Coin requirements"""
        if 'DOGE_' in symbol or 'XRP_' in symbol:
            # DOGE and XRP: integer, minimum 10
            formatted_size = max(10, int(size))
            return f"{formatted_size}"
        elif 'BTC_' in symbol:
            # BTC: 8 decimal places, minimum 0.0001
            formatted_size = max(0.0001, round(size, 8))
            return f"{formatted_size:.8f}"
        elif 'ETH_' in symbol:
            # ETH: 8 decimal places, minimum 0.001
            formatted_size = max(0.001, round(size, 8))
            return f"{formatted_size:.8f}"
        else:
            # Others: 4 decimal places, minimum 1
            formatted_size = max(1, round(size, 4))
            return f"{formatted_size:.4f}"

    def _record_trade(self, trade_type: str, amount: float, price: float, indicators_data: Dict):
        """Record trade in database (GitHub project integration)"""
        try:
            if not self.user:
                logger.warning('No user context for trade recording')
                return
                
            # Import here to avoid circular imports
            from models import Trade, db
            
            new_trade = Trade()
            new_trade.user_id = self.user.id
            new_trade.currency_pair = self.product_code
            new_trade.trade_type = trade_type.lower()
            new_trade.amount = amount
            new_trade.price = price
            new_trade.status = 'open'
            new_trade.indicators_data = indicators_data
            new_trade.created_at = datetime.datetime.utcnow()
            
            if db:
                db.session.add(new_trade)
                db.session.commit()
                logger.info(f'Trade recorded in database: ID {new_trade.id}')
            
            # Also log with TradeLogger
            TradeLogger.log_trade_execution(new_trade, is_bot=True)
            
        except Exception as e:
            logger.error(f'Trade recording error: {str(e)}')

    def run_trading_cycle(self) -> bool:
        """
        Run one complete trading cycle (main method)
        """
        try:
            logger.info(f'Starting trading cycle for {self.product_code}')
            
            # Update parameters if needed
            if self._should_update_params():
                self.update_optimize_params()
            
            # Get market data with indicators
            df = self._get_market_data_for_optimization()
            if df is None or len(df) < 10:
                logger.warning('Insufficient market data for trading')
                return False
            
            # Get current price
            current_price = df['close'].iloc[-1]
            
            # Get trading signal
            signal = self.get_trade_signal(df)
            
            # Execute trade if signal is not HOLD
            if signal != 'HOLD':
                success = self.execute_trade(signal, current_price, df)
                if success:
                    logger.info(f'Trading cycle completed successfully: {signal} at {current_price}')
                    return True
                else:
                    logger.warning(f'Trade execution failed for signal: {signal}')
            else:
                logger.info('No trading opportunity detected')
            
            return False
            
        except Exception as e:
            logger.error(f'Trading cycle error: {str(e)}')
            return False

    def get_performance_metrics(self) -> Dict:
        """Get performance metrics (from original ai.py)"""
        return {
            'trade_count': self.trade_count,
            'win_count': self.win_count,
            'lose_count': self.lose_count,
            'total_profit': self.total_profit,
            'win_rate': self.win_count / max(1, self.trade_count) * 100,
            'daily_profit': self.total_profit - self.total_profit_prev
        }

    def __del__(self):
        """Cleanup on destruction"""
        logger.info('Enhanced AI Controller destroyed')