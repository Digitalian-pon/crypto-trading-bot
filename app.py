import os
import logging

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager
from config import load_config


class Base(DeclarativeBase):
    pass


# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load configuration from setting.ini
config = load_config()

# Initialize SQLAlchemy with a custom model class
db = SQLAlchemy(model_class=Base)

# Create the Flask app
app = Flask(__name__)
app.secret_key = config['application'].get('secret_key', os.environ.get("SESSION_SECRET", "your-secret-key-for-development"))

# Get base directory
basedir = os.path.abspath(os.path.dirname(__file__))

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "instance", "crypto_trader.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Make sure the instance directory exists
db_dir = os.path.join(basedir, "instance")
os.makedirs(db_dir, exist_ok=True)
logger.info(f"Using database path: {app.config['SQLALCHEMY_DATABASE_URI']}")
logger.info(f"Instance directory: {db_dir}")

# Store API credentials from config for easy access
app.config["API_KEY"] = config['api_credentials'].get('api_key', '')
app.config["API_SECRET"] = config['api_credentials'].get('api_secret', '')

# Initialize the database with the app
db.init_app(app)

# Configure Flask-Login - temporarily disabled for direct dashboard access
# login_manager = LoginManager()
# login_manager.init_app(app)
# login_manager.login_view = 'auth.login'

