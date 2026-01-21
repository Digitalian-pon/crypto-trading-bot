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
from datetime import datetime, timedelta
import logging

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import User
from services.gmo_api import GMOCoinAPI
from services.data_service import DataService
from services.optimized_trading_logic import OptimizedTradingLogic as SimpleTradingLogic

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
        # JST時刻で初期化（UTC+9時間）
        from datetime import timedelta
        self.last_update = datetime.utcnow() + timedelta(hours=9)
        self.data_service = None
        self.trading_logic = SimpleTradingLogic()
        self.update_all_data()

    def update_all_data(self):
        """Update all dashboard data"""
        try:
            # Try to get API credentials from environment variables first (for Railway)
            api_key = os.environ.get('GMO_API_KEY')
            api_secret = os.environ.get('GMO_API_SECRET')

            logger.info(f"[DASHBOARD] Environment check - API_KEY exists: {bool(api_key)} (len={len(api_key) if api_key else 0}), API_SECRET exists: {bool(api_secret)} (len={len(api_secret) if api_secret else 0})")
            if api_key:
                logger.info(f"[DASHBOARD] API_KEY first 10 chars: {api_key[:10]}...")

            # If not in environment, try database
            if not api_key or not api_secret:
                logger.info("Attempting to load credentials from database...")
                with app.app_context():
                    user = User.query.filter_by(username='trading_user').first()
                    if not user:
                        logger.error("User not found and no environment variables set")
                        return
                    api_key = user.api_key
                    api_secret = user.api_secret
                    logger.info("Credentials loaded from database successfully")
            else:
                logger.info("Using credentials from environment variables")

            api = GMOCoinAPI(api_key, api_secret)

            # Get current price
            self.get_current_price()

            # レバレッジ取引: ポジション取得
            try:
                logger.info("[DASHBOARD] Fetching positions from /v1/openPositions...")
                self.api_positions = api.get_positions(symbol='DOGE_JPY')
                logger.info(f"[DASHBOARD] Positions fetched: {len(self.api_positions)} positions")
                if self.api_positions:
                    logger.info(f"[DASHBOARD] First position: {self.api_positions[0]}")
            except Exception as e:
                logger.error(f"[DASHBOARD] Position fetch failed: {e}")
                self.api_positions = []

            # Get execution history (取引履歴)
            try:
                # 最新20件の取引履歴を取得（より多くの履歴を表示）
                executions_response = api.get_latest_executions(symbol='DOGE_JPY', page=1, count=20)
                if executions_response and executions_response.get('status') == 0:
                    data = executions_response.get('data', {})
                    if isinstance(data, dict) and 'list' in data:
                        self.execution_history = data['list']
                        logger.info(f"[DASHBOARD] Execution history fetched: {len(self.execution_history)} records")
                    else:
                        self.execution_history = []
                else:
                    self.execution_history = []
            except Exception as e:
                logger.error(f"Execution history fetch failed: {e}")
                self.execution_history = []

            # Get balance information (レバレッジ取引: /v1/account/assets)
            try:
                logger.info("[DASHBOARD] Fetching balance from /v1/account/assets...")
                balance_response = api.get_account_balance()
                logger.info(f"[DASHBOARD] Balance response status: {balance_response.get('status') if balance_response else 'None'}")
                if balance_response and balance_response.get('status') == 0 and balance_response.get('data'):
                    # JPYとDOGEの残高を抽出
                    self.balance_info = {'jpy': 0, 'doge': 0}
                    for asset in balance_response['data']:
                        if asset['symbol'] == 'JPY':
                            self.balance_info['jpy'] = float(asset.get('available', 0))
                        elif asset['symbol'] == 'DOGE':
                            self.balance_info['doge'] = float(asset.get('available', 0))
                    logger.info(f"[DASHBOARD] Balance parsed: JPY={self.balance_info['jpy']}, DOGE={self.balance_info['doge']}")
                else:
                    error_detail = balance_response if balance_response else "No response"
                    logger.error(f"[DASHBOARD] Balance fetch failed: {error_detail}")
                    self.balance_info = {'jpy': 0, 'doge': 0, 'error': 'Failed to fetch balance'}
            except Exception as e:
                logger.error(f"[DASHBOARD] Balance fetch exception: {e}", exc_info=True)
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

                    # Generate trading signal (OptimizedTradingLogic returns 6 values)
                    should_trade, trade_type, reason, confidence, stop_loss, take_profit = self.trading_logic.should_trade(
                        self.market_data, market_data_response
                    )
                    self.signal_info = {
                        'should_trade': should_trade,
                        'trade_type': trade_type,
                        'reason': reason,
                        'confidence': confidence,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit
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

            # JST時刻で更新（UTC+9時間）
            from datetime import timedelta
            self.last_update = datetime.utcnow() + timedelta(hours=9)
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
        """Generate execution history HTML with P&L for settlements"""
        try:
            if not self.execution_history:
                return '<div style="color: #888; padding: 20px; text-align: center;">取引履歴がありません</div>'

            history_html = '<div style="overflow-x: auto;">'
            history_html += '<table style="width: 100%; border-collapse: collapse; color: #ffffff;">'
            history_html += '<thead><tr style="background: rgba(255,255,255,0.1); border-bottom: 2px solid rgba(255,255,255,0.2);">'
            history_html += '<th style="padding: 12px; text-align: left;">日時</th>'
            history_html += '<th style="padding: 12px; text-align: center;">売買</th>'
            history_html += '<th style="padding: 12px; text-align: center;">タイプ</th>'
            history_html += '<th style="padding: 12px; text-align: right;">数量</th>'
            history_html += '<th style="padding: 12px; text-align: right;">価格</th>'
            history_html += '<th style="padding: 12px; text-align: right;">損益</th>'
            history_html += '<th style="padding: 12px; text-align: right;">手数料</th>'
            history_html += '</tr></thead><tbody>'

            for execution in self.execution_history:
                side = execution.get('side', 'N/A')
                side_color = '#00E676' if side == 'BUY' else '#FF1744' if side == 'SELL' else '#FFEB3B'
                side_text = '買い' if side == 'BUY' else '売り' if side == 'SELL' else side

                # 新規/決済の判定
                settle_type = execution.get('settleType', 'OPEN')
                if settle_type == 'CLOSE':
                    type_text = '決済'
                    type_color = '#FF9800'  # オレンジ
                else:
                    type_text = '新規'
                    type_color = '#2196F3'  # 青

                timestamp = execution.get('timestamp', '')
                # タイムスタンプをフォーマット（UTC→JST変換）
                try:
                    from datetime import datetime, timedelta
                    dt = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%fZ')
                    # UTC→JST変換（+9時間）
                    dt_jst = dt + timedelta(hours=9)
                    timestamp_formatted = dt_jst.strftime('%m/%d %H:%M:%S')
                except:
                    timestamp_formatted = timestamp[:16] if len(timestamp) > 16 else timestamp

                size = float(execution.get('size', 0))
                price = float(execution.get('price', 0))
                fee = float(execution.get('fee', 0))

                # 損益の取得（決済時のみ）
                loss_gain = execution.get('lossGain', None)
                if loss_gain is not None and settle_type == 'CLOSE':
                    loss_gain = float(loss_gain)
                    if loss_gain > 0:
                        pnl_text = f'<span style="color: #00E676; font-weight: bold;">+¥{loss_gain:,.0f}</span>'
                    elif loss_gain < 0:
                        pnl_text = f'<span style="color: #FF1744; font-weight: bold;">¥{loss_gain:,.0f}</span>'
                    else:
                        pnl_text = f'<span style="color: #FFEB3B;">¥0</span>'
                else:
                    pnl_text = '<span style="color: #666;">-</span>'

                history_html += f'<tr style="border-bottom: 1px solid rgba(255,255,255,0.1);">'
                history_html += f'<td style="padding: 10px; color: #ffffff;">{timestamp_formatted}</td>'
                history_html += f'<td style="padding: 10px; text-align: center;"><span style="color: {side_color}; font-weight: bold;">{side_text}</span></td>'
                history_html += f'<td style="padding: 10px; text-align: center;"><span style="color: {type_color}; font-weight: bold;">{type_text}</span></td>'
                history_html += f'<td style="padding: 10px; text-align: right; color: #ffffff;">{size:.0f}</td>'
                history_html += f'<td style="padding: 10px; text-align: right; color: #ffffff;">¥{price:,.3f}</td>'
                history_html += f'<td style="padding: 10px; text-align: right;">{pnl_text}</td>'
                history_html += f'<td style="padding: 10px; text-align: right; color: #FF9800;">¥{fee:,.2f}</td>'
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
        current_time = self.last_update.strftime('%Y-%m-%d %H:%M:%S') + ' (JST)'

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
            <h2>📜 取引履歴 (最新20件)</h2>
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

# Global dashboard instance (shared across all requests)
_dashboard_instance = None

def get_dashboard_instance():
    """Get or create the global dashboard instance"""
    global _dashboard_instance
    if _dashboard_instance is None:
        _dashboard_instance = FinalDashboard()
    return _dashboard_instance

class FinalDashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            # ログエンドポイント
            if self.path == '/logs':
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Refresh', '30')  # 30秒ごとに自動更新
                self.end_headers()

                try:
                    html_header = '''
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Trading Bot Logs</title>
                        <meta charset="utf-8">
                        <style>
                            body {
                                background: #1a1a2e;
                                color: #00ff00;
                                font-family: 'Courier New', monospace;
                                padding: 20px;
                                font-size: 12px;
                            }
                            .header {
                                background: #16213e;
                                padding: 15px;
                                border-radius: 5px;
                                margin-bottom: 20px;
                                color: #ffffff;
                            }
                            .log-line { margin: 2px 0; }
                            .cycle-start { color: #00E676; font-weight: bold; }
                            .decision-close { color: #FF1744; font-weight: bold; }
                            .decision-hold { color: #FFC107; }
                            .position-fetch { color: #2196F3; }
                            .error { color: #FF5722; font-weight: bold; }
                            .entry-success { color: #00E676; font-weight: bold; background: #1B5E20; padding: 2px 5px; }
                            .entry-failed { color: #FF5722; font-weight: bold; background: #BF360C; padding: 2px 5px; }
                            .reversal-order { color: #FF6F00; font-weight: bold; background: #E65100; padding: 2px 5px; }
                            .trade-entry { color: #00BCD4; font-weight: bold; }
                            .trade-exit { color: #9C27B0; font-weight: bold; }
                            pre { white-space: pre-wrap; word-wrap: break-word; }
                        </style>
                    </head>
                    <body>
                        <div class="header">
                            <h2>🤖 Trading Bot Execution Logs</h2>
                            <p>最終更新: ''' + (datetime.utcnow() + timedelta(hours=9)).strftime('%Y-%m-%d %H:%M:%S') + ''' (JST)</p>
                            <p>自動更新: 30秒間隔 | <a href="/" style="color: #00E676;">ダッシュボードに戻る</a></p>
                        </div>
                        <pre>
                    '''

                    # ボット実行ログを読み込み
                    if os.path.exists('bot_execution_log.txt'):
                        with open('bot_execution_log.txt', 'r') as f:
                            log_content = f.read()
                        # 最新1000行のみ表示
                        lines = log_content.split('\n')
                        recent_lines = lines[-1000:] if len(lines) > 1000 else lines

                        # ログの色分け
                        formatted_lines = []
                        for line in recent_lines:
                            if 'CYCLE_START' in line or '======' in line:
                                formatted_lines.append(f'<span class="cycle-start">{line}</span>')
                            elif 'ENTRY_SUCCESS' in line or 'POSITION_OPENED' in line:
                                formatted_lines.append(f'<span class="entry-success">{line}</span>')
                            elif 'ENTRY_FAILED' in line:
                                formatted_lines.append(f'<span class="entry-failed">{line}</span>')
                            elif 'REVERSAL_ORDER' in line:
                                formatted_lines.append(f'<span class="reversal-order">{line}</span>')
                            elif 'TRADE_ENTRY' in line:
                                formatted_lines.append(f'<span class="trade-entry">{line}</span>')
                            elif 'TRADE_EXIT' in line:
                                formatted_lines.append(f'<span class="trade-exit">{line}</span>')
                            elif 'DECISION: CLOSE' in line:
                                formatted_lines.append(f'<span class="decision-close">{line}</span>')
                            elif 'DECISION: HOLD' in line:
                                formatted_lines.append(f'<span class="decision-hold">{line}</span>')
                            elif 'POSITION_FETCH' in line:
                                formatted_lines.append(f'<span class="position-fetch">{line}</span>')
                            elif 'ERROR' in line or 'Error' in line or 'FAILED' in line:
                                formatted_lines.append(f'<span class="error">{line}</span>')
                            else:
                                formatted_lines.append(f'<span class="log-line">{line}</span>')

                        log_html = '\n'.join(formatted_lines)
                    else:
                        log_html = '<span class="error">No log file found. Bot may not be running.</span>'

                    html_footer = '''
                        </pre>
                    </body>
                    </html>
                    '''

                    self.wfile.write((html_header + log_html + html_footer).encode('utf-8'))
                except Exception as e:
                    error_html = f'''
                    <!DOCTYPE html>
                    <html>
                    <body style="background: #1a1a2e; color: #FF5722; font-family: monospace; padding: 20px;">
                        <h2>Error reading logs</h2>
                        <p>{str(e)}</p>
                    </body>
                    </html>
                    '''
                    self.wfile.write(error_html.encode('utf-8'))
                return

            # 通常のダッシュボード
            # Use shared dashboard instance
            dashboard = get_dashboard_instance()

            # Update data on each request
            dashboard.update_all_data()

            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()

            # Generate and send HTML
            html_content = dashboard.generate_html()
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