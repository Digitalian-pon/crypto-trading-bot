"""
最適化されたDOGE_JPYレバレッジ取引ボット
OptimizedTradingLogicを使用した改良版
"""

import logging
import time
from datetime import datetime
import sys
from services.gmo_api import GMOCoinAPI
from services.optimized_trading_logic import OptimizedTradingLogic
from services.data_service import DataService
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
        self.interval = 180  # チェック間隔（秒）- 3分（1時間足に適した間隔）

        # 動的ストップロス/テイクプロフィット管理
        self.active_positions_stops = {}  # {position_id: {'stop_loss': price, 'take_profit': price}}

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
                time.sleep(self.interval)

    def _trading_cycle(self):
        """1回の取引サイクル"""
        cycle_time = datetime.now()

        # ボット稼働状況をログファイルに記録（ダッシュボードで表示可能）
        try:
            log_file = 'bot_execution_log.txt'
            with open(log_file, 'a') as f:
                f.write(f"\n{'='*70}\n")
                f.write(f"CYCLE_START: {cycle_time.isoformat()}\n")
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

        # 標準出力にも詳細を表示
        if positions:
            for pos in positions:
                logger.info(f"  └─ Position {pos.get('positionId')}: {pos.get('side')} {pos.get('size')} @ ¥{pos.get('price')}")

        # 3. ポジションの決済チェック（動的SL/TP使用）
        any_closed = False
        reversal_signal = False
        tp_sl_closed = False
        reversal_trade_type = None

        if positions:
            logger.info(f"Checking {len(positions)} positions for closing...")
            # ファイルログにも記録
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"CHECKING_CLOSE: Analyzing {len(positions)} positions\n")
            except:
                pass

            any_closed, reversal_signal, tp_sl_closed, reversal_trade_type = self._check_positions_for_closing(positions, current_price, df)

            # 決済後、ポジションを再取得
            positions = self.api.get_positions(symbol=self.symbol)
            logger.info(f"📊 Positions after close check: {len(positions)}")

            # ファイルログにも記録
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"CLOSE_CHECK_RESULT: any_closed={any_closed}, reversal={reversal_signal}, tp_sl={tp_sl_closed}\n")
                    f.write(f"POSITIONS_REMAINING: {len(positions)}\n")
            except:
                pass

        # 4. パフォーマンス統計表示
        self._display_performance_stats()

        # 5. 新規取引シグナルをチェック
        # - 反転シグナルで決済された場合は即座にチェック（機会損失防止、逆注文を強制実行）
        # - TP/SL決済の場合は継続チェック（中程度の閾値）
        # - 全ポジション決済された場合もチェック
        # - ポジションがない場合もチェック
        should_check_new_trade = (
            reversal_signal or                    # 反転シグナル決済
            tp_sl_closed or                       # TP/SL決済（継続機会）
            (any_closed and not positions) or     # 全ポジション決済
            not positions                         # ポジションなし
        )

        if should_check_new_trade:
            if reversal_signal and reversal_trade_type:
                logger.info(f"🔄 Position closed by reversal signal - FORCING {reversal_trade_type} order immediately...")
                # 反転シグナル時は、シグナル再評価なしで強制的に反対注文を出す
                self._place_forced_reversal_order(reversal_trade_type, current_price, df)
            elif tp_sl_closed:
                logger.info("💰 Position closed by TP/SL - checking for continuation opportunity with moderate threshold...")
                # TP/SL決済時は中程度の閾値で継続機会を検討
                self._check_for_new_trade(df, current_price, is_tpsl_continuation=True)
            elif not positions:
                logger.info("✅ No positions - checking for new trade opportunities...")
                self._check_for_new_trade(df, current_price, is_reversal=False)
        else:
            logger.info(f"⏸️  Still have {len(positions)} open positions - waiting...")

    def _check_positions_for_closing(self, positions, current_price, df):
        """
        ポジション決済チェック（動的SL/TP使用）

        Returns:
            (any_closed: bool, reversal_signal: bool, tp_sl_closed: bool, reversal_trade_type: str or None)
        """
        any_closed = False
        reversal_signal = False
        tp_sl_closed = False
        reversal_trade_type = None  # 反転シグナルのタイプ（BUY/SELL）

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

            # 動的SL/TP取得
            if position_id in self.active_positions_stops:
                stop_loss = self.active_positions_stops[position_id]['stop_loss']
                take_profit = self.active_positions_stops[position_id]['take_profit']
                logger.info(f"   Dynamic SL=¥{stop_loss:.2f}, TP=¥{take_profit:.2f}")
            else:
                # SL/TPが記録されていない場合はデフォルト値を使用
                stop_loss = entry_price * 0.98 if side == 'BUY' else entry_price * 1.02
                take_profit = entry_price * 1.03 if side == 'BUY' else entry_price * 0.97
                logger.warning(f"   No recorded SL/TP, using defaults: SL=¥{stop_loss:.2f}, TP=¥{take_profit:.2f}")

            # 決済条件チェック
            should_close, reason, close_trade_type = self._should_close_position(
                position, current_price, df.iloc[-1].to_dict(), pl_ratio, stop_loss, take_profit
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
                self._close_position(position, current_price, reason)
                any_closed = True

                # 決済理由を判定
                if "Reversal" in reason or "reversal" in reason:
                    # 反転シグナルで決済された場合
                    reversal_signal = True
                    reversal_trade_type = close_trade_type  # 反転シグナルのタイプを記録
                    logger.info(f"🔄 REVERSAL DETECTED - Will place {close_trade_type} order immediately")
                elif "Take Profit" in reason or "Stop Loss" in reason:
                    # TP/SLで決済された場合
                    tp_sl_closed = True
                    logger.info(f"💰 TP/SL CLOSE - Will check for continuation with moderate threshold")

                # 決済後、SL/TP記録を削除
                if position_id in self.active_positions_stops:
                    del self.active_positions_stops[position_id]

                # 取引結果を記録
                self.trading_logic.record_trade(side, entry_price, pl_ratio)

        return any_closed, reversal_signal, tp_sl_closed, reversal_trade_type

    def _should_close_position(self, position, current_price, indicators, pl_ratio, stop_loss, take_profit):
        """
        ポジション決済判定（動的SL/TP使用）

        Returns:
            (should_close: bool, reason: str, trade_type: str or None)
        """
        side = position.get('side')
        size = float(position.get('size', 0))  # 文字列→floatに変換（重要！）
        entry_price = float(position.get('price', 0))

        logger.info(f"   📊 Closure Decision Analysis:")
        logger.info(f"      Position: {side} {size} @ ¥{entry_price:.3f}")
        logger.info(f"      Current Price: ¥{current_price:.3f}")
        logger.info(f"      P/L Ratio: {pl_ratio*100:.2f}%")

        # 【最優先】利益・損失チェック（最適化版）
        # 往復手数料¥2を考慮し、純利益で判定
        if side == 'BUY':
            profit_jpy = size * (current_price - entry_price)
        else:  # SELL
            profit_jpy = size * (entry_price - current_price)

        # 往復手数料を引いた純利益
        net_profit = profit_jpy - 2.0  # 往復手数料¥2

        logger.info(f"      Gross Profit: ¥{profit_jpy:.2f}")
        logger.info(f"      Net Profit (after fees): ¥{net_profit:.2f}")

        # 【トレーリングストップ】¥2以上の利益が出ている場合、損切りラインを建値に移動
        if position_id in self.active_positions_stops:
            original_stop_loss = self.active_positions_stops[position_id].get('original_stop_loss')

            # トレーリングストップがまだ発動していない場合
            if original_stop_loss is None and net_profit >= 2.0:
                logger.info(f"      🔒 TRAILING STOP ACTIVATED: Net profit ¥{net_profit:.2f} >= ¥2.0")
                logger.info(f"         Moving stop loss to break-even (entry price)")

                # 元のストップロスを保存
                self.active_positions_stops[position_id]['original_stop_loss'] = stop_loss

                # 損切りラインを建値に移動（リスクフリー）
                self.active_positions_stops[position_id]['stop_loss'] = entry_price
                stop_loss = entry_price

                try:
                    with open('bot_execution_log.txt', 'a') as f:
                        f.write(f"TRAILING_STOP_ACTIVATED: net_profit=¥{net_profit:.2f}, new_stop_loss=¥{entry_price:.3f}\n")
                except:
                    pass

        # ログファイルに決済判定を記録
        try:
            with open('bot_execution_log.txt', 'a') as f:
                f.write(f"POSITION_CHECK: {side} {size} @ ¥{entry_price:.3f}\n")
                f.write(f"CURRENT_PRICE: ¥{current_price:.3f}\n")
                f.write(f"GROSS_PROFIT: ¥{profit_jpy:.2f}\n")
                f.write(f"NET_PROFIT: ¥{net_profit:.2f}\n")
                f.write(f"P/L_RATIO: {pl_ratio*100:.2f}%\n")
                f.write(f"THRESHOLD: ¥2.5 (profit) / -0.5% (loss) / -¥2.0 (absolute loss)\n")
        except:
            pass

        # 【利確】純利益が¥2.5以上なら利確（手数料¥2 + 最小利益¥0.5）
        if net_profit >= 2.5:
            logger.info(f"   ✅ CLOSE DECISION: Profit target reached: ¥{net_profit:.2f} (≥¥2.5)")
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"DECISION: CLOSE (net_profit ¥{net_profit:.2f} >= ¥2.5)\n")
            except:
                pass
            return True, f"Take Profit: ¥{net_profit:.2f}", None

        # 【損切り】固定損失リミット: -0.5%で早期損切り（1時間足に最適化）
        if pl_ratio <= -0.005:  # -0.5%以上の損失で早期損切り
            logger.info(f"   🚨 CLOSE DECISION: Stop Loss Hit: {pl_ratio*100:.2f}% <= -0.5%")
            logger.info(f"      Net loss in JPY: ¥{net_profit:.2f}")
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"DECISION: CLOSE (stop_loss {pl_ratio*100:.2f}% <= -0.5%, net_loss ¥{net_profit:.2f})\n")
            except:
                pass
            return True, f"Stop Loss: {pl_ratio*100:.2f}% (¥{net_profit:.2f})", None

        # 【緊急損切り】絶対額での損切り: -¥2.0（より早めに）
        if net_profit <= -2.0:
            logger.info(f"   🚨 CLOSE DECISION: Absolute Loss Limit Hit: ¥{net_profit:.2f} <= -¥2.0")
            try:
                with open('bot_execution_log.txt', 'a') as f:
                    f.write(f"DECISION: CLOSE (absolute_loss ¥{net_profit:.2f} <= -¥2.0)\n")
            except:
                pass
            return True, f"Absolute Loss Limit: ¥{net_profit:.2f}", None

        # 利益も損失も小さい場合はHOLDをログに記録（デバッグ用）
        logger.info(f"   ⏸️  HOLD: Profit ¥{net_profit:.2f} (target ¥2.5), Loss {pl_ratio*100:.2f}% (limit -0.5%)")
        try:
            with open('bot_execution_log.txt', 'a') as f:
                f.write(f"DECISION: HOLD (net_profit ¥{net_profit:.2f} < ¥2.5 and pl_ratio {pl_ratio*100:.2f}% > -0.5%)\n")
        except:
            pass

        # 動的ストップロス/テイクプロフィットチェック
        logger.info(f"      SL: ¥{stop_loss:.3f}, TP: ¥{take_profit:.3f}")
        if side == 'BUY':
            if current_price <= stop_loss:
                logger.info(f"   ✅ CLOSE DECISION: Stop Loss Hit (¥{current_price:.2f} <= ¥{stop_loss:.2f})")
                return True, f"Stop Loss Hit: ¥{current_price:.2f} <= ¥{stop_loss:.2f}", None
            if current_price >= take_profit:
                logger.info(f"   ✅ CLOSE DECISION: Take Profit Hit (¥{current_price:.2f} >= ¥{take_profit:.2f})")
                return True, f"Take Profit Hit: ¥{current_price:.2f} >= ¥{take_profit:.2f}", None

        else:  # SELL
            if current_price >= stop_loss:
                logger.info(f"   ✅ CLOSE DECISION: Stop Loss Hit (¥{current_price:.2f} >= ¥{stop_loss:.2f})")
                return True, f"Stop Loss Hit: ¥{current_price:.2f} >= ¥{stop_loss:.2f}", None
            if current_price <= take_profit:
                logger.info(f"   ✅ CLOSE DECISION: Take Profit Hit (¥{current_price:.2f} <= ¥{take_profit:.2f})")
                return True, f"Take Profit Hit: ¥{current_price:.2f} <= ¥{take_profit:.2f}", None

        logger.info(f"      SL/TP not hit")

        # 反転シグナルチェック（決済判定用 - 緩い閾値とフィルタースキップ）
        # 注: 価格変動フィルターは削除（純利益チェックで十分）
        # skip_price_filter=True により、価格フィルター＋閾値の両方が緩和される
        logger.info(f"      Checking reversal signal...")
        should_trade, trade_type, reason, confidence, _, _ = self.trading_logic.should_trade(
            indicators, None, skip_price_filter=True
        )

        logger.info(f"      Reversal result: should_trade={should_trade}, type={trade_type}, confidence={confidence:.2f}, reason={reason}")

        # 決済判定の閾値: 1.0（強い反転シグナルのみで決済 - 誤判定防止）
        if should_trade and trade_type and confidence >= 1.0:
            logger.info(f"      Checking signal match: position={side}, signal={trade_type}, confidence={confidence:.2f} >= 1.0")
            if side == 'BUY' and trade_type.upper() == 'SELL':
                logger.info(f"   ✅ CLOSE DECISION: Strong Reversal SELL (confidence={confidence:.2f})")
                return True, f"Strong Reversal: SELL (confidence={confidence:.2f})", 'SELL'
            elif side == 'SELL' and trade_type.upper() == 'BUY':
                logger.info(f"   ✅ CLOSE DECISION: Strong Reversal BUY (confidence={confidence:.2f})")
                return True, f"Strong Reversal: BUY (confidence={confidence:.2f})", 'BUY'
            else:
                logger.info(f"      Signal direction doesn't match position (pos={side}, sig={trade_type})")
        else:
            if not should_trade:
                logger.info(f"      No reversal signal detected")
            elif not trade_type:
                logger.info(f"      No trade type in signal")
            else:
                logger.info(f"      Confidence too low: {confidence:.2f} < 0.5")

        logger.info(f"   ❌ No close signal - position will be held")
        return False, "No close signal", None

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
            logger.warning(f"⚠️  Method 1 failed: {error_msg}")
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
            return

        # ポジションサイズ計算（残高の95%）
        max_jpy = available_jpy * 0.95
        max_doge_quantity = int(max_jpy / current_price)
        trade_size = max(10, (max_doge_quantity // 10) * 10)  # 10DOGE単位

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

        # 注文実行
        success = self._place_order(trade_type, trade_size, current_price,
                                    f"Forced {trade_type.upper()} on trend reversal",
                                    stop_loss, take_profit)

        if success:
            # 取引記録
            self.trading_logic.record_trade(trade_type, current_price)
            logger.info(f"✅ Forced reversal order completed successfully")

    def _check_for_new_trade(self, df, current_price, is_reversal=False, is_tpsl_continuation=False):
        """
        新規取引チェック（動的SL/TP付き）

        Args:
            df: 市場データのDataFrame
            current_price: 現在価格
            is_reversal: 反転シグナル直後かどうか（Trueの場合は価格変動フィルターをスキップ、緩い閾値）
            is_tpsl_continuation: TP/SL決済直後かどうか（Trueの場合は中程度の閾値）
        """
        last_row = df.iloc[-1].to_dict()

        # シグナル取得（DataFrameも渡す）
        should_trade, trade_type, reason, confidence, stop_loss, take_profit = self.trading_logic.should_trade(
            last_row, df, skip_price_filter=is_reversal, is_tpsl_continuation=is_tpsl_continuation
        )

        logger.info(f"🔍 Signal: should_trade={should_trade}, type={trade_type}, confidence={confidence:.2f}")
        if is_reversal:
            logger.info(f"   🔄 Reversal mode: price filter SKIPPED, relaxed threshold")
        elif is_tpsl_continuation:
            logger.info(f"   💰 TP/SL continuation mode: moderate threshold")

        # 閾値チェック（レジーム別の閾値は trading_logic 内で処理済み）
        if not should_trade or not trade_type:
            logger.info(f"⏸️  No trade signal")
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

        # ポジションサイズ計算（残高の95%）
        max_jpy = available_jpy * 0.95
        max_doge_quantity = int(max_jpy / current_price)
        trade_size = max(10, (max_doge_quantity // 10) * 10)  # 10DOGE単位

        logger.info(f"🎯 Placing {trade_type.upper()} order: {trade_size} DOGE")
        logger.info(f"   Stop Loss: ¥{stop_loss:.2f}, Take Profit: ¥{take_profit:.2f}")

        # 注文実行
        success = self._place_order(trade_type, trade_size, current_price, reason, stop_loss, take_profit)

        if success:
            # 取引記録
            self.trading_logic.record_trade(trade_type, current_price)

    def _place_order(self, trade_type, size, price, reason, stop_loss, take_profit):
        """注文実行（SL/TP記録付き）"""
        try:
            result = self.api.place_order(
                symbol=self.symbol,
                side=trade_type.upper(),
                execution_type="MARKET",
                size=str(size)
            )

            if 'data' in result:
                logger.info(f"✅ {trade_type.upper()} order successful!")
                logger.info(f"   Size: {size} DOGE, Price: ¥{price:.2f}")
                logger.info(f"   Reason: {reason}")

                # 注文後、ポジションIDを取得してSL/TP記録
                time.sleep(2)
                positions = self.api.get_positions(symbol=self.symbol)

                if positions:
                    # 最新のポジション（今開いたもの）を取得
                    latest_position = positions[-1]
                    position_id = latest_position.get('positionId')

                    # SL/TP記録（トレーリングストップ用のフィールドも初期化）
                    self.active_positions_stops[position_id] = {
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'original_stop_loss': None  # トレーリングストップ未発動状態
                    }

                    logger.info(f"📝 Recorded SL/TP for position {position_id}")
                    logger.info(f"   SL: ¥{stop_loss:.2f}, TP: ¥{take_profit:.2f}")
                    logger.info(f"   Trailing stop: Ready (activates at ¥2+ profit)")
                    logger.info(f"📊 Active positions: {len(positions)}")

                return True
            else:
                logger.error(f"❌ Order failed: {result}")
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