# Import routes and register blueprints
with app.app_context():
    # Import and register blueprints
    # from routes.auth import auth_bp
    # from routes.public_dashboard import public_dashboard_bp
    # from routes.settings import settings_bp
    # from routes.api import api_bp
    # from routes.logs import logs_bp
    # from routes.status import status_bp
    
    # app.register_blueprint(public_dashboard_bp)
    # app.register_blueprint(api_bp)
    # app.register_blueprint(auth_bp)
    # app.register_blueprint(settings_bp)
    # app.register_blueprint(logs_bp)
    # app.register_blueprint(status_bp)
    
    # Import models to ensure they're registered with SQLAlchemy
    import models
    
    # Create all database tables
    db.create_all()
    
    from models import User
    
    # @login_manager.user_loader
    # def load_user(user_id):
    #     return User.query.get(int(user_id))
    
    # Trading bot auto-start enabled for real trading
    logger.info("Trading bot auto-start enabled")
    
    # Start trading bot for the first user with trading enabled
    try:
        from services.trading_bot import TradingBot
        user = User.query.filter_by(username='trading_user').first()
        
        if user and user.settings and user.settings.trading_enabled:
            logger.info(f"Starting trading bot for user: {user.username}")
            trading_bot = TradingBot(user=user, api_key=user.api_key, api_secret=user.api_secret)
            trading_bot.set_db_session(db.session)
            
            # Start the bot with 60 second intervals
            if trading_bot.start(interval=60):
                logger.info("Trading bot started successfully")
            else:
                logger.error("Failed to start trading bot")
        else:
            logger.warning("No user found with trading enabled")
    except Exception as e:
        logger.error(f"Error starting trading bot: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    # Register blueprints
    # from routes.status import status_bp
    # app.register_blueprint(status_bp, name='system_status')
    
    # Register dashboard routes
    # from routes.dashboard import dashboard_bp
    # app.register_blueprint(dashboard_bp, name='dashboard_routes')
    
    # Register API routes
    # from routes.api import api_bp
    # app.register_blueprint(api_bp, name='api_routes')
    
    # Register trading API routes (delayed import to avoid circular imports)
    try:
        # from routes.trading_api import trading_api_bp
        # app.register_blueprint(trading_api_bp, name='trading_api_routes')
        pass # Keep the try-except block structure
    except ImportError as e:
        logger.warning(f"Trading API routes not available: {e}")
    
    # Register auth routes
    # from routes.auth import auth_bp
    # app.register_blueprint(auth_bp, name='auth_routes')
    
    # Register test chart routes
    # from routes.test_chart import test_chart_bp
    # app.register_blueprint(test_chart_bp, name='test_chart_routes')
    
    # Add direct dashboard route for external VPS access
    # from routes.dashboard import index as dashboard_index
    # app.add_url_rule('/dashboard', 'direct_dashboard', dashboard_index, methods=['GET'])
    
    # Add main dashboard route
    @app.route('/')
    @app.route('/dashboard')
    def dashboard():
        """Main dashboard"""
        from flask import render_template, jsonify
        from services.gmo_api import GMOCoinAPI
        from services.data_service import DataService
        
        try:
            # Initialize API with config credentials
            api_key = config['api_credentials'].get('api_key', '')
            api_secret = config['api_credentials'].get('api_secret', '')
            
            logger.info(f"Dashboard access - API key available: {bool(api_key)}, length: {len(api_key) if api_key else 0}")
            
            if not api_key or not api_secret:
                logger.warning("API credentials not found in configuration")
                return render_template('simple_dashboard.html', data={'status': 'not_configured'})
            
            # Get basic market data
            api = GMOCoinAPI(api_key, api_secret)
            data_service = DataService(api_key, api_secret)
            
            # Get ticker data (public API)
            logger.info("Fetching ticker data...")
            ticker_data = api.get_ticker("DOGE_JPY")
            logger.info(f"Ticker data result: {ticker_data}")
            
            # Get balance data (private API)
            logger.info("Fetching balance data...")
            balance_data = api.get_account_balance() if api_key and api_secret else None
            logger.info(f"Balance data success: {bool(balance_data and balance_data.get('data'))}")
            
            dashboard_data = {
                'ticker': ticker_data,
                'balance': balance_data,
                'status': 'running' if api_key and api_secret else 'not_configured',
                'api_key_length': len(api_key),
                'api_secret_length': len(api_secret)
            }
            
            return render_template('simple_dashboard.html', data=dashboard_data)
            
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            return render_template('simple_dashboard.html', data={'error': str(e)})
    
    # Add clean dashboard route without infinite loops
    @app.route('/clean')
    def dashboard_clean():
        """Clean dashboard implementation"""
        from flask import render_template
        return render_template('dashboard_working.html')
    
    # Add backup route for original dashboard
    @app.route('/dashboard_original')
    def dashboard_original():
        """Original dashboard for reference"""
        from flask import render_template
        return render_template('dashboard_clean.html')
    
    # Add chart fix route
    @app.route('/fix')
    def dashboard_fix():
        """Chart fix dashboard"""
        from flask import render_template
        return render_template('chart_fix.html')
    
    # Add API route for ticker data
    @app.route('/api/ticker/<symbol>')
    def api_ticker(symbol):
        """API endpoint for ticker data"""
        from flask import jsonify
        from services.gmo_api import GMOCoinAPI
        
        try:
            api_key = config['api_credentials'].get('api_key', '')
            api_secret = config['api_credentials'].get('api_secret', '')
            
            if not api_key or not api_secret:
                return jsonify({'error': 'API credentials not configured'})
            
            api = GMOCoinAPI(api_key, api_secret)
            ticker_data = api.get_ticker(symbol)
            
            return jsonify(ticker_data)
            
        except Exception as e:
            return jsonify({'error': str(e)})
    
    # Add API route for trading analysis
    @app.route('/api/trading-analysis/<symbol>')
    def api_trading_analysis(symbol):
        """API endpoint for real-time trading analysis"""
        from flask import jsonify
        from datetime import datetime
        from services.gmo_api import GMOCoinAPI
        from services.data_service import DataService
        from services.simple_trading_logic import SimpleTradingLogic
        
        try:
            api_key = config['api_credentials'].get('api_key', '')
            api_secret = config['api_credentials'].get('api_secret', '')
            
            if not api_key or not api_secret:
                return jsonify({'error': 'API credentials not configured'})
            
            # Get market data with indicators
            data_service = DataService(api_key, api_secret)
            df = data_service.get_data_with_indicators(symbol, interval="1h", limit=50)
            
            if df is None or df.empty:
                # Fallback: Use current ticker data
                api = GMOCoinAPI(api_key, api_secret)
                ticker_data = api.get_ticker(symbol)
                
                if ticker_data and ticker_data.get('data'):
                    current_price = float(ticker_data['data'][0]['last'])
                    # Create mock data for analysis
                    latest = {
                        'close': current_price,
                        'rsi_14': 50.0,  # Neutral RSI
                        'macd_line': 0.0,
                        'macd_signal': 0.0,
                        'bb_upper': current_price * 1.02,
                        'bb_lower': current_price * 0.98,
                        'bb_middle': current_price,
                        'sma_20': current_price
                    }
                else:
                    return jsonify({'error': 'Could not get market data or ticker data'})
            else:
                # Get latest data point
                latest = df.iloc[-1].to_dict()
            
            # Analyze trading signals
            trading_logic = SimpleTradingLogic()
            should_trade, trade_type, reason, confidence = trading_logic.should_trade(latest)
            market_summary = trading_logic.get_market_summary(latest)
            
            return jsonify({
                'should_trade': should_trade,
                'trade_type': trade_type,
                'reason': reason,
                'confidence': round(confidence, 2) if confidence else 0,
                'market_summary': market_summary,
                'indicators': {
                    'rsi': round(latest.get('rsi_14', 50), 2),
                    'macd_line': round(latest.get('macd_line', 0), 4),
                    'macd_signal': round(latest.get('macd_signal', 0), 4),
                    'price': round(latest.get('close', 0), 3)
                },
                'timestamp': datetime.now().isoformat(),
                'status': 'success'
            })
            
        except Exception as e:
            logger.error(f"Error in trading analysis: {e}")
            return jsonify({'error': str(e)})
    
    # Add settings route
    @app.route('/settings', methods=['GET', 'POST'])
    def settings():
        """Settings page"""
        from flask import render_template, request, flash, redirect, url_for
        from config import save_api_credentials
        
        if request.method == 'POST':
            api_key = request.form.get('api_key', '').strip()
            api_secret = request.form.get('api_secret', '').strip()
            
            if api_key and api_secret:
                if save_api_credentials(api_key, api_secret):
                    flash('API認証情報を保存しました', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('API認証情報の保存に失敗しました', 'error')
            else:
                flash('API KeyとAPI Secretを入力してください', 'error')
        
        return render_template('simple_settings.html')
    
    logger.info("Application initialized successfully")
