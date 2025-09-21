#!/usr/bin/env python3
"""
Quick Dashboard - Port 8080
"""

import http.server
import socketserver
import sys
import os
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import Trade, User
from services.gmo_api import GMOCoinAPI

class QuickDashboard:
    def get_data(self):
        with app.app_context():
            try:
                user = User.query.filter_by(username='trading_user').first()
                if not user:
                    return {'error': 'User not found', 'db_positions': 0, 'api_positions': 0}

                # Database positions
                db_trades = Trade.query.filter_by(
                    user_id=user.id,
                    currency_pair='DOGE_JPY',
                    status='open'
                ).all()

                # All database trades (including closed)
                all_db_trades = Trade.query.filter_by(
                    user_id=user.id,
                    currency_pair='DOGE_JPY'
                ).order_by(Trade.id.desc()).limit(10).all()

                # API positions
                api = GMOCoinAPI(user.api_key, user.api_secret)
                api_positions = api.get_positions('DOGE_JPY')
                api_count = 0
                api_list = []
                if 'data' in api_positions and 'list' in api_positions['data']:
                    api_list = api_positions['data']['list']
                    api_count = len(api_list)

                # Get current price
                try:
                    import requests
                    response = requests.get('https://api.coin.z.com/public/v1/ticker?symbol=DOGE_JPY', timeout=5)
                    current_price = 0.0
                    if response.status_code == 200:
                        ticker_data = response.json()
                        if ticker_data['status'] == 0 and 'data' in ticker_data:
                            current_price = float(ticker_data['data'][0]['last'])
                except:
                    current_price = 0.0

                # Get account balance
                balance_info = {}
                try:
                    balance = api.get_balance()
                    if 'data' in balance:
                        balance_info = balance['data']
                except:
                    balance_info = {'error': 'Balance fetch failed'}

                return {
                    'db_positions': len(db_trades),
                    'api_positions': api_count,
                    'db_trades': db_trades,
                    'all_db_trades': all_db_trades,
                    'api_data': api_list,
                    'current_price': current_price,
                    'balance': balance_info,
                    'user_info': {
                        'username': user.username,
                        'has_api_key': bool(user.api_key),
                        'has_api_secret': bool(user.api_secret)
                    }
                }
            except Exception as e:
                return {'error': str(e), 'db_positions': 'Error', 'api_positions': 'Error'}

    def generate_html(self):
        data = self.get_data()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        sync_status = "✅ 完全同期" if data.get('db_positions') == data.get('api_positions') else "❌ 未同期"

        # Current price and user info
        current_price = data.get('current_price', 0.0)
        user_info = data.get('user_info', {})
        balance = data.get('balance', {})

        # Balance HTML
        balance_html = ""
        if 'error' not in balance:
            available = balance.get('available', 'N/A')
            actual_pnl = balance.get('actualProfitLoss', 'N/A')
            balance_html = f'''
            <div style="background: rgba(76, 175, 80, 0.2); padding: 10px; border-radius: 5px; margin: 5px;">
                <strong>利用可能残高:</strong> ¥{available}<br>
                <strong>実現損益:</strong> ¥{actual_pnl}
            </div>
            '''
        else:
            balance_html = f'<div style="color: #ff6b6b;">残高取得エラー: {balance.get("error", "Unknown")}</div>'

        # Open positions HTML
        db_html = ""
        if 'db_trades' in data and data['db_trades']:
            for trade in data['db_trades']:
                pnl = 0
                if current_price > 0:
                    if trade.trade_type.lower() == 'buy':
                        pnl = (current_price - trade.price) * trade.amount
                    else:
                        pnl = (trade.price - current_price) * trade.amount

                pnl_color = "#4CAF50" if pnl > 0 else "#F44336" if pnl < 0 else "#FFC107"
                status_color = "#4CAF50" if trade.exchange_position_id else "#F44336"

                db_html += f'''
                <div style="background: rgba(255,255,255,0.1); padding: 15px; margin: 8px; border-radius: 8px; border-left: 4px solid {status_color};">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <strong>DB ID: {trade.id}</strong>
                        <strong style="color: {pnl_color};">含み損益: ¥{pnl:+.2f}</strong>
                    </div>
                    <div><strong>タイプ:</strong> {trade.trade_type.upper()} | <strong>数量:</strong> {trade.amount} | <strong>エントリー価格:</strong> ¥{trade.price}</div>
                    <div><strong>取引所ID:</strong> {trade.exchange_position_id or '❌ 未設定'} | <strong>作成:</strong> {trade.created_at.strftime('%Y-%m-%d %H:%M') if trade.created_at else 'N/A'}</div>
                </div>
                '''
        else:
            db_html = '<div style="color: #888;">オープンポジションなし</div>'

        # API positions HTML
        api_html = ""
        if 'api_data' in data and data['api_data']:
            for pos in data['api_data']:
                pnl = 0
                if current_price > 0:
                    entry_price = float(pos['price'])
                    size = float(pos['size'])
                    if pos['side'].upper() == 'BUY':
                        pnl = (current_price - entry_price) * size
                    else:
                        pnl = (entry_price - current_price) * size

                pnl_color = "#4CAF50" if pnl > 0 else "#F44336" if pnl < 0 else "#FFC107"

                api_html += f'''
                <div style="background: rgba(255,255,255,0.1); padding: 15px; margin: 8px; border-radius: 8px; border-left: 4px solid #2196F3;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <strong>API ID: {pos['positionId']}</strong>
                        <strong style="color: {pnl_color};">含み損益: ¥{pnl:+.2f}</strong>
                    </div>
                    <div><strong>サイド:</strong> {pos['side']} | <strong>数量:</strong> {pos['size']} | <strong>エントリー価格:</strong> ¥{pos['price']}</div>
                </div>
                '''
        else:
            api_html = '<div style="color: #888;">取引所にポジションなし</div>'

        # Recent trades history
        history_html = ""
        if 'all_db_trades' in data and data['all_db_trades']:
            for trade in data['all_db_trades']:
                status_color = "#4CAF50" if trade.status == 'open' else "#888"
                closed_info = ""
                if trade.status == 'closed':
                    profit = trade.profit_loss or 0
                    profit_color = "#4CAF50" if profit > 0 else "#F44336" if profit < 0 else "#FFC107"
                    closed_info = f' | <span style="color: {profit_color};">損益: ¥{profit:+.2f}</span>'

                history_html += f'''
                <div style="background: rgba(255,255,255,0.05); padding: 10px; margin: 3px; border-radius: 5px;">
                    <strong style="color: {status_color};">#{trade.id}</strong> {trade.trade_type.upper()} {trade.amount} @ ¥{trade.price}
                    [{trade.status.upper()}]{closed_info}
                </div>
                '''

        return f'''<!DOCTYPE html>
<html>
<head>
    <title>詳細ダッシュボード - 暗号通貨取引Bot</title>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="30">
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            margin: 15px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            background: rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .status {{
            font-size: 2em;
            margin: 15px 0;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
        }}
        .section {{
            background: rgba(255, 255, 255, 0.05);
            padding: 20px;
            border-radius: 10px;
        }}
        .count {{
            font-size: 1.8em;
            color: #4CAF50;
            font-weight: bold;
        }}
        .price {{
            font-size: 2.5em;
            color: #2196F3;
            font-weight: bold;
            text-align: center;
            margin: 15px 0;
        }}
        .highlight {{
            background: rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 暗号通貨取引Bot - 詳細ダッシュボード</h1>
            <div class="status">{sync_status}</div>
            <div class="price">DOGE/JPY: ¥{current_price:.3f}</div>
            <p>ユーザー: {user_info.get('username', 'N/A')} | API接続: {'✅' if user_info.get('has_api_key') and user_info.get('has_api_secret') else '❌'}</p>
            <p>最終更新: {current_time}</p>
        </div>

        <div class="grid">
            <div class="section">
                <h2>📈 ポジション数</h2>
                <div class="highlight">
                    <p><span class="count">データベース: {data.get('db_positions', 'Error')}</span></p>
                    <p><span class="count">取引所API: {data.get('api_positions', 'Error')}</span></p>
                </div>
            </div>

            <div class="section">
                <h2>💰 口座残高</h2>
                {balance_html}
            </div>
        </div>

        <div class="section">
            <h2>💾 データベース オープンポジション</h2>
            {db_html}
        </div>

        <div class="section">
            <h2>🔗 取引所API オープンポジション</h2>
            {api_html}
        </div>

        <div class="section">
            <h2>📋 最近の取引履歴（最新10件）</h2>
            {history_html if history_html else '<div style="color: #888;">取引履歴なし</div>'}
        </div>

        <div class="section">
            <h2>⚠️ システム情報</h2>
            <div class="highlight">
                <p><strong>エラー:</strong> {data.get('error', 'なし')}</p>
                <p><strong>自動更新:</strong> 30秒間隔</p>
                <p><strong>対象通貨ペア:</strong> DOGE/JPY</p>
            </div>
        </div>
    </div>
</body>
</html>'''

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()

        dashboard = QuickDashboard()
        self.wfile.write(dashboard.generate_html().encode('utf-8'))

if __name__ == "__main__":
    PORT = 9000
    print(f"🚀 Fresh Dashboard starting on port {PORT}")
    print(f"🌐 URL: http://localhost:{PORT}")
    print("📊 Post-sync data loading...")

    with socketserver.TCPServer(("0.0.0.0", PORT), DashboardHandler) as httpd:
        httpd.serve_forever()