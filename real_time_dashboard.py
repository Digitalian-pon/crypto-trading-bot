#!/usr/bin/env python3
"""
Real-time Trading Dashboard - Shows actual API positions and signals
実際のAPIポジションとシグナルを表示するリアルタイムダッシュボード
"""

import sys
import os
import json
import http.server
import socketserver
from datetime import datetime
import logging
import threading
import time

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import Trade, User
from services.gmo_api import GMOCoinAPI
from services.data_service import DataService
from services.simple_trading_logic import SimpleTradingLogic
from services.technical_indicators import TechnicalIndicators

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RealTimeDashboard:
    def __init__(self):
        self.current_price = 0.0
        self.volume = 0
        self.high = 0.0
        self.low = 0.0
        self.last_update = datetime.now()
        self.api_positions = []
        self.balance_info = {}
        self.current_signal = "待機中"
        self.signal_reason = "シグナル分析中..."
        self.signal_confidence = 0.0
        self.rsi_value = 0.0
        self.market_trend = "分析中"
        self.trend_strength = 0.0

    def get_user_and_api(self):
        """Get user and API instance"""
        with app.app_context():
            user = User.query.filter_by(username='trading_user').first()
            if not user:
                return None, None
            api = GMOCoinAPI(user.api_key, user.api_secret)
            return user, api

    def get_trading_signals(self):
        """Get current trading signals"""
        try:
            user, api = self.get_user_and_api()
            if not user or not api:
                return

            # Get market data
            data_service = DataService()
            market_data_df = data_service.get_data_with_indicators('DOGE_JPY', '5m')

            if market_data_df is None or market_data_df.empty:
                logger.warning("No market data available for signal analysis")
                return

            # Get latest row as dictionary
            latest_data = market_data_df.iloc[-1].to_dict()

            # Calculate RSI if not available
            indicators = TechnicalIndicators()
            if 'rsi_14' not in latest_data:
                rsi_series = indicators.calculate_rsi(market_data_df['close'])
                if rsi_series is not None and len(rsi_series) > 0:
                    latest_data['rsi_14'] = float(rsi_series.iloc[-1])

            current_rsi = latest_data.get('rsi_14', 50.0)
            self.rsi_value = current_rsi

            # Generate signals using SimpleTradingLogic
            trading_logic = SimpleTradingLogic()
            should_trade, trade_type, reason, confidence = trading_logic.should_trade(latest_data)

            if should_trade and trade_type:
                if trade_type.upper() == 'BUY':
                    self.current_signal = "買いシグナル"
                elif trade_type.upper() == 'SELL':
                    self.current_signal = "売りシグナル"
                else:
                    self.current_signal = "ポジションなし"
            else:
                self.current_signal = "ポジションなし"

            self.signal_confidence = float(confidence)
            self.signal_reason = reason

            # Market trend analysis
            if current_rsi > 70:
                self.market_trend = "上昇トレンド（過買い）"
                self.trend_strength = (current_rsi - 50) / 50
            elif current_rsi < 30:
                self.market_trend = "下降トレンド（過売り）"
                self.trend_strength = (50 - current_rsi) / 50
            else:
                self.market_trend = "中性"
                self.trend_strength = abs(current_rsi - 50) / 50

        except Exception as e:
            logger.error(f"Error getting trading signals: {e}")
            self.current_signal = "エラー"
            self.signal_reason = f"シグナル取得エラー: {str(e)}"

    def get_api_positions(self):
        """Get actual API positions"""
        try:
            user, api = self.get_user_and_api()
            if not user or not api:
                return

            # Get actual positions from API
            positions_response = api.get_positions('DOGE_JPY')
            self.api_positions = []

            if 'data' in positions_response and 'list' in positions_response['data']:
                self.api_positions = positions_response['data']['list']

            # Get balance information (using margin account for leveraged trading)
            try:
                balance_response = api.get_margin_account()
                if 'data' in balance_response:
                    self.balance_info = balance_response['data']
            except Exception as balance_error:
                logger.error(f"Error getting margin account: {balance_error}")
                # Try account assets as fallback
                try:
                    balance_response = api.get_account_balance()
                    if 'data' in balance_response:
                        self.balance_info = balance_response['data']
                except Exception as asset_error:
                    logger.error(f"Error getting account assets: {asset_error}")
                    self.balance_info = {'error': f'Balance fetch failed: {str(balance_error)}'}

        except Exception as e:
            logger.error(f"Error getting API positions: {e}")
            self.api_positions = []
            self.balance_info = {'error': str(e)}

    def get_current_price(self):
        """Get current DOGE/JPY price"""
        try:
            import requests
            response = requests.get('https://api.coin.z.com/public/v1/ticker?symbol=DOGE_JPY', timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 0 and 'data' in data:
                    ticker = data['data'][0]
                    self.current_price = float(ticker['last'])
                    self.volume = float(ticker['volume'])
                    self.high = float(ticker['high'])
                    self.low = float(ticker['low'])

        except Exception as e:
            logger.error(f"Error getting current price: {e}")

    def update_all_data(self):
        """Update all dashboard data"""
        try:
            self.get_current_price()
            self.get_api_positions()
            self.get_trading_signals()
            self.last_update = datetime.now()
            logger.info(f"Dashboard data updated - Price: ¥{self.current_price}, Positions: {len(self.api_positions)}, Signal: {self.current_signal}")
        except Exception as e:
            logger.error(f"Error updating dashboard data: {e}")

    def generate_html(self):
        """Generate real-time dashboard HTML"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Position HTML
        position_html = ""
        total_pnl = 0.0

        logger.info(f"API positions count: {len(self.api_positions)}")
        logger.info(f"Current price: {self.current_price}")

        if self.api_positions:
            for pos in self.api_positions:
                logger.info(f"Processing position: {pos}")
                pnl = 0.0
                if self.current_price > 0:
                    entry_price = float(pos['price'])
                    size = float(pos['size'])
                    if pos['side'].upper() == 'BUY':
                        pnl = (self.current_price - entry_price) * size
                    else:
                        pnl = (entry_price - self.current_price) * size
                    total_pnl += pnl

                pnl_color = "#4CAF50" if pnl > 0 else "#F44336" if pnl < 0 else "#FFC107"

                position_html += f'''
                <div style="background: rgba(255,255,255,0.1); padding: 15px; margin: 8px; border-radius: 8px; border-left: 4px solid #2196F3;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <strong>ポジションID: {pos['positionId']}</strong>
                        <strong style="color: {pnl_color};">含み損益: ¥{pnl:+,.2f}</strong>
                    </div>
                    <div><strong>方向:</strong> {pos['side']} | <strong>数量:</strong> {pos['size']} | <strong>エントリー価格:</strong> ¥{pos['price']}</div>
                </div>
                '''
        else:
            position_html = f'<div style="color: #888;">アクティブなポジションはありません（デバッグ: positions={len(self.api_positions)}, price={self.current_price}）</div>'

        # Balance HTML
        balance_html = ""
        if 'error' not in self.balance_info and self.balance_info:
            # Handle different balance response formats
            if isinstance(self.balance_info, dict):
                # Margin account format
                available = self.balance_info.get('availableAmount',
                            self.balance_info.get('available',
                            self.balance_info.get('transferableAmount', 'N/A')))
                actual_pnl = self.balance_info.get('actualProfitLoss',
                             self.balance_info.get('realizedProfitLoss', 'N/A'))
                margin = self.balance_info.get('margin', 'N/A')

                balance_html = f'''
                <div style="background: rgba(76, 175, 80, 0.2); padding: 15px; border-radius: 8px; margin: 5px;">
                    <strong>利用可能残高:</strong> ¥{available}<br>
                    <strong>証拠金:</strong> ¥{margin}<br>
                    <strong>実現損益:</strong> ¥{actual_pnl}<br>
                    <strong>含み損益合計:</strong> ¥{total_pnl:+,.2f}
                </div>
                '''
            elif isinstance(self.balance_info, list):
                # Account assets format (array)
                jpy_asset = None
                for asset in self.balance_info:
                    if asset.get('symbol') == 'JPY':
                        jpy_asset = asset
                        break

                if jpy_asset:
                    available = jpy_asset.get('available', 'N/A')
                    onhand = jpy_asset.get('onHand', 'N/A')
                    balance_html = f'''
                    <div style="background: rgba(76, 175, 80, 0.2); padding: 15px; border-radius: 8px; margin: 5px;">
                        <strong>利用可能残高:</strong> ¥{available}<br>
                        <strong>保有残高:</strong> ¥{onhand}<br>
                        <strong>含み損益合計:</strong> ¥{total_pnl:+,.2f}
                    </div>
                    '''
                else:
                    balance_html = '<div style="color: #ff9800;">JPY残高情報が見つかりません</div>'
        else:
            error_msg = self.balance_info.get("error", "Unknown error") if self.balance_info else "No balance data"
            balance_html = f'<div style="color: #ff6b6b;">残高情報取得エラー: {error_msg}</div>'

        # Signal color
        signal_color = "#4CAF50" if "買い" in self.current_signal else "#F44336" if "売り" in self.current_signal else "#FF9800"

        return f'''<!DOCTYPE html>
<html>
<head>
    <title>リアルタイム取引ダッシュボード - DOGE/JPY</title>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="15">
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin: 15px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            background: rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .price {{
            font-size: 3em;
            color: #4CAF50;
            font-weight: bold;
            margin: 10px 0;
        }}
        .signal-section {{
            background: rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }}
        .signal {{
            font-size: 2.5em;
            font-weight: bold;
            color: {signal_color};
            margin: 10px 0;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 15px;
        }}
        .section {{
            background: rgba(255, 255, 255, 0.05);
            padding: 20px;
            border-radius: 10px;
        }}
        .stat {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .stat:last-child {{
            border-bottom: none;
        }}
        .value {{
            font-weight: bold;
            color: #4CAF50;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 リアルタイム取引ダッシュボード</h1>
            <div class="price">DOGE/JPY: ¥{self.current_price:.3f}</div>
            <p>最終更新: {current_time}</p>
        </div>

        <div class="signal-section">
            <h2>📊 現在のトレーディングシグナル</h2>
            <div class="signal">{self.current_signal}</div>
            <p><strong>判断理由:</strong> {self.signal_reason}</p>
            <p><strong>信頼度:</strong> {self.signal_confidence:.2f}/1.0</p>
            <div class="stat">
                <span>RSI:</span>
                <span class="value">{self.rsi_value:.1f}</span>
            </div>
            <div class="stat">
                <span>市場トレンド:</span>
                <span class="value">{self.market_trend}</span>
            </div>
        </div>

        <div class="grid">
            <div class="section">
                <h2>💰 残高情報</h2>
                {balance_html}
            </div>

            <div class="section">
                <h2>📈 市場データ</h2>
                <div class="stat">
                    <span>現在価格:</span>
                    <span class="value">¥{self.current_price:.3f}</span>
                </div>
                <div class="stat">
                    <span>24h高値:</span>
                    <span class="value">¥{self.high:.3f}</span>
                </div>
                <div class="stat">
                    <span>24h安値:</span>
                    <span class="value">¥{self.low:.3f}</span>
                </div>
                <div class="stat">
                    <span>24h出来高:</span>
                    <span class="value">{self.volume:,.0f}</span>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>🎯 アクティブポジション ({len(self.api_positions)}個)</h2>
            {position_html}
        </div>

        <div class="section" style="text-align: center; margin-top: 20px;">
            <p>🔄 自動更新: 15秒間隔</p>
            <p>📡 データソース: GMO Coin API (リアルタイム)</p>
        </div>
    </div>
</body>
</html>'''

class RealTimeDashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.dashboard = RealTimeDashboard()
        super().__init__(*args, **kwargs)

    def do_GET(self):
        try:
            # Update data on each request
            self.dashboard.update_all_data()

            # Send response with proper headers
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()

            # Generate and send HTML
            html_content = self.dashboard.generate_html()
            self.wfile.write(html_content.encode('utf-8'))

        except Exception as e:
            logger.error(f"Error in request handler: {e}")
            self.send_error(500, f"Internal Server Error: {str(e)}")

def start_background_updater():
    """Background data updater thread"""
    dashboard = RealTimeDashboard()
    while True:
        try:
            dashboard.update_all_data()
            time.sleep(10)  # Update every 10 seconds
        except Exception as e:
            logger.error(f"Background updater error: {e}")
            time.sleep(30)  # Wait longer on error

if __name__ == "__main__":
    # Configuration
    PORT = 8080
    HOST = "0.0.0.0"

    # Start background data updater
    updater_thread = threading.Thread(target=start_background_updater, daemon=True)
    updater_thread.start()

    # Server startup
    logger.info(f"Starting Real-time Trading Dashboard on {HOST}:{PORT}")
    logger.info(f"Dashboard URL: http://localhost:{PORT}")
    logger.info("Features: Real-time signals, API positions, balance info")

    try:
        with socketserver.TCPServer((HOST, PORT), RealTimeDashboardHandler) as httpd:
            logger.info("Real-time dashboard server started successfully")
            httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Dashboard server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise