import os
import json
import time
import hmac
import hashlib
import requests
import logging
import sys
from urllib.parse import urlencode
from datetime import datetime

# ロギング設定を初期化
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class GMOCoinAPI:
    """
    Class for interacting with the GMO Coin API for cryptocurrency trading
    """
    
    BASE_URL = "https://api.coin.z.com/public"
    PRIVATE_URL = "https://api.coin.z.com/private"
    
    def __init__(self, api_key=None, api_secret=None):
        """
        Initialize with API credentials
        
        :param api_key: GMO Coin API key
        :param api_secret: GMO Coin API secret
        """
        self.api_key = api_key or os.environ.get("GMO_API_KEY")
        self.api_secret = api_secret or os.environ.get("GMO_API_SECRET")
        
        if not self.api_key or not self.api_secret:
            logger.warning("GMO Coin API credentials not provided. Some methods will be unavailable.")
    
    def _generate_signature(self, timestamp, method, path, request_body=""):
        """
        Generate signature for private API requests
        
        :param timestamp: Unix timestamp in milliseconds
        :param method: HTTP method (GET, POST, PUT, DELETE)
        :param path: API endpoint path
        :param request_body: Request body for POST requests (JSON string)
        :return: Signature string
        """
        if not self.api_secret:
            raise ValueError("API secret is required to generate signature")
            
        message = timestamp + method + path + request_body
        signature = hmac.new(
            bytes(str(self.api_secret), 'utf-8'),
            bytes(message, 'utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _private_request(self, method, endpoint, params=None):
        """
        Make an authenticated request to the private API

        :param method: HTTP method (GET, POST, PUT, DELETE)
        :param endpoint: API endpoint path
        :param params: Parameters to send with the request
        :return: JSON response
        """
        if not self.api_key or not self.api_secret:
            logger.error("API credentials not available for private request")
            raise ValueError("API key and secret required for private API access")

        timestamp = str(int(time.time() * 1000))
        url = f"{self.PRIVATE_URL}{endpoint}"

        headers = {
            "API-KEY": self.api_key,
            "API-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }

        request_body = ""
        if params and method in ["POST", "PUT"]:
            request_body = json.dumps(params)

        # 署名生成 - GMO Coin APIの仕様: GETの場合クエリパラメータは署名に含めない
        signature = self._generate_signature(timestamp, method, endpoint, request_body)
        headers["API-SIGN"] = signature

        # デバッグ用ログ
        logger.info(f"[API] {method} {endpoint} - Key length: {len(self.api_key)}, Secret length: {len(self.api_secret)}")
        logger.info(f"[API] Timestamp: {timestamp}, Signature: {signature[:20]}...")

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method == "POST":
                response = requests.post(url, headers=headers, data=request_body)
            elif method == "PUT":
                response = requests.put(url, headers=headers, data=request_body)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            logger.info(f"[API] Response status: {response.status_code}")
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"[API] Request error: {e}")
            return {"status": -1, "error": str(e)}
    
    def _public_request(self, method, endpoint, params=None):
        """
        Make a request to the public API
        
        :param method: HTTP method (GET, POST)
        :param endpoint: API endpoint path
        :param params: Parameters to send with the request
        :return: JSON response or error dictionary
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        # Initialize json_response outside the try block to ensure it's always defined
        json_response = None
        
        try:
            logger.info(f"Making {method} request to {url} with params: {params}")
            
            if method == "GET":
                response = requests.get(url, params=params)
            elif method == "POST":
                response = requests.post(url, json=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Try to parse JSON even if status code indicates error
            try:
                json_response = response.json()
                logger.info(f"Response status code: {response.status_code}, content: {json_response}")
            except ValueError:
                logger.error(f"Failed to parse JSON response: {response.text}")
                json_response = {"error": "Failed to parse JSON response", "text": response.text[:200]}
            
            # Raise for HTTP errors
            response.raise_for_status()
            return json_response
            
        except requests.exceptions.HTTPError as e:
            # マージン不足エラーは警告レベルで記録（ERRORではない）
            error_msg = str(e)
            if json_response and isinstance(json_response, dict):
                error_code = json_response.get('messages', [{}])[0].get('message_code', '') if 'messages' in json_response else ''
                # ERR-5122: 証拠金不足エラー
                if error_code == 'ERR-5122' or 'insufficient' in error_msg.lower() or 'margin' in error_msg.lower():
                    logger.info(f"Margin insufficient (expected condition): {json_response}")
                    return json_response

            logger.error(f"API HTTP error: {e} for URL: {url} with params: {params}")
            # Return JSON error response if available
            if json_response:
                logger.info(f"Error response content: {json_response}")
                return json_response
            return {"status": -1, "error": str(e), "status_code": e.response.status_code if hasattr(e, 'response') else None}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {e} for URL: {url} with params: {params}")
            return {"status": -1, "error": str(e)}
    
    # Public API Methods
    
    def get_ticker(self, symbol="BTC_JPY"):
        """
        Get current ticker information for a symbol

        :param symbol: Trading pair symbol (default: BTC_JPY)
        :return: Ticker data (dict or None)
        """
        endpoint = "/v1/ticker"
        params = {"symbol": symbol}
        response = self._public_request("GET", endpoint, params)

        # APIレスポンスからデータを抽出
        if response and response.get('status') == 0 and response.get('data'):
            data = response['data']
            # dataがリストの場合は最初の要素を返す
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            # dataが辞書の場合はそのまま返す
            elif isinstance(data, dict):
                return data

        return None
    
    def get_orderbooks(self, symbol="BTC_JPY"):
        """
        Get order book for a symbol
        
        :param symbol: Trading pair symbol (default: BTC_JPY)
        :return: Order book data
        """
        endpoint = "/v1/orderbooks"
        params = {"symbol": symbol}
        return self._public_request("GET", endpoint, params)
    
    def get_klines(self, symbol="BTC_JPY", interval="1h", date=None):
        """
        Get candlestick/OHLCV data
        
        :param symbol: Trading pair symbol (default: BTC_JPY)
        :param interval: Time interval (1min, 5min, 10min, 15min, 30min, 1h, 4h, 8h, 12h, 1d, 1w)
        :param date: Target date (YYYYMMDD format) - required by API
        :return: Candlestick data or error message
        """
        endpoint = f"/v1/klines"
        
        # GMO Coin APIはdateパラメータが必須
        # 過去の日付を指定する必要があるため、現在の日付より1日前を使用
        if not date:
            from datetime import timedelta
            current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            # 当日のデータより1日前のデータを使用（当日データは不完全な可能性があるため）
            yesterday = current_date - timedelta(days=1)
            date = yesterday.strftime('%Y%m%d')
            logger.info(f"No date provided, using yesterday's date: {date}")
        
        params = {
            "symbol": symbol,
            "interval": interval,
            "date": date
        }
            
        logger.info(f"Getting klines with params: {params}")
        return self._public_request("GET", endpoint, params)
    
    # Private API Methods
    
    def get_account_balance(self):
        """
        Get account balance information
        
        :return: Account balance data
        """
        endpoint = "/v1/account/assets"
        return self._private_request("GET", endpoint)
    
    def place_order(self, symbol, side, execution_type, size, price=None, time_in_force="FAS"):
        """
        Place a new order
        
        :param symbol: Trading pair symbol (e.g., BTC_JPY)
        :param side: Order side (BUY or SELL)
        :param execution_type: MARKET or LIMIT
        :param size: Order size
        :param price: Limit price (required for LIMIT orders)
        :param time_in_force: Time in force (FAS, FAK, FOK)
        :return: Order placement result
        """
        endpoint = "/v1/order"
        params = {
            "symbol": symbol,
            "side": side,
            "executionType": execution_type,
            "size": str(size),
        }
        
        if execution_type == "LIMIT":
            if price is None:
                raise ValueError("Price must be specified for LIMIT orders")
            params["price"] = str(price)
            params["timeInForce"] = time_in_force
        
        return self._private_request("POST", endpoint, params)
    
    def cancel_order(self, order_id):
        """
        Cancel an open order
        
        :param order_id: Order ID to cancel
        :return: Cancellation result
        """
        endpoint = "/v1/cancelOrder"
        params = {"orderId": order_id}
        return self._private_request("POST", endpoint, params)
    
    def get_active_orders(self, symbol=None, page=1, count=100):
        """
        Get active orders
        
        :param symbol: Trading pair symbol (optional)
        :param page: Page number
        :param count: Number of orders per page
        :return: Active orders data
        """
        endpoint = "/v1/activeOrders"
        params = {"page": page, "count": count}
        
        if symbol:
            params["symbol"] = symbol
            
        return self._private_request("GET", endpoint, params)
    
    def get_latest_executions(self, symbol=None, page=1, count=100):
        """
        Get latest execution history (past 1 day)

        :param symbol: Trading pair symbol (optional)
        :param page: Page number
        :param count: Number of executions per page
        :return: Latest execution history data
        """
        endpoint = "/v1/latestExecutions"
        params = {"page": page, "count": count}

        if symbol:
            params["symbol"] = symbol

        return self._private_request("GET", endpoint, params)

    def get_execution_history(self, symbol=None, page=1, count=100):
        """
        Get execution history (alias for get_latest_executions)

        :param symbol: Trading pair symbol (optional)
        :param page: Page number
        :param count: Number of executions per page
        :return: Execution history data
        """
        return self.get_latest_executions(symbol, page, count)
    
    # Leverage Trading Methods
    
    def get_margin_account(self):
        """
        Get margin account information including open positions

        :return: Margin account data with positions (dict or None)
        """
        endpoint = "/v1/account/margin"
        response = self._private_request("GET", endpoint)

        # APIレスポンスからデータを抽出
        if response and response.get('status') == 0 and response.get('data'):
            return response['data']

        return None
    
    def get_positions(self, symbol=None, page=1, count=100):
        """
        Get detailed open positions (建玉一覧を取得)

        :param symbol: Trading pair symbol (e.g., 'DOGE_JPY')
        :param page: Page number (default: 1)
        :param count: Number of positions per page (default: 100)
        :return: List of open positions or empty list
        """
        endpoint = "/v1/openPositions"
        params = {"page": page, "count": count}

        if symbol:
            params["symbol"] = symbol

        response = self._private_request("GET", endpoint, params)

        # APIレスポンスからデータを抽出
        if response and response.get('status') == 0:
            data = response.get('data', {})
            # dataの中のlistを返す
            if isinstance(data, dict) and 'list' in data:
                return data['list']
            # dataが空の辞書の場合は空リストを返す
            elif isinstance(data, dict) and not data:
                return []

        return []
    
    def close_position(self, symbol, side, execution_type="MARKET", position_id=None, size=None, price=None):
        """
        Close a leverage position (決済注文)
        
        :param symbol: Trading pair symbol (e.g., 'DOGE_JPY')
        :param side: Order side ('BUY' or 'SELL')
        :param execution_type: Order type ('MARKET', 'LIMIT', 'STOP')
        :param position_id: Position ID to close (required if size specified)
        :param size: Size to close (required if position_id specified)
        :param price: Price for LIMIT/STOP orders
        :return: Close order result
        """
        endpoint = "/v1/closeOrder"
        params = {
            "symbol": symbol,
            "side": side,
            "executionType": execution_type
        }
        
        if execution_type in ["LIMIT", "STOP"] and price:
            params["price"] = str(price)
            
        if position_id and size:
            params["settlePosition"] = [{
                "positionId": position_id,
                "size": str(size)
            }]
        
        return self._private_request("POST", endpoint, params)
    
    def close_bulk_position(self, symbol, side, execution_type="MARKET", size=None, price=None):
        """
        Close multiple positions at once (一括決済注文)
        
        :param symbol: Trading pair symbol (e.g., 'DOGE_JPY')
        :param side: Position side to close ('BUY' or 'SELL')
        :param execution_type: Order type ('MARKET', 'LIMIT', 'STOP')
        :param size: Total size to close (required)
        :param price: Price for LIMIT/STOP orders
        :return: Bulk close result
        """
        endpoint = "/v1/closeBulkOrder"
        params = {
            "symbol": symbol,
            "side": side,
            "executionType": execution_type
        }
        
        if size:
            # For DOGE and other whole number instruments, ensure integer size
            if symbol and 'DOGE' in symbol:
                params["size"] = str(int(float(size)))
            else:
                params["size"] = str(size)
            
        if execution_type in ["LIMIT", "STOP"] and price:
            params["price"] = str(price)
        
        return self._private_request("POST", endpoint, params)
    
    def close_all_positions_by_symbol(self, symbol, side=None):
        """
        Convenience method to close all positions for a symbol using bulk close
        
        :param symbol: Trading pair symbol (e.g., 'DOGE_JPY')
        :param side: Position side to close ('BUY' or 'SELL')
        :return: Bulk close result
        """
        # First get current positions to calculate total size
        positions_response = self.get_positions(symbol=symbol)
        
        if positions_response.get('status') != 0:
            return {'error': f'Failed to get positions: {positions_response}'}
        
        if not positions_response.get('data') or not positions_response['data'].get('list'):
            return {'message': 'No positions found'}
        
        positions = positions_response['data']['list']
        total_size = 0
        
        # Calculate total size for the specified side
        for position in positions:
            if position.get('symbol') == symbol:
                if side is None or position.get('side') == side:
                    total_size += float(position.get('size', 0))
        
        if total_size == 0:
            return {'message': f'No {side or "any"} positions found for {symbol}'}
        
        # Use bulk close to close all positions at once
        return self.close_bulk_position(
            symbol=symbol,
            side=side,
            execution_type="MARKET",
            size=str(total_size)
        )
