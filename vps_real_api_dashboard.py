#!/usr/bin/env python3
"""
VPS Real API Dashboard - GMO Coin API Integration
Real-time position, balance, and trade data from GMO Coin API
"""

import http.server
import socketserver
import requests
import json
import time
import hmac
import hashlib
import configparser
import os
from datetime import datetime
from typing import Dict, List, Optional

class GMOCoinAPIClient:
    """GMO Coin API client for real data"""
    
    def __init__(self):
        self.config = self.load_config()
        self.api_key = self.config.get('api_credentials', 'api_key', fallback='')
        self.api_secret = self.config.get('api_credentials', 'api_secret', fallback='')
        self.base_url = "https://api.coin.z.com"
        self.private_base_url = "https://api.coin.z.com/private"
        
    def load_config(self):
        """Load configuration from setting.ini"""
        config = configparser.ConfigParser()
        config_path = 'setting.ini'
        if os.path.exists(config_path):
            config.read(config_path)
        else:
            # Create default config if not exists
            config['api_credentials'] = {
                'api_key': '',
                'api_secret': ''
            }
            with open(config_path, 'w') as f:
                config.write(f)
        return config
    
    def create_signature(self, method: str, endpoint: str, body: str = "") -> str:
        """Create API signature"""
        if not self.api_secret:
            return ""
        
        timestamp = str(int(time.time() * 1000))
        message = timestamp + method + endpoint + body
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def get_public_ticker(self, symbol: str = "DOGE_JPY") -> Dict:
        """Get public ticker data"""
        try:
            url = f"{self.base_url}/public/v1/ticker?symbol={symbol}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 0:
                    return data.get('data', [{}])[0]
        except Exception as e:
            print(f"Public ticker error: {e}")
        return {}
    
    def get_account_balance(self) -> Dict:
        """Get account balance via private API"""
        if not self.api_key or not self.api_secret:
            return self.get_mock_balance()
        
        try:
            endpoint = "/v1/account/margin"
            timestamp = str(int(time.time() * 1000))
            signature = self.create_signature("GET", endpoint)
            
            headers = {
                "API-KEY": self.api_key,
                "API-TIMESTAMP": timestamp,
                "API-SIGN": signature
            }
            
            url = f"{self.private_base_url}{endpoint}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 0:
                    return data.get('data', {})
        except Exception as e:
            print(f"Balance API error: {e}")
        
        return self.get_mock_balance()
    
    def get_positions(self) -> List[Dict]:
        """Get active positions via private API"""
        if not self.api_key or not self.api_secret:
            return self.get_mock_positions()
        
        try:
            endpoint = "/v1/openPositions"
            timestamp = str(int(time.time() * 1000))
            signature = self.create_signature("GET", endpoint)
            
            headers = {
                "API-KEY": self.api_key,
                "API-TIMESTAMP": timestamp,
                "API-SIGN": signature
            }
            
            url = f"{self.private_base_url}{endpoint}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 0:
                    return data.get('data', {}).get('list', [])
        except Exception as e:
            print(f"Positions API error: {e}")
        
        return self.get_mock_positions()
    
    def get_trade_history(self, symbol: str = "DOGE_JPY") -> List[Dict]:
        """Get trade history via private API"""
        if not self.api_key or not self.api_secret:
            return self.get_mock_trade_history()
        
        try:
            endpoint = f"/v1/latestExecutions?symbol={symbol}"
            timestamp = str(int(time.time() * 1000))
            signature = self.create_signature("GET", endpoint)
            
            headers = {
                "API-KEY": self.api_key,
                "API-TIMESTAMP": timestamp,
                "API-SIGN": signature
            }
            
            url = f"{self.private_base_url}{endpoint}"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 0:
                    return data.get('data', {}).get('list', [])
        except Exception as e:
            print(f"Trade history API error: {e}")
        
        return self.get_mock_trade_history()
    
    def get_mock_balance(self) -> Dict:
        """Mock balance data when API is not available"""
        return {
            'available': 813.0,
            'transferable': 813.0,
            'margin': 813.0,
            'actualProfitLoss': 0.0,
            'positionLossGain': 0.0
        }
    
    def get_mock_positions(self) -> List[Dict]:
        """Mock position data when API is not available"""
        current_price = float(self.get_public_ticker().get('last', '30.3'))
        return [{
            'symbol': 'DOGE_JPY',
            'side': 'BUY',
            'size': '20',
            'price': '30.407',
            'lossGain': str((current_price - 30.407) * 20),
            'timestamp': datetime.now().isoformat()
        }]
    
    def get_mock_trade_history(self) -> List[Dict]:
        """Mock trade history when API is not available"""
        return [
            {
                'symbol': 'DOGE_JPY',
                'side': 'SELL',
                'size': '20',
                'price': '30.407',
                'timestamp': '2025-07-14T17:04:18',
                'fee': '0.1'
            },
            {
                'symbol': 'DOGE_JPY',
                'side': 'BUY',
                'size': '10',
                'price': '30.56',
                'timestamp': '2025-07-14T13:29:19',
                'fee': '0.05'
            }
        ]

