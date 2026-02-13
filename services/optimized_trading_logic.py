"""
MACD主体トレーディングロジック v3.3.0
MACDポジションベースエントリー + クロスベース決済

方針:
- エントリー: MACDの位置で判断（Line > Signal → BUY、Line < Signal → SELL）
- 決済: MACDクロスで判断（反対クロス発生時に決済）
- EMAトレンドフィルター: トレンド方向の取引のみ許可
- レンジフィルター撤去（v3.3.0）
- リスクリワード比 2:1（利確3%、損切り1.5%）
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class OptimizedTradingLogic:
    """
    MACD主体トレーディングロジック v3.3.0

    設計思想:
    - エントリー: MACDポジションベース（Line > Signal → BUY、Line < Signal → SELL）
    - 決済: MACDクロスベース（反対クロスで決済）
    - EMAトレンドフィルターでトレンド方向の取引のみ許可
    - レンジフィルター撤去（シグナルがあれば取引実行）
    - リスクリワード比 2:1（TP +3% / SL -1.5%）
    """

    def __init__(self, config=None):
        """初期化"""
        self.config = config or {}
        self.last_trade_time = None
        self.last_trade_price = None
        self.last_exit_price = None
        self.min_trade_interval = 300  # 5分

        # シンプルなTP/SL設定（固定%）- リスクリワード比 2:1
        self.take_profit_pct = 0.03   # 3%利確
        self.stop_loss_pct = 0.015    # 1.5%損切り

        # 取引履歴
        self.trade_history = []
        self.recent_trades_limit = 20

        # MACD状態追跡
        self.last_macd_position = None  # 'above' or 'below'

    def should_trade(self, market_data, historical_df=None, skip_price_filter=False, is_tpsl_continuation=False):
        """
        取引判定 - v3.2.0 MACDポジションベースエントリー

        ルール:
        1. MACD Line > Signal + 上昇トレンド → BUY
        2. MACD Line < Signal + 下降トレンド → SELL
        3. EMAフィルター: 上昇トレンド=BUYのみ、下降トレンド=SELLのみ
        4. 決済はクロスベース（bot側で処理）

        Returns:
            (should_trade, trade_type, reason, confidence, stop_loss, take_profit)
        """
        try:
            # === 基本データ取得 ===
            current_price = market_data.get('close', 0)
            macd_line = market_data.get('macd_line', 0)
            macd_signal = market_data.get('macd_signal', 0)
            macd_histogram = market_data.get('macd_histogram', 0)
            ema_20 = market_data.get('ema_20', current_price)
            ema_50 = market_data.get('ema_50', current_price)

            logger.info(f"📊 [MACD v3.2.0 Position-Based] Price=¥{current_price:.3f}")
            logger.info(f"   MACD Line: {macd_line:.6f}")
            logger.info(f"   MACD Signal: {macd_signal:.6f}")
            logger.info(f"   MACD Histogram: {macd_histogram:.6f}")

            # === MACDポジション判定 ===
            macd_position = 'above' if macd_line > macd_signal else 'below'

            # クロス検出（ログ用・決済判定のstate追跡用）
            if self.last_macd_position is not None:
                if self.last_macd_position == 'below' and macd_position == 'above':
                    logger.info(f"🟢 MACD GOLDEN CROSS detected!")
                elif self.last_macd_position == 'above' and macd_position == 'below':
                    logger.info(f"🔴 MACD DEATH CROSS detected!")

            # 状態を更新
            self.last_macd_position = macd_position

            # === シグナル強度計算 ===
            histogram_strength = abs(macd_histogram)

            if histogram_strength > 0.03:
                confidence = 2.5
            elif histogram_strength > 0.01:
                confidence = 2.0
            elif histogram_strength > 0.005:
                confidence = 1.5
            else:
                confidence = 1.0

            # === EMAトレンド確認 ===
            ema_trend = 'up' if ema_20 > ema_50 else 'down'
            ema_diff_pct = abs(ema_20 - ema_50) / ema_50 * 100 if ema_50 > 0 else 0

            logger.info(f"   MACD Position: {macd_position.upper()} | EMA Trend: {ema_trend} ({ema_diff_pct:.2f}%)")

            # === レンジ相場フィルター無効化（v3.3.0） ===
            # フィルターを撤去し、シグナルがあれば取引を実行
            logger.info(f"   EMA spread: {ema_diff_pct:.3f}% | Confidence: {confidence:.1f} (filters disabled)")

            # === 取引タイミングフィルター ===
            if not skip_price_filter:
                if not self._check_trade_timing():
                    return False, None, "Trade interval too short", 0.0, None, None

                if self.last_trade_price is not None:
                    price_change = abs(current_price - self.last_trade_price) / self.last_trade_price
                    if price_change < 0.005:
                        return False, None, f"Price change too small", 0.0, None, None

            # === 売買判定（MACDポジションベース + EMAトレンドフォロー） ===
            # v3.2.0: MACDの位置でシグナル、クロスを待たない

            if macd_position == 'above':
                # MACD Line > Signal → BUY候補
                if ema_trend == 'down':
                    logger.info(f"🚫 MACD Bullish BLOCKED - Downtrend (EMA20 < EMA50)")
                    return False, None, "MACD bullish but downtrend", confidence, None, None
                else:
                    take_profit = current_price * (1 + self.take_profit_pct)
                    stop_loss = current_price * (1 - self.stop_loss_pct)
                    logger.info(f"🟢 BUY SIGNAL - MACD above signal + Uptrend")
                    logger.info(f"   Confidence: {confidence:.2f} | TP: ¥{take_profit:.2f} | SL: ¥{stop_loss:.2f}")
                    return True, 'BUY', 'MACD Bullish + Uptrend', confidence, stop_loss, take_profit

            elif macd_position == 'below':
                # MACD Line < Signal → SELL候補
                if ema_trend == 'up':
                    logger.info(f"🚫 MACD Bearish BLOCKED - Uptrend (EMA20 > EMA50)")
                    return False, None, "MACD bearish but uptrend", confidence, None, None
                else:
                    take_profit = current_price * (1 - self.take_profit_pct)
                    stop_loss = current_price * (1 + self.stop_loss_pct)
                    logger.info(f"🔴 SELL SIGNAL - MACD below signal + Downtrend")
                    logger.info(f"   Confidence: {confidence:.2f} | TP: ¥{take_profit:.2f} | SL: ¥{stop_loss:.2f}")
                    return True, 'SELL', 'MACD Bearish + Downtrend', confidence, stop_loss, take_profit

            return False, None, "No signal", confidence, None, None

        except Exception as e:
            logger.error(f"Error in MACD trading logic: {e}", exc_info=True)
            return False, None, f"Error: {str(e)}", 0.0, None, None

    def _check_trade_timing(self):
        """取引タイミングチェック"""
        if not self.last_trade_time:
            return True

        elapsed = (datetime.now(timezone.utc) - self.last_trade_time).total_seconds()
        return elapsed >= self.min_trade_interval

    def record_stop_loss(self, side):
        """損切り記録"""
        logger.info(f"📝 Stop loss recorded: {side}")

    def record_trade(self, trade_type, price, result=None, is_exit=False):
        """取引記録"""
        self.last_trade_time = datetime.now(timezone.utc)

        if is_exit:
            self.last_exit_price = price
            logger.info(f"💰 Exit recorded: ¥{price:.2f}")
        else:
            self.last_trade_price = price
            logger.info(f"📝 Entry recorded: ¥{price:.2f}")

        # ファイルログ
        try:
            with open('bot_execution_log.txt', 'a') as f:
                action = "EXIT" if is_exit else "ENTRY"
                f.write(f"TRADE_{action}: {trade_type.upper()} @ ¥{price:.2f}\n")
        except:
            pass

        trade_record = {
            'timestamp': self.last_trade_time,
            'type': trade_type,
            'price': price,
            'result': result,
            'is_exit': is_exit
        }

        self.trade_history.append(trade_record)

        if len(self.trade_history) > self.recent_trades_limit:
            self.trade_history = self.trade_history[-self.recent_trades_limit:]

    def get_performance_stats(self):
        """パフォーマンス統計"""
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

    # === 互換性のためのダミーメソッド ===
    def _calculate_atr_from_data(self, df, period=14):
        """ATR計算（互換性用）"""
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
        except:
            return 0.0

    def _detect_market_regime(self, market_data, historical_df):
        """市場レジーム検出（互換性用 - 常にTRENDINGを返す）"""
        return 'TRENDING'

    # レジームパラメータ（互換性用）
    regime_params = {
        'TRENDING': {
            'stop_loss_atr_mult': 1.5,
            'take_profit_atr_mult': 3.0,
        },
        'RANGING': {
            'stop_loss_atr_mult': 1.5,
            'take_profit_atr_mult': 3.0,
        },
        'VOLATILE': {
            'stop_loss_atr_mult': 2.0,
            'take_profit_atr_mult': 4.0,
        }
    }
