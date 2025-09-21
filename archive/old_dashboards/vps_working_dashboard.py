#!/usr/bin/env python3
"""
VPS Working Dashboard - Simple and Reliable
Optimized for VPS deployment with minimal dependencies
"""

import json
import http.server
import socketserver
import requests
from datetime import datetime
import logging
import threading
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WorkingDashboard:
    def __init__(self):
        self.current_price = 0.0
        self.volume = 0
        self.high = 0.0
        self.low = 0.0
        self.last_update = datetime.now()
        self.update_prices()
        
    def get_gmo_price(self):
        """Get DOGE/JPY price from GMO Coin API"""
        try:
            response = requests.get('https://api.coin.z.com/public/v1/ticker?symbol=DOGE_JPY', timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 0 and 'data' in data:
                    price_data = data['data']
                    return {
                        'price': float(price_data['last']),
                        'volume': float(price_data['volume']),
                        'high': float(price_data['high']),
                        'low': float(price_data['low'])
                    }
        except Exception as e:
            logger.error(f"Error fetching GMO price: {e}")
        return None
    
    def update_prices(self):
        """Update price data"""
        price_data = self.get_gmo_price()
        if price_data:
            self.current_price = price_data['price']
            self.volume = price_data['volume']
            self.high = price_data['high']
            self.low = price_data['low']
            self.last_update = datetime.now()
            logger.info(f"DOGE/JPY Price updated: ¥{self.current_price}")
    
    def generate_html(self):
        """Generate working dashboard HTML"""
        return f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DOGE/JPY VPS Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding: 30px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .header p {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        .price-section {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }}
        .main-price {{
            background: rgba(255, 255, 255, 0.15);
            border-radius: 25px;
            padding: 40px;
            text-align: center;
            backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}
        .price-value {{
            font-size: 4em;
            font-weight: 700;
            color: #4CAF50;
            margin-bottom: 15px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            letter-spacing: -2px;
        }}
        .price-label {{
            font-size: 1.4em;
            color: #f0f0f0;
            font-weight: 300;
        }}
        .volume-card {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 30px;
            text-align: center;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.15);
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        .volume-value {{
            font-size: 2.5em;
            font-weight: bold;
            color: #2196F3;
            margin-bottom: 10px;
        }}
        .volume-label {{
            font-size: 1.1em;
            color: #d0d0d0;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: transform 0.3s ease;
        }}
        .stat-card:hover {{
            transform: translateY(-5px);
        }}
        .stat-value {{
            font-size: 2.2em;
            font-weight: bold;
            color: #FF9800;
            margin-bottom: 8px;
        }}
        .stat-label {{
            font-size: 1.1em;
            color: #c0c0c0;
            font-weight: 300;
        }}
        .info-section {{
            background: rgba(255, 255, 255, 0.08);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 30px;
            backdrop-filter: blur(5px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }}
        .info-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .info-item:last-child {{
            border-bottom: none;
        }}
        .info-label {{
            font-size: 1.1em;
            color: #e0e0e0;
            font-weight: 300;
        }}
        .info-value {{
            font-size: 1.1em;
            font-weight: 600;
            color: #4CAF50;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            color: #b0b0b0;
        }}
        .status-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            background: #4CAF50;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0% {{ box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }}
            70% {{ box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }}
        }}
        .auto-refresh {{
            display: inline-block;
            background: rgba(76, 175, 80, 0.2);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9em;
            margin-top: 10px;
            border: 1px solid rgba(76, 175, 80, 0.3);
        }}
        @media (max-width: 768px) {{
            .price-section {{
                grid-template-columns: 1fr;
            }}
            .price-value {{
                font-size: 3em;
            }}
            .header h1 {{
                font-size: 2em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 DOGE/JPY VPS Dashboard</h1>
            <p><span class="status-indicator"></span>Real-time GMO Coin Market Data</p>
        </div>
        
        <div class="price-section">
            <div class="main-price">
                <div class="price-value">¥{self.current_price:.3f}</div>
                <div class="price-label">Current DOGE/JPY Price</div>
            </div>
            <div class="volume-card">
                <div class="volume-value">{self.volume:,.0f}</div>
                <div class="volume-label">24h Volume</div>
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">¥{self.high:.3f}</div>
                <div class="stat-label">24h High</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">¥{self.low:.3f}</div>
                <div class="stat-label">24h Low</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">Online</div>
                <div class="stat-label">API Status</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">Active</div>
                <div class="stat-label">VPS Status</div>
            </div>
        </div>
        
        <div class="info-section">
            <div class="info-grid">
                <div class="info-item">
                    <span class="info-label">Server IP:</span>
                    <span class="info-value">49.212.131.248</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Trading Pair:</span>
                    <span class="info-value">DOGE/JPY</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Data Source:</span>
                    <span class="info-value">GMO Coin API</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Last Update:</span>
                    <span class="info-value">{self.last_update.strftime('%H:%M:%S')}</span>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>🔄 VPS DOGE/JPY Trading Dashboard - GitHub Auto-Deploy Enabled</p>
            <div class="auto-refresh">Auto-refresh every 30 seconds</div>
        </div>
    </div>
    
    <script>
        // Auto-refresh every 30 seconds
        setTimeout(function() {{
            location.reload();
        }}, 30000);
        
        // Console logging
        console.log('VPS Dashboard loaded successfully');
        console.log('Current DOGE/JPY price: ¥{self.current_price}');
        console.log('24h Volume: {self.volume:,}');
        console.log('GitHub Auto-Deploy: Enabled');
        
        // Page load time
        window.addEventListener('load', function() {{
            console.log('Dashboard render complete');
        }});
    </script>
</body>
</html>
"""

class WorkingDashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.dashboard = WorkingDashboard()
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        try:
            # Update prices on each request
            self.dashboard.update_prices()
            
            # Send response with proper headers
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Generate and send HTML
            html_content = self.dashboard.generate_html()
            self.wfile.write(html_content.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error in request handler: {e}")
            self.send_error(500, f"Internal Server Error: {str(e)}")

def start_background_updater():
    """Background price updater thread"""
    dashboard = WorkingDashboard()
    while True:
        try:
            dashboard.update_prices()
            time.sleep(30)  # Update every 30 seconds
        except Exception as e:
            logger.error(f"Background updater error: {e}")
            time.sleep(60)  # Wait longer on error

if __name__ == "__main__":
    # Configuration
    PORT = 5000
    HOST = "0.0.0.0"
    
    # Start background price updater
    updater_thread = threading.Thread(target=start_background_updater, daemon=True)
    updater_thread.start()
    
    # Server startup
    logger.info(f"Starting VPS Working Dashboard on {HOST}:{PORT}")
    logger.info(f"Dashboard URL: http://49.212.131.248:{PORT}")
    logger.info("Features: Real-time DOGE/JPY price, GitHub auto-deploy ready")
    
    try:
        with socketserver.TCPServer((HOST, PORT), WorkingDashboardHandler) as httpd:
            logger.info("VPS Dashboard server started successfully")
            httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Dashboard server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
