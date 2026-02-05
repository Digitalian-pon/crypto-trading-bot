"""
MACD専用トレーディングロジック v4.0.0
純粋なMACDクロスのみ - シンプル

ルール:
- MACDゴールデンクロス → BUY
- MACDデッドクロス → SELL
- それ以外のフィルターなし
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class OptimizedTradingLogic:
    """
    純粋なMACDクロスのみのトレーディングロジック v4.0.0
    """

    def __init__(self, config=None):
        """初期化"""
        self.config = config or {}
        self.last_trade_time = None
        self.last_trade_price = None
        self.last_exit_price = None

        # シンプルなTP/SL設定（固定%）
        self.take_profit_pct = 0.02   # 2%利確
        self.stop_loss_pct = 0.015    # 1.5%損切り

        # 取引履歴
        self.trade_history = []
        self.recent_trades_limit = 20

        # MACD状態追跡
        self.last_macd_position = None  # 'above' or 'below'

    def should_trade(self, market_data, historical_df=None, skip_price_filter=False, is_tpsl_continuation=False):
        """
        取引判定 - 純粋MACDクロスのみ v4.0.0

        ルール:
        - MACDゴールデンクロス（MACD Line > Signal Line に変化）→ BUY
        - MACDデッドクロス（MACD Line < Signal Line に変化）→ SELL
        - フィルターなし

        Returns:
            (should_trade, trade_type, reason, confidence, stop_loss, take_profit)
        """
        try:
            current_price = market_data.get('close', 0)
            macd_line = market_data.get('macd_line', 0)
            macd_signal = market_data.get('macd_signal', 0)
            macd_histogram = market_data.get('macd_histogram', 0)

            logger.info(f"📊 [MACD PURE v4.0.0] Price=¥{current_price:.3f}")
            logger.info(f"   MACD Line: {macd_line:.6f}")
            logger.info(f"   MACD Signal: {macd_signal:.6f}")
            logger.info(f"   Histogram: {macd_histogram:.6f}")

            # MACDクロス判定
            macd_position = 'above' if macd_line > macd_signal else 'below'

            is_golden_cross = False
            is_death_cross = False

            if self.last_macd_position is not None:
                if self.last_macd_position == 'below' and macd_position == 'above':
                    is_golden_cross = True
                    logger.info(f"🟢 GOLDEN CROSS detected!")
                elif self.last_macd_position == 'above' and macd_position == 'below':
                    is_death_cross = True
                    logger.info(f"🔴 DEATH CROSS detected!")

            self.last_macd_position = macd_position

            # 信頼度（ログ用）
            confidence = min(abs(macd_histogram) * 50, 3.0)
            if confidence < 0.5:
                confidence = 0.5

            # BUY: ゴールデンクロス
            if is_golden_cross:
                take_profit = current_price * (1 + self.take_profit_pct)
                stop_loss = current_price * (1 - self.stop_loss_pct)
                logger.info(f"🟢 BUY SIGNAL - MACD Golden Cross")
                logger.info(f"   TP: ¥{take_profit:.2f} (+{self.take_profit_pct*100:.1f}%)")
                logger.info(f"   SL: ¥{stop_loss:.2f} (-{self.stop_loss_pct*100:.1f}%)")
                return True, 'BUY', 'MACD Golden Cross', confidence, stop_loss, take_profit

            # SELL: デッドクロス
            if is_death_cross:
                take_profit = current_price * (1 - self.take_profit_pct)
                stop_loss = current_price * (1 + self.stop_loss_pct)
                logger.info(f"🔴 SELL SIGNAL - MACD Death Cross")
                logger.info(f"   TP: ¥{take_profit:.2f} (-{self.take_profit_pct*100:.1f}%)")
                logger.info(f"   SL: ¥{stop_loss:.2f} (+{self.stop_loss_pct*100:.1f}%)")
                return True, 'SELL', 'MACD Death Cross', confidence, stop_loss, take_profit

            # クロスなし
            logger.info(f"⏸️ No cross - MACD {macd_position.upper()}, waiting...")
            return False, None, "Waiting for MACD cross", confidence, None, None

        except Exception as e:
            logger.error(f"Error in MACD trading logic: {e}", exc_info=True)
            return False, None, f"Error: {str(e)}", 0.0, None, None

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
        """市場レジーム検出（互換性用）"""
        return 'TRENDING'

    regime_params = {
        'TRENDING': {'stop_loss_atr_mult': 1.5, 'take_profit_atr_mult': 3.0},
        'RANGING': {'stop_loss_atr_mult': 1.5, 'take_profit_atr_mult': 3.0},
        'VOLATILE': {'stop_loss_atr_mult': 2.0, 'take_profit_atr_mult': 4.0},
    }
