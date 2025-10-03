"""
Machine Learning Integration - Enhancing ML model with original ai.py features
機械学習統合 - 元のai.pyの機能でMLモデルを強化
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import time
import pickle
import os

# GitHub project ML imports
from services.ml_model import TradingModel
from services.technical_indicators import TechnicalIndicators

# Original ai.py style imports
import constants

logger = logging.getLogger(__name__)

class EnhancedMLModel:
    """
    Enhanced Machine Learning Model combining GitHub project ML with ai.py optimization
    統合機械学習モデル - GitHubプロジェクトのMLとai.pyの最適化を統合
    """
    
    def __init__(self):
        """Initialize Enhanced ML Model"""
        # GitHub project ML model
        self.base_ml_model = TradingModel()
        self.technical_indicators = TechnicalIndicators()
        
        # Original ai.py optimization features
        self.optimized_params = None
        self.last_optimization_time = None
        self.optimization_interval = 24 * 60 * 60  # 24 hours
        self.performance_history = []
        
        # Enhanced features
        self.model_confidence_threshold = 0.6
        self.feature_importance_weights = {}
        self.prediction_history = []
        
        logger.info('Enhanced ML Model initialized')

    def predict_with_optimization(self, df: pd.DataFrame, optimize_params: bool = True) -> Dict[str, Any]:
        """
        Enhanced prediction combining ML model with parameter optimization
        最適化パラメータと組み合わせた拡張予測
        
        Args:
            df: Market data DataFrame with indicators
            optimize_params: Whether to run parameter optimization
            
        Returns:
            Dict containing prediction, probability, confidence, and optimization info
        """
        try:
            # Run parameter optimization if needed
            if optimize_params and self._should_optimize_params():
                logger.info("Running parameter optimization...")
                self.optimized_params = self.optimize_trading_parameters(df)
                self._update_optimization_time()
            
            # Get base ML prediction
            base_prediction = self.base_ml_model.predict(df)
            
            if not base_prediction:
                logger.warning("Base ML prediction failed, using fallback")
                return self._fallback_prediction(df)
            
            # Enhance prediction with optimized parameters
            enhanced_prediction = self._enhance_prediction_with_optimization(
                base_prediction, df
            )
            
            # Calculate confidence based on multiple factors
            confidence = self._calculate_prediction_confidence(
                enhanced_prediction, df
            )
            
            # Store prediction history for analysis
            self._store_prediction_history(enhanced_prediction, confidence)
            
            result = {
                'prediction': enhanced_prediction.get('prediction', 0),
                'probability': enhanced_prediction.get('probability', 0.5),
                'confidence': confidence,
                'signal_strength': enhanced_prediction.get('signal_strength', 0.5),
                'optimized_params': self.optimized_params,
                'feature_importance': enhanced_prediction.get('feature_importance', {}),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Enhanced prediction: {result['prediction']}, "
                       f"probability: {result['probability']:.3f}, "
                       f"confidence: {confidence:.3f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Enhanced prediction error: {str(e)}")
            return self._fallback_prediction(df)

    def optimize_trading_parameters(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Optimize trading parameters using combined ML and technical analysis
        MLとテクニカル分析を組み合わせた取引パラメータの最適化
        
        Args:
            df: Historical market data with indicators
            
        Returns:
            Dict containing optimized parameters
        """
        try:
            logger.info("Starting trading parameter optimization...")
            
            if df is None or len(df) < 100:
                logger.warning("Insufficient data for optimization")
                return self._get_default_params()
            
            # Perform backtesting on different parameter combinations
            best_params = self._backtest_parameter_combinations(df)
            
            # Enhance with ML feature importance
            ml_features = self._get_ml_feature_importance(df)
            
            # Combine technical and ML insights
            optimized_params = self._combine_optimization_results(best_params, ml_features)
            
            logger.info(f"Optimization completed. Best parameters: {optimized_params}")
            
            return optimized_params
            
        except Exception as e:
            logger.error(f"Parameter optimization error: {str(e)}")
            return self._get_default_params()

    def _backtest_parameter_combinations(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Backtest different parameter combinations to find optimal settings
        異なるパラメータ組み合わせのバックテストで最適設定を発見
        """
        try:
            # Define parameter ranges for optimization
            param_combinations = [
                # EMA parameters
                {'ema_fast': 12, 'ema_slow': 26, 'rsi_period': 14, 'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9},
                {'ema_fast': 10, 'ema_slow': 21, 'rsi_period': 14, 'macd_fast': 10, 'macd_slow': 21, 'macd_signal': 9},
                {'ema_fast': 8, 'ema_slow': 21, 'rsi_period': 14, 'macd_fast': 8, 'macd_slow': 21, 'macd_signal': 9},
                {'ema_fast': 15, 'ema_slow': 30, 'rsi_period': 14, 'macd_fast': 15, 'macd_slow': 30, 'macd_signal': 9},
                
                # RSI variations
                {'ema_fast': 12, 'ema_slow': 26, 'rsi_period': 10, 'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9},
                {'ema_fast': 12, 'ema_slow': 26, 'rsi_period': 18, 'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9},
                {'ema_fast': 12, 'ema_slow': 26, 'rsi_period': 21, 'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9},
                
                # MACD variations
                {'ema_fast': 12, 'ema_slow': 26, 'rsi_period': 14, 'macd_fast': 8, 'macd_slow': 21, 'macd_signal': 6},
                {'ema_fast': 12, 'ema_slow': 26, 'rsi_period': 14, 'macd_fast': 15, 'macd_slow': 30, 'macd_signal': 12},
            ]
            
            best_score = -float('inf')
            best_params = param_combinations[0]
            
            for params in param_combinations:
                score = self._evaluate_parameter_set(df, params)
                
                if score > best_score:
                    best_score = score
                    best_params = params
                    
                logger.debug(f"Parameter set {params} scored: {score:.4f}")
            
            logger.info(f"Best parameter set scored: {best_score:.4f}")
            return best_params
            
        except Exception as e:
            logger.error(f"Backtest error: {str(e)}")
            return self._get_default_params()

    def _evaluate_parameter_set(self, df: pd.DataFrame, params: Dict[str, int]) -> float:
        """
        Evaluate a parameter set using backtesting simulation
        バックテストシミュレーションでパラメータセットを評価
        """
        try:
            # Add indicators with specified parameters
            df_test = df.copy()
            
            # Calculate indicators with test parameters
            df_test = self._add_indicators_with_params(df_test, params)
            
            # Simulate trading with these parameters
            signals = self._generate_signals_with_params(df_test, params)
            
            # Calculate performance metrics
            returns = self._calculate_strategy_returns(df_test, signals)
            
            # Calculate score (profit factor * win rate * total trades)
            total_return = returns['total_return']
            win_rate = returns['win_rate']
            total_trades = returns['total_trades']
            max_drawdown = returns['max_drawdown']
            
            # Scoring function: balance profitability, consistency, and activity
            score = (
                total_return * 0.4 +                    # 40% weight on returns
                win_rate * 0.3 +                        # 30% weight on win rate
                min(total_trades / 50, 1.0) * 0.2 -     # 20% weight on trade frequency (capped)
                max_drawdown * 0.1                      # 10% penalty for drawdown
            )
            
            return score
            
        except Exception as e:
            logger.error(f"Parameter evaluation error: {str(e)}")
            return -1.0

    def _add_indicators_with_params(self, df: pd.DataFrame, params: Dict[str, int]) -> pd.DataFrame:
        """Add technical indicators with specified parameters"""
        try:
            df_with_indicators = df.copy()
            
            # Add EMA indicators
            df_with_indicators[f"ema_{params['ema_fast']}"] = df_with_indicators['close'].ewm(span=params['ema_fast']).mean()
            df_with_indicators[f"ema_{params['ema_slow']}"] = df_with_indicators['close'].ewm(span=params['ema_slow']).mean()
            
            # Add RSI
            delta = df_with_indicators['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=params['rsi_period']).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=params['rsi_period']).mean()
            rs = gain / loss
            df_with_indicators[f"rsi_{params['rsi_period']}"] = 100 - (100 / (1 + rs))
            
            # Add MACD
            ema_fast = df_with_indicators['close'].ewm(span=params['macd_fast']).mean()
            ema_slow = df_with_indicators['close'].ewm(span=params['macd_slow']).mean()
            df_with_indicators['macd_line'] = ema_fast - ema_slow
            df_with_indicators['macd_signal'] = df_with_indicators['macd_line'].ewm(span=params['macd_signal']).mean()
            df_with_indicators['macd_histogram'] = df_with_indicators['macd_line'] - df_with_indicators['macd_signal']
            
            return df_with_indicators
            
        except Exception as e:
            logger.error(f"Indicator calculation error: {str(e)}")
            return df

    def _generate_signals_with_params(self, df: pd.DataFrame, params: Dict[str, int]) -> List[int]:
        """Generate trading signals using specified parameters"""
        try:
            signals = []
            
            for i in range(len(df)):
                if i < max(params.values()) + 1:  # Skip initial rows without enough data
                    signals.append(0)  # Hold
                    continue
                
                signal = 0  # Default to hold
                signal_score = 0
                
                # EMA crossover signals
                ema_fast_current = df.iloc[i][f"ema_{params['ema_fast']}"]
                ema_slow_current = df.iloc[i][f"ema_{params['ema_slow']}"]
                ema_fast_prev = df.iloc[i-1][f"ema_{params['ema_fast']}"]
                ema_slow_prev = df.iloc[i-1][f"ema_{params['ema_slow']}"]
                
                if ema_fast_prev < ema_slow_prev and ema_fast_current > ema_slow_current:
                    signal_score += 1  # Golden cross
                elif ema_fast_prev > ema_slow_prev and ema_fast_current < ema_slow_current:
                    signal_score -= 1  # Death cross
                
                # RSI signals
                rsi_current = df.iloc[i][f"rsi_{params['rsi_period']}"]
                rsi_prev = df.iloc[i-1][f"rsi_{params['rsi_period']}"]
                
                if rsi_prev < 30 and rsi_current >= 30:
                    signal_score += 1  # Recovery from oversold
                elif rsi_prev > 70 and rsi_current <= 70:
                    signal_score -= 1  # Fall from overbought
                
                # MACD signals
                macd_current = df.iloc[i]['macd_line']
                macd_signal_current = df.iloc[i]['macd_signal']
                macd_prev = df.iloc[i-1]['macd_line']
                macd_signal_prev = df.iloc[i-1]['macd_signal']
                
                if macd_prev < macd_signal_prev and macd_current > macd_signal_current:
                    signal_score += 1  # MACD bullish crossover
                elif macd_prev > macd_signal_prev and macd_current < macd_signal_current:
                    signal_score -= 1  # MACD bearish crossover
                
                # Convert score to signal
                if signal_score >= 2:
                    signal = 1  # Buy
                elif signal_score <= -2:
                    signal = -1  # Sell
                else:
                    signal = 0  # Hold
                
                signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Signal generation error: {str(e)}")
            return [0] * len(df)

    def _calculate_strategy_returns(self, df: pd.DataFrame, signals: List[int]) -> Dict[str, float]:
        """Calculate strategy performance metrics"""
        try:
            trades = []
            position = 0
            entry_price = 0
            
            for i in range(len(signals)):
                signal = signals[i]
                price = df.iloc[i]['close']
                
                if signal == 1 and position == 0:  # Buy signal, no position
                    position = 1
                    entry_price = price
                elif signal == -1 and position == 1:  # Sell signal, have position
                    exit_price = price
                    returns = (exit_price - entry_price) / entry_price
                    trades.append(returns)
                    position = 0
                    entry_price = 0
                elif signal == -1 and position == 0:  # Sell signal, no position
                    position = -1
                    entry_price = price
                elif signal == 1 and position == -1:  # Buy signal, have short position
                    exit_price = price
                    returns = (entry_price - exit_price) / entry_price
                    trades.append(returns)
                    position = 0
                    entry_price = 0
            
            if not trades:
                return {
                    'total_return': 0,
                    'win_rate': 0,
                    'total_trades': 0,
                    'max_drawdown': 0
                }
            
            # Calculate metrics
            total_return = sum(trades)
            winning_trades = [t for t in trades if t > 0]
            win_rate = len(winning_trades) / len(trades) if trades else 0
            
            # Calculate max drawdown
            cumulative_returns = np.cumsum(trades)
            max_drawdown = np.max(np.maximum.accumulate(cumulative_returns) - cumulative_returns)
            
            return {
                'total_return': total_return,
                'win_rate': win_rate,
                'total_trades': len(trades),
                'max_drawdown': max_drawdown
            }
            
        except Exception as e:
            logger.error(f"Returns calculation error: {str(e)}")
            return {
                'total_return': 0,
                'win_rate': 0,
                'total_trades': 0,
                'max_drawdown': 0
            }

    def _get_ml_feature_importance(self, df: pd.DataFrame) -> Dict[str, float]:
        """Get feature importance from ML model"""
        try:
            # Use GitHub project's ML model to get feature importance
            ml_result = self.base_ml_model.optimize_parameters(df)
            
            if ml_result and 'top_features' in ml_result:
                return ml_result['top_features']
            else:
                return {}
                
        except Exception as e:
            logger.error(f"ML feature importance error: {str(e)}")
            return {}

    def _combine_optimization_results(self, technical_params: Dict[str, Any], 
                                    ml_features: Dict[str, float]) -> Dict[str, Any]:
        """Combine technical parameter optimization with ML feature importance"""
        try:
            combined_params = {
                # Technical parameters from backtesting
                'technical_params': technical_params,
                
                # ML feature importance
                'ml_feature_importance': ml_features,
                
                # Combined confidence thresholds
                'signal_confidence_threshold': 0.65,
                'ml_probability_threshold': 0.6,
                
                # Risk management parameters
                'risk_multiplier': 1.0,
                'position_sizing_factor': 1.0,
                
                # Optimization metadata
                'optimization_timestamp': datetime.utcnow().isoformat(),
                'optimization_method': 'combined_technical_ml'
            }
            
            # Adjust thresholds based on ML feature importance
            if ml_features:
                avg_importance = np.mean(list(ml_features.values()))
                if avg_importance > 0.1:  # High feature importance
                    combined_params['signal_confidence_threshold'] = 0.6  # Lower threshold
                elif avg_importance < 0.05:  # Low feature importance
                    combined_params['signal_confidence_threshold'] = 0.75  # Higher threshold
            
            return combined_params
            
        except Exception as e:
            logger.error(f"Combination error: {str(e)}")
            return self._get_default_params()

    def _enhance_prediction_with_optimization(self, base_prediction: Dict, df: pd.DataFrame) -> Dict[str, Any]:
        """Enhance base prediction with optimization parameters"""
        try:
            enhanced_prediction = base_prediction.copy()
            
            if not self.optimized_params:
                return enhanced_prediction
            
            # Apply technical parameter filters
            technical_params = self.optimized_params.get('technical_params', {})
            if technical_params:
                # Adjust prediction based on optimized technical indicators
                technical_signal = self._get_optimized_technical_signal(df, technical_params)
                
                # Combine ML and technical signals
                ml_weight = 0.6
                technical_weight = 0.4
                
                combined_probability = (
                    enhanced_prediction.get('probability', 0.5) * ml_weight +
                    technical_signal * technical_weight
                )
                
                enhanced_prediction['probability'] = combined_probability
                enhanced_prediction['signal_strength'] = abs(combined_probability - 0.5) * 2
            
            # Apply confidence threshold
            confidence_threshold = self.optimized_params.get('signal_confidence_threshold', 0.65)
            if enhanced_prediction.get('probability', 0.5) < confidence_threshold:
                enhanced_prediction['prediction'] = 0  # Hold if confidence too low
                enhanced_prediction['probability'] = 0.5
            
            return enhanced_prediction
            
        except Exception as e:
            logger.error(f"Prediction enhancement error: {str(e)}")
            return base_prediction

    def _get_optimized_technical_signal(self, df: pd.DataFrame, params: Dict[str, int]) -> float:
        """Get technical signal using optimized parameters"""
        try:
            if len(df) < 2:
                return 0.5
            
            signal_score = 0
            max_signals = 3  # EMA, RSI, MACD
            
            # EMA signal
            if f"ema_{params['ema_fast']}" in df.columns and f"ema_{params['ema_slow']}" in df.columns:
                ema_fast_current = df.iloc[-1][f"ema_{params['ema_fast']}"]
                ema_slow_current = df.iloc[-1][f"ema_{params['ema_slow']}"]
                
                if ema_fast_current > ema_slow_current:
                    signal_score += 1
                else:
                    signal_score -= 1
            
            # RSI signal
            if f"rsi_{params['rsi_period']}" in df.columns:
                rsi = df.iloc[-1][f"rsi_{params['rsi_period']}"]
                if rsi < 30:
                    signal_score += 1
                elif rsi > 70:
                    signal_score -= 1
            
            # MACD signal
            if 'macd_line' in df.columns and 'macd_signal' in df.columns:
                macd_line = df.iloc[-1]['macd_line']
                macd_signal = df.iloc[-1]['macd_signal']
                
                if macd_line > macd_signal:
                    signal_score += 1
                else:
                    signal_score -= 1
            
            # Normalize to 0-1 scale
            normalized_signal = (signal_score + max_signals) / (2 * max_signals)
            return max(0, min(1, normalized_signal))
            
        except Exception as e:
            logger.error(f"Technical signal error: {str(e)}")
            return 0.5

    def _calculate_prediction_confidence(self, prediction: Dict, df: pd.DataFrame) -> float:
        """Calculate confidence score for the prediction"""
        try:
            confidence_factors = []
            
            # Factor 1: Prediction probability distance from 0.5
            prob = prediction.get('probability', 0.5)
            prob_confidence = abs(prob - 0.5) * 2
            confidence_factors.append(prob_confidence)
            
            # Factor 2: Signal strength consistency
            signal_strength = prediction.get('signal_strength', 0.5)
            confidence_factors.append(signal_strength)
            
            # Factor 3: Historical accuracy (if available)
            historical_accuracy = self._get_historical_accuracy()
            confidence_factors.append(historical_accuracy)
            
            # Factor 4: Market volatility adjustment
            volatility_adjustment = self._get_volatility_adjustment(df)
            confidence_factors.append(volatility_adjustment)
            
            # Calculate weighted average confidence
            weights = [0.3, 0.25, 0.25, 0.2]  # Adjust weights as needed
            confidence = sum(f * w for f, w in zip(confidence_factors, weights))
            
            return max(0.0, min(1.0, confidence))
            
        except Exception as e:
            logger.error(f"Confidence calculation error: {str(e)}")
            return 0.5

    def _get_historical_accuracy(self) -> float:
        """Get historical prediction accuracy"""
        try:
            if not self.prediction_history or len(self.prediction_history) < 5:
                return 0.5  # Default confidence
            
            # Calculate accuracy of recent predictions
            recent_predictions = self.prediction_history[-20:]  # Last 20 predictions
            correct_predictions = sum(1 for pred in recent_predictions if pred.get('correct', False))
            accuracy = correct_predictions / len(recent_predictions)
            
            return accuracy
            
        except Exception as e:
            logger.error(f"Historical accuracy error: {str(e)}")
            return 0.5

    def _get_volatility_adjustment(self, df: pd.DataFrame) -> float:
        """Get volatility-based confidence adjustment"""
        try:
            if len(df) < 20:
                return 0.5
            
            # Calculate recent price volatility
            recent_prices = df['close'].tail(20)
            returns = recent_prices.pct_change().dropna()
            volatility = returns.std()
            
            # Higher volatility reduces confidence
            # Normalize volatility (assuming typical crypto volatility 0.01-0.1)
            normalized_volatility = min(1.0, volatility * 10)
            volatility_confidence = 1.0 - normalized_volatility
            
            return max(0.1, volatility_confidence)
            
        except Exception as e:
            logger.error(f"Volatility adjustment error: {str(e)}")
            return 0.5

    def _store_prediction_history(self, prediction: Dict, confidence: float):
        """Store prediction in history for accuracy tracking"""
        try:
            history_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'prediction': prediction.get('prediction', 0),
                'probability': prediction.get('probability', 0.5),
                'confidence': confidence,
                'correct': None  # To be updated later when outcome is known
            }
            
            self.prediction_history.append(history_entry)
            
            # Keep only recent history (last 100 predictions)
            if len(self.prediction_history) > 100:
                self.prediction_history = self.prediction_history[-100:]
                
        except Exception as e:
            logger.error(f"History storage error: {str(e)}")

    def _should_optimize_params(self) -> bool:
        """Check if parameter optimization is needed"""
        if not self.optimized_params:
            return True
            
        if self.last_optimization_time:
            elapsed = time.time() - self.last_optimization_time
            return elapsed >= self.optimization_interval
            
        return True

    def _update_optimization_time(self):
        """Update last optimization timestamp"""
        self.last_optimization_time = time.time()

    def _get_default_params(self) -> Dict[str, Any]:
        """Get default optimization parameters"""
        return {
            'technical_params': {
                'ema_fast': 12,
                'ema_slow': 26,
                'rsi_period': 14,
                'macd_fast': 12,
                'macd_slow': 26,
                'macd_signal': 9
            },
            'ml_feature_importance': {},
            'signal_confidence_threshold': 0.65,
            'ml_probability_threshold': 0.6,
            'optimization_timestamp': datetime.utcnow().isoformat(),
            'optimization_method': 'default'
        }

    def _fallback_prediction(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Fallback prediction when ML model fails"""
        try:
            if df is None or len(df) < 2:
                return {
                    'prediction': 0,
                    'probability': 0.5,
                    'confidence': 0.3,
                    'signal_strength': 0.0,
                    'fallback': True
                }
            
            # Use simple technical analysis as fallback
            last_row = df.iloc[-1]
            
            # RSI-based prediction
            rsi = last_row.get('rsi_14', 50)
            if rsi < 30:
                prediction = 1  # Buy
                probability = 0.7
            elif rsi > 70:
                prediction = 0  # Sell
                probability = 0.3
            else:
                prediction = 0  # Hold
                probability = 0.5
            
            return {
                'prediction': prediction,
                'probability': probability,
                'confidence': 0.4,  # Lower confidence for fallback
                'signal_strength': abs(probability - 0.5) * 2,
                'fallback': True
            }
            
        except Exception as e:
            logger.error(f"Fallback prediction error: {str(e)}")
            return {
                'prediction': 0,
                'probability': 0.5,
                'confidence': 0.2,
                'signal_strength': 0.0,
                'fallback': True,
                'error': str(e)
            }

    def save_model_state(self, filepath: str = 'models/enhanced_ml_state.pkl'):
        """Save enhanced ML model state"""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            state = {
                'optimized_params': self.optimized_params,
                'last_optimization_time': self.last_optimization_time,
                'performance_history': self.performance_history,
                'prediction_history': self.prediction_history,
                'feature_importance_weights': self.feature_importance_weights,
                'model_confidence_threshold': self.model_confidence_threshold
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(state, f)
                
            logger.info(f"Enhanced ML model state saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Model save error: {str(e)}")

    def load_model_state(self, filepath: str = 'models/enhanced_ml_state.pkl'):
        """Load enhanced ML model state"""
        try:
            if not os.path.exists(filepath):
                logger.info("No saved model state found, using defaults")
                return
            
            with open(filepath, 'rb') as f:
                state = pickle.load(f)
            
            self.optimized_params = state.get('optimized_params')
            self.last_optimization_time = state.get('last_optimization_time')
            self.performance_history = state.get('performance_history', [])
            self.prediction_history = state.get('prediction_history', [])
            self.feature_importance_weights = state.get('feature_importance_weights', {})
            self.model_confidence_threshold = state.get('model_confidence_threshold', 0.6)
            
            logger.info(f"Enhanced ML model state loaded from {filepath}")
            
        except Exception as e:
            logger.error(f"Model load error: {str(e)}")