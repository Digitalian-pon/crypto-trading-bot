"""
MACD現在ポジションベース トレーディングロジック v3.21.0

方針:
- クロス待ちをやめ「現在MACDがシグナルラインのどちら側にいるか」でシグナルを出す
- iloc[-2](確定済みローソク足)のMACDポジション(above/below)を見る
  - 'above'(MACD Line > Signal) → BUY方向
  - 'below'(MACD Line < Signal) → SELL方向
- 前回エントリーと同方向の場合はスキップ（即再エントリー防止）
- ポジションクローズ後は last_entry_macd_position をリセット → 次サイクルで即再エントリー可能
- 再起動後も初回サイクルで即トレード可能（last_entry_macd_position=None）

v3.21.0 変更点:
- MACDクロス検出方式を廃止
  - クロス待ちのため長時間シグナルが出ない問題を解消
  - ダウン復帰後も即座にトレード可能
- MACD現在ポジション方式に変更
  - 確定ローソク足(iloc[-2])のMACD位置で判定
  - ヒストグラム強度フィルターは維持（弱すぎるシグナルを除外）
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class OptimizedTradingLogic:
    """
    MACD現在ポジションベース トレーディングロジック v3.21.0

    設計思想:
    - エントリー: 確定済みローソク足(iloc[-2])のMACDが上(above)→BUY / 下(below)→SELL
    - クロス待ちなし: 現在のMACD位置を見るだけなので再起動後も即エントリー可能
    - 同方向再エントリー防止: last_entry_macd_position で制御
    - ポジションクローズ後リセット: record_trade(is_exit=True) で None に戻す → 即再エントリー可能
    - SLクールダウン: SL発動後5分間は新規エントリー禁止（往復ビンタ防止）
    """

    def __init__(self, config=None):
        """初期化 v3.21.0"""
        self.config = config or {}
        self.last_trade_time = None
        self.last_trade_price = None
        self.last_exit_price = None
        self.min_trade_interval = 60  # 1分（チェック間隔に合わせる）

        # シンプルなTP/SL設定（固定%）- リスクリワード比 2:1
        self.take_profit_pct = 0.05   # 5%利確（v3.18.0: 利益を伸ばす）
        self.stop_loss_pct = 0.008    # 0.8%損切り（v3.18.0: 損失を小さく、リスクリワード改善）

        # 取引履歴
        self.trade_history = []
        self.recent_trades_limit = 20

        # v3.21.0: MACD現在ポジションベース追跡
        # None = 未エントリー（再起動直後・クローズ直後）→ 即エントリー可能
        # 'above' = 直前のエントリーがBUY方向
        # 'below' = 直前のエントリーがSELL方向
        self.last_entry_macd_position = None

        # 互換性のため保持（close側で参照される可能性）
        self.last_macd_position = None
        self.pending_cross = None
        self.no_position_cycles = 0

        # v3.20.0: SL後クールダウン（即再エントリー防止）
        self.last_sl_time = None          # 最後のSL発動時刻
        self.sl_cooldown_seconds = 300    # SL後5分間は新規エントリー禁止

        # v3.19.0: ローリング最適化による動的パラメータ
        self.optimized_params = None  # RollingOptimizerからのパラメータ
        self.entry_hist_filter = 0.01  # デフォルト（最適化で上書き可能）
        self.close_hist_filter = 0.003  # デフォルト（最適化で上書き可能）

    def update_parameters(self, params):
        """
        ローリング最適化から最適パラメータを適用（v3.19.0）

        Args:
            params: dict with keys like 'stop_loss_pct', 'entry_hist_filter', etc.
        """
        if params is None:
            return

        old_sl = self.stop_loss_pct
        old_tp = self.take_profit_pct
        old_entry_hist = self.entry_hist_filter
        old_close_hist = self.close_hist_filter

        self.stop_loss_pct = params.get('stop_loss_pct', self.stop_loss_pct)
        self.entry_hist_filter = params.get('entry_hist_filter', self.entry_hist_filter)
        self.close_hist_filter = params.get('close_hist_filter', self.close_hist_filter)
        self.optimized_params = params

        changes = []
        if old_sl != self.stop_loss_pct:
            changes.append(f"SL: {old_sl*100:.1f}%→{self.stop_loss_pct*100:.1f}%")
        if old_entry_hist != self.entry_hist_filter:
            changes.append(f"EntryHist: {old_entry_hist:.3f}→{self.entry_hist_filter:.3f}")
        if old_close_hist != self.close_hist_filter:
            changes.append(f"CloseHist: {old_close_hist:.3f}→{self.close_hist_filter:.3f}")

        if changes:
            logger.info(f"🧠 [OPTIMIZER] Parameters updated: {', '.join(changes)}")

    def should_trade(self, market_data, historical_df=None, skip_price_filter=False, is_tpsl_continuation=False):
        """
        取引判定 - v3.21.0 MACD現在ポジションベース

        クロス待ちではなく「今MACDがシグナルラインのどちら側にいるか」でシグナルを出す。
        - 再起動後も初回サイクルで即エントリー可能
        - ポジションクローズ後も即再エントリー可能
        - 同方向への再エントリーは last_entry_macd_position でブロック

        ルール:
        1. 確定済みローソク足(iloc[-2])のMACDポジションを確認
        2. 'above'(MACD Line > Signal Line) → BUY方向
        3. 'below'(MACD Line < Signal Line) → SELL方向
        4. 前回エントリー方向と同じならスキップ（無限ループ防止）
        5. ポジションクローズ後は last_entry_macd_position=None → 次サイクルで即エントリー

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

            logger.info(f"📊 [MACD v3.21.0 Position] Price=¥{current_price:.3f}")
            logger.info(f"   Live MACD: Line={macd_line:.6f}, Signal={macd_signal:.6f}, Hist={macd_histogram:.6f}")

            # === 確定済みローソク足(iloc[-2])のMACD位置を取得 ===
            confirmed_histogram = abs(macd_histogram)  # フォールバック: ライブ値
            confirmed_position = 'above' if macd_line > macd_signal else 'below'  # フォールバック

            if historical_df is not None and len(historical_df) >= 3 and 'macd_line' in historical_df.columns:
                confirmed = historical_df.iloc[-2]
                confirmed_macd_line = float(confirmed.get('macd_line', 0))
                confirmed_macd_signal = float(confirmed.get('macd_signal', 0))
                confirmed_histogram = abs(confirmed_macd_line - confirmed_macd_signal)
                confirmed_position = 'above' if confirmed_macd_line > confirmed_macd_signal else 'below'

                logger.info(f"   Confirmed candle MACD: Line={confirmed_macd_line:.6f}, Signal={confirmed_macd_signal:.6f}")

            # 互換性のため last_macd_position を更新（close側ロジックで参照される場合に備える）
            self.last_macd_position = confirmed_position

            # EMA参考ログ
            ema_trend = 'up' if ema_20 > ema_50 else 'down'
            ema_diff_pct = abs(ema_20 - ema_50) / ema_50 * 100 if ema_50 > 0 else 0
            logger.info(f"   MACD Position: {confirmed_position}, Hist: {confirmed_histogram:.6f}")
            logger.info(f"   Last Entry Direction: {self.last_entry_macd_position}, EMA: {ema_trend} ({ema_diff_pct:.2f}%)")

            # === タイミングチェック（SLクールダウンのみ）===
            if not skip_price_filter:
                if not self._check_trade_timing():
                    logger.info(f"   ⏳ Trade timing blocked (SL cooldown or min interval)")
                    return False, None, "Trade timing blocked", 0.0, None, None

            # === ヒストグラム強度フィルター（弱すぎるシグナルを除外）===
            if confirmed_histogram < self.entry_hist_filter:
                self.no_position_cycles += 1
                logger.info(f"   ⚠️ Weak signal (hist={confirmed_histogram:.6f} < {self.entry_hist_filter:.3f}) - waiting")
                return False, None, f"Weak signal (hist={confirmed_histogram:.6f})", 0.0, None, None

            # === 同方向への再エントリー防止 ===
            if self.last_entry_macd_position == confirmed_position:
                self.no_position_cycles += 1
                logger.info(f"   ↔️ Already entered in '{confirmed_position}' direction - waiting for direction change")
                return False, None, f"Already in {confirmed_position} direction", 0.0, None, None

            # === シグナル強度計算 ===
            if confirmed_histogram > 0.03:
                confidence = 2.5
            elif confirmed_histogram > 0.01:
                confidence = 2.0
            else:
                confidence = 1.5

            self.no_position_cycles = 0

            # === BUY / SELL シグナル生成 ===
            if confirmed_position == 'above':
                reason = f'MACD Position BUY (above signal, hist={confirmed_histogram:.4f})'
                stop_loss = current_price * (1 - self.stop_loss_pct)
                take_profit = current_price * (1 + self.take_profit_pct)
                logger.info(f"   🟢 BUY SIGNAL: {reason} (confidence={confidence:.2f})")
                self.last_entry_macd_position = confirmed_position
                return True, 'BUY', reason, confidence, stop_loss, take_profit
            else:
                reason = f'MACD Position SELL (below signal, hist={confirmed_histogram:.4f})'
                stop_loss = current_price * (1 + self.stop_loss_pct)
                take_profit = current_price * (1 - self.take_profit_pct)
                logger.info(f"   🔴 SELL SIGNAL: {reason} (confidence={confidence:.2f})")
                self.last_entry_macd_position = confirmed_position
                return True, 'SELL', reason, confidence, stop_loss, take_profit

        except Exception as e:
            logger.error(f"Error in MACD trading logic: {e}", exc_info=True)
            return False, None, f"Error: {str(e)}", 0.0, None, None

    def _check_trade_timing(self):
        """取引タイミングチェック（v3.20.0: SLクールダウン追加）"""
        if not self.last_trade_time:
            return True

        elapsed = (datetime.now(timezone.utc) - self.last_trade_time).total_seconds()
        if elapsed < self.min_trade_interval:
            return False

        # v3.20.0: SL後クールダウン（5分間は新規エントリーを禁止）
        if self.last_sl_time is not None:
            sl_elapsed = (datetime.now(timezone.utc) - self.last_sl_time).total_seconds()
            if sl_elapsed < self.sl_cooldown_seconds:
                remaining = self.sl_cooldown_seconds - sl_elapsed
                logger.info(f"   ⏳ [SL Cooldown] {remaining:.0f}s remaining - blocking new entry")
                return False

        return True

    def record_stop_loss(self, side):
        """損切り記録（v3.20.0: 5分クールダウン開始）"""
        self.last_sl_time = datetime.now(timezone.utc)
        logger.info(f"📝 Stop loss recorded: {side} - 5min cooldown started")
        try:
            with open('bot_execution_log.txt', 'a') as f:
                f.write(f"SL_COOLDOWN_START: {side}, blocking new entry for {self.sl_cooldown_seconds}s\n")
        except:
            pass

    def record_trade(self, trade_type, price, result=None, is_exit=False):
        """取引記録"""
        self.last_trade_time = datetime.now(timezone.utc)

        if is_exit:
            self.last_exit_price = price
            # v3.21.0: クローズ後は last_entry_macd_position をリセット
            # → 次サイクルで現在のMACD位置に基づき即再エントリー可能
            self.last_entry_macd_position = None
            logger.info(f"💰 Exit recorded: ¥{price:.2f} - MACD entry direction reset (ready for re-entry)")
        else:
            self.last_trade_price = price
            self.no_position_cycles = 0
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
