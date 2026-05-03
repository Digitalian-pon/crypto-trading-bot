"""
v4.0.0 - DOGE_JPY 4-hour trend-following leverage bot

Strategy:
  - Timeframe: 4h
  - Entry: ADX(14) > 25 + EMA20/EMA50 trend + MACD histogram aligned
  - Exit: TP +2%, SL -1% (fixed)
  - 1 position max
  - 90% balance sizing
  - 24h same-direction reentry block
  - No trailing stop, no forced reversal, no rolling optimizer

Position state file: position_history.json (tracks last close per side, for 24h block).
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta

from config import load_config
from services.gmo_api import GMOCoinAPI
from services.data_service import DataService
from services.optimized_trading_logic import OptimizedTradingLogic

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class OptimizedLeverageTradingBot:
    SYMBOL = 'DOGE_JPY'
    TIMEFRAME = '4hour'
    CHECK_INTERVAL_SEC = 300  # 5 min
    LEVERAGE = 2.0
    BALANCE_USAGE_RATIO = 0.90
    TAKE_PROFIT_RATIO = 0.02   # +2%
    STOP_LOSS_RATIO = 0.01     # -1%
    REENTRY_BLOCK_SECONDS = 24 * 3600
    HISTORY_FILE = 'position_history.json'
    LOG_FILE = 'bot_execution_log.txt'
    LOG_MAX_BYTES = 500_000  # ~500KB; truncate to last half when exceeded

    def __init__(self):
        config = load_config()
        api_key = config.get('api_credentials', 'api_key')
        api_secret = config.get('api_credentials', 'api_secret')

        self.api = GMOCoinAPI(api_key, api_secret)
        self.data_service = DataService(api_key, api_secret)
        self.logic = OptimizedTradingLogic()

        self.history = self._load_history()

    def _load_history(self):
        if not os.path.exists(self.HISTORY_FILE):
            return {'last_close': {}}
        try:
            with open(self.HISTORY_FILE, 'r') as f:
                data = json.load(f)
            data.setdefault('last_close', {})
            return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"History load failed: {e} — starting fresh")
            return {'last_close': {}}

    def _save_history(self):
        try:
            with open(self.HISTORY_FILE, 'w') as f:
                json.dump(self.history, f)
        except IOError as e:
            logger.error(f"History save failed: {e}")

    def _record_close(self, side):
        self.history['last_close'][side] = datetime.now(timezone.utc).isoformat()
        self._save_history()

    def _log_event(self, text):
        """Append a line to bot_execution_log.txt (read by /logs endpoint)."""
        try:
            if os.path.exists(self.LOG_FILE) and os.path.getsize(self.LOG_FILE) > self.LOG_MAX_BYTES:
                with open(self.LOG_FILE, 'r') as f:
                    data = f.read()
                with open(self.LOG_FILE, 'w') as f:
                    f.write(data[-self.LOG_MAX_BYTES // 2:])
            with open(self.LOG_FILE, 'a') as f:
                f.write(text + '\n')
        except IOError:
            pass

    def _is_blocked(self, side):
        last_iso = self.history['last_close'].get(side)
        if not last_iso:
            return False
        try:
            last = datetime.fromisoformat(last_iso)
        except ValueError:
            return False
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed < self.REENTRY_BLOCK_SECONDS

    def _get_jpy_balance(self):
        resp = self.api.get_account_balance()
        if not isinstance(resp, dict) or resp.get('status') != 0:
            logger.error(f"Balance fetch failed: {resp}")
            return 0.0
        for asset in resp.get('data', []):
            if asset.get('symbol') == 'JPY':
                return float(asset.get('available', 0))
        return 0.0

    def _get_current_price(self):
        ticker = self.api.get_ticker(self.SYMBOL)
        if not isinstance(ticker, dict):
            return None
        if 'data' in ticker and isinstance(ticker['data'], list) and ticker['data']:
            return float(ticker['data'][0].get('last', 0))
        if 'last' in ticker:
            return float(ticker.get('last', 0))
        return None

    def _calculate_size(self, jpy_available, price):
        if price <= 0:
            return 0
        usable_jpy = jpy_available * self.BALANCE_USAGE_RATIO
        notional = usable_jpy * self.LEVERAGE
        size = int(notional / price)
        return max(size, 0)

    def _get_open_position(self):
        positions = self.api.get_positions(symbol=self.SYMBOL)
        if not positions:
            return None
        return positions[0]

    def _check_exit(self, position, current_price):
        side = position.get('side')
        entry = float(position.get('price', 0))
        if entry <= 0:
            return None
        if side == 'BUY':
            pnl_ratio = (current_price - entry) / entry
        else:
            pnl_ratio = (entry - current_price) / entry

        if pnl_ratio >= self.TAKE_PROFIT_RATIO:
            return f"TP +{pnl_ratio*100:.2f}%"
        if pnl_ratio <= -self.STOP_LOSS_RATIO:
            return f"SL {pnl_ratio*100:.2f}%"
        return None

    def _close_position(self, position, current_price, reason):
        pid = position.get('positionId')
        side = position.get('side')
        size = position.get('size')
        opposite = 'BUY' if side == 'SELL' else 'SELL'
        logger.info(f"🔻 Closing {side} {size} @ ¥{current_price} ({reason}) [id={pid}]")
        result = self.api.close_position(
            symbol=self.SYMBOL,
            side=opposite,
            execution_type='MARKET',
            position_id=pid,
            size=size,
        )
        logger.info(f"   close result: {result}")
        if isinstance(result, dict) and result.get('status') == 0:
            self._record_close(side)
            return True
        return False

    def _open_position(self, side, current_price):
        if self._is_blocked(side):
            logger.info(f"⏸️ {side} blocked: 24h same-direction reentry block active")
            return False

        jpy = self._get_jpy_balance()
        size = self._calculate_size(jpy, current_price)
        if size <= 0:
            logger.warning(f"❌ Size 0 — JPY={jpy} price={current_price}")
            return False

        logger.info(f"🟢 Opening {side} {size} {self.SYMBOL} @ ~¥{current_price} (JPY={jpy})")
        result = self.api.place_order(
            symbol=self.SYMBOL,
            side=side,
            execution_type='MARKET',
            size=size,
        )
        logger.info(f"   order result: {result}")
        return isinstance(result, dict) and result.get('status') == 0

    def _trading_cycle(self):
        cycle_ts = datetime.now(timezone.utc).isoformat()
        self._log_event("=" * 70)
        self._log_event(f"CYCLE_START: {cycle_ts}")
        self._log_event(f"INTERVAL: {self.CHECK_INTERVAL_SEC}s | TIMEFRAME: {self.TIMEFRAME}")

        df = self.data_service.get_data_with_indicators(
            symbol=self.SYMBOL, interval=self.TIMEFRAME, limit=200
        )
        if df is None or df.empty:
            logger.warning("No market data")
            self._log_event("ERROR: No market data")
            return

        current_price = self._get_current_price()
        if current_price is None or current_price <= 0:
            logger.warning("No current price")
            self._log_event("ERROR: No current price")
            return
        self._log_event(f"CURRENT_PRICE: ¥{current_price}")

        position = self._get_open_position()
        self._log_event(f"POSITION_FETCH: symbol={self.SYMBOL}, count={1 if position else 0}")

        if position:
            entry = float(position.get('price', 0))
            side = position.get('side')
            size = position.get('size')
            pid = position.get('positionId')
            pnl_ratio = ((current_price - entry) / entry) if side == 'BUY' else ((entry - current_price) / entry)
            logger.info(f"📊 Position: {side} {size} @ ¥{entry} | now ¥{current_price} | P/L {pnl_ratio*100:+.2f}%")
            self._log_event(f"  - Position: {pid} {side} {size} @ {entry}")
            self._log_event(f"PNL_RATIO: {pnl_ratio*100:+.2f}% | TP={self.TAKE_PROFIT_RATIO*100:.0f}% SL=-{self.STOP_LOSS_RATIO*100:.0f}%")

            exit_reason = self._check_exit(position, current_price)
            if exit_reason:
                self._log_event(f"DECISION: CLOSE ({exit_reason})")
                closed = self._close_position(position, current_price, exit_reason)
                self._log_event(f"TRADE_EXIT: {side} {size} @ ¥{current_price} | success={closed}")
            else:
                self._log_event(f"DECISION: HOLD (P/L {pnl_ratio*100:+.2f}% within bounds)")
            return

        signal = self.logic.should_trade(df.iloc[-1].to_dict(), df)
        should_trade, trade_type, reason, confidence, _, _ = signal
        logger.info(f"📈 Signal: should={should_trade} type={trade_type} conf={confidence:.2f} reason={reason}")
        self._log_event(f"SIGNAL: should_trade={should_trade} type={trade_type} conf={confidence:.2f} reason={reason}")

        if should_trade and trade_type in ('BUY', 'SELL'):
            opened = self._open_position(trade_type, current_price)
            if opened:
                self._log_event(f"ENTRY_SUCCESS: {trade_type} @ ~¥{current_price}")
                self._log_event(f"TRADE_ENTRY: {trade_type} @ ¥{current_price}")
            else:
                self._log_event(f"ENTRY_FAILED: {trade_type} @ ~¥{current_price}")
        else:
            self._log_event("DECISION: HOLD (no entry signal)")

    def run(self):
        logger.info("=" * 70)
        logger.info("🤖 v4.0.0 simple trend-following bot started")
        logger.info(f"   {self.SYMBOL} | {self.TIMEFRAME} | check={self.CHECK_INTERVAL_SEC}s")
        logger.info(f"   TP=+{self.TAKE_PROFIT_RATIO*100:.0f}% SL=-{self.STOP_LOSS_RATIO*100:.0f}% | sizing={self.BALANCE_USAGE_RATIO*100:.0f}% bal × {self.LEVERAGE}x")
        logger.info(f"   Reentry block: {self.REENTRY_BLOCK_SECONDS//3600}h same-side")
        logger.info("=" * 70)

        while True:
            try:
                self._trading_cycle()
            except Exception as e:
                logger.error(f"Cycle error: {e}", exc_info=True)
            time.sleep(self.CHECK_INTERVAL_SEC)
