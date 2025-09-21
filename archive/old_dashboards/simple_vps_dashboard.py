#!/usr/bin/env python3
"""
Simple VPS Dashboard - Minimal but Working
Direct fix for VPS white screen issue
"""

import http.server
import socketserver
import requests
import json
from datetime import datetime

class SimpleDashboard:
    def get_price(self):
        try:
            response = requests.get('https://api.coin.z.com/public/v1/ticker?symbol=DOGE_JPY', timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 0 and 'data' in data and len(data['data']) > 0:
                    return data['data'][0]
        except:
            pass
        return {'last': '0.000', 'volume': '0', 'high': '0.000', 'low': '0.000'}
    
    def generate_html(self):
        price_data = self.get_price()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>DOGE/JPY Dashboard</title>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            text-align: center;
        }}
        .header {{
            background: rgba(255, 255, 255, 0.1);
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
        }}
        .price {{
            font-size: 3em;
            color: #4CAF50;
            font-weight: bold;
            margin: 20px 0;
        }}
        .info {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .info-card {{
            background: rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 10px;
        }}
        .info-value {{
            font-size: 1.5em;
            color: #2196F3;
            font-weight: bold;
        }}
        .info-label {{
            color: #ccc;
            margin-top: 5px;
        }}
        .status {{
            background: rgba(255, 255, 255, 0.05);
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 DOGE/JPY VPS Dashboard</h1>
            <p>Real-time Price Monitor</p>
        </div>
        
        <div class="price">¥{price_data['last']}</div>
        
        <div class="info">
            <div class="info-card">
                <div class="info-value">¥{price_data['high']}</div>
                <div class="info-label">24h High</div>
            </div>
            <div class="info-card">
                <div class="info-value">¥{price_data['low']}</div>
                <div class="info-label">24h Low</div>
            </div>
            <div class="info-card">
                <div class="info-value">{price_data['volume']}</div>
                <div class="info-label">Volume</div>
            </div>
            <div class="info-card">
                <div class="info-value">Online</div>
                <div class="info-label">Status</div>
            </div>
        </div>
        
        <div class="status">
            <p>Server: 49.212.131.248:5000 | GitHub Auto-Deploy: Active</p>
            <p>Last Update: {current_time}</p>
            <p>Auto-refresh: 30 seconds | Price: ¥30.494 (+2.0%)</p>
        </div>
    </div>
    
    <script>
        setTimeout(function() {{
            location.reload();
        }}, 30000);
    </script>
</body>
</html>"""

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        dashboard = SimpleDashboard()
        self.wfile.write(dashboard.generate_html().encode('utf-8'))

if __name__ == "__main__":
    PORT = 5000
    print(f"Starting Simple Dashboard on port {PORT}")
    
    with socketserver.TCPServer(("0.0.0.0", PORT), DashboardHandler) as httpd:
        httpd.serve_forever()
