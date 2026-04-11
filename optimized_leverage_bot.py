"""
最適化されたDOGE_JPYレバレッジ取引ボット
OptimizedTradingLogicを使用した改良版
"""

import logging
import time
import os
from datetime import datetime
import sys
from services.gmo_api import GMOCoinAPI
from services.optimized_trading_logic import OptimizedTradingLogic
from services.data_service import DataService
from services.rolling_optimizer import RollingOptimizer
from config import load_config

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class OptimizedLeverageTradingBot:
    """
    最適化されたレバレッジ取引ボット

    改善点:
    1. 市場レジーム検出（トレンド/レンジ/高ボラティリティ）
    2. レジーム別の適応的パラメータ
    3. ATRベースの動的ストップロス/テイクプロフィット
    4. マルチタイムフレーム分析
    5. 取引品質スコアリング
    6. パフォーマンス追跡
    """

    def __init__(self):
        config = load_config()
        api_key = config.get('api_credentials', 'api_key')
        api_secret = config.get('api_credentials', 'api_secret')

        self.api = GMOCoinAPI(api_key, api_secret)
        self.data_service = DataService(api_key, api_secret)
        self.trading_logic = OptimizedTradingLogic()

        # 取引設定
        self.symbol = config.get('trading', 'default_symbol', fallback='DOGE_JPY')
        self.timeframe = config.get('trading', 'default_timeframe', fallback='1hour')
        self.interval = 60  # チェック間隔（秒）- 1分（リアルタイム性重視）

        # v3.19.0: ローリングパラメータ最適化エンジン
        self.optimizer = RollingOptimizer()
        self.optimization_cycle_count = 0

        # 動的ストップロス/テイクプロフィット管理
        self.active_positions_stops = {}  # {position_id: {'stop_loss': price, 'take_profit': price}}

        # v3.12.1: 重複注文防止 - 最後の注文時刻を記録
        self.last_order_time = self._load_last_order_time()  # v3.17.6: ファイルから復元（再起動対応）
        self._orders_placed_this_cycle = 0  # v3.20.0: サイクル内注文カウント（旧bool → count）

        # v3.20.1: 最大同時ポジション数 = 1（残高全額を1注文・手数料1回）
        # GMO Coin分割約定で2件表示されても、1件以上あれば新規注文をブロック
        self.MAX_POSITIONS = 1

        # MACDクロス検出用（決済判定）- v3.1.1: position-based → cross-based
        self.last_close_macd_position = None

        # v3.19.0: 動的トレーリングストップテンプレート
        self.trailing_template = [
            (0.005, 0.0),    # +0.5% → 建値ロック
            (0.010, 0.005),  # +1.0% → +0.5%
            (0.015, 0.010),  # +1.5% → +1.0%
            (0.020, 0.015),  # +2.0% → +1.5%
            (0.030, 0.020),  # +3.0% → +2.0%
        ]
        self.dynamic_hard_sl = -0.008  # デフォルトSL -0.8%

    def _update_trailing_template(self, params):
        """ローリング最適化からトレーリングストップテンプレートを更新（v3.20.2: SL下限0.8%）"""
        if params is None:
            return
        old_sl = self.dynamic_hard_sl
        # v3.20.2: SL下限クランプ - 最適化が0.8%未満を選んでも0.8%を維持
        MIN_SL = 0.008  # 0.8%（15分足ノイズ対策）
        raw_sl = params.get('stop_loss_pct', MIN_SL)
        self.dynamic_hard_sl = -max(raw_sl, MIN_SL)
        if 'trailing_stops' in params:
            self.trailing_template = params['trailing_stops']
        elif 'breakeven_threshold' in params:
            be = params['breakeven_threshold']
            self.trailing_template = [
                (be, 0.0),
                (be * 2, be),
                (be * 3, be * 2),
                (be * 4, be * 3),
                (be * 6, be * 4),
            ]
        if old_sl != self.dynamic_hard_sl:
            logger.info(f"🧠 [OPTIMIZER] Trailing SL updated: {old_sl*100:.1f}% → {self.dynamic_hard_sl*100:.1f}%")

    # v3.17.6: ファイルベースの注文時刻管理（再起動しても消えない）
    ORDER_TIME_FILE = 'last_order_time.txt'

    def _load_last_order_time(self):
        """ファイルから最後の注文時刻を読み込む"""
        try:
            with open(self.ORDER_TIME_FILE, 'r') as f:
                ts = float(f.read().strip())
                from datetime import datetime, timezone
                t = datetime.fromtimestamp(ts, tz=timezone.utc)
                logger.info(f"📂 Loaded last order time from file: {t.isoformat()}")
                return t
        except:
            return None

    def _save_last_order_time(self, t):
        """最後の注文時刻をファイルに保存する"""
        try:
            with open(self.ORDER_TIME_FILE, 'w') as f:
                f.write(str(t.timestamp()))
        except Exception as e:
            logger.warning(f"⚠️ Failed to save order time: {e}")

    def run(self):
        """メインループ"""
        logger.info("="*70)
        logger.info(f"🚀 Optimized DOGE_JPY Leverage Trading Bot Started")
        logger.info(f"📊 Symbol: {self.symbol}, Timeframe: {self.timeframe}")
        logger.info(f"⏱️  Check Interval: {self.interval}s")
        logger.info("="*70)

        while True:
            try:
                self._trading_cycle()
                logger.info(f"💤 Sleeping for {self.interval} seconds...\n")
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"❌ Error in trading loop: {e}", exc_info=True)
                # ファイルログにもエラーを記録
                try:
                    import traceback
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"ERROR: {type(e).__name__}: {str(e)}\n")
                        f.write(f"TRACEBACK:\n")
                        traceback.print_exc(file=f)
                except:
                    pass
                time.sleep(self.interval)

    def _trading_cycle(self):
        """1回の取引サイクル"""
        self._orders_placed_this_cycle = 0  # サイクル開始時にリセット
        cycle_time = datetime.now()

        # ボット稼働状況をログファイルに記録（ダッシュボードで表示可能）
        try:
            log_file = 'bot_execution_log.txt'
            bot_version = os.environ.get('BOT_VERSION', 'unknown')
            with open(log_file, 'a') as f:
                f.write(f"\n{'='*70}\n")
                f.write(f"CYCLE_START: {cycle_time.isoformat()}\n")
                f.write(f"BOT_VERSION: {bot_version}\n")
                f.write(f"INTERVAL: {self.interval}s\n")
        except Exception as e:
            logger.error(f"Failed to write log file: {e}")

        logger.info(f"\n{'='*70}")
        logger.info(f"🔄 Trading Cycle - {cycle_time}")
        logger.info(f"{'='*70}")

        # 1. 市場データ取得（過去100本）
        logger.info(f"📊 Fetching market data: symbol={self.symbol}, timeframe={self.timeframe}")
        df = self.data_service.get_data_with_indicators(
            self.symbol,
            interval=self.timeframe,
            limit=100
        )

        if df is None or df.empty:
            logger.error(f"❌ CRITICAL: Failed to get market data for {self.symbol} with timeframe {self.timeframe}")
            logger.error(f"❌ Possible reasons:")
            logger.error(f"   1. GMO Coin API may not support '{self.timeframe}' timeframe")
            logger.error(f"   2. Supported intervals: 1min, 5min, 15min, 30min ONLY")
            logger.error(f"   3. Network connectivity issues")
            logger.error(f"❌ Skipping this trading cycle")
            # ログファイルにもエラーを記録
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"ERROR: Failed to get market data - symbol={self.symbol}, timeframe={self.timeframe}\n")
                    f.write(f"ERROR: Check if timeframe is supported by GMO Coin API\n")
            except:
                pass
            return

        current_price = float(df['close'].iloc[-1])
        logger.info(f"💹 Current {self.symbol} price: ¥{current_price:.2f}")

        # 市場レジーム表示
        market_regime = df['market_regime'].iloc[-1] if 'market_regime' in df.columns else 'Unknown'
        logger.info(f"🎯 Market Regime: {market_regime}")

        # v3.19.0: ローリングパラメータ最適化
        self.optimization_cycle_count += 1
        if self.optimizer.should_optimize():
            try:
                # マルチデイデータ取得（3日分 = 約288本の15分足）
                opt_df = self.optimizer.fetch_extended_data(
                    self.data_service, self.symbol, self.timeframe, days=3
                )
                if opt_df is None or len(opt_df) < 50:
                    opt_df = df  # フォールバック: 通常のデータを使用

                best_params = self.optimizer.optimize(opt_df)
                if best_params:
                    # トレーディングロジックのパラメータを更新
                    self.trading_logic.update_parameters(best_params)
                    # トレーリングストップのテンプレートも更新
                    self._update_trailing_template(best_params)
            except Exception as e:
                logger.error(f"⚠️ Optimization error (non-fatal): {e}")
        else:
            opt_status = self.optimizer.get_status()
            if opt_status['params']:
                p = opt_status['params']
                logger.info(f"🧠 [OPTIMIZER] Active: SL={p['stop_loss_pct']*100:.1f}% MACD={p['macd_preset']} EntryHist={p['entry_hist_filter']:.3f}")

        # 2. 既存ポジション確認
        logger.info(f"🔍 Fetching positions for symbol: {self.symbol}")
        positions = self.api.get_positions(symbol=self.symbol)
        logger.info(f"📊 Active positions: {len(positions)}")

        # 詳細ログをファイルに記録
        try:
            with open('bot_execution_log.txt', 'a') as f:
                f.write(f"POSITION_FETCH: symbol={self.symbol}, count={len(positions)}\n")
                if positions:
                    for pos in positions:
                        f.write(f"  - Position: {pos.get('positionId')} {pos.get('side')} {pos.get('size')} @ {pos.get('price')}\n")
                else:
                    f.write(f"  - No positions found\n")
        except:
            pass

        # v3.19.1: 最大ポジション数超過フラグ
        max_pos_exceeded = False

        # 標準出力にも詳細を表示
        if positions:
            # v3.14.0+: ポジション保有中はフォールバックカウンターをリセット
            self.trading_logic.no_position_cycles = 0
            for pos in positions:
                logger.info(f"  └─ Position {pos.get('positionId')}: {pos.get('side')} {pos.get('size')} @ ¥{pos.get('price')}")

            # v3.20.0: 最大ポジション数（MAX_POSITIONS）超過時は決済チェックのみで新規注文は出さない
            if len(positions) >= self.MAX_POSITIONS:
                logger.warning(f"⚠️ [MAX_POS] {len(positions)} positions detected (max={self.MAX_POSITIONS}) - close check only, no new orders")
                max_pos_exceeded = True
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"MAX_POSITION_LIMIT: {len(positions)}/{self.MAX_POSITIONS} positions, skipping new orders\n")
                except:
                    pass

        # 3. ポジションの決済チェック（動的SL/TP使用）
        any_closed = False
        reversal_signal = False
        tp_sl_closed = False
        reversal_trade_type = None
        loss_close = False  # v3.10.2: MACDクロス損失クローズフラグ

        # デバッグログ
        try:
            with open('bot_execution_log.txt', 'a') as f:
                f.write(f"POSITION_CHECK_START: has_positions={len(positions) > 0}, count={len(positions)}\n")
        except:
            pass

        if positions:
            logger.info(f"Checking {len(positions)} positions for closing...")
            # ファイルログにも記録
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"CHECKING_CLOSE: Analyzing {len(positions)} positions\n")
            except:
                pass

            any_closed, reversal_signal, tp_sl_closed, reversal_trade_type, loss_close = self._check_positions_for_closing(positions, current_price, df)

            # 決済後、ポジションを再取得
            positions = self.api.get_positions(symbol=self.symbol)
            logger.info(f"📊 Positions after close check: {len(positions)}")

            # ファイルログにも記録
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"CLOSE_CHECK_RESULT: any_closed={any_closed}, reversal={reversal_signal}, tp_sl={tp_sl_closed}, loss_close={loss_close}\n")
                    f.write(f"POSITIONS_REMAINING: {len(positions)}\n")
            except:
                pass
        else:
            # ポジションがない場合もログに記録
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"NO_POSITIONS_TO_CLOSE: Skipping close check\n")
            except:
                pass

        # 4. パフォーマンス統計表示
        self._display_performance_stats()

        # 5. 新規取引シグナルをチェック
        # - 反転シグナルで決済された場合は即座にチェック（機会損失防止、逆注文を強制実行）
        # - TP/SL決済の場合は継続チェック（中程度の閾値）
        # - 全ポジション決済された場合もチェック
        # - ポジションがない場合もチェック
        # - v3.10.2: MACDクロスで損失クローズの場合は同サイクルの新規エントリーを禁止（往復ビンタ防止）
        if loss_close:
            logger.info("⛔ Loss Close this cycle - skipping new trade check (往復ビンタ防止)")
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"NEW_TRADE_ACTION: SKIPPED (loss_close=True, 往復ビンタ防止)\n")
            except:
                pass
            return

        # v3.20.0: max_pos_exceeded時は新規注文を一切出さない
        if max_pos_exceeded:
            logger.warning(f"⚠️ [MAX_POS] Skipping all new order checks due to {len(positions)}/{self.MAX_POSITIONS} positions")
            return

        should_check_new_trade = (
            reversal_signal or                    # 反転シグナル決済
            tp_sl_closed or                       # TP/SL決済（継続機会）
            (any_closed and not positions) or     # 全ポジション決済
            not positions                         # ポジションなし
        )

        # デバッグログをファイルに記録
        try:
            with open('bot_execution_log.txt', 'a') as f:
                f.write(f"NEW_TRADE_CHECK_CONDITIONS: reversal={reversal_signal}, tp_sl={tp_sl_closed}, any_closed={any_closed}, positions={len(positions)}, should_check={should_check_new_trade}\n")
        except:
            pass

        if should_check_new_trade:
            # v3.19.1: 1サイクル1注文を厳格化 - reversal OR new trade、両方は実行しない
            if reversal_signal and reversal_trade_type:
                logger.info(f"🔄 Position closed by reversal signal - FORCING {reversal_trade_type} order immediately...")
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"NEW_TRADE_ACTION: REVERSAL_ORDER type={reversal_trade_type}\n")
                except:
                    pass
                self._place_forced_reversal_order(reversal_trade_type, current_price, df)
                # ★ v3.19.1: reversal注文後は必ずreturn（_check_for_new_tradeに進まない）
                return
            elif tp_sl_closed:
                logger.info("💰 Position closed by TP/SL - checking for new opportunities...")
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"NEW_TRADE_ACTION: TP_SL_CHECK (with price distance filter)\n")
                except:
                    pass
                self._check_for_new_trade(df, current_price, is_reversal=False)
            elif not positions:
                logger.info("✅ No positions - checking for new trade opportunities...")
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"NEW_TRADE_ACTION: NO_POSITIONS_CHECK\n")
                except:
                    pass
                self._check_for_new_trade(df, current_price, is_reversal=False)
        else:
            logger.info(f"⏸️  Still have {len(positions)} open positions - waiting...")
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"NEW_TRADE_ACTION: WAITING (positions={len(positions)})\n")
            except:
                pass

    def _check_positions_for_closing(self, positions, current_price, df):
        """
        ポジション決済チェック（動的SL/TP使用）

        Returns:
            (any_closed: bool, reversal_signal: bool, tp_sl_closed: bool, reversal_trade_type: str or None, loss_close: bool)
        """
        any_closed = False
        reversal_signal = False
        tp_sl_closed = False
        reversal_trade_type = None  # 反転シグナルのタイプ（BUY/SELL）
        loss_close = False  # v3.10.2: MACDクロスで損失中のポジションをクローズした場合

        for position in positions:
            side = position.get('side')
            size = float(position.get('size', 0))  # 文字列→floatに変換（重要！）
            entry_price = float(position.get('price', 0))
            position_id = position.get('positionId')

            # P/L計算
            if side == 'BUY':
                pl_ratio = (current_price - entry_price) / entry_price
            else:  # SELL
                pl_ratio = (entry_price - current_price) / entry_price

            logger.info(f"Position {position_id} ({side}): Entry=¥{entry_price:.2f}, P/L={pl_ratio*100:.2f}%")

            # === トレーリングストップ管理 (v3.19.0: 動的パラメータ対応) ===
            hard_sl = self.dynamic_hard_sl  # ローリング最適化から動的に設定

            if position_id not in self.active_positions_stops:
                # 既存ポジション（再起動後など）の初期化
                stop_loss = entry_price * (1 + hard_sl) if side == 'BUY' else entry_price * (1 - hard_sl)
                self.active_positions_stops[position_id] = {
                    'stop_loss': stop_loss,
                    'take_profit': None,
                    'peak_pl_ratio': max(0.0, pl_ratio),
                    'trailing_sl_ratio': hard_sl,
                }
                logger.warning(f"   Initialized trailing stop for existing position: SL={hard_sl*100:.1f}%")

            stops = self.active_positions_stops[position_id]
            peak_pl = stops.get('peak_pl_ratio', 0.0)

            # ピークP/L更新
            if pl_ratio > peak_pl:
                stops['peak_pl_ratio'] = pl_ratio
                peak_pl = pl_ratio

            # トレーリングストップレベル更新（v3.19.0: 動的テンプレート）
            for threshold, lock in reversed(self.trailing_template):
                if peak_pl >= threshold:
                    stops['trailing_sl_ratio'] = lock
                    break
            else:
                # どの閾値にも到達していない → ハードSLのまま
                stops['trailing_sl_ratio'] = hard_sl

            stop_loss = stops.get('stop_loss', entry_price * 0.985)
            take_profit = stops.get('take_profit')
            trailing_sl = stops.get('trailing_sl_ratio', hard_sl)
            logger.info(f"   📈 Trailing Stop: Peak={peak_pl*100:.2f}%, SL={trailing_sl*100:.1f}%")

            # 決済条件チェック（v3.12.2: dfも渡してstartup時のクロス検出に使用）
            should_close, reason, close_trade_type = self._should_close_position(
                position, current_price, df.iloc[-1].to_dict(), pl_ratio, stop_loss, take_profit, df
            )

            # デバッグログ追加
            logger.info(f"   DEBUG: should_close={should_close}, reason='{reason}', type={type(should_close)}")
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"DEBUG_CLOSE_CHECK: should_close={should_close}, reason='{reason}'\n")
            except:
                pass

            if should_close:
                logger.info(f"🔄 Closing position: {reason}")
                close_success = self._close_position(position, current_price, reason)

                if not close_success:
                    # API失敗 → ポジションが既にGMO側で決済済みか確認
                    logger.warning(f"⚠️ Close API failed - verifying position status...")
                    remaining = self.api.get_positions(symbol=self.symbol)
                    pos_still_exists = any(
                        str(p.get('positionId')) == str(position_id) for p in (remaining or [])
                    )
                    if pos_still_exists:
                        # ポジションがまだ存在する → 決済失敗として扱う
                        logger.error(f"❌ Position {position_id} still exists - close truly failed, skipping")
                        try:
                            with open('bot_execution_log.txt', 'a') as f:
                                f.write(f"CLOSE_VERIFIED_FAILED: Position {position_id} still open\n")
                        except:
                            pass
                        continue  # このポジションはスキップ、次のポジションへ
                    else:
                        # ポジションが消えている → GMO側で既に決済済み
                        logger.info(f"✅ Position {position_id} already closed on exchange side")
                        try:
                            with open('bot_execution_log.txt', 'a') as f:
                                f.write(f"CLOSE_ALREADY_DONE: Position {position_id} closed by exchange\n")
                        except:
                            pass

                any_closed = True

                # 決済理由を判定
                if "Reversal" in reason or "reversal" in reason:
                    # 反転シグナルで決済された場合
                    reversal_signal = True
                    reversal_trade_type = close_trade_type  # 反転シグナルのタイプを記録
                    logger.info(f"🔄 REVERSAL DETECTED - Will place {close_trade_type} order immediately")
                elif "Loss Close" in reason:
                    # v3.10.2: MACDクロスで損失中のポジションをクローズ → 同サイクルの新規エントリー禁止
                    loss_close = True
                    logger.info(f"⛔ LOSS CLOSE - Skipping new trade check this cycle (防往復ビンタ)")
                    try:
                        with open('bot_execution_log.txt', 'a') as f:
                            f.write(f"LOSS_CLOSE_DETECTED: Suppressing new trade check this cycle\n")
                    except:
                        pass
                elif "Take Profit" in reason or "Stop Loss" in reason or "Loss Limit" in reason:
                    # TP/SL/絶対損失リミットで決済された場合
                    tp_sl_closed = True
                    logger.info(f"💰 TP/SL CLOSE - Will check for continuation with moderate threshold")

                    # v3.3.0: 損切り時はクールダウンを記録（連続損失防止）
                    if "Stop Loss" in reason:
                        self.trading_logic.record_stop_loss(side)
                        logger.info(f"⏳ Stop loss cooldown started: {side} blocked for 30 minutes")

                # 決済後、SL/TP記録を削除
                if position_id in self.active_positions_stops:
                    del self.active_positions_stops[position_id]

                # 取引結果を記録（決済時はis_exit=True、決済価格を記録）
                self.trading_logic.record_trade(side, current_price, pl_ratio, is_exit=True)

        return any_closed, reversal_signal, tp_sl_closed, reversal_trade_type, loss_close

    def _should_close_position(self, position, current_price, indicators, pl_ratio, stop_loss, take_profit, df=None):
        """
        ポジション決済判定 - v3.6.0 トレーリングストップ + MACDクロス確認決済

        ルール:
        1. トレーリングストップ（v3.18.0: 利益を伸ばす + 早期建値ロック）
           - 含み益 0〜+0.5%: SL -0.8%（ハードストップ）
           - 含み益 +0.5%到達: SL 0%（建値ロック = 損失ゼロ保証）
           - 含み益 +1%到達: SL +0.5%
           - 含み益 +1.5%到達: SL +1%
           - 含み益 +2%到達: SL +1.5%
           - 含み益 +3%到達: SL +2%（利益を追従）
           ※固定TPなし - トレーリングストップが自動的に利益を追従
        2. MACDクロス確認決済
           - クロス検出 + ヒストグラム強い(>0.003) → 決済
           - クロス検出 + ヒストグラム弱い → 保持継続（トレーリングが保護）

        Returns:
            (should_close: bool, reason: str, trade_type: str or None)
        """
        side = position.get('side')
        size = float(position.get('size', 0))
        entry_price = float(position.get('price', 0))
        position_id = position.get('positionId')

        # MACDデータ
        macd_line = indicators.get('macd_line', 0)
        macd_signal = indicators.get('macd_signal', 0)
        macd_histogram = indicators.get('macd_histogram', 0)

        # EMAデータ
        ema_20 = indicators.get('ema_20', current_price)
        ema_50 = indicators.get('ema_50', current_price)
        ema_trend = 'up' if ema_20 > ema_50 else 'down'

        # トレーリングストップ情報取得（v3.19.0: 動的SL）
        hard_sl = self.dynamic_hard_sl
        trailing_sl_ratio = hard_sl
        peak_pl = 0.0
        if position_id and position_id in self.active_positions_stops:
            stops = self.active_positions_stops[position_id]
            trailing_sl_ratio = stops.get('trailing_sl_ratio', hard_sl)
            peak_pl = stops.get('peak_pl_ratio', 0.0)

        logger.info(f"   📊 [v3.4.0 Trailing Stop] Position Check:")
        logger.info(f"      {side} {size} DOGE @ ¥{entry_price:.3f}")
        logger.info(f"      Current: ¥{current_price:.3f}, P/L: {pl_ratio*100:.2f}%")
        logger.info(f"      Peak P/L: {peak_pl*100:.2f}%, Trailing SL: {trailing_sl_ratio*100:.1f}%")
        logger.info(f"      MACD: Line={macd_line:.6f}, Signal={macd_signal:.6f}, Hist={macd_histogram:.6f}")
        logger.info(f"      EMA Trend: {ema_trend} (EMA20={ema_20:.3f}, EMA50={ema_50:.3f})")

        # ログファイルに記録
        try:
            with open('bot_execution_log.txt', 'a') as f:
                f.write(f"POSITION_CHECK: {side} {size} @ ¥{entry_price:.3f}\n")
                f.write(f"CURRENT_PRICE: ¥{current_price:.3f}, P/L: {pl_ratio*100:.2f}%\n")
                f.write(f"TRAILING_STOP: SL={trailing_sl_ratio*100:.1f}%, Peak={peak_pl*100:.2f}%\n")
                f.write(f"MACD_LIVE: Line={macd_line:.6f}, Signal={macd_signal:.6f}\n")
                f.write(f"MACD_CLOSE_STATE: last={self.last_close_macd_position}\n")
        except:
            pass

        # === 1. トレーリングストップチェック ===
        if pl_ratio <= trailing_sl_ratio:
            if trailing_sl_ratio >= 0:
                # 利益ロック状態でのストップ（利益を確保して決済）
                logger.info(f"   ✅ TRAILING STOP HIT: P/L {pl_ratio*100:.2f}% <= lock {trailing_sl_ratio*100:.1f}%")
                return True, f"Trailing Stop: {pl_ratio*100:.2f}% (locked at {trailing_sl_ratio*100:.1f}%)", None
            else:
                # 通常の損切り（初期SL -1.2%）
                logger.info(f"   🚨 STOP LOSS: {pl_ratio*100:.2f}% <= {trailing_sl_ratio*100:.1f}%")
                # v3.17.5: ハードSL後は反転注文を出さない（レンジ相場での往復ビンタ防止）
                # 反転注文なしで "Loss Close" として処理 → 同サイクルの新規エントリーも禁止
                return True, f"Loss Close: Hard SL {pl_ratio*100:.2f}%", None

        # === 2. MACDクロス確認決済（v3.13.0: 確定済みローソク足ベース） ===
        # ライブMACDは不安定なため、確定済みローソク足(iloc[-2])のMACDでクロス検出
        is_close_death_cross = False
        is_close_golden_cross = False
        confirmed_close_histogram = abs(macd_histogram)  # fallback

        if df is not None and len(df) >= 4 and 'macd_line' in df.columns:
            confirmed = df.iloc[-2]
            confirmed_ml = float(confirmed.get('macd_line', 0))
            confirmed_ms = float(confirmed.get('macd_signal', 0))
            confirmed_close_pos = 'above' if confirmed_ml > confirmed_ms else 'below'
            confirmed_close_histogram = abs(confirmed_ml - confirmed_ms)

            logger.info(f"   🔍 [v3.13.0] Confirmed MACD: {confirmed_close_pos} (Line={confirmed_ml:.6f}, Signal={confirmed_ms:.6f})")
            logger.info(f"   🔍 Last close state: {self.last_close_macd_position}")

            if self.last_close_macd_position is None:
                # 初回: 前々回の確定ローソク足から状態を復元
                prev = df.iloc[-3]
                prev_ml = float(prev.get('macd_line', 0))
                prev_ms = float(prev.get('macd_signal', 0))
                self.last_close_macd_position = 'above' if prev_ml > prev_ms else 'below'
                logger.info(f"   🔄 [STARTUP] Close state restored: {self.last_close_macd_position} → {confirmed_close_pos}")
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"MACD_STARTUP_INIT: side={side}, confirmed={confirmed_close_pos}, prev={self.last_close_macd_position}\n")
                except:
                    pass

            # クロス検出（確定済みローソク足ベース）
            if self.last_close_macd_position == 'above' and confirmed_close_pos == 'below':
                is_close_death_cross = True
                logger.info(f"   🔴 CONFIRMED Death Cross (from confirmed candle)")
            elif self.last_close_macd_position == 'below' and confirmed_close_pos == 'above':
                is_close_golden_cross = True
                logger.info(f"   🟢 CONFIRMED Golden Cross (from confirmed candle)")

            # ★ v3.13.0: ヒストグラムが強い場合のみ状態を更新
            # 弱いヒストグラムでクロスを「消費」すると、後でヒストグラムが強くなっても
            # クロスが再検出できなくなるバグを防止
            if is_close_death_cross or is_close_golden_cross:
                if confirmed_close_histogram > self.trading_logic.close_hist_filter:
                    # ヒストグラム十分 → 状態を更新（クロスを消費）
                    self.last_close_macd_position = confirmed_close_pos
                else:
                    # ヒストグラム不十分 → 状態を更新しない（次回再検出可能）
                    logger.info(f"   ⏸️ Cross detected but histogram weak ({confirmed_close_histogram:.6f}) - NOT consuming cross")
            else:
                self.last_close_macd_position = confirmed_close_pos
        else:
            # Fallback: dfがない場合
            macd_close_pos = 'above' if macd_line > macd_signal else 'below'
            confirmed_close_pos = macd_close_pos
            if self.last_close_macd_position is None:
                self.last_close_macd_position = macd_close_pos
                logger.info(f"   🔄 [STARTUP] No df, initialized: {macd_close_pos}")
            else:
                if self.last_close_macd_position == 'above' and macd_close_pos == 'below':
                    is_close_death_cross = True
                elif self.last_close_macd_position == 'below' and macd_close_pos == 'above':
                    is_close_golden_cross = True
                self.last_close_macd_position = macd_close_pos

        # ★ 起動時チェック: 確定済みMACDがポジションと逆方向なら決済検討
        close_hist_threshold = self.trading_logic.close_hist_filter  # v3.19.0: 動的パラメータ
        if self.last_close_macd_position is not None and not is_close_death_cross and not is_close_golden_cross:
            # 起動直後で既にMACDがポジションと逆方向
            if side == 'BUY' and confirmed_close_pos == 'below' and confirmed_close_histogram > close_hist_threshold:
                logger.info(f"   ⚠️ BUY pos + confirmed bearish MACD → close")
                if pl_ratio >= 0:
                    return True, f"MACD Bearish [Confirmed] → Reversal SELL", 'SELL'
                else:
                    return True, f"MACD Bearish [Confirmed] - Loss Close", None
            elif side == 'SELL' and confirmed_close_pos == 'above' and confirmed_close_histogram > close_hist_threshold:
                logger.info(f"   ⚠️ SELL pos + confirmed bullish MACD → close")
                if pl_ratio >= 0:
                    return True, f"MACD Bullish [Confirmed] → Reversal BUY", 'BUY'
                else:
                    return True, f"MACD Bullish [Confirmed] - Loss Close", None

        # BUYポジション: MACDデッドクロス + ヒストグラム確認
        if side == 'BUY' and is_close_death_cross:
            if confirmed_close_histogram > close_hist_threshold:
                logger.info(f"   🔴 Closing BUY - Death Cross CONFIRMED (hist={confirmed_close_histogram:.6f})")
                if pl_ratio >= 0:
                    logger.info(f"   🔄 Profitable position - Will reverse to SELL")
                    return True, f"MACD Death Cross (Confirmed) → Reversal SELL", 'SELL'
                else:
                    logger.info(f"   ⛔ Loss position ({pl_ratio*100:.2f}%) - Closing only, no reversal")
                    return True, f"MACD Death Cross (Confirmed) - Loss Close", None
            else:
                logger.info(f"   ⏸️ Death Cross but histogram weak ({confirmed_close_histogram:.6f} < {close_hist_threshold:.3f}) - HOLDING")

        # SELLポジション: MACDゴールデンクロス + ヒストグラム確認
        if side == 'SELL' and is_close_golden_cross:
            if confirmed_close_histogram > close_hist_threshold:
                logger.info(f"   🟢 Closing SELL - Golden Cross CONFIRMED (hist={confirmed_close_histogram:.6f})")
                if pl_ratio >= 0:
                    logger.info(f"   🔄 Profitable position - Will reverse to BUY")
                    return True, f"MACD Golden Cross (Confirmed) → Reversal BUY", 'BUY'
                else:
                    logger.info(f"   ⛔ Loss position ({pl_ratio*100:.2f}%) - Closing only, no reversal")
                    return True, f"MACD Golden Cross (Confirmed) - Loss Close", None
            else:
                logger.info(f"   ⏸️ Golden Cross but histogram weak ({confirmed_close_histogram:.6f} < {close_hist_threshold:.3f}) - HOLDING")

        # 保持継続
        logger.info(f"   ✅ Holding position (P/L: {pl_ratio*100:.2f}%, SL: {trailing_sl_ratio*100:.1f}%, Peak: {peak_pl*100:.2f}%)")
        return False, "Holding position", None

    def _close_position(self, position, current_price, reason):
        """
        ポジション決済（リトライロジック付き）

        エラーハンドリング:
        1. 個別決済（close_position）を試行
        2. 失敗した場合、一括決済（close_bulk_position）を試行
        3. それでも失敗した場合、エラーログを残して継続
        """
        # 強制ログ追加
        try:
            with open('bot_execution_log.txt', 'a') as f:
                f.write(f"CLOSE_POSITION_CALLED: reason='{reason}'\n")
        except:
            pass

        try:
            symbol = position.get('symbol')
            side = position.get('side')
            size = float(position.get('size', 0))  # 文字列→floatに変換（重要！）
            position_id = position.get('positionId')

            # symbolがNoneの場合はself.symbolを使用
            if not symbol:
                symbol = self.symbol
                logger.warning(f"Position symbol is None, using self.symbol: {symbol}")

            close_side = "SELL" if side == "BUY" else "BUY"

            logger.info(f"🔄 Closing {side} position: {size} {symbol} at ¥{current_price:.2f}")
            logger.info(f"   Reason: {reason}")

            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"CLOSE_ATTEMPT: {side} {size} {symbol} @ ¥{current_price:.2f}\n")
                    f.write(f"CLOSE_PARAMS: symbol={symbol}, side={close_side}, positionId={position_id}, size={size}\n")
            except:
                pass

            # 【方法1】個別ポジション決済を試行
            logger.info(f"   Method 1: Trying individual position close (positionId={position_id})")
            result = self.api.close_position(
                symbol=symbol,
                side=close_side,
                execution_type="MARKET",
                position_id=position_id,
                size=str(int(size))  # floatをintに変換してから文字列化（20.0 → "20"）
            )

            # API結果をログに記録
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"CLOSE_API_RESULT (Method 1): {result}\n")
            except:
                pass

            # 成功判定
            if result.get('status') == 0:
                logger.info(f"✅ Position closed successfully (Method 1)")
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"CLOSE_SUCCESS (Method 1)\n")
                except:
                    pass
                return True

            # 【方法1失敗】エラーログ記録
            error_msg = result.get('messages', [{}])[0].get('message_string', 'Unknown error') if 'messages' in result else str(result)
            error_code = result.get('messages', [{}])[0].get('message_code', '') if 'messages' in result else ''
            logger.warning(f"⚠️  Method 1 failed: {error_msg} ({error_code})")

            # ERR-254 (Not found position) → GMO側で既に決済済み
            if error_code == 'ERR-254':
                logger.info(f"   Position already closed on exchange (ERR-254) - treating as success")
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"CLOSE_ALREADY_CLOSED_BY_EXCHANGE: ERR-254 (Not found position)\n")
                except:
                    pass
                return True  # 決済済みとして扱う

            logger.info(f"   Trying fallback method...")

            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"CLOSE_FAILED (Method 1): {error_msg}\n")
                    f.write(f"TRYING_FALLBACK (Method 2: Bulk close)\n")
            except:
                pass

            # 【方法2】一括決済を試行（フォールバック）
            logger.info(f"   Method 2: Trying bulk close (size={int(size)})")
            time.sleep(1)  # APIレート制限対策

            bulk_result = self.api.close_bulk_position(
                symbol=symbol,
                side=close_side,
                execution_type="MARKET",
                size=str(int(size))
            )

            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"CLOSE_API_RESULT (Method 2): {bulk_result}\n")
            except:
                pass

            if bulk_result.get('status') == 0:
                logger.info(f"✅ Position closed successfully (Method 2 - Bulk)")
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"CLOSE_SUCCESS (Method 2)\n")
                except:
                    pass
                return True

            # 【両方失敗】最終エラーログ
            bulk_error_msg = bulk_result.get('messages', [{}])[0].get('message_string', 'Unknown error') if 'messages' in bulk_result else str(bulk_result)
            logger.error(f"❌ Both close methods failed!")
            logger.error(f"   Method 1 error: {error_msg}")
            logger.error(f"   Method 2 error: {bulk_error_msg}")
            logger.error(f"   ⚠️  CRITICAL: Position may remain open - manual intervention may be required")

            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"CLOSE_FAILED (Method 2): {bulk_error_msg}\n")
                    f.write(f"CRITICAL_ERROR: Both methods failed - position may remain open\n")
            except:
                pass

            return False

        except Exception as e:
            logger.error(f"❌ Exception in close_position: {e}", exc_info=True)
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"CLOSE_EXCEPTION: {type(e).__name__}: {str(e)}\n")
            except:
                pass
            return False

    def _place_forced_reversal_order(self, trade_type, current_price, df):
        """
        トレンド転換時の強制反対注文

        Args:
            trade_type: 注文タイプ（BUY/SELL）- 反転シグナルで決済された時のシグナルタイプ
            current_price: 現在価格
            df: 市場データのDataFrame
        """
        logger.info(f"💥 FORCING {trade_type} ORDER - No signal re-evaluation")

        # ファイルログに記録（可視性向上）
        try:
            with open('bot_execution_log.txt', 'a') as f:
                f.write(f"REVERSAL_ORDER_START: Forcing {trade_type.upper()} @ ¥{current_price:.2f}\n")
        except:
            pass

        # v3.20.0: 反転注文前の既存ポジション確認（MAX_POSITIONS上限）
        existing_positions = self.api.get_positions(symbol=self.symbol)
        if existing_positions and len(existing_positions) >= self.MAX_POSITIONS:
            logger.warning(f"⚠️ [REVERSAL] Already have {len(existing_positions)}/{self.MAX_POSITIONS} position(s) - skipping reversal order")
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"REVERSAL_DUPLICATE_PREVENTION: Skipped {trade_type} order - already have {len(existing_positions)} position(s)\n")
                    for p in existing_positions:
                        f.write(f"  - Existing: {p.get('positionId')} {p.get('side')} {p.get('size')} @ {p.get('price')}\n")
            except:
                pass
            return

        # 残高確認
        balance = self.api.get_account_balance()
        available_jpy = 0

        if 'data' in balance:
            for asset in balance['data']:
                if asset['symbol'] == 'JPY':
                    available_jpy = float(asset['available'])

        logger.info(f"💰 Available JPY: ¥{available_jpy:.2f}")

        if available_jpy < 100:
            logger.warning("⚠️  Insufficient JPY balance for reversal order")
            # ファイルログに記録
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"REVERSAL_ORDER_FAILED: Insufficient balance (¥{available_jpy:.2f})\n")
            except:
                pass
            return

        # ポジションサイズ計算（残高の95%）
        max_jpy = available_jpy * 0.95
        max_doge_quantity = int(max_jpy / current_price)
        trade_size = max(10, (max_doge_quantity // 10) * 10)  # GMO Coin: 10DOGE単位必須

        # 動的SL/TP計算（ATRベース）
        last_row = df.iloc[-1].to_dict()

        # ATR取得
        atr = self.trading_logic._calculate_atr_from_data(df)

        # 市場レジーム取得
        regime = self.trading_logic._detect_market_regime(last_row, df)
        regime_config = self.trading_logic.regime_params.get(regime, self.trading_logic.regime_params['RANGING'])

        # SL/TP計算
        if trade_type.upper() == 'BUY':
            stop_loss = current_price - (atr * regime_config['stop_loss_atr_mult'])
            take_profit = current_price + (atr * regime_config['take_profit_atr_mult'])
        else:  # SELL
            stop_loss = current_price + (atr * regime_config['stop_loss_atr_mult'])
            take_profit = current_price - (atr * regime_config['take_profit_atr_mult'])

        logger.info(f"🎯 FORCED {trade_type.upper()} order: {trade_size} DOGE")
        logger.info(f"   Stop Loss: ¥{stop_loss:.2f}, Take Profit: ¥{take_profit:.2f}")
        logger.info(f"   Reason: Trend Reversal - Forced Opposite Position")

        # ファイルログに詳細記録
        try:
            with open('bot_execution_log.txt', 'a') as f:
                f.write(f"REVERSAL_ORDER_ATTEMPT: {trade_type.upper()} {trade_size} DOGE @ ¥{current_price:.2f}\n")
                f.write(f"REVERSAL_ORDER_SL_TP: SL=¥{stop_loss:.2f}, TP=¥{take_profit:.2f}\n")
        except:
            pass

        # 注文実行
        success = self._place_order(trade_type, trade_size, current_price,
                                    f"Forced {trade_type.upper()} on trend reversal",
                                    stop_loss, take_profit)

        if success:
            # 取引記録
            self.trading_logic.record_trade(trade_type, current_price)
            logger.info(f"✅ Forced reversal order completed successfully")
            # ファイルログに成功記録
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"REVERSAL_ORDER_COMPLETED: {trade_type.upper()} successfully executed\n")
            except:
                pass
        else:
            # ファイルログに失敗記録
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"REVERSAL_ORDER_FAILED: {trade_type.upper()} execution failed\n")
            except:
                pass

    def _check_for_new_trade(self, df, current_price, is_reversal=False, is_tpsl_continuation=False):
        """
        新規取引チェック（動的SL/TP付き）

        Args:
            df: 市場データのDataFrame
            current_price: 現在価格
            is_reversal: 反転シグナル直後かどうか（Trueの場合は価格変動フィルターをスキップ、緩い閾値）
            is_tpsl_continuation: TP/SL決済直後かどうか（Trueの場合は中程度の閾値）
        """
        # デバッグログ
        try:
            with open('bot_execution_log.txt', 'a') as f:
                f.write(f"CHECK_NEW_TRADE_CALLED: is_reversal={is_reversal}, is_tpsl={is_tpsl_continuation}, price=¥{current_price:.2f}\n")
        except:
            pass

        try:
            last_row = df.iloc[-1].to_dict()

            # シグナル取得（DataFrameも渡す）
            should_trade, trade_type, reason, confidence, stop_loss, take_profit = self.trading_logic.should_trade(
                last_row, df, skip_price_filter=is_reversal, is_tpsl_continuation=is_tpsl_continuation
            )

            # デバッグログ
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"SIGNAL_RESULT: should_trade={should_trade}, type={trade_type}, confidence={confidence:.2f}, reason={reason}\n")
            except:
                pass

            logger.info(f"🔍 Signal: should_trade={should_trade}, type={trade_type}, confidence={confidence:.2f}")
        except Exception as e:
            logger.error(f"❌ ERROR in _check_for_new_trade: {e}", exc_info=True)
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    import traceback
                    f.write(f"ERROR_CHECK_NEW_TRADE: {type(e).__name__}: {str(e)}\n")
                    f.write(f"TRACEBACK:\n")
                    traceback.print_exc(file=f)
            except:
                pass
            return
        if is_reversal:
            logger.info(f"   🔄 Reversal mode: price filter SKIPPED, relaxed threshold")
        elif is_tpsl_continuation:
            logger.info(f"   💰 TP/SL continuation mode: moderate threshold")

        # 閾値チェック（レジーム別の閾値は trading_logic 内で処理済み）
        if not should_trade or not trade_type:
            logger.info(f"⏸️  No trade signal")
            return

        # v3.20.0: 既存ポジション確認（MAX_POSITIONS未満なら追加発注可能）
        existing_positions = self.api.get_positions(symbol=self.symbol)
        existing_count = len(existing_positions) if existing_positions else 0

        if existing_count >= self.MAX_POSITIONS:
            logger.warning(f"⚠️ Max positions reached ({existing_count}/{self.MAX_POSITIONS}) - skipping new order")
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"DUPLICATE_PREVENTION: Skipped, {existing_count}/{self.MAX_POSITIONS} positions\n")
            except:
                pass
            return

        # 残高確認
        balance = self.api.get_account_balance()
        available_jpy = 0

        if 'data' in balance:
            for asset in balance['data']:
                if asset['symbol'] == 'JPY':
                    available_jpy = float(asset['available'])

        logger.info(f"💰 Available JPY: ¥{available_jpy:.2f}")

        if available_jpy < 100:
            logger.warning("⚠️  Insufficient JPY balance")
            return

        # v3.20.0: 残高全額を1回の注文で使い切る（手数料1回）
        max_jpy = available_jpy * 0.95
        max_doge_quantity = int(max_jpy / current_price)
        trade_size = max(10, (max_doge_quantity // 10) * 10)  # GMO Coin: 10DOGE単位必須

        logger.info(f"🎯 Placing {trade_type.upper()} order: {trade_size} DOGE (full balance ¥{max_jpy:.0f})")
        logger.info(f"   Stop Loss: ¥{stop_loss:.2f}, Take Profit: ¥{take_profit:.2f}")

        # 1回の注文で全額使用（手数料1回）
        success = self._place_order(trade_type, trade_size, current_price, reason, stop_loss, take_profit)

        if success:
            # 取引記録
            self.trading_logic.record_trade(trade_type, current_price)

    def _place_order(self, trade_type, size, price, reason, stop_loss, take_profit):
        """注文実行（SL/TP記録付き・重複防止付き v3.17.6）"""
        # v3.20.0: サイクル内注文数ガード（MAX_POSITIONS件まで許可）
        if self._orders_placed_this_cycle >= self.MAX_POSITIONS:
            logger.warning(f"⚠️ [CYCLE_GUARD] Max orders/cycle reached ({self._orders_placed_this_cycle}/{self.MAX_POSITIONS})")
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"CYCLE_GUARD: {trade_type} blocked, {self._orders_placed_this_cycle}/{self.MAX_POSITIONS} orders this cycle\n")
            except:
                pass
            return False

        # v3.20.0: 時間ベースの重複注文防止（同サイクル2本目以降はスキップ）
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if self._orders_placed_this_cycle == 0 and self.last_order_time is not None:
            # サイクル最初の注文のみ60秒チェック（2本目以降は意図的な連続注文なのでスキップ）
            elapsed = (now - self.last_order_time).total_seconds()
            if elapsed < 60:
                logger.warning(f"⚠️ [DUPLICATE_GUARD] Order blocked - only {elapsed:.1f}s since last order (min 60s)")
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"DUPLICATE_GUARD: {trade_type} blocked, {elapsed:.1f}s since last order\n")
                except:
                    pass
                return False

        # v3.20.0: 注文直前のポジション存在チェック（MAX_POSITIONS上限）
        # 5秒待機してAPIに決済が反映されるのを待つ
        time.sleep(5)
        try:
            pre_check_positions = self.api.get_positions(symbol=self.symbol)
            if pre_check_positions and len(pre_check_positions) >= self.MAX_POSITIONS:
                logger.warning(f"⚠️ [MAX_POS_GUARD] {len(pre_check_positions)}/{self.MAX_POSITIONS} positions exist - blocking {trade_type}")
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"MAX_POS_GUARD: {trade_type} blocked, {len(pre_check_positions)}/{self.MAX_POSITIONS} positions exist\n")
                except:
                    pass
                return False
        except Exception as e:
            logger.warning(f"⚠️ Pre-order position check failed: {e} - proceeding with order")

        try:
            result = self.api.place_order(
                symbol=self.symbol,
                side=trade_type.upper(),
                execution_type="MARKET",
                size=str(size)
            )

            if 'data' in result:
                # v3.17.6: 注文成功時刻を記録（メモリ + ファイル永続化）
                self.last_order_time = now
                self._save_last_order_time(now)
                self._orders_placed_this_cycle += 1  # v3.20.0: サイクル内注文カウント
                logger.info(f"✅ {trade_type.upper()} order successful!")
                logger.info(f"   Size: {size} DOGE, Price: ¥{price:.2f}")
                logger.info(f"   Reason: {reason}")

                # ファイルログに記録（可視性向上）
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"ENTRY_SUCCESS: {trade_type.upper()} {size} DOGE @ ¥{price:.2f}\n")
                        f.write(f"ENTRY_REASON: {reason}\n")
                        f.write(f"ENTRY_SL_TP: SL=¥{stop_loss:.2f}, TP=¥{take_profit:.2f}\n")
                        f.flush()  # 即座にディスクに書き込み
                    logger.info(f"📝 Entry log written to file")
                except Exception as e:
                    logger.error(f"❌ Failed to write entry log: {e}")
                    # エラーでも継続

                # 注文後、ポジションIDを取得してSL/TP記録（v2.7.2: 待機時間延長で重複防止）
                time.sleep(5)  # 2秒→5秒に延長
                positions = self.api.get_positions(symbol=self.symbol)

                if positions:
                    # 最新のポジション（今開いたもの）を取得
                    latest_position = positions[-1]
                    position_id = latest_position.get('positionId')

                    # v3.4.0: トレーリングストップ初期化
                    self.active_positions_stops[position_id] = {
                        'stop_loss': stop_loss,
                        'take_profit': None,  # 固定TPなし（トレーリングストップで管理）
                        'peak_pl_ratio': 0.0,
                        'trailing_sl_ratio': -0.008,  # 初期SL -0.8%
                    }

                    logger.info(f"📝 Trailing stop initialized for position {position_id}")
                    logger.info(f"   Initial SL: -0.8% | +0.3%→0% | +1%→+0.5% | +1.5%→+1% | +2%→+1.5%")
                    logger.info(f"📊 Active positions: {len(positions)}")

                    # ファイルログにポジションID記録
                    try:
                        with open('bot_execution_log.txt', 'a') as f:
                            f.write(f"POSITION_OPENED: ID={position_id}, {trade_type.upper()} {size} @ ¥{price:.2f}\n")
                            f.flush()  # 即座にディスクに書き込み
                        logger.info(f"📝 Position opened log written to file")
                    except Exception as e:
                        logger.error(f"❌ Failed to write position log: {e}")
                        # エラーでも継続

                # v3.13.0: record_tradeは呼び出し元(_check_for_new_trade等)で実行するため、ここでは不要
                return True
            else:
                logger.error(f"❌ Order failed: {result}")
                # ファイルログに失敗記録
                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"ENTRY_FAILED: {trade_type.upper()} {size} DOGE - {result}\n")
                except:
                    pass
                return False

        except Exception as e:
            logger.error(f"Error placing order: {e}", exc_info=True)
            return False

    def _display_performance_stats(self):
        """パフォーマンス統計表示"""
        stats = self.trading_logic.get_performance_stats()

        if stats:
            logger.info(f"\n{'─'*70}")
            logger.info(f"📊 Performance Stats (Last {stats['total_trades']} trades)")
            logger.info(f"{'─'*70}")
            logger.info(f"   Win Rate:     {stats['win_rate']*100:.1f}% ({stats['wins']}W / {stats['losses']}L)")
            logger.info(f"   Total P/L:    ¥{stats['total_pnl']:.2f}")
            logger.info(f"   Avg P/L:      ¥{stats['avg_pnl']:.2f}")
            logger.info(f"{'─'*70}\n")

if __name__ == "__main__":
    bot = OptimizedLeverageTradingBot()
    bot.run()
