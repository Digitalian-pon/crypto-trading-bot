"""
DOGE_JPYレバレッジ取引ボット - Railway/Standalone対応版
空売り（SELL）とロング（BUY）の両方に対応
"""

import logging
import time
from datetime import datetime
import sys
from services.gmo_api import GMOCoinAPI
from services.enhanced_trading_logic import EnhancedTradingLogic
from services.data_service import DataService
from config import load_config

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class LeverageTradingBot:
    """
    DOGE_JPYレバレッジ取引ボット
    - BUY: ロングポジション（価格上昇で利益）
    - SELL: ショートポジション（価格下降で利益=空売り）
    """

    def __init__(self):
        config = load_config()
        api_key = config.get('api_credentials', 'api_key')
        api_secret = config.get('api_credentials', 'api_secret')

        self.api = GMOCoinAPI(api_key, api_secret)
        self.data_service = DataService(api_key, api_secret)
        self.trading_logic = EnhancedTradingLogic()

        # 取引設定
        self.symbol = config.get('trading', 'default_symbol', fallback='DOGE_JPY')
        self.timeframe = config.get('trading', 'default_timeframe', fallback='5m')
        self.interval = 60  # チェック間隔（秒）

    def run(self):
        """メインループ"""
        logger.info("="*60)
        logger.info(f"DOGE_JPY Leverage Trading Bot Started")
        logger.info(f"Symbol: {self.symbol}, Timeframe: {self.timeframe}")
        logger.info("="*60)

        while True:
            try:
                self._trading_cycle()
                logger.info(f"Sleeping for {self.interval} seconds...")
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                time.sleep(self.interval)

    def _trading_cycle(self):
        """1回の取引サイクル"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Trading Cycle - {datetime.now()}")
        logger.info(f"{'='*60}")

        # 1. 市場データ取得
        df = self.data_service.get_data_with_indicators(
            self.symbol,
            interval=self.timeframe,
            limit=100
        )

        if df is None or df.empty:
            logger.error("Failed to get market data")
            return

        current_price = float(df['close'].iloc[-1])
        logger.info(f"💹 Current {self.symbol} price: ¥{current_price:.2f}")

        # 2. 既存ポジション確認
        positions = self.api.get_positions(symbol=self.symbol)
        logger.info(f"📊 Active positions: {len(positions)}")

        # 3. ポジションの決済チェック（全ポジションをチェック）
        if positions:
            logger.info(f"Checking {len(positions)} positions for closing...")
            self._check_positions_for_closing(positions, current_price, df.iloc[-1].to_dict())
            # 決済後、ポジションを再取得して確認
            positions = self.api.get_positions(symbol=self.symbol)
            logger.info(f"📊 Positions after close check: {len(positions)}")

        # 4. ポジションがない場合は新規取引シグナルをチェック
        if not positions:
            logger.info("✅ No positions - checking for new trade opportunities...")
            self._check_for_new_trade(df, current_price)
        else:
            logger.info(f"⏸️ Still have {len(positions)} open positions - waiting...")

    def _check_positions_for_closing(self, positions, current_price, indicators):
        """ポジション決済チェック"""
        for position in positions:
            side = position.get('side')
            size = position.get('size')
            entry_price = float(position.get('price', 0))
            position_id = position.get('positionId')

            # P/L計算
            if side == 'BUY':
                pl_ratio = (current_price - entry_price) / entry_price
            else:  # SELL (空売り)
                pl_ratio = (entry_price - current_price) / entry_price

            logger.info(f"Position {position_id} ({side}): Entry=¥{entry_price:.2f}, P/L={pl_ratio*100:.2f}%")

            # 決済条件チェック
            should_close, reason = self._should_close_position(position, current_price, indicators, pl_ratio)

            if should_close:
                logger.info(f"🔄 Closing position: {reason}")
                self._close_position(position, current_price, reason)

    def _should_close_position(self, position, current_price, indicators, pl_ratio):
        """ポジション決済判定"""
        side = position.get('side')

        # 損切り: 3%損失
        if pl_ratio <= -0.03:
            return True, f"Stop loss: {pl_ratio*100:.2f}%"

        # 利確: 5%利益
        if pl_ratio >= 0.05:
            return True, f"Take profit: {pl_ratio*100:.2f}%"

        # 新規取引シグナルをチェック（反転シグナル）
        should_trade, trade_type, reason, confidence = self.trading_logic.should_trade(indicators)

        logger.info(f"  → Close signal check: should_trade={should_trade}, type={trade_type}, confidence={confidence:.2f}")

        if should_trade and trade_type and confidence >= 0.8:
            # BUYポジションを持っている時にSELLシグナル → 決済
            if side == 'BUY' and trade_type.upper() == 'SELL':
                return True, f"Reversal signal: {trade_type.upper()} (confidence={confidence:.2f}) - {reason}"
            # SELLポジションを持っている時にBUYシグナル → 決済
            elif side == 'SELL' and trade_type.upper() == 'BUY':
                return True, f"Reversal signal: {trade_type.upper()} (confidence={confidence:.2f}) - {reason}"

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
                logger.info(f"✅ Position closed successfully: {result}")
            else:
                logger.error(f"❌ Failed to close position: {result}")

        except Exception as e:
            logger.error(f"Error closing position: {e}", exc_info=True)

    def _check_for_new_trade(self, df, current_price):
        """新規取引チェック"""
        last_row = df.iloc[-1].to_dict()

        # シグナル取得
        should_trade, trade_type, reason, confidence = self.trading_logic.should_trade(last_row)

        logger.info(f"Signal: should_trade={should_trade}, type={trade_type}, confidence={confidence:.2f}")

        if not should_trade or not trade_type or confidence < 0.5:
            logger.info("No strong signal - waiting...")
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
            logger.warning("Insufficient JPY balance")
            return

        # ポジションサイズ計算（残高の95%）
        max_jpy = available_jpy * 0.95
        max_doge_quantity = int(max_jpy / current_price)
        trade_size = max(10, (max_doge_quantity // 10) * 10)  # 10DOGE単位

        logger.info(f"🎯 Placing {trade_type.upper()} order: {trade_size} DOGE")

        # 注文実行
        self._place_order(trade_type, trade_size, current_price, reason)

    def _place_order(self, trade_type, size, price, reason):
        """注文実行"""
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

                # 注文後確認
                time.sleep(2)
                positions = self.api.get_positions(symbol=self.symbol)
                logger.info(f"📊 Positions after order: {len(positions)}")
            else:
                logger.error(f"❌ Order failed: {result}")

        except Exception as e:
            logger.error(f"Error placing order: {e}", exc_info=True)

if __name__ == "__main__":
    bot = LeverageTradingBot()
    bot.run()
