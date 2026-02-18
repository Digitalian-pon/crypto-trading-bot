"""
MACD主体トレーディングロジック v3.6.0
MACDクロスベースエントリー + EMAハイブリッドフィルター + トレーリングストップ決済

方針:
- エントリー: MACDクロスの瞬間のみ（ゴールデンクロス→BUY、デッドクロス→SELL）
- ヒストグラムフィルター: |histogram| < 0.005 のクロスは無視（ノイズ除去）
- EMAハイブリッドフィルター:
  - EMA差 > 0.3% で逆方向 → エントリー禁止（強いトレンドに逆らわない）
  - EMA差 <= 0.3% → confidence調整のみ（順方向+30%、逆方向-30%）
- 決済: トレーリングストップ + MACDクロス確認（bot側で処理）
- リスクリワード比: トレーリングストップで自動管理
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class OptimizedTradingLogic:
    """
    MACD主体トレーディングロジック v3.6.0

    設計思想:
    - エントリー: MACDクロスベース（クロスの瞬間のみ取引）
    - ヒストグラムフィルター: |histogram| < 0.005 → ノイズとして無視
    - EMAハイブリッドフィルター: 強トレンド逆方向はブロック、弱い場合はconfidence調整
    - 決済: トレーリングストップ + MACDクロス確認（bot側で処理）
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
        取引判定 - v3.5.0 MACDクロスベースエントリー

        ルール:
        1. MACDゴールデンクロス（below→above遷移）→ BUY
        2. MACDデッドクロス（above→below遷移）→ SELL
        3. クロスなし → 取引なし（ポジションベースの常時シグナルを廃止）
        4. EMAトレンドはconfidence調整のみ（順方向+30%、逆方向-30%）
           → ブロックしない、シグナルが出れば必ず取引

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

            logger.info(f"📊 [MACD v3.5.0 Cross-Based] Price=¥{current_price:.3f}")
            logger.info(f"   MACD Line: {macd_line:.6f}, Signal: {macd_signal:.6f}, Hist: {macd_histogram:.6f}")

            # === MACDポジション判定 ===
            macd_position = 'above' if macd_line > macd_signal else 'below'

            # === クロス検出（エントリーの核心） ===
            is_golden_cross = False
            is_death_cross = False

            if self.last_macd_position is not None:
                if self.last_macd_position == 'below' and macd_position == 'above':
                    is_golden_cross = True
                    logger.info(f"🟢 MACD GOLDEN CROSS detected!")
                elif self.last_macd_position == 'above' and macd_position == 'below':
                    is_death_cross = True
                    logger.info(f"🔴 MACD DEATH CROSS detected!")

            # 状態を更新
            self.last_macd_position = macd_position

            # === クロスなし → 取引なし ===
            if not is_golden_cross and not is_death_cross:
                logger.info(f"   No MACD cross - waiting (state: {macd_position})")
                return False, None, "No MACD cross", 0.0, None, None

            # === ヒストグラム強度フィルター（ノイズ除去） ===
            histogram_strength = abs(macd_histogram)

            if histogram_strength < 0.005:
                cross_type = "Golden Cross" if is_golden_cross else "Death Cross"
                logger.info(f"   🚫 {cross_type} IGNORED - histogram too weak ({macd_histogram:.6f}, threshold: 0.005)")
                return False, None, f"Weak {cross_type} (histogram={macd_histogram:.6f})", 0.0, None, None

            # === シグナル強度計算 ===
            if histogram_strength > 0.03:
                confidence = 2.5
            elif histogram_strength > 0.01:
                confidence = 2.0
            else:
                confidence = 1.5

            # === EMAトレンド確認（ハイブリッドフィルター） ===
            ema_trend = 'up' if ema_20 > ema_50 else 'down'
            ema_diff_pct = abs(ema_20 - ema_50) / ema_50 * 100 if ema_50 > 0 else 0

            logger.info(f"   EMA Trend: {ema_trend} ({ema_diff_pct:.2f}%)")

            # === 取引タイミングフィルター ===
            if not skip_price_filter:
                if not self._check_trade_timing():
                    return False, None, "Trade interval too short", 0.0, None, None

                if self.last_trade_price is not None:
                    price_change = abs(current_price - self.last_trade_price) / self.last_trade_price
                    if price_change < 0.003:
                        return False, None, "Price change too small", 0.0, None, None

            # === 売買判定（MACDクロス + EMAハイブリッドフィルター） ===
            if is_golden_cross:
                # EMAフィルター: 強い下降トレンドではBUYをブロック
                if ema_trend == 'down' and ema_diff_pct > 0.3:
                    logger.info(f"   🚫 Golden Cross BLOCKED - Strong downtrend (EMA diff: {ema_diff_pct:.2f}% > 0.3%)")
                    return False, None, f"Golden Cross blocked by downtrend ({ema_diff_pct:.2f}%)", 0.0, None, None

                # EMAでconfidence調整
                if ema_trend == 'up':
                    confidence *= 1.3
                    reason = 'MACD Golden Cross + Uptrend'
                else:
                    confidence *= 0.7
                    reason = 'MACD Golden Cross (weak trend)'

                stop_loss = current_price * (1 - self.stop_loss_pct)
                take_profit = current_price * (1 + self.take_profit_pct)
                logger.info(f"🟢 BUY SIGNAL: {reason} (confidence={confidence:.2f})")
                return True, 'BUY', reason, confidence, stop_loss, take_profit

            elif is_death_cross:
                # EMAフィルター: 強い上昇トレンドではSELLをブロック
                if ema_trend == 'up' and ema_diff_pct > 0.3:
                    logger.info(f"   🚫 Death Cross BLOCKED - Strong uptrend (EMA diff: {ema_diff_pct:.2f}% > 0.3%)")
                    return False, None, f"Death Cross blocked by uptrend ({ema_diff_pct:.2f}%)", 0.0, None, None

                # EMAでconfidence調整
                if ema_trend == 'down':
                    confidence *= 1.3
                    reason = 'MACD Death Cross + Downtrend'
                else:
                    confidence *= 0.7
                    reason = 'MACD Death Cross (weak trend)'

                stop_loss = current_price * (1 + self.stop_loss_pct)
                take_profit = current_price * (1 - self.take_profit_pct)
                logger.info(f"🔴 SELL SIGNAL: {reason} (confidence={confidence:.2f})")
                return True, 'SELL', reason, confidence, stop_loss, take_profit

            return False, None, "No signal", 0.0, None, None

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
