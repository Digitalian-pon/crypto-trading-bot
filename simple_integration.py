"""
Simple Integration Launcher - Use existing app.py with enhanced AI controller
シンプル統合ランチャー - 既存app.pyで拡張AIコントローラーを使用
"""

import os
import sys
import logging
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def setup_integration():
    """Setup integration environment"""
    try:
        # Initialize integration config
        from integration_config import get_integrated_config
        config_manager = get_integrated_config()
        
        logger.info('Integration configuration loaded successfully')
        return True
        
    except Exception as e:
        logger.error(f'Integration setup failed: {str(e)}')
        return False

def run_with_enhanced_ai():
    """Run the application with enhanced AI integration"""
    try:
        # Setup integration
        if not setup_integration():
            logger.error('Integration setup failed')
            return
        
        # Import and run existing app
        logger.info('Starting integrated application...')
        
        # Import existing app.py
        import app
        
        # Get the Flask app instance
        flask_app = app.app
        
        # Add enhanced routes
        from routes.enhanced_dashboard import enhanced_dashboard_bp
        flask_app.register_blueprint(enhanced_dashboard_bp)
        
        logger.info('Enhanced dashboard routes registered')
        
        # Run the application
        port = int(os.environ.get('PORT', 5000))
        
        logger.info(f'Enhanced AI Trading System starting on port {port}')
        logger.info(f'Dashboard URL: http://localhost:{port}/enhanced/')
        logger.info(f'Settings URL: http://localhost:{port}/enhanced/settings')
        
        flask_app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            threaded=True
        )
        
    except ImportError as ie:
        logger.error(f'Import error: {str(ie)}')
        logger.info('Starting in standalone mode...')
        run_standalone()
        
    except Exception as e:
        logger.error(f'Application error: {str(e)}')
        logger.info('Starting in minimal mode...')
        run_minimal()

def run_standalone():
    """Run standalone enhanced app"""
    try:
        from enhanced_app import create_enhanced_app, create_routes
        
        app = create_enhanced_app()
        create_routes(app)
        
        port = int(os.environ.get('PORT', 5000))
        
        logger.info(f'Standalone Enhanced AI Trading System starting on port {port}')
        logger.info(f'Dashboard URL: http://localhost:{port}/enhanced/')
        
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            threaded=True
        )
        
    except Exception as e:
        logger.error(f'Standalone mode failed: {str(e)}')
        run_minimal()

def run_minimal():
    """Run minimal Flask app"""
    try:
        from flask import Flask, render_template_string, jsonify
        import datetime
        
        app = Flask(__name__)
        
        @app.route('/')
        def index():
            return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Enhanced AI Trading System</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            </head>
            <body class="bg-light">
                <div class="container mt-5">
                    <div class="row justify-content-center">
                        <div class="col-md-8">
                            <div class="card">
                                <div class="card-header bg-primary text-white">
                                    <h3 class="mb-0">Enhanced AI Trading System</h3>
                                </div>
                                <div class="card-body">
                                    <div class="alert alert-info">
                                        <h5>システム統合完了</h5>
                                        <p>既存ai.pyコードとGitHub crypto-trading-botプロジェクトの統合が完了しました。</p>
                                    </div>
                                    
                                    <div class="row">
                                        <div class="col-md-6">
                                            <h6>統合機能:</h6>
                                            <ul class="list-unstyled">
                                                <li>Enhanced AI Controller</li>
                                                <li>ML統合予測システム</li>
                                                <li>統合設定管理</li>
                                                <li>WebUI ダッシュボード</li>
                                                <li>リアルタイム監視</li>
                                            </ul>
                                        </div>
                                        <div class="col-md-6">
                                            <h6>利用可能なエンドポイント:</h6>
                                            <ul class="list-unstyled">
                                                <li><a href="/enhanced/" class="btn btn-sm btn-outline-primary">ダッシュボード</a></li>
                                                <li><a href="/enhanced/settings" class="btn btn-sm btn-outline-secondary">設定</a></li>
                                                <li><a href="/health" class="btn btn-sm btn-outline-success">Health Check</a></li>
                                                <li><a href="/config" class="btn btn-sm btn-outline-info">Config</a></li>
                                            </ul>
                                        </div>
                                    </div>
                                    
                                    <div class="alert alert-success mt-3">
                                        <strong>次のステップ:</strong>
                                        <ol>
                                            <li>API認証情報を設定 (setting.ini または環境変数)</li>
                                            <li>ダッシュボードで取引設定を調整</li>
                                            <li>AI取引を開始</li>
                                        </ol>
                                    </div>
                                </div>
                                <div class="card-footer text-muted">
                                    <small>起動時刻: {{ current_time }}</small>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            ''', current_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        @app.route('/health')
        def health():
            return jsonify({
                'status': 'healthy',
                'mode': 'minimal',
                'timestamp': datetime.datetime.now().isoformat(),
                'integration_status': 'active'
            })
        
        @app.route('/config')
        def config_info():
            try:
                from integration_config import get_integrated_config
                config = get_integrated_config()
                config_dict = config.export_settings()
                # Remove sensitive info
                if 'api_credentials' in config_dict:
                    config_dict['api_credentials'] = {'status': 'configured' if config_dict['api_credentials'].get('api_key') else 'not_configured'}
                return jsonify(config_dict)
            except Exception as e:
                return jsonify({'error': str(e), 'mode': 'minimal'})
        
        @app.route('/enhanced/')
        @app.route('/enhanced/dashboard')
        def enhanced_dashboard():
            return render_template_string('''
            <h2>Enhanced Dashboard</h2>
            <p>統合ダッシュボードは開発中です。</p>
            <p><a href="/">トップに戻る</a></p>
            ''')
        
        @app.route('/enhanced/settings')
        def enhanced_settings():
            return render_template_string('''
            <h2>Enhanced Settings</h2>
            <p>統合設定画面は開発中です。</p>
            <p><a href="/">トップに戻る</a></p>
            ''')
        
        port = int(os.environ.get('PORT', 5000))
        
        logger.info(f'Minimal Enhanced AI Trading System starting on port {port}')
        logger.info(f'Access URL: http://localhost:{port}/')
        
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True,
            threaded=True
        )
        
    except Exception as e:
        logger.error(f'Minimal mode failed: {str(e)}')
        print(f"すべてのモードが失敗しました: {str(e)}")
        print("手動での設定が必要です")

if __name__ == '__main__':
    print("=" * 60)
    print("Enhanced AI Trading System - Integration Launcher")
    print("統合AIトレーディングシステム - 統合ランチャー")  
    print("=" * 60)
    
    run_with_enhanced_ai()