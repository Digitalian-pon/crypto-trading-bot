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
from services.data_service import DataService
from services.enhanced_trading_logic import EnhancedTradingLogic as SimpleTradingLogic

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
        self.execution_history = []
        self.balance_info = {}
        self.signal_info = {'should_trade': False, 'trade_type': None, 'reason': 'システム初期化中', 'confidence': 0.0}
        self.market_data = {}
        self.last_update = datetime.now()
        self.data_service = None
        self.trading_logic = SimpleTradingLogic()
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

                # レバレッジ取引: ポジション取得
                try:
                    self.api_positions = api.get_positions(symbol='DOGE_JPY')
                except Exception as e:
                    logger.error(f"Position fetch failed: {e}")
                    self.api_positions = []

                # Get execution history (取引履歴)
                try:
                    executions_response = api.get_latest_executions(symbol='DOGE_JPY', page=1, count=10)
                    if executions_response and executions_response.get('status') == 0:
                        data = executions_response.get('data', {})
                        if isinstance(data, dict) and 'list' in data:
                            self.execution_history = data['list']
                        else:
                            self.execution_history = []
                    else:
                        self.execution_history = []
                except Exception as e:
                    logger.error(f"Execution history fetch failed: {e}")
                    self.execution_history = []

                # Get balance information (レバレッジ取引: /v1/account/assets)
                try:
                    balance_response = api.get_account_balance()
                    if balance_response and balance_response.get('status') == 0 and balance_response.get('data'):
                        # JPYとDOGEの残高を抽出
                        self.balance_info = {'jpy': 0, 'doge': 0}
                        for asset in balance_response['data']:
                            if asset['symbol'] == 'JPY':
                                self.balance_info['jpy'] = float(asset.get('available', 0))
                            elif asset['symbol'] == 'DOGE':
                                self.balance_info['doge'] = float(asset.get('available', 0))
                    else:
                        self.balance_info = {'jpy': 0, 'doge': 0, 'error': 'Failed to fetch balance'}
                except Exception as e:
                    logger.error(f"Balance fetch failed: {e}")
                    self.balance_info = {'jpy': 0, 'doge': 0, 'error': str(e)}

                # Get trading signals
                try:
                    if not self.data_service:
                        self.data_service = DataService()

                    # Get market data with indicators
                    market_data_response = self.data_service.get_data_with_indicators('DOGE_JPY', interval='5m')
                    if market_data_response is not None and not market_data_response.empty:
                        # Convert DataFrame to dictionary for the last row (most recent data)
                        self.market_data = market_data_response.iloc[-1].to_dict()

                        # Generate trading signal
                        should_trade, trade_type, reason, confidence = self.trading_logic.should_trade(self.market_data)
                        self.signal_info = {
                            'should_trade': should_trade,
                            'trade_type': trade_type,
                            'reason': reason,
                            'confidence': confidence
                        }
                    else:
                        self.signal_info = {
                            'should_trade': False,
                            'trade_type': None,
                            'reason': 'マーケットデータ取得失敗',
                            'confidence': 0.0
                        }
                except Exception as e:
                    logger.error(f"Error getting signals: {e}")
                    self.signal_info = {
                        'should_trade': False,
                        'trade_type': None,
                        'reason': f'シグナル取得エラー: {str(e)}',
                        'confidence': 0.0
                    }

                self.last_update = datetime.now()
                logger.info(f"Dashboard updated - Positions: {len(self.api_positions)}, Price: ¥{self.current_price}, Signal: {self.signal_info.get('trade_type', 'なし')}")

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

    def get_execution_history_html(self):
        """Generate execution history HTML"""
        try:
            if not self.execution_history:
                return '<div style="color: #888; padding: 20px; text-align: center;">取引履歴がありません</div>'

            history_html = '<div style="overflow-x: auto;">'
            history_html += '<table style="width: 100%; border-collapse: collapse; color: #ffffff;">'
            history_html += '<thead><tr style="background: rgba(255,255,255,0.1); border-bottom: 2px solid rgba(255,255,255,0.2);">'
            history_html += '<th style="padding: 12px; text-align: left;">日時</th>'
            history_html += '<th style="padding: 12px; text-align: center;">売買</th>'
            history_html += '<th style="padding: 12px; text-align: right;">数量 (DOGE)</th>'
            history_html += '<th style="padding: 12px; text-align: right;">価格 (JPY)</th>'
            history_html += '<th style="padding: 12px; text-align: right;">手数料 (JPY)</th>'
            history_html += '<th style="padding: 12px; text-align: center;">注文ID</th>'
            history_html += '</tr></thead><tbody>'

            for execution in self.execution_history:
                side = execution.get('side', 'N/A')
                side_color = '#00E676' if side == 'BUY' else '#FF1744' if side == 'SELL' else '#FFEB3B'
                side_text = '買い' if side == 'BUY' else '売り' if side == 'SELL' else side

                timestamp = execution.get('timestamp', '')
                # タイムスタンプをフォーマット
                try:
                    from datetime import datetime
                    dt = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%fZ')
                    timestamp_formatted = dt.strftime('%m/%d %H:%M:%S')
                except:
                    timestamp_formatted = timestamp[:16] if len(timestamp) > 16 else timestamp

                size = float(execution.get('size', 0))
                price = float(execution.get('price', 0))
                fee = float(execution.get('fee', 0))
                order_id = execution.get('orderId', 'N/A')

                history_html += f'<tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">'
                history_html += f'<td style="padding: 10px; color: #ffffff;">{timestamp_formatted}</td>'
                history_html += f'<td style="padding: 10px; text-align: center;"><span style="color: {side_color}; font-weight: bold;">{side_text}</span></td>'
                history_html += f'<td style="padding: 10px; text-align: right; color: #ffffff;">{size:.0f}</td>'
                history_html += f'<td style="padding: 10px; text-align: right; color: #ffffff;">¥{price:,.0f}</td>'
                history_html += f'<td style="padding: 10px; text-align: right; color: #FF9800;">¥{fee:,.0f}</td>'
                history_html += f'<td style="padding: 10px; text-align: center; color: #888; font-size: 0.85em;">{order_id}</td>'
                history_html += '</tr>'

            history_html += '</tbody></table></div>'
            return history_html

        except Exception as e:
            logger.error(f"Error generating execution history HTML: {e}")
            return f'<div style="color: #ff6b6b; padding: 20px; text-align: center;">取引履歴表示エラー: {str(e)}</div>'

    def get_signal_html(self):
        """Generate trading signal HTML"""
        try:
            signal = self.signal_info
            should_trade = signal.get('should_trade', False)
            trade_type = signal.get('trade_type', None)
            reason = signal.get('reason', '不明')
            confidence = signal.get('confidence', 0.0)

            # Enhanced Signal Logic - Consider Current Positions
            if should_trade and trade_type:
                # Check if we have existing positions
                has_buy_position = any(pos['side'].upper() == 'BUY' for pos in self.api_positions)
                has_sell_position = any(pos['side'].upper() == 'SELL' for pos in self.api_positions)

                if trade_type.upper() == 'BUY':
                    if has_sell_position:
                        # BUY signal with SELL position = Close SELL position
                        signal_color = '#00E676'  # Bright Green
                        signal_icon = '🔄'
                        signal_text = 'SELL決済シグナル'
                        reason = f'SELL決済: {reason}'
                    elif has_buy_position:
                        # BUY signal with BUY position = Hold/Wait
                        signal_color = '#FFEB3B'  # Yellow
                        signal_icon = '⏸️'
                        signal_text = 'BUYポジション保持中'
                        reason = 'ポジション保持・決済待ち'
                    else:
                        # BUY signal with no position = New BUY
                        signal_color = '#00E676'  # Bright Green
                        signal_icon = '📈'
                        signal_text = '新規買いシグナル'
                else:  # SELL signal
                    if has_buy_position:
                        # SELL signal with BUY position = Close BUY position
                        signal_color = '#FF1744'  # Bright Red
                        signal_icon = '🔄'
                        signal_text = 'BUY決済シグナル'
                        reason = f'BUY決済: {reason}'
                    elif has_sell_position:
                        # SELL signal with SELL position = Hold/Wait
                        signal_color = '#FFEB3B'  # Yellow
                        signal_icon = '⏸️'
                        signal_text = 'SELLポジション保持中'
                        reason = 'ポジション保持・決済待ち'
                    else:
                        # SELL signal with no position = New SELL
                        signal_color = '#FF1744'  # Bright Red
                        signal_icon = '📉'
                        signal_text = '新規売りシグナル'
            else:
                signal_color = '#FFEB3B'  # Bright Yellow
                signal_icon = '⏸️'
                signal_text = 'シグナルなし'

            # Get technical indicators if available
            rsi = self.market_data.get('rsi_14', 'N/A')
            macd_line = self.market_data.get('macd_line', 'N/A')
            macd_signal = self.market_data.get('macd_signal', 'N/A')
            bb_upper = self.market_data.get('bb_upper', 'N/A')
            bb_lower = self.market_data.get('bb_lower', 'N/A')

            # Format indicators
            def format_indicator(value):
                if value == 'N/A' or value is None:
                    return 'N/A'
                try:
                    return f"{float(value):.2f}"
                except (ValueError, TypeError):
                    return str(value)

            signal_html = f'''
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                <div style="background: rgba(255,255,255,0.12); padding: 20px; border-radius: 10px; text-align: center; border-left: 5px solid {signal_color}; border: 1px solid rgba(255,255,255,0.15);">
                    <div style="font-size: 2em; margin-bottom: 10px;">{signal_icon}</div>
                    <div style="font-size: 1.5em; font-weight: bold; color: {signal_color}; margin-bottom: 10px; text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">{signal_text}</div>
                    <div style="margin-bottom: 10px; color: #ffffff;"><strong>信頼度:</strong> {confidence:.2f}/1.0</div>
                    <div style="font-size: 0.9em; color: #e0e0e0;">判断理由: {reason}</div>
                </div>

                <div style="background: rgba(255,255,255,0.12); padding: 20px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.15);">
                    <h4 style="margin: 0 0 15px 0; color: #FFEB3B; text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">📊 テクニカル指標</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9em; color: #ffffff;">
                        <div style="color: #ffffff;"><strong>RSI:</strong> {format_indicator(rsi)}</div>
                        <div style="color: #ffffff;"><strong>MACD線:</strong> {format_indicator(macd_line)}</div>
                        <div style="color: #ffffff;"><strong>MACDシグナル:</strong> {format_indicator(macd_signal)}</div>
                        <div style="color: #ffffff;"><strong>BB上限:</strong> ¥{format_indicator(bb_upper)}</div>
                        <div style="color: #ffffff;"><strong>BB下限:</strong> ¥{format_indicator(bb_lower)}</div>
                        <div style="color: #ffffff;"><strong>現在価格:</strong> ¥{self.current_price:.3f}</div>
                    </div>
                </div>
            </div>
            '''

            return signal_html

        except Exception as e:
            logger.error(f"Error generating signal HTML: {e}")
            return f'<div style="color: #ff6b6b; padding: 20px; text-align: center;">シグナル表示エラー: {str(e)}</div>'

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

                pnl_color = "#00E676" if pnl > 0 else "#FF1744" if pnl < 0 else "#FFEB3B"

                position_html += f'''
                <div style="background: rgba(255,255,255,0.12); padding: 15px; margin: 8px; border-radius: 8px; border-left: 4px solid #2196F3; border: 1px solid rgba(255,255,255,0.15);">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px; color: #ffffff;">
                        <strong>ポジションID: {pos['positionId']}</strong>
                        <strong style="color: {pnl_color}; text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">含み損益: ¥{pnl:+,.0f}</strong>
                    </div>
                    <div style="color: #ffffff;"><strong>方向:</strong> {pos['side']} | <strong>数量:</strong> {pos['size']} | <strong>エントリー価格:</strong> ¥{pos['price']}</div>
                    <div style="color: #ffffff;"><strong>レバレッジ:</strong> {pos['leverage']}倍 | <strong>ロスカット価格:</strong> ¥{pos['losscutPrice']}</div>
                </div>
                '''
        else:
            position_html = '<div style="color: #888; padding: 20px; text-align: center;">アクティブなポジションはありません</div>'

        # Balance HTML (レバレッジ取引用)
        balance_html = ""
        if 'error' not in self.balance_info and self.balance_info:
            jpy_balance = self.balance_info.get('jpy', 0)
            doge_balance = self.balance_info.get('doge', 0)

            # DOGE評価額（JPY換算）
            doge_value_jpy = doge_balance * self.current_price if self.current_price > 0 else 0

            balance_html = f'''
            <div style="background: rgba(76, 175, 80, 0.15); padding: 20px; border-radius: 8px; margin: 5px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div style="color: #ffffff;"><strong>JPY 残高（証拠金）:</strong><br><span style="font-size: 1.3em; color: #00E676; text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">¥{jpy_balance:,.0f}</span></div>
                    <div style="color: #ffffff;"><strong>DOGE 残高:</strong><br><span style="font-size: 1.3em; color: #FF9800; text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">{doge_balance:,.0f} DOGE</span></div>
                </div>
            </div>
            '''
        else:
            error_msg = self.balance_info.get("error", "Unknown error") if self.balance_info else "No balance data"
            balance_html = f'<div style="color: #ff6b6b; padding: 20px; text-align: center;">残高情報取得エラー: {error_msg}</div>'

        return f'''<!DOCTYPE html>
<html>
<head>
    <title>DOGE/JPY レバレッジ取引ダッシュボード</title>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="10">
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            color: #ffffff;
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
            background: rgba(255, 255, 255, 0.15);
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }}
        .price {{
            font-size: 4em;
            color: #00E676;
            font-weight: bold;
            margin: 20px 0;
            text-shadow: 2px 2px 8px rgba(0,0,0,0.5);
        }}
        .status-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .status-card {{
            background: rgba(255, 255, 255, 0.12);
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            backdrop-filter: blur(5px);
            border: 1px solid rgba(255, 255, 255, 0.15);
        }}
        .status-value {{
            font-size: 2em;
            font-weight: bold;
            margin: 10px 0;
        }}
        .section {{
            background: rgba(255, 255, 255, 0.08);
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 20px;
            backdrop-filter: blur(5px);
            border: 1px solid rgba(255, 255, 255, 0.12);
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
            <h1>🐕 DOGE/JPY レバレッジ取引ダッシュボード</h1>
            <div class="price">¥{self.current_price:.2f}</div>
            <p>最終更新: {current_time} | 自動更新: 10秒間隔</p>
        </div>

        <div class="status-grid">
            <div class="status-card">
                <div style="color: #ffffff;">取引タイプ</div>
                <div class="status-value" style="color: #FF5722; text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">⚡ レバレッジ</div>
            </div>
            <div class="status-card">
                <div style="color: #ffffff;">24時間高値</div>
                <div class="status-value" style="color: #00E676; text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">¥{self.high:,.0f}</div>
            </div>
            <div class="status-card">
                <div style="color: #ffffff;">24時間安値</div>
                <div class="status-value" style="color: #FF1744; text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">¥{self.low:,.0f}</div>
            </div>
            <div class="status-card">
                <div style="color: #ffffff;">24時間出来高</div>
                <div class="status-value" style="color: #FF9800; text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">{self.volume:,.2f}</div>
            </div>
        </div>

        <div class="section">
            <h2>📊 取引シグナル</h2>
            {self.get_signal_html()}
        </div>

        <div class="section">
            <h2>📊 ポジション情報</h2>
            {position_html}
        </div>

        <div class="section">
            <h2>💰 残高情報</h2>
            {balance_html}
        </div>

        <div class="section">
            <h2>📜 取引履歴 (最新10件)</h2>
            {self.get_execution_history_html()}
        </div>

        <div class="section" style="text-align: center; color: #ccc; font-size: 0.9em;">
            <p>🔄 GMO Coin APIからリアルタイムデータを取得</p>
            <p>⚡ レバレッジ取引（空売り対応）</p>
            <p>📡 アクティブポジション数: {len(self.api_positions)}</p>
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
    PORT = int(os.environ.get('PORT', 8082))
    HOST = os.environ.get('HOST', '0.0.0.0')

    logger.info(f"Starting Final Dashboard on {HOST}:{PORT}")
    logger.info("Features: Real positions, balance, P&L calculation")

    # エラーハンドリング強化
    import signal
    import sys
    import traceback

    def signal_handler(signum, frame):
        logger.info("Received shutdown signal - graceful shutdown")
        sys.exit(0)

    def exception_handler(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    # シグナル・例外ハンドラ設定
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    sys.excepthook = exception_handler

    try:
        with socketserver.TCPServer((HOST, PORT), FinalDashboardHandler) as httpd:
            logger.info("Final dashboard server started successfully")
            httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Dashboard server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")

        # 自動再起動試行
        logger.info("Attempting automatic recovery...")
        try:
            import subprocess
            subprocess.run(['./auto_recovery.sh'], check=True, cwd='/data/data/com.termux/files/home/crypto-trading-bot')
        except Exception as recovery_error:
            logger.error(f"Auto recovery failed: {recovery_error}")

        sys.exit(1)