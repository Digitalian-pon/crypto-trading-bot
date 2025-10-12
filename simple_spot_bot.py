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

class SimpleSpotTradingBot:
    """
    シンプルな現物取引ボット - BTC/JPYのみ
    レバレッジなし、ポジション管理なし
    """

    def __init__(self):
        config = load_config()
        api_key = config.get('api_credentials', 'api_key')
        api_secret = config.get('api_credentials', 'api_secret')

        self.api = GMOCoinAPI(api_key, api_secret)
        self.data_service = DataService(api_key, api_secret)
        self.trading_logic = EnhancedTradingLogic()
        self.symbol = config.get('trading', 'default_symbol', fallback='BTC_JPY')
        self.timeframe = config.get('trading', 'default_timeframe', fallback='30m')
        self.running = False
        self.interval = 60  # 60秒間隔でチェック

        logger.info(f"Simple Spot Bot initialized - {self.symbol} on {self.timeframe}")

    def get_balances(self):
        """残高取得"""
        try:
            balance_response = self.api.get_account_balance()
            if 'data' not in balance_response:
                logger.error(f"Failed to get balance: {balance_response}")
                return None, None

            jpy_balance = 0
            btc_balance = 0

            for asset in balance_response['data']:
                if asset['symbol'] == 'JPY':
                    jpy_balance = float(asset['available'])
                elif asset['symbol'] == 'BTC':
                    btc_balance = float(asset['available'])

            logger.info(f"💰 Balances - JPY: {jpy_balance:.0f}, BTC: {btc_balance:.8f}")
            return jpy_balance, btc_balance

        except Exception as e:
            logger.error(f"Error getting balances: {e}")
            return None, None

    def execute_buy(self, current_price, jpy_balance):
        """BUY実行 - JPYでBTC購入"""
        try:
            # 95%の残高を使用
            max_jpy = jpy_balance * 0.95
            btc_amount = max_jpy / current_price

            # BTCの最小注文単位は0.0001
            btc_amount = round(btc_amount, 4)

            if btc_amount < 0.0001:
                logger.warning(f"Insufficient JPY for BUY: {jpy_balance:.0f} JPY")
                return False

            logger.info(f"🚀 Executing BUY: {btc_amount:.4f} BTC at {current_price:.0f} JPY")

            result = self.api.place_order(
                symbol=self.symbol,
                side="BUY",
                execution_type="MARKET",
                size=f"{btc_amount:.4f}"
            )

            if 'data' in result:
                logger.info(f"✅ BUY successful: {result['data']}")
                return True
            else:
                logger.error(f"❌ BUY failed: {result}")
                return False

        except Exception as e:
            logger.error(f"Error executing BUY: {e}")
            return False

    def execute_sell(self, btc_balance):
        """SELL実行 - BTC全額売却"""
        try:
            # BTC残高の95%を売却
            btc_amount = btc_balance * 0.95
            btc_amount = round(btc_amount, 4)

            if btc_amount < 0.0001:
                logger.warning(f"Insufficient BTC for SELL: {btc_balance:.8f} BTC")
                return False

            logger.info(f"🚀 Executing SELL: {btc_amount:.4f} BTC")

            result = self.api.place_order(
                symbol=self.symbol,
                side="SELL",
                execution_type="MARKET",
                size=f"{btc_amount:.4f}"
            )

            if 'data' in result:
                logger.info(f"✅ SELL successful: {result['data']}")
                return True
            else:
                logger.error(f"❌ SELL failed: {result}")
                return False

        except Exception as e:
            logger.error(f"Error executing SELL: {e}")
            return False

    def run(self):
        """メインループ"""
        logger.info("🤖 Starting Simple Spot Trading Bot...")
        self.running = True

        while self.running:
            try:
                logger.info("=" * 80)
                logger.info(f"🔍 Checking market at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                # 市場データ取得
                df = self.data_service.get_data_with_indicators(
                    symbol=self.symbol,
                    interval=self.timeframe,
                    limit=50
                )

                if df is None or df.empty:
                    logger.error("Failed to get market data")
                    time.sleep(self.interval)
                    continue

                # 現在価格と指標
                current_price = df['close'].iloc[-1]
                latest_data = df.iloc[-1].to_dict()

                logger.info(f"💹 Current {self.symbol} price: {current_price:.0f} JPY")

                # トレーディングシグナル
                should_trade, trade_type, reason, confidence = self.trading_logic.should_trade(latest_data)

                logger.info(f"📊 Signal: {trade_type if should_trade else 'NONE'} - {reason} (confidence: {confidence:.2f})")

                if not should_trade:
                    logger.info("⏸️  No trade signal - waiting")
                    time.sleep(self.interval)
                    continue

                # 残高取得
                jpy_balance, btc_balance = self.get_balances()

                if jpy_balance is None or btc_balance is None:
                    logger.error("Failed to get balances")
                    time.sleep(self.interval)
                    continue

                # シグナルに応じて取引実行
                if trade_type == 'BUY':
                    if jpy_balance > 100:  # 最低100円必要
                        logger.info(f"💰 BUY Signal detected - available JPY: {jpy_balance:.0f}")
                        self.execute_buy(current_price, jpy_balance)
                    else:
                        logger.info(f"⚠️  BUY signal but insufficient JPY: {jpy_balance:.0f}")

                elif trade_type == 'SELL':
                    if btc_balance > 0.0001:  # 最低0.0001 BTC必要
                        logger.info(f"💰 SELL Signal detected - available BTC: {btc_balance:.8f}")
                        self.execute_sell(btc_balance)
                    else:
                        logger.info(f"⚠️  SELL signal but insufficient BTC: {btc_balance:.8f}")

                logger.info(f"⏳ Sleeping for {self.interval} seconds...")
                time.sleep(self.interval)

            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                self.running = False
                break

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(self.interval)

        logger.info("🛑 Bot stopped")

if __name__ == "__main__":
    bot = SimpleSpotTradingBot()
    bot.run()
