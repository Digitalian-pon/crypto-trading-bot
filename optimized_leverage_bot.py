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
        self.timeframe = config.get('trading', 'default_timeframe', fallback='5m')
        self.interval = 180  # チェック間隔（秒）- 3分（現実的な間隔に変更）

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
        logger.info(f"\n{'='*70}")
        logger.info(f"🔄 Trading Cycle - {datetime.now()}")
        logger.info(f"{'='*70}")

        # 1. 市場データ取得（過去100本）
        df = self.data_service.get_data_with_indicators(
            self.symbol,
            interval=self.timeframe,
            limit=100
        )

        if df is None or df.empty:
            logger.error("❌ Failed to get market data")
            return

        current_price = float(df['close'].iloc[-1])
        logger.info(f"💹 Current {self.symbol} price: ¥{current_price:.2f}")

        # 市場レジーム表示
        market_regime = df['market_regime'].iloc[-1] if 'market_regime' in df.columns else 'Unknown'
        logger.info(f"🎯 Market Regime: {market_regime}")

        # 2. 既存ポジション確認
        positions = self.api.get_positions(symbol=self.symbol)
        logger.info(f"📊 Active positions: {len(positions)}")

        # 3. ポジションの決済チェック（動的SL/TP使用）
        any_closed = False
        reversal_signal = False

        if positions:
            logger.info(f"Checking {len(positions)} positions for closing...")
            any_closed, reversal_signal = self._check_positions_for_closing(positions, current_price, df)
            # 決済後、ポジションを再取得
            positions = self.api.get_positions(symbol=self.symbol)
            logger.info(f"📊 Positions after close check: {len(positions)}")

        # 4. パフォーマンス統計表示
        self._display_performance_stats()

        # 5. 新規取引シグナルをチェック
        # - 反転シグナルで決済された場合は即座にチェック（機会損失防止）
        # - 全ポジション決済された場合もチェック
        # - ポジションがない場合もチェック
        should_check_new_trade = (
            reversal_signal or                    # 反転シグナル決済
            (any_closed and not positions) or     # 全ポジション決済
            not positions                         # ポジションなし
        )

        if should_check_new_trade:
            if reversal_signal:
                logger.info("🔄 Position closed by reversal signal - checking for opposite position immediately...")
            elif not positions:
                logger.info("✅ No positions - checking for new trade opportunities...")

            self._check_for_new_trade(df, current_price)
        else:
            logger.info(f"⏸️  Still have {len(positions)} open positions - waiting...")

    def _check_positions_for_closing(self, positions, current_price, df):
        """
        ポジション決済チェック（動的SL/TP使用）

        Returns:
            (any_closed: bool, reversal_signal: bool)
        """
        any_closed = False
        reversal_signal = False

        for position in positions:
            side = position.get('side')
            size = position.get('size')
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
            should_close, reason = self._should_close_position(
                position, current_price, df.iloc[-1].to_dict(), pl_ratio, stop_loss, take_profit
            )

            if should_close:
                logger.info(f"🔄 Closing position: {reason}")
                self._close_position(position, current_price, reason)
                any_closed = True

                # 反転シグナルで決済された場合
                if "Reversal" in reason or "reversal" in reason:
                    reversal_signal = True
                    logger.info(f"🔄 REVERSAL DETECTED - Will check for opposite position immediately")

                # 決済後、SL/TP記録を削除
                if position_id in self.active_positions_stops:
                    del self.active_positions_stops[position_id]

                # 取引結果を記録
                self.trading_logic.record_trade(side, entry_price, pl_ratio)

        return any_closed, reversal_signal

    def _should_close_position(self, position, current_price, indicators, pl_ratio, stop_loss, take_profit):
        """ポジション決済判定（動的SL/TP使用）"""
        side = position.get('side')

        # 動的ストップロス/テイクプロフィットチェック
        if side == 'BUY':
            if current_price <= stop_loss:
                return True, f"Stop Loss Hit: ¥{current_price:.2f} <= ¥{stop_loss:.2f}"
            if current_price >= take_profit:
                return True, f"Take Profit Hit: ¥{current_price:.2f} >= ¥{take_profit:.2f}"

        else:  # SELL
            if current_price >= stop_loss:
                return True, f"Stop Loss Hit: ¥{current_price:.2f} >= ¥{stop_loss:.2f}"
            if current_price <= take_profit:
                return True, f"Take Profit Hit: ¥{current_price:.2f} <= ¥{take_profit:.2f}"

        # 最小価格変動チェック（手数料負け防止）
        entry_price = float(position.get('price', 0))
        price_change_ratio = abs(current_price - entry_price) / entry_price

        if price_change_ratio < 0.005:  # 0.5%未満では決済しない
            logger.info(f"   → Price change too small ({price_change_ratio*100:.2f}% < 0.5%) - holding")
            return False, "Price change too small"

        # 反転シグナルチェック（高信頼度のみ）
        should_trade, trade_type, reason, confidence, _, _ = self.trading_logic.should_trade(indicators, None)

        logger.info(f"   → Reversal check: should_trade={should_trade}, type={trade_type}, confidence={confidence:.2f}")

        if should_trade and trade_type and confidence >= 1.2:  # 3.0 → 1.2 に引き下げ（現実的な閾値）
            if side == 'BUY' and trade_type.upper() == 'SELL':
                return True, f"Strong Reversal: SELL (confidence={confidence:.2f})"
            elif side == 'SELL' and trade_type.upper() == 'BUY':
                return True, f"Strong Reversal: BUY (confidence={confidence:.2f})"

        return False, "No close signal"

    def _close_position(self, position, current_price, reason):
        """ポジション決済"""
        try:
            symbol = position.get('symbol')
            side = position.get('side')
            size = position.get('size')
            position_id = position.get('positionId')

            close_side = "SELL" if side == "BUY" else "BUY"

            logger.info(f"Closing {side} position: {size} {symbol} at ¥{current_price:.2f}")

            result = self.api.close_position(
                symbol=symbol,
                side=close_side,
                execution_type="MARKET",
                position_id=position_id,
                size=str(size)
            )

            if result.get('status') == 0:
                logger.info(f"✅ Position closed successfully")
            else:
                logger.error(f"❌ Failed to close position: {result}")

        except Exception as e:
            logger.error(f"Error closing position: {e}", exc_info=True)

    def _check_for_new_trade(self, df, current_price):
        """新規取引チェック（動的SL/TP付き）"""
        last_row = df.iloc[-1].to_dict()

        # シグナル取得（DataFrameも渡す）
        should_trade, trade_type, reason, confidence, stop_loss, take_profit = self.trading_logic.should_trade(
            last_row, df
        )

        logger.info(f"🔍 Signal: should_trade={should_trade}, type={trade_type}, confidence={confidence:.2f}")

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

                    # SL/TP記録
                    self.active_positions_stops[position_id] = {
                        'stop_loss': stop_loss,
                        'take_profit': take_profit
                    }

                    logger.info(f"📝 Recorded SL/TP for position {position_id}")
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