class RealAPIDashboard:
    """Real-time API dashboard"""
    
    def __init__(self):
        self.api_client = GMOCoinAPIClient()
        
    def get_dashboard_data(self) -> Dict:
        """Get all dashboard data from API"""
        ticker = self.api_client.get_public_ticker()
        balance = self.api_client.get_account_balance()
        positions = self.api_client.get_positions()
        trade_history = self.api_client.get_trade_history()
        
        current_price = float(ticker.get('last', '30.3'))
        
        # Calculate total P&L
        total_pnl = 0
        for pos in positions:
            if pos['side'] == 'BUY':
                pnl = (current_price - float(pos['price'])) * float(pos['size'])
            else:
                pnl = (float(pos['price']) - current_price) * float(pos['size'])
            total_pnl += pnl
        
        # Generate trading signal
        signal = self.generate_signal(current_price, positions)
        
        return {
            'ticker': ticker,
            'balance': balance,
            'positions': positions,
            'trade_history': trade_history,
            'current_price': current_price,
            'total_pnl': total_pnl,
            'signal': signal,
            'timestamp': datetime.now().isoformat()
        }
    
    def generate_signal(self, current_price: float, positions: List[Dict]) -> Dict:
        """Generate trading signal based on positions"""
        if not positions:
            return {'action': 'HOLD', 'reason': 'ポジションなし', 'color': 'yellow'}
        
        # Calculate average position P&L
        total_pnl_pct = 0
        position_count = len(positions)
        
        for pos in positions:
            entry_price = float(pos['price'])
            size = float(pos['size'])
            
            if pos['side'] == 'BUY':
                pnl = (current_price - entry_price) * size
            else:
                pnl = (entry_price - current_price) * size
            
            pnl_pct = (pnl / (entry_price * size)) * 100
            total_pnl_pct += pnl_pct
        
        avg_pnl_pct = total_pnl_pct / position_count if position_count > 0 else 0
        
        # Signal logic
        if avg_pnl_pct > 3:
            return {'action': 'SELL', 'reason': f'利益確定推奨 ({avg_pnl_pct:+.1f}%)', 'color': 'green'}
        elif avg_pnl_pct < -2:
            return {'action': 'SELL', 'reason': f'損切り推奨 ({avg_pnl_pct:+.1f}%)', 'color': 'red'}
        else:
            return {'action': 'HOLD', 'reason': f'ポジション維持 ({avg_pnl_pct:+.1f}%)', 'color': 'yellow'}
    
    def generate_html(self) -> str:
        """Generate dashboard HTML"""
        data = self.get_dashboard_data()
        
        # Position HTML
        position_html = ""
        for pos in data['positions']:
            entry_price = float(pos['price'])
            size = float(pos['size'])
            current_price = data['current_price']
            
            if pos['side'] == 'BUY':
                pnl = (current_price - entry_price) * size
            else:
                pnl = (entry_price - current_price) * size
            
            pnl_pct = (pnl / (entry_price * size)) * 100
            pnl_class = 'positive' if pnl > 0 else 'negative' if pnl < 0 else 'neutral'
            side_class = 'buy' if pos['side'] == 'BUY' else 'sell'
            
            position_html += f'''
            <div class="position-item">
                <div class="position-header">
                    <span class="position-side {side_class}">{pos['side']}</span>
                    <span class="position-size">{size:.1f} DOGE</span>
                </div>
                <div class="position-details">
                    <div class="detail-row">
                        <span>エントリー価格</span>
                        <span>¥{entry_price:.3f}</span>
                    </div>
                    <div class="detail-row">
                        <span>含み損益</span>
                        <span class="{pnl_class}">¥{pnl:+.2f} ({pnl_pct:+.1f}%)</span>
                    </div>
                </div>
            </div>
            '''
        
        # Trade history HTML
        trade_html = ""
        for trade in data['trade_history'][:5]:  # Show last 5 trades
            trade_time = datetime.fromisoformat(trade['timestamp'].replace('Z', '+00:00'))
            side_class = 'buy' if trade['side'] == 'BUY' else 'sell'
            
            trade_html += f'''
            <div class="trade-item">
                <div class="trade-info">
                    <span class="trade-side {side_class}">{trade['side']}</span>
                    <span class="trade-size">{float(trade['size']):.1f} DOGE</span>
                    <span class="trade-price">¥{float(trade['price']):.3f}</span>
                    <span class="trade-time">{trade_time.strftime('%H:%M')}</span>
                </div>
            </div>
            '''
        
        # API status check
        api_status = "接続済み" if data['balance'].get('available', 0) != 813 else "デモデータ"
        api_class = "connected" if api_status == "接続済み" else "demo"
        
        return f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GMO Coin Real API Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: Arial, sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; min-height: 100vh; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ color: #4CAF50; font-size: 2.5em; margin-bottom: 10px; }}
        .api-status {{ padding: 15px; border-radius: 8px; margin-bottom: 20px; text-align: center; }}
        .api-status.connected {{ background: #2E8B57; }}
        .api-status.demo {{ background: #FF8C00; }}
        .dashboard {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }}
        .card {{ background: linear-gradient(145deg, #0f3460 0%, #1e3c72 100%); padding: 25px; border-radius: 15px; border: 2px solid #2a5298; }}
        .card h3 {{ color: #64B5F6; margin-bottom: 15px; font-size: 1.3em; }}
        .price-display {{ font-size: 2.5em; font-weight: bold; text-align: center; margin: 15px 0; }}
        .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 15px 0; }}
        .stat-item {{ background: rgba(255,255,255,0.1); padding: 15px; border-radius: 8px; text-align: center; }}
        .stat-label {{ opacity: 0.8; font-size: 0.9em; }}
        .stat-value {{ font-weight: bold; font-size: 1.2em; margin-top: 5px; }}
        .positive {{ color: #4CAF50; }}
        .negative {{ color: #F44336; }}
        .neutral {{ color: #FFC107; }}
        .signal-card {{ text-align: center; padding: 30px; }}
        .signal-value {{ font-size: 2.5em; font-weight: bold; margin: 20px 0; }}
        .signal-green {{ color: #4CAF50; }}
        .signal-red {{ color: #F44336; }}
        .signal-yellow {{ color: #FFC107; }}
        .position-item, .trade-item {{ background: rgba(255,255,255,0.1); padding: 15px; border-radius: 8px; margin: 10px 0; }}
        .position-header, .trade-info {{ display: flex; justify-content: space-between; align-items: center; }}
        .position-side, .trade-side {{ padding: 4px 8px; border-radius: 4px; font-size: 0.9em; font-weight: bold; }}
        .position-side.buy, .trade-side.buy {{ background: #4CAF50; }}
        .position-side.sell, .trade-side.sell {{ background: #F44336; }}
        .detail-row {{ display: flex; justify-content: space-between; margin: 5px 0; }}
        .scrollable {{ max-height: 300px; overflow-y: auto; }}
        .footer {{ text-align: center; margin-top: 30px; opacity: 0.7; }}
        .indicator {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 8px; }}
        .indicator.green {{ background: #4CAF50; }}
        .indicator.orange {{ background: #FF8C00; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 GMO Coin Real API Dashboard</h1>
            <p>リアルタイムAPI連携ダッシュボード</p>
        </div>
        
        <div class="api-status {api_class}">
            <span class="indicator {'green' if api_status == '接続済み' else 'orange'}"></span>
            API Status: {api_status}
        </div>
        
        <div class="dashboard">
            <div class="card">
                <h3>💹 現在価格</h3>
                <div class="price-display">¥{data['current_price']:.3f}</div>
                <div class="stat-grid">
                    <div class="stat-item">
                        <div class="stat-label">24時間出来高</div>
                        <div class="stat-value">{float(data['ticker'].get('volume', '0')):,.0f}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">価格変動</div>
                        <div class="stat-value">¥{float(data['ticker'].get('last', '30.3')) - 30.407:.3f}</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3>💰 口座残高</h3>
                <div class="stat-grid">
                    <div class="stat-item">
                        <div class="stat-label">利用可能金額</div>
                        <div class="stat-value">¥{data['balance'].get('available', 0):,.0f}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">証拠金余力</div>
                        <div class="stat-value">¥{data['balance'].get('transferable', 0):,.0f}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">実現損益</div>
                        <div class="stat-value {'positive' if data['balance'].get('actualProfitLoss', 0) > 0 else 'negative'}">
                            ¥{data['balance'].get('actualProfitLoss', 0):+.2f}
                        </div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">含み損益</div>
                        <div class="stat-value {'positive' if data['total_pnl'] > 0 else 'negative' if data['total_pnl'] < 0 else 'neutral'}">
                            ¥{data['total_pnl']:+.2f}
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3>📈 保有ポジション</h3>
                <div class="scrollable">
                    {position_html if position_html else '<div class="stat-item">現在ポジションなし</div>'}
                </div>
            </div>
            
            <div class="card signal-card">
                <h3>🎯 取引シグナル</h3>
                <div class="signal-value signal-{data['signal']['color']}">{data['signal']['action']}</div>
                <div>{data['signal']['reason']}</div>
            </div>
            
            <div class="card">
                <h3>📋 取引履歴</h3>
                <div class="scrollable">
                    {trade_html if trade_html else '<div class="stat-item">取引履歴なし</div>'}
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S JST')}</p>
            <p>VPS: 49.212.131.248:5000 | GMO Coin API Integration</p>
        </div>
    </div>
    
    <script>
        setTimeout(() => {{ location.reload(); }}, 30000);
        console.log('API Dashboard Data:', {json.dumps(data, default=str, indent=2)});
    </script>
</body>
</html>'''

class RealAPIHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.dashboard = RealAPIDashboard()
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        if self.path == '/' or self.path == '/dashboard':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            html = self.dashboard.generate_html()
            self.wfile.write(html.encode('utf-8'))
        elif self.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            data = self.dashboard.get_dashboard_data()
            self.wfile.write(json.dumps(data, default=str, indent=2).encode('utf-8'))
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        pass

def main():
    PORT = 5000
    print(f"📊 GMO Coin Real API Dashboard Starting...")
    print(f"🌐 Dashboard: http://49.212.131.248:{PORT}")
    print(f"🔌 API Data: http://49.212.131.248:{PORT}/api/data")
    print(f"⚙️  Config: setting.ini (API Key/Secret)")
    print(f"🔄 Auto-refresh: 30 seconds")
    
    try:
        with socketserver.TCPServer(("", PORT), RealAPIHandler) as httpd:
            print("✅ Real API Dashboard is now RUNNING!")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()