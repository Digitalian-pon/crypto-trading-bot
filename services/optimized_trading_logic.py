"""
MACD単体トレーディングロジック v3.15.0
確定済みローソク足のMACDクロス + EMAトレンドフィルター + ポジションベースフォールバック

方針:
- エントリー優先: 確定済みローソク足のMACDクロス（ファントムクロス防止）
  - iloc[-2](確定済み) vs iloc[-3](前回確定) でクロス検出
  - iloc[-1](ライブ価格上書き)のMACDは使用しない（不安定なため）
- EMAトレンドフィルター: 【絶対ルール】完全ブロック（緩和禁止）
  - EMA20 > EMA50（上昇トレンド）→ BUYのみ許可、SELL完全禁止
  - EMA20 < EMA50（下降トレンド）→ SELLのみ許可、BUY完全禁止
  - ヒストグラム強度に関係なく完全ブロック（過去の緩和は全て損失に繋がった）
- フォールバック: クロスなし + ポジションなし + ヒストグラム十分 → トレンド方向にエントリー
  - EMAトレンドフィルターも適用（逆方向はブロック）
- クロス保持: タイミングフィルターで拒否されたクロスは保持（次回再試行）
  - EMAフィルターで拒否されたクロスは保持しない（騙しクロスのため）
- 決済: トレーリングストップ + MACDクロス確認（bot側で処理）
- 決済時のMACDクロス → 即座に反対注文（トレンド転換を捉える）

v3.15.2 変更点:
- EMAトレンドフィルターを完全ブロックに確定（【絶対ルール】緩和禁止）
  - v3.15.1の条件付き許可は損失を招いた（EMAが正しかったのにBUYして-0.83%損失）
  - 過去の緩和は全て失敗: v3.11.0削除→損失, v3.14.0参考のみ→損失, v3.15.1条件付き→損失
  - EMAが遅行指標でも、逆方向取引の損失 > 機会損失
  - この完全ブロックは今後いかなる理由でも緩和してはならない
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class OptimizedTradingLogic:
    """
    MACD主体トレーディングロジック v3.15.0

    設計思想:
    - エントリー: 確定済みローソク足のMACDクロス（優先）
    - EMAトレンドフィルター: トレンド方向のシグナルのみ許可
    - フォールバック: クロスなし + ポジションなし → ポジションベースエントリー（EMAフィルター付き）
    - クロス保持: タイミングフィルター拒否時のみ保持（EMAブロック時は破棄）
    - 決済: トレーリングストップ + MACDクロス確認 → 反対注文
    """

    def __init__(self, config=None):
        """初期化 v3.15.0"""
        self.config = config or {}
        self.last_trade_time = None
        self.last_trade_price = None
        self.last_exit_price = None
        self.min_trade_interval = 60  # 1分（チェック間隔に合わせる）

        # シンプルなTP/SL設定（固定%）- リスクリワード比 2:1
        self.take_profit_pct = 0.03   # 3%利確
        self.stop_loss_pct = 0.010    # 1.0%損切り

        # 取引履歴
        self.trade_history = []
        self.recent_trades_limit = 20

        # MACD状態追跡（確定済みローソク足ベース）
        self.last_macd_position = None  # 'above' or 'below'
        self.pending_cross = None       # フィルター拒否されたクロスを保持

        # v3.14.0: ポジションベースエントリー用の待機カウンター
        self.no_position_cycles = 0  # ポジションなしで待機したサイクル数

    def should_trade(self, market_data, historical_df=None, skip_price_filter=False, is_tpsl_continuation=False):
        """
        取引判定 - v3.15.0 確定済みMACDクロス + EMAトレンドフィルター + フォールバック

        ルール:
        1. 確定済みローソク足(iloc[-2])のMACDでクロス検出（優先）
        2. EMAトレンドフィルター: トレンド逆方向のクロスはブロック
           - 上昇トレンド(EMA20>EMA50) → SELL禁止
           - 下降トレンド(EMA20<EMA50) → BUY禁止
        3. クロスなし + ポジションなし → ポジションベースフォールバック（EMAフィルター付き）
        4. タイミングフィルターで拒否 → クロスを保持し次回再試行

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

            logger.info(f"📊 [MACD v3.15.0 Cross+EMA+Fallback] Price=¥{current_price:.3f}")
            logger.info(f"   Live MACD: Line={macd_line:.6f}, Signal={macd_signal:.6f}, Hist={macd_histogram:.6f}")

            # === v3.15.0: 確定済みローソク足でMACDクロス判定 ===
            is_golden_cross = False
            is_death_cross = False
            confirmed_histogram = abs(macd_histogram)  # fallback
            confirmed_position = 'above' if macd_line > macd_signal else 'below'  # fallback

            if historical_df is not None and len(historical_df) >= 4 and 'macd_line' in historical_df.columns:
                # 確定済みローソク足(iloc[-2])のMACD
                confirmed = historical_df.iloc[-2]
                confirmed_macd_line = float(confirmed.get('macd_line', 0))
                confirmed_macd_signal = float(confirmed.get('macd_signal', 0))
                confirmed_histogram = abs(confirmed_macd_line - confirmed_macd_signal)
                confirmed_position = 'above' if confirmed_macd_line > confirmed_macd_signal else 'below'

                logger.info(f"   Confirmed candle MACD: Line={confirmed_macd_line:.6f}, Signal={confirmed_macd_signal:.6f}")
                logger.info(f"   Confirmed position: {confirmed_position}, Last tracked: {self.last_macd_position}")

                if self.last_macd_position is None:
                    # 初回: 前々回の確定ローソク足から状態を復元
                    prev = historical_df.iloc[-3]
                    prev_ml = float(prev.get('macd_line', 0))
                    prev_ms = float(prev.get('macd_signal', 0))
                    self.last_macd_position = 'above' if prev_ml > prev_ms else 'below'
                    logger.info(f"   🔄 [STARTUP] Restored: {self.last_macd_position} → {confirmed_position}")

                # クロス検出（確定済みローソク足ベース）
                if self.last_macd_position == 'below' and confirmed_position == 'above':
                    is_golden_cross = True
                    self.pending_cross = None
                    logger.info(f"   🟢 CONFIRMED Golden Cross! (from confirmed candle)")
                elif self.last_macd_position == 'above' and confirmed_position == 'below':
                    is_death_cross = True
                    self.pending_cross = None
                    logger.info(f"   🔴 CONFIRMED Death Cross! (from confirmed candle)")

                # 保留中のクロス復元
                if not is_golden_cross and not is_death_cross and self.pending_cross is not None:
                    if self.pending_cross == 'golden' and confirmed_position == 'above':
                        is_golden_cross = True
                        logger.info(f"   🟢 PENDING Golden Cross RESTORED")
                    elif self.pending_cross == 'death' and confirmed_position == 'below':
                        is_death_cross = True
                        logger.info(f"   🔴 PENDING Death Cross RESTORED")
                    else:
                        logger.info(f"   Pending cross '{self.pending_cross}' expired")
                        self.pending_cross = None

                # 状態を更新（確定済みローソク足ベース）
                self.last_macd_position = confirmed_position
            else:
                # Fallback: historical_dfがない場合はライブMACDを使用
                macd_position = 'above' if macd_line > macd_signal else 'below'
                if self.last_macd_position is None:
                    self.last_macd_position = macd_position
                    logger.info(f"   🔄 [STARTUP] No historical data, initialized: {macd_position}")
                else:
                    if self.last_macd_position == 'below' and macd_position == 'above':
                        is_golden_cross = True
                    elif self.last_macd_position == 'above' and macd_position == 'below':
                        is_death_cross = True
                    self.last_macd_position = macd_position

            # === EMAトレンドフィルター（v3.15.0: トレンド方向のみ取引許可） ===
            ema_trend = 'up' if ema_20 > ema_50 else 'down'
            ema_diff_pct = abs(ema_20 - ema_50) / ema_50 * 100 if ema_50 > 0 else 0
            logger.info(f"   EMA Trend: {ema_trend} ({ema_diff_pct:.2f}%), Confirmed hist: {confirmed_histogram:.6f}")
            logger.info(f"   No-position cycles: {self.no_position_cycles}")

            # === クロスあり → クロスベースエントリー ===
            if is_golden_cross or is_death_cross:
                # クロス検出時はカウンターリセット
                self.no_position_cycles = 0

                # ============================================================
                # 【絶対ルール】EMAトレンドフィルター - 完全ブロック
                # ============================================================
                # ⚠️ この完全ブロックを「条件付き許可」や「confidence調整」に
                #    緩和してはいけない。過去に何度も緩和して損失を出している:
                #    - v3.11.0: EMA削除 → 逆張り損失
                #    - v3.14.0: EMA参考のみ → 上昇中SELL連発で損失
                #    - v3.15.1: 条件付き許可 → EMA正しかったのにBUYして損失
                #    EMAが遅行指標でも、逆方向取引の損失 > 機会損失
                # ============================================================
                if is_golden_cross and ema_trend == 'down':
                    logger.info(f"   🚫 Golden Cross BLOCKED by EMA downtrend ({ema_diff_pct:.2f}%) [ABSOLUTE RULE]")
                    self.pending_cross = None
                    return False, None, f"Golden Cross blocked - EMA downtrend ({ema_diff_pct:.2f}%)", 0.0, None, None
                if is_death_cross and ema_trend == 'up':
                    logger.info(f"   🚫 Death Cross BLOCKED by EMA uptrend ({ema_diff_pct:.2f}%) [ABSOLUTE RULE]")
                    self.pending_cross = None
                    return False, None, f"Death Cross blocked - EMA uptrend ({ema_diff_pct:.2f}%)", 0.0, None, None

                # シグナル強度計算（確定済みヒストグラム使用）
                if confirmed_histogram > 0.03:
                    confidence = 2.5
                elif confirmed_histogram > 0.01:
                    confidence = 2.0
                elif confirmed_histogram > 0.005:
                    confidence = 1.5
                else:
                    confidence = 1.0

                # 取引タイミングフィルター
                if not skip_price_filter:
                    if not self._check_trade_timing():
                        cross_type = 'golden' if is_golden_cross else 'death'
                        self.pending_cross = cross_type
                        logger.info(f"   ⏳ Cross PENDING (trade interval too short)")
                        return False, None, "Trade interval too short (cross pending)", 0.0, None, None

                    if self.last_trade_price is not None:
                        price_change = abs(current_price - self.last_trade_price) / self.last_trade_price
                        if price_change < 0.003:
                            cross_type = 'golden' if is_golden_cross else 'death'
                            self.pending_cross = cross_type
                            logger.info(f"   ⏳ Cross PENDING (price change too small: {price_change*100:.2f}%)")
                            return False, None, "Price change too small (cross pending)", 0.0, None, None

                self.pending_cross = None

                if is_golden_cross:
                    reason = f'MACD Golden Cross [Confirmed] (EMA: {ema_trend} {ema_diff_pct:.2f}%)'
                    stop_loss = current_price * (1 - self.stop_loss_pct)
                    take_profit = current_price * (1 + self.take_profit_pct)
                    logger.info(f"   🟢 BUY SIGNAL: {reason} (confidence={confidence:.2f})")
                    return True, 'BUY', reason, confidence, stop_loss, take_profit
                else:
                    reason = f'MACD Death Cross [Confirmed] (EMA: {ema_trend} {ema_diff_pct:.2f}%)'
                    stop_loss = current_price * (1 + self.stop_loss_pct)
                    take_profit = current_price * (1 - self.take_profit_pct)
                    logger.info(f"   🔴 SELL SIGNAL: {reason} (confidence={confidence:.2f})")
                    return True, 'SELL', reason, confidence, stop_loss, take_profit

            # === v3.14.0: クロスなし → ポジションベースフォールバック ===
            # ポジションなしで3サイクル以上待機 + ヒストグラム十分 → トレンド方向にエントリー
            self.no_position_cycles += 1

            if self.no_position_cycles >= 3 and confirmed_histogram > 0.01:
                # タイミングフィルター
                if not skip_price_filter:
                    if not self._check_trade_timing():
                        logger.info(f"   ⏳ Position-based entry blocked (trade interval)")
                        return False, None, "Position-based: trade interval too short", 0.0, None, None

                    if self.last_exit_price is not None:
                        exit_distance = abs(current_price - self.last_exit_price) / self.last_exit_price
                        if exit_distance < 0.003:
                            logger.info(f"   ⏳ Position-based entry blocked (too close to exit: {exit_distance*100:.2f}%)")
                            return False, None, "Position-based: too close to exit price", 0.0, None, None

                # confidence は控えめ（クロスより低い）
                if confirmed_histogram > 0.03:
                    confidence = 2.0
                elif confirmed_histogram > 0.02:
                    confidence = 1.5
                else:
                    confidence = 1.2

                # ============================================================
                # 【絶対ルール】EMAトレンドフィルター - フォールバックも完全ブロック
                # ⚠️ 上記クロスベースと同じ理由で、緩和禁止
                # ============================================================
                if confirmed_position == 'above' and ema_trend == 'down':
                    logger.info(f"   🚫 Position-Based BUY BLOCKED by EMA downtrend ({ema_diff_pct:.2f}%) [ABSOLUTE RULE]")
                    return False, None, "Position BUY blocked - EMA downtrend", 0.0, None, None
                if confirmed_position == 'below' and ema_trend == 'up':
                    logger.info(f"   🚫 Position-Based SELL BLOCKED by EMA uptrend ({ema_diff_pct:.2f}%) [ABSOLUTE RULE]")
                    return False, None, "Position SELL blocked - EMA uptrend", 0.0, None, None

                if confirmed_position == 'above':
                    reason = f'MACD Position-Based BUY [Fallback] (hist={confirmed_histogram:.4f}, cycles={self.no_position_cycles}, EMA: {ema_trend})'
                    stop_loss = current_price * (1 - self.stop_loss_pct)
                    take_profit = current_price * (1 + self.take_profit_pct)
                    logger.info(f"   🟢 POSITION-BASED BUY: {reason} (confidence={confidence:.2f})")
                    return True, 'BUY', reason, confidence, stop_loss, take_profit
                else:
                    reason = f'MACD Position-Based SELL [Fallback] (hist={confirmed_histogram:.4f}, cycles={self.no_position_cycles}, EMA: {ema_trend})'
                    stop_loss = current_price * (1 + self.stop_loss_pct)
                    take_profit = current_price * (1 - self.take_profit_pct)
                    logger.info(f"   🔴 POSITION-BASED SELL: {reason} (confidence={confidence:.2f})")
                    return True, 'SELL', reason, confidence, stop_loss, take_profit

            logger.info(f"   No MACD cross - waiting (cycles={self.no_position_cycles}, need 3+ with hist>0.01)")
            return False, None, "No MACD cross - waiting", 0.0, None, None

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
            self.no_position_cycles = 0  # v3.14.0: エントリー時にリセット
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
