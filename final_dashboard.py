#!/usr/bin/env python3
"""
Final Working Dashboard - Shows actual positions and balance correctly
確実に動作する最終ダッシュボード
"""

import sys
import os
import json
import http.server
import socketserver
from datetime import datetime
import logging

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import User
from services.gmo_api import GMOCoinAPI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FinalDashboard:
    def __init__(self):
        self.current_price = 0.0
        self.volume = 0
        self.high = 0.0
        self.low = 0.0
        self.api_positions = []
        self.balance_info = {}
        self.last_update = datetime.now()
        self.update_all_data()

    def update_all_data(self):
        """Update all dashboard data"""
        try:
            with app.app_context():
                user = User.query.filter_by(username='trading_user').first()
                if not user:
                    logger.error("User not found")
                    return

                api = GMOCoinAPI(user.api_key, user.api_secret)

                # Get current price
                self.get_current_price()

                # Get API positions
                positions_response = api.get_positions('DOGE_JPY')
                self.api_positions = []
                if 'data' in positions_response and 'list' in positions_response['data']:
                    self.api_positions = positions_response['data']['list']

                # Get balance information
                try:
                    balance_response = api.get_margin_account()
                    if 'data' in balance_response:
                        self.balance_info = balance_response['data']
                except Exception:
                    try:
                        balance_response = api.get_account_balance()
                        if 'data' in balance_response:
                            self.balance_info = balance_response['data']
                    except Exception as e:
                        self.balance_info = {'error': f'Balance fetch failed: {str(e)}'}

                self.last_update = datetime.now()
                logger.info(f"Dashboard updated - Positions: {len(self.api_positions)}, Price: ¥{self.current_price}")

        except Exception as e:
            logger.error(f"Error updating dashboard data: {e}")

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

    def generate_html(self):
        """Generate dashboard HTML"""
        current_time = self.last_update.strftime('%Y-%m-%d %H:%M:%S')

        # Position HTML
        position_html = ""
        total_pnl = 0.0

        if self.api_positions:
            for pos in self.api_positions:
                # Calculate P&L
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
                        <strong style="color: {pnl_color};">含み損益: ¥{pnl:+,.0f}</strong>
                    </div>
                    <div><strong>方向:</strong> {pos['side']} | <strong>数量:</strong> {pos['size']} | <strong>エントリー価格:</strong> ¥{pos['price']}</div>
                    <div><strong>レバレッジ:</strong> {pos['leverage']}倍 | <strong>ロスカット価格:</strong> ¥{pos['losscutPrice']}</div>
                </div>
                '''
        else:
            position_html = '<div style="color: #888; padding: 20px; text-align: center;">アクティブなポジションはありません</div>'

        # Balance HTML
        balance_html = ""
        if 'error' not in self.balance_info and self.balance_info:
            if isinstance(self.balance_info, dict):
                # Margin account format
                available = self.balance_info.get('availableAmount',
                           self.balance_info.get('available',
                           self.balance_info.get('transferableAmount', 'N/A')))
                actual_pnl = self.balance_info.get('actualProfitLoss', 'N/A')
                margin = self.balance_info.get('margin', 'N/A')
                profit_loss = self.balance_info.get('profitLoss', 'N/A')

                # Format values safely
                def format_value(value):
                    if value == 'N/A' or value is None:
                        return 'N/A'
                    try:
                        return f"{float(value):,.0f}"
                    except (ValueError, TypeError):
                        return str(value)

                balance_html = f'''
                <div style="background: rgba(76, 175, 80, 0.15); padding: 20px; border-radius: 8px; margin: 5px;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                        <div><strong>利用可能残高:</strong><br><span style="font-size: 1.3em; color: #4CAF50;">¥{format_value(available)}</span></div>
                        <div><strong>証拠金:</strong><br><span style="font-size: 1.3em; color: #FF9800;">¥{format_value(margin)}</span></div>
                        <div><strong>実現損益:</strong><br><span style="font-size: 1.3em; color: #2196F3;">¥{format_value(actual_pnl)}</span></div>
                        <div><strong>含み損益合計:</strong><br><span style="font-size: 1.3em; color: {'#4CAF50' if total_pnl >= 0 else '#F44336'};">¥{total_pnl:+,.0f}</span></div>
                    </div>
                </div>
                '''
        else:
            error_msg = self.balance_info.get("error", "Unknown error") if self.balance_info else "No balance data"
            balance_html = f'<div style="color: #ff6b6b; padding: 20px; text-align: center;">残高情報取得エラー: {error_msg}</div>'

        return f'''<!DOCTYPE html>
<html>
<head>
    <title>DOGE/JPY取引ダッシュボード</title>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="10">
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            background: rgba(255, 255, 255, 0.1);
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
        }}
        .price {{
            font-size: 4em;
            color: #4CAF50;
            font-weight: bold;
            margin: 20px 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .status-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .status-card {{
            background: rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            backdrop-filter: blur(5px);
        }}
        .status-value {{
            font-size: 2em;
            font-weight: bold;
            margin: 10px 0;
        }}
        .section {{
            background: rgba(255, 255, 255, 0.05);
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 20px;
            backdrop-filter: blur(5px);
        }}
        .section h2 {{
            margin: 0 0 20px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid rgba(255,255,255,0.2);
            font-size: 1.5em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 DOGE/JPY 取引ダッシュボード</h1>
            <div class="price">¥{self.current_price:.3f}</div>
            <p>最終更新: {current_time} | 自動更新: 10秒間隔</p>
        </div>

        <div class="status-grid">
            <div class="status-card">
                <div>アクティブポジション</div>
                <div class="status-value" style="color: #2196F3;">{len(self.api_positions)}個</div>
            </div>
            <div class="status-card">
                <div>24時間高値</div>
                <div class="status-value" style="color: #4CAF50;">¥{self.high:.3f}</div>
            </div>
            <div class="status-card">
                <div>24時間安値</div>
                <div class="status-value" style="color: #F44336;">¥{self.low:.3f}</div>
            </div>
            <div class="status-card">
                <div>24時間出来高</div>
                <div class="status-value" style="color: #FF9800;">{self.volume:,.0f}</div>
            </div>
        </div>

        <div class="section">
            <h2>💰 残高情報</h2>
            {balance_html}
        </div>

        <div class="section">
            <h2>📊 アクティブポジション ({len(self.api_positions)}個)</h2>
            {position_html}
        </div>

        <div class="section" style="text-align: center; color: #ccc; font-size: 0.9em;">
            <p>🔄 GMO Coin APIからリアルタイムデータを取得</p>
            <p>📡 URL: http://localhost:8081</p>
        </div>
    </div>
</body>
</html>'''

class FinalDashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.dashboard = FinalDashboard()
        super().__init__(*args, **kwargs)

    def do_GET(self):
        try:
            # Update data on each request
            self.dashboard.update_all_data()

            # Send response
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

if __name__ == "__main__":
    PORT = 8081
    HOST = "0.0.0.0"

    logger.info(f"Starting Final Dashboard on {HOST}:{PORT}")
    logger.info("Features: Real positions, balance, P&L calculation")

    try:
        with socketserver.TCPServer((HOST, PORT), FinalDashboardHandler) as httpd:
            logger.info("Final dashboard server started successfully")
            httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Dashboard server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise