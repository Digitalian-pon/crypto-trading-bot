"""
最適化されたトレーディングロジック - DOGE/JPYレバレッジ取引専用
データ駆動型アプローチ + 適応的パラメータ調整
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class OptimizedTradingLogic:
    """
    最適化されたトレーディングロジック

    主な改善点:
    1. 市場レジーム（トレンド/レンジ/高ボラティリティ）の自動検出
    2. レジーム別の適応的パラメータ調整
    3. ATRベースの動的ストップロス/テイクプロフィット
    4. 複数時間足分析（マルチタイムフレーム）
    5. 取引品質スコアリングシステム
    6. トレンド強度の定量化
    """

    def __init__(self, config=None):
        """初期化"""
        self.config = config or {}
        self.last_trade_time = None
        self.min_trade_interval = 300  # 5分（300秒）- 過剰取引防止

        # 取引履歴トラッキング（パフォーマンス分析用）
        self.trade_history = []
        self.recent_trades_limit = 20  # 直近20取引を追跡

        # 市場レジーム別パラメータ
        self.regime_params = {
            'TRENDING': {
                'rsi_oversold': 40,      # トレンド中は逆張り禁止
                'rsi_overbought': 60,
                'signal_threshold': 1.2,  # 比較的低い閾値（トレンドフォロー）
                'stop_loss_atr_mult': 2.0,
                'take_profit_atr_mult': 4.0,
            },
            'RANGING': {
                'rsi_oversold': 30,      # レンジ相場は逆張り
                'rsi_overbought': 70,
                'signal_threshold': 1.5,  # 高い閾値（慎重に）
                'stop_loss_atr_mult': 1.5,
                'take_profit_atr_mult': 2.5,
            },
            'VOLATILE': {
                'rsi_oversold': 35,
                'rsi_overbought': 65,
                'signal_threshold': 2.0,  # 非常に高い閾値（極めて慎重）
                'stop_loss_atr_mult': 3.0,  # 広めのストップ
                'take_profit_atr_mult': 5.0,
            }
        }

    def should_trade(self, market_data, historical_df=None):
        """
        取引判定 - 最適化版

        Args:
            market_data: 最新の市場データ（辞書形式）
            historical_df: 過去データのDataFrame（マルチタイムフレーム分析用）

        Returns:
            (should_trade, trade_type, reason, confidence, stop_loss, take_profit)
        """
        try:
            # 1. 基本データ抽出
            current_price = market_data.get('close', 0)
            rsi = market_data.get('rsi', 50)
            macd_line = market_data.get('macd_line', 0)
            macd_signal = market_data.get('macd_signal', 0)
            macd_histogram = market_data.get('macd_histogram', 0)
            bb_upper = market_data.get('bb_upper', current_price * 1.02)
            bb_lower = market_data.get('bb_lower', current_price * 0.98)
            bb_middle = market_data.get('bb_middle', current_price)
            ema_20 = market_data.get('ema_20', current_price)
            ema_50 = market_data.get('ema_50', current_price)

            # ATR取得（ボラティリティ測定）
            atr = self._calculate_atr_from_data(historical_df) if historical_df is not None else current_price * 0.02

            logger.info(f"📊 Market Data: Price={current_price:.3f}, RSI={rsi:.2f}, MACD={macd_line:.4f}/{macd_signal:.4f}, ATR={atr:.4f}")

            # 2. 市場レジーム分析
            regime = self._detect_market_regime(market_data, historical_df)
            regime_config = self.regime_params.get(regime, self.regime_params['RANGING'])

            logger.info(f"🎯 Market Regime: {regime}")
            logger.info(f"   Parameters: RSI({regime_config['rsi_oversold']}/{regime_config['rsi_overbought']}), "
                       f"Threshold={regime_config['signal_threshold']:.2f}")

            # 3. トレンド分析（改善版）
            trend_analysis = self._advanced_trend_analysis(market_data, historical_df)
            trend_direction = trend_analysis['direction']
            trend_strength = trend_analysis['strength']
            trend_quality = trend_analysis['quality']

            logger.info(f"📈 Trend: {trend_direction} (Strength={trend_strength:.3f}, Quality={trend_quality:.3f})")

            # 4. シグナル収集
            signals = []

            # === RSIシグナル（レジーム適応型） ===
            rsi_signals = self._analyze_rsi(
                rsi, trend_direction, regime,
                regime_config['rsi_oversold'],
                regime_config['rsi_overbought']
            )
            signals.extend(rsi_signals)

            # === MACDシグナル（ヒストグラム重視） ===
            macd_signals = self._analyze_macd(
                macd_line, macd_signal, macd_histogram,
                trend_direction, regime
            )
            signals.extend(macd_signals)

            # === ボリンジャーバンドシグナル（レジーム適応型） ===
            bb_signals = self._analyze_bollinger_bands(
                current_price, bb_upper, bb_lower, bb_middle,
                trend_direction, regime
            )
            signals.extend(bb_signals)

            # === EMAシグナル（トレンド確認） ===
            ema_signals = self._analyze_ema(
                current_price, ema_20, ema_50, trend_strength
            )
            signals.extend(ema_signals)

            # === プライスアクションシグナル（追加） ===
            if historical_df is not None and len(historical_df) > 3:
                pa_signals = self._analyze_price_action(historical_df, current_price)
                signals.extend(pa_signals)

            # 5. シグナル統合・スコアリング
            buy_signals = [s for s in signals if s[0] == 'BUY']
            sell_signals = [s for s in signals if s[0] == 'SELL']

            buy_score = sum([s[2] for s in buy_signals])
            sell_score = sum([s[2] for s in sell_signals])

            # トレンド品質ボーナス（高品質トレンドは信頼度UP）
            if trend_quality > 0.7:
                if trend_direction in ['STRONG_UP', 'UP']:
                    buy_score *= 1.3
                    logger.info(f"✨ High quality uptrend bonus: Buy score x1.3")
                elif trend_direction in ['STRONG_DOWN', 'DOWN']:
                    sell_score *= 1.3
                    logger.info(f"✨ High quality downtrend bonus: Sell score x1.3")

            logger.info(f"📊 Signal Scores: BUY={buy_score:.2f}, SELL={sell_score:.2f}")
            logger.info(f"   Buy Signals ({len(buy_signals)}): {[f'{s[1]}({s[2]:.1f})' for s in buy_signals]}")
            logger.info(f"   Sell Signals ({len(sell_signals)}): {[f'{s[1]}({s[2]:.1f})' for s in sell_signals]}")

            # 6. 最終判定（レジーム別閾値）
            required_threshold = regime_config['signal_threshold']

            # 取引タイミングチェック（過剰取引防止）
            if not self._check_trade_timing():
                logger.info(f"⏸️ Trade interval too short - waiting...")
                return False, None, "Trade interval too short", 0.0, None, None

            # 動的ストップロス/テイクプロフィット計算
            stop_loss_atr_mult = regime_config['stop_loss_atr_mult']
            take_profit_atr_mult = regime_config['take_profit_atr_mult']

            if buy_score >= required_threshold and buy_score > sell_score:
                reasons = [s[1] for s in buy_signals]
                confidence = buy_score

                # BUY用のストップロス/テイクプロフィット
                stop_loss_price = current_price - (atr * stop_loss_atr_mult)
                take_profit_price = current_price + (atr * take_profit_atr_mult)

                logger.info(f"🟢 BUY Signal - Confidence={confidence:.2f}, SL=¥{stop_loss_price:.2f}, TP=¥{take_profit_price:.2f}")

                return True, 'BUY', f"Optimized Buy ({regime}): {', '.join(reasons)}", confidence, stop_loss_price, take_profit_price

            elif sell_score >= required_threshold and sell_score > buy_score:
                reasons = [s[1] for s in sell_signals]
                confidence = sell_score

                # SELL用のストップロス/テイクプロフィット
                stop_loss_price = current_price + (atr * stop_loss_atr_mult)
                take_profit_price = current_price - (atr * take_profit_atr_mult)

                logger.info(f"🔴 SELL Signal - Confidence={confidence:.2f}, SL=¥{stop_loss_price:.2f}, TP=¥{take_profit_price:.2f}")

                return True, 'SELL', f"Optimized Sell ({regime}): {', '.join(reasons)}", confidence, stop_loss_price, take_profit_price

            # シグナル不足
            logger.info(f"⏸️ No strong signal - Buy={buy_score:.2f}, Sell={sell_score:.2f}, Required={required_threshold:.2f}")
            return False, None, f"Weak signals ({regime})", max(buy_score, sell_score), None, None

        except Exception as e:
            logger.error(f"Error in optimized trading logic: {e}", exc_info=True)
            return False, None, f"Error: {str(e)}", 0.0, None, None

    def _detect_market_regime(self, market_data, historical_df):
        """
        市場レジーム検出（改善版）

        Returns: 'TRENDING', 'RANGING', 'VOLATILE'
        """
        try:
            if historical_df is None or len(historical_df) < 20:
                return 'RANGING'

            # ATRベースのボラティリティ測定
            atr = self._calculate_atr_from_data(historical_df)
            current_price = market_data.get('close', 0)
            atr_pct = (atr / current_price * 100) if current_price > 0 else 0

            # トレンド強度測定（線形回帰の傾き）
            recent_closes = historical_df['close'].tail(20).values
            x = np.arange(len(recent_closes))
            slope, intercept = np.polyfit(x, recent_closes, 1)
            normalized_slope = slope / current_price if current_price > 0 else 0

            # EMAクロス確認
            ema_20 = market_data.get('ema_20', current_price)
            ema_50 = market_data.get('ema_50', current_price)
            ema_diff_pct = abs(ema_20 - ema_50) / ema_50 * 100 if ema_50 > 0 else 0

            logger.info(f"Regime Detection: ATR%={atr_pct:.3f}, Slope={normalized_slope:.6f}, EMA Diff%={ema_diff_pct:.3f}")

            # レジーム判定
            if atr_pct > 4.0:  # 4%以上のボラティリティ
                return 'VOLATILE'
            elif abs(normalized_slope) > 0.01 and ema_diff_pct > 1.0:  # 強いトレンド
                return 'TRENDING'
            else:
                return 'RANGING'

        except Exception as e:
            logger.error(f"Error detecting regime: {e}")
            return 'RANGING'

    def _advanced_trend_analysis(self, market_data, historical_df):
        """
        高度なトレンド分析

        Returns:
            {
                'direction': str,  # STRONG_UP, UP, NEUTRAL, DOWN, STRONG_DOWN
                'strength': float,  # -1.0 ~ 1.0
                'quality': float,   # 0.0 ~ 1.0 (トレンドの信頼性)
            }
        """
        try:
            current_price = market_data.get('close', 0)
            ema_20 = market_data.get('ema_20', current_price)
            ema_50 = market_data.get('ema_50', current_price)

            # 基本的なEMAトレンド
            price_ema_diff = (current_price - ema_20) / ema_20 if ema_20 > 0 else 0
            ema_trend = (ema_20 - ema_50) / ema_50 if ema_50 > 0 else 0

            # 履歴データがある場合は線形回帰も使用
            if historical_df is not None and len(historical_df) >= 20:
                recent_closes = historical_df['close'].tail(20).values
                x = np.arange(len(recent_closes))
                slope, intercept = np.polyfit(x, recent_closes, 1)
                normalized_slope = slope / current_price if current_price > 0 else 0

                # R²値（トレンド品質）計算
                y_pred = slope * x + intercept
                ss_res = np.sum((recent_closes - y_pred) ** 2)
                ss_tot = np.sum((recent_closes - np.mean(recent_closes)) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

                # 総合トレンド強度（線形回帰を重視）
                trend_strength = (normalized_slope * 2 + price_ema_diff + ema_trend) / 4
                trend_quality = r_squared

            else:
                # 履歴データなしの場合はEMAのみ
                trend_strength = (price_ema_diff + ema_trend) / 2
                trend_quality = 0.5  # デフォルト品質

            # トレンド方向分類
            if trend_strength > 0.03:
                direction = 'STRONG_UP'
            elif trend_strength > 0.01:
                direction = 'UP'
            elif trend_strength < -0.03:
                direction = 'STRONG_DOWN'
            elif trend_strength < -0.01:
                direction = 'DOWN'
            else:
                direction = 'NEUTRAL'

            return {
                'direction': direction,
                'strength': trend_strength,
                'quality': max(0.0, min(1.0, trend_quality))
            }

        except Exception as e:
            logger.error(f"Error in trend analysis: {e}")
            return {'direction': 'NEUTRAL', 'strength': 0.0, 'quality': 0.0}

    def _analyze_rsi(self, rsi, trend_direction, regime, oversold_level, overbought_level):
        """RSI分析（レジーム適応型）"""
        signals = []

        if regime == 'TRENDING':
            # トレンド相場：トレンドフォロー重視
            if trend_direction in ['STRONG_DOWN', 'DOWN']:
                if rsi > overbought_level:
                    signals.append(('SELL', 'RSI Pullback Downtrend', 0.8))
            elif trend_direction in ['STRONG_UP', 'UP']:
                if rsi < oversold_level:
                    signals.append(('BUY', 'RSI Dip Uptrend', 0.8))

        elif regime == 'RANGING':
            # レンジ相場：逆張り戦略
            if rsi < oversold_level:
                signals.append(('BUY', 'RSI Oversold Range', 0.7))
            elif rsi > overbought_level:
                signals.append(('SELL', 'RSI Overbought Range', 0.7))

        elif regime == 'VOLATILE':
            # 高ボラティリティ：極端な値のみ
            if rsi < 25:
                signals.append(('BUY', 'RSI Extreme Oversold', 0.6))
            elif rsi > 75:
                signals.append(('SELL', 'RSI Extreme Overbought', 0.6))

        return signals

    def _analyze_macd(self, macd_line, macd_signal, macd_histogram, trend_direction, regime):
        """MACD分析（ヒストグラム重視）"""
        signals = []

        # MACDクロス検出
        is_bullish_cross = macd_line > macd_signal and macd_histogram > 0
        is_bearish_cross = macd_line < macd_signal and macd_histogram < 0

        # ヒストグラム強度
        histogram_strength = abs(macd_histogram)

        if is_bullish_cross:
            # 上昇トレンドまたは中立時のみ採用
            if trend_direction in ['UP', 'STRONG_UP', 'NEUTRAL']:
                if histogram_strength > 1.0:
                    signals.append(('BUY', 'MACD Strong Bullish', 1.5))
                elif histogram_strength > 0.3:
                    signals.append(('BUY', 'MACD Bullish', 1.0))

        elif is_bearish_cross:
            # 下降トレンドまたは中立時のみ採用
            if trend_direction in ['DOWN', 'STRONG_DOWN', 'NEUTRAL']:
                if histogram_strength > 1.0:
                    signals.append(('SELL', 'MACD Strong Bearish', 1.5))
                elif histogram_strength > 0.3:
                    signals.append(('SELL', 'MACD Bearish', 1.0))

        return signals

    def _analyze_bollinger_bands(self, price, bb_upper, bb_lower, bb_middle, trend_direction, regime):
        """ボリンジャーバンド分析"""
        signals = []

        # バンド位置計算
        bb_width = bb_upper - bb_lower
        if bb_width <= 0:
            return signals

        bb_position = (price - bb_lower) / bb_width

        if regime == 'TRENDING':
            # トレンド相場：トレンド方向のみ
            if trend_direction in ['UP', 'STRONG_UP'] and bb_position < 0.2:
                signals.append(('BUY', 'BB Lower Uptrend', 0.7))
            elif trend_direction in ['DOWN', 'STRONG_DOWN'] and bb_position > 0.8:
                signals.append(('SELL', 'BB Upper Downtrend', 0.7))

        elif regime == 'RANGING':
            # レンジ相場：バンドタッチで逆張り
            if bb_position < 0.1:
                signals.append(('BUY', 'BB Bounce Range', 0.8))
            elif bb_position > 0.9:
                signals.append(('SELL', 'BB Rejection Range', 0.8))

        return signals

    def _analyze_ema(self, price, ema_20, ema_50, trend_strength):
        """EMA分析"""
        signals = []

        # EMA配置確認
        if ema_20 > ema_50 * 1.01:  # 明確な上昇配置
            if price > ema_20 * 1.005:
                weight = 0.5 + min(0.5, abs(trend_strength) * 10)
                signals.append(('BUY', 'EMA Bullish Align', weight))

        elif ema_20 < ema_50 * 0.99:  # 明確な下降配置
            if price < ema_20 * 0.995:
                weight = 0.5 + min(0.5, abs(trend_strength) * 10)
                signals.append(('SELL', 'EMA Bearish Align', weight))

        return signals

    def _analyze_price_action(self, historical_df, current_price):
        """プライスアクション分析（追加機能）"""
        signals = []

        try:
            if len(historical_df) < 3:
                return signals

            # 最新3本のローソク足
            last_3 = historical_df.tail(3)

            # ブリッシュエンガルフィング検出
            if len(last_3) >= 2:
                prev_candle = last_3.iloc[-2]
                curr_candle = last_3.iloc[-1]

                # ブリッシュ
                if (prev_candle['close'] < prev_candle['open'] and  # 前が陰線
                    curr_candle['close'] > curr_candle['open'] and  # 現在が陽線
                    curr_candle['open'] < prev_candle['close'] and  # 前の終値より安く始まる
                    curr_candle['close'] > prev_candle['open']):     # 前の始値より高く終わる
                    signals.append(('BUY', 'Bullish Engulfing', 0.6))

                # ベアリッシュ
                elif (prev_candle['close'] > prev_candle['open'] and  # 前が陽線
                      curr_candle['close'] < curr_candle['open'] and  # 現在が陰線
                      curr_candle['open'] > prev_candle['close'] and  # 前の終値より高く始まる
                      curr_candle['close'] < prev_candle['open']):     # 前の始値より安く終わる
                    signals.append(('SELL', 'Bearish Engulfing', 0.6))

        except Exception as e:
            logger.error(f"Error in price action analysis: {e}")

        return signals

    def _calculate_atr_from_data(self, df, period=14):
        """DataFrameからATRを計算"""
        try:
            if df is None or len(df) < period:
                return 0.0

            high = df['high'].tail(period)
            low = df['low'].tail(period)
            close = df['close'].tail(period)

            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())

            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.mean()

            return atr if not pd.isna(atr) else 0.0

        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return 0.0

    def _check_trade_timing(self):
        """取引タイミングチェック（過剰取引防止）"""
        if not self.last_trade_time:
            return True

        elapsed = (datetime.now() - self.last_trade_time).total_seconds()
        return elapsed >= self.min_trade_interval

    def record_trade(self, trade_type, price, result=None):
        """取引記録（パフォーマンス追跡用）"""
        self.last_trade_time = datetime.now()

        trade_record = {
            'timestamp': self.last_trade_time,
            'type': trade_type,
            'price': price,
            'result': result
        }

        self.trade_history.append(trade_record)

        # 古い履歴を削除
        if len(self.trade_history) > self.recent_trades_limit:
            self.trade_history = self.trade_history[-self.recent_trades_limit:]

    def get_performance_stats(self):
        """パフォーマンス統計取得"""
        if not self.trade_history:
            return None

        results = [t['result'] for t in self.trade_history if t.get('result')]

        if not results:
            return None

        wins = sum(1 for r in results if r > 0)
        losses = sum(1 for r in results if r < 0)
        total_pnl = sum(results)

        return {
            'total_trades': len(results),
            'wins': wins,
            'losses': losses,
            'win_rate': wins / len(results) if results else 0,
            'total_pnl': total_pnl,
            'avg_pnl': total_pnl / len(results) if results else 0
        }
