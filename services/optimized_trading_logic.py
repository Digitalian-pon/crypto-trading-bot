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

        # v3.26.0: アンチチェイスフィルター（SL発動価格帯での再エントリー禁止）
        self.last_sl_price = None                # 最後のSL発動価格
        self.sl_price_range_pct = 0.005          # SL価格から±0.5%以内は禁止
        self.sl_price_cooldown_seconds = 1800    # 30分間は価格帯ブロック

        # v3.27.1: サーキットブレーカー（連敗で自動停止 / 閾値5に緩和）
        self.consecutive_losses = 0                   # 連敗カウンター
        self.circuit_breaker_threshold = 5            # 5連敗でトリップ（v3.27.1: 3→5に緩和）
        self.circuit_breaker_tripped_at = None        # トリップ時刻
        self.circuit_breaker_cooldown_seconds = 21600 # 6時間停止
        self.circuit_breaker_state_file = 'circuit_breaker_state.txt'
        self._load_circuit_breaker_state()

        # v3.19.0: ローリング最適化による動的パラメータ
        self.optimized_params = None  # RollingOptimizerからのパラメータ
        self.entry_hist_filter = 0.01  # デフォルト（最適化で上書き可能）
        self.close_hist_filter = 0.003  # デフォルト（最適化で上書き可能）

        # v3.28.0: レンジ相場フィルター（BB幅で判定）
        # BB幅(%) = (BB_upper - BB_lower) / current_price * 100
        # SL=1.2%なのにBB幅が0.4%だと、BB端→端の到達=価格1%未満→TP到達不可・SL頻発
        # 閾値0.8%: SL+BE+手数料の合計を上回る最低値幅を要求
        self.range_filter_bb_width_pct = 0.8  # 0.8%未満はレンジ判定でエントリー停止

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

            # === v3.27.0: サーキットブレーカーチェック（最優先）===
            cb_ok, cb_reason = self._check_circuit_breaker()
            if not cb_ok:
                self.no_position_cycles += 1
                logger.warning(f"   🚨 {cb_reason}")
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"CIRCUIT_BREAKER_BLOCK: {cb_reason}\n")
                except:
                    pass
                return False, None, cb_reason, 0.0, None, None

            # === タイミングチェック（SLクールダウンのみ）===
            if not skip_price_filter:
                if not self._check_trade_timing():
                    logger.info(f"   ⏳ Trade timing blocked (SL cooldown or min interval)")
                    return False, None, "Trade timing blocked", 0.0, None, None

            # === v3.26.0: アンチチェイスフィルター（SL価格帯での再エントリー禁止）===
            anti_chase_ok, anti_chase_reason = self._check_anti_chase(current_price)
            if not anti_chase_ok:
                self.no_position_cycles += 1
                logger.info(f"   🚫 {anti_chase_reason}")
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"ANTI_CHASE_BLOCK: {anti_chase_reason}\n")
                except:
                    pass
                return False, None, anti_chase_reason, 0.0, None, None

            # === ヒストグラム強度フィルター（弱すぎるシグナルを除外）===
            if confirmed_histogram < self.entry_hist_filter:
                self.no_position_cycles += 1
                logger.info(f"   ⚠️ Weak signal (hist={confirmed_histogram:.6f} < {self.entry_hist_filter:.3f}) - waiting")
                return False, None, f"Weak signal (hist={confirmed_histogram:.6f})", 0.0, None, None

            # === v3.28.1: レンジ相場フィルター（BB幅で判定・NaN対応）===
            # 値幅が狭すぎる時はSL頻発・TP不能でエントリーしない
            bb_check_done = False
            if historical_df is not None and 'bb_upper' in historical_df.columns and 'bb_lower' in historical_df.columns:
                try:
                    # market_data (last_row) から取得を試みる（iloc[-2] が NaN の場合に備えて last_row も確認）
                    bb_upper_md = market_data.get('bb_upper') if isinstance(market_data, dict) else None
                    bb_lower_md = market_data.get('bb_lower') if isinstance(market_data, dict) else None

                    last_bb = historical_df.iloc[-2]
                    bb_upper_raw = last_bb.get('bb_upper')
                    bb_lower_raw = last_bb.get('bb_lower')

                    # NaN/None チェック → market_data からフォールバック
                    import math
                    def _valid(v):
                        try:
                            return v is not None and not math.isnan(float(v)) and float(v) > 0
                        except (TypeError, ValueError):
                            return False

                    if _valid(bb_upper_raw) and _valid(bb_lower_raw):
                        bb_upper = float(bb_upper_raw)
                        bb_lower = float(bb_lower_raw)
                    elif _valid(bb_upper_md) and _valid(bb_lower_md):
                        bb_upper = float(bb_upper_md)
                        bb_lower = float(bb_lower_md)
                        logger.info(f"   📊 BB fallback to market_data (iloc[-2] was NaN)")
                    else:
                        logger.warning(f"   ⚠️ BB values invalid: iloc[-2] upper={bb_upper_raw} lower={bb_lower_raw}, market_data upper={bb_upper_md} lower={bb_lower_md}")
                        bb_upper = 0
                        bb_lower = 0

                    if bb_upper > 0 and bb_lower > 0 and current_price > 0:
                        bb_check_done = True
                        bb_width_pct = (bb_upper - bb_lower) / current_price * 100
                        if bb_width_pct < self.range_filter_bb_width_pct:
                            self.no_position_cycles += 1
                            block_msg = f"Range market (BB width={bb_width_pct:.2f}% < {self.range_filter_bb_width_pct}%)"
                            logger.info(f"   📊 {block_msg} - blocking entry")
                            try:
                                with open('bot_execution_log.txt', 'a') as f:
                                    f.write(f"RANGE_FILTER_BLOCK: BB width {bb_width_pct:.2f}% < {self.range_filter_bb_width_pct}%, price=¥{current_price:.3f}\n")
                            except:
                                pass
                            return False, None, block_msg, 0.0, None, None
                        else:
                            logger.info(f"   📊 BB width OK: {bb_width_pct:.2f}% >= {self.range_filter_bb_width_pct}%")
                except Exception as e:
                    logger.warning(f"   ⚠️ BB width check failed: {e}", exc_info=True)
            else:
                cols_info = list(historical_df.columns) if historical_df is not None else 'None'
                logger.warning(f"   ⚠️ BB columns missing — historical_df cols: {cols_info}")

            if not bb_check_done:
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"RANGE_FILTER_SKIPPED: bb columns invalid or missing\n")
                except:
                    pass

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

    def record_stop_loss(self, side, price=None):
        """損切り記録（v3.20.0: 5分クールダウン / v3.26.0: 価格帯ブロック）"""
        self.last_sl_time = datetime.now(timezone.utc)
        if price is not None:
            self.last_sl_price = price
            logger.info(f"📝 Stop loss recorded: {side} @ ¥{price:.3f} - 5min cooldown + 30min price-zone block")
        else:
            logger.info(f"📝 Stop loss recorded: {side} - 5min cooldown started")
        try:
            with open('bot_execution_log.txt', 'a') as f:
                if price is not None:
                    f.write(f"SL_COOLDOWN_START: {side} @ ¥{price:.3f}, time={self.sl_cooldown_seconds}s, price_zone=±{self.sl_price_range_pct*100:.1f}% for {self.sl_price_cooldown_seconds}s\n")
                else:
                    f.write(f"SL_COOLDOWN_START: {side}, blocking new entry for {self.sl_cooldown_seconds}s\n")
        except:
            pass

    def _load_circuit_breaker_state(self):
        """v3.27.0: サーキットブレーカー状態をディスクから復元（再起動耐性）"""
        try:
            import os
            if not os.path.exists(self.circuit_breaker_state_file):
                return
            with open(self.circuit_breaker_state_file, 'r') as f:
                content = f.read().strip()
            if not content:
                return
            parts = dict(line.split('=', 1) for line in content.split('\n') if '=' in line)
            self.consecutive_losses = int(parts.get('consecutive_losses', 0))
            tripped = parts.get('tripped_at', '')
            if tripped and tripped != 'None':
                self.circuit_breaker_tripped_at = datetime.fromisoformat(tripped)
            logger.info(f"🔌 [Circuit Breaker] State loaded: losses={self.consecutive_losses}, tripped_at={self.circuit_breaker_tripped_at}")

            # v3.27.1: 閾値緩和時の自動リセット（losses < 新threshold ならトリップ解除）
            if self.circuit_breaker_tripped_at is not None and self.consecutive_losses < self.circuit_breaker_threshold:
                logger.info(f"🔌 [Circuit Breaker] Auto-reset: losses={self.consecutive_losses} < threshold={self.circuit_breaker_threshold}")
                self.circuit_breaker_tripped_at = None
                self.consecutive_losses = 0
                self._save_circuit_breaker_state()
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"CIRCUIT_BREAKER_AUTO_RESET: threshold loosened, clearing trip\n")
                except:
                    pass
        except Exception as e:
            logger.warning(f"Could not load circuit breaker state: {e}")

    def _save_circuit_breaker_state(self):
        """v3.27.0: サーキットブレーカー状態をディスクに保存"""
        try:
            tripped_str = self.circuit_breaker_tripped_at.isoformat() if self.circuit_breaker_tripped_at else 'None'
            with open(self.circuit_breaker_state_file, 'w') as f:
                f.write(f"consecutive_losses={self.consecutive_losses}\n")
                f.write(f"tripped_at={tripped_str}\n")
        except Exception as e:
            logger.warning(f"Could not save circuit breaker state: {e}")

    def _check_circuit_breaker(self):
        """v3.27.0: サーキットブレーカーチェック
        Returns: (allowed: bool, reason: str or None)
        """
        if self.circuit_breaker_tripped_at is None:
            return True, None
        elapsed = (datetime.now(timezone.utc) - self.circuit_breaker_tripped_at).total_seconds()
        if elapsed >= self.circuit_breaker_cooldown_seconds:
            logger.info(f"🔌 [Circuit Breaker] Cooldown expired ({elapsed:.0f}s) - resetting")
            self.circuit_breaker_tripped_at = None
            self.consecutive_losses = 0
            self._save_circuit_breaker_state()
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"CIRCUIT_BREAKER_RESET: cooldown expired, resuming trading\n")
            except:
                pass
            return True, None
        remaining = self.circuit_breaker_cooldown_seconds - elapsed
        reason = f"Circuit breaker tripped ({self.consecutive_losses} consecutive losses) - {remaining/3600:.1f}h remaining"
        return False, reason

    def _record_loss(self):
        """v3.27.0: 連敗カウント増加・閾値到達でトリップ"""
        self.consecutive_losses += 1
        logger.info(f"🔴 [Circuit Breaker] Consecutive losses: {self.consecutive_losses}/{self.circuit_breaker_threshold}")
        if self.consecutive_losses >= self.circuit_breaker_threshold and self.circuit_breaker_tripped_at is None:
            self.circuit_breaker_tripped_at = datetime.now(timezone.utc)
            logger.warning(f"🚨 [Circuit Breaker] TRIPPED at {self.consecutive_losses} losses - pausing {self.circuit_breaker_cooldown_seconds/3600:.1f}h")
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"CIRCUIT_BREAKER_TRIPPED: {self.consecutive_losses} consecutive losses, pausing {self.circuit_breaker_cooldown_seconds}s\n")
            except:
                pass
        self._save_circuit_breaker_state()

    def _record_win(self):
        """v3.27.0: 勝ちトレードで連敗カウンターをリセット"""
        if self.consecutive_losses > 0:
            logger.info(f"🟢 [Circuit Breaker] Win recorded - reset losses ({self.consecutive_losses} → 0)")
        self.consecutive_losses = 0
        self.circuit_breaker_tripped_at = None
        self._save_circuit_breaker_state()

    def _check_anti_chase(self, current_price):
        """v3.26.0: アンチチェイスフィルター - SL価格帯での再エントリー禁止"""
        if self.last_sl_price is None or self.last_sl_time is None:
            return True, None
        elapsed = (datetime.now(timezone.utc) - self.last_sl_time).total_seconds()
        if elapsed >= self.sl_price_cooldown_seconds:
            return True, None
        price_diff_pct = abs(current_price - self.last_sl_price) / self.last_sl_price
        if price_diff_pct <= self.sl_price_range_pct:
            remaining = self.sl_price_cooldown_seconds - elapsed
            reason = f"Anti-chase: ¥{current_price:.3f} within ±{self.sl_price_range_pct*100:.1f}% of last SL ¥{self.last_sl_price:.3f} ({remaining:.0f}s left)"
            return False, reason
        return True, None

    def record_trade(self, trade_type, price, result=None, is_exit=False):
        """取引記録"""
        self.last_trade_time = datetime.now(timezone.utc)

        if is_exit:
            self.last_exit_price = price
            # v3.21.0: クローズ後は last_entry_macd_position をリセット
            # → 次サイクルで現在のMACD位置に基づき即再エントリー可能
            self.last_entry_macd_position = None
            logger.info(f"💰 Exit recorded: ¥{price:.2f} - MACD entry direction reset (ready for re-entry)")

            # v3.27.0: サーキットブレーカー用の勝敗カウント
            if result is not None:
                if result < 0:
                    self._record_loss()
                elif result > 0:
                    self._record_win()
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
