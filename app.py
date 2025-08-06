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
    
    # Trading bot auto-start temporarily disabled to fix numpy import issues
    # TODO: Re-enable after fixing pandas/numpy import conflicts
    logger.info("Trading bot auto-start is disabled for system stability")
    
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
            
            if not api_key or not api_secret:
                return render_template('simple_dashboard.html', data={'status': 'not_configured'})
            
            # Get basic market data
            api = GMOCoinAPI(api_key, api_secret)
            data_service = DataService(api_key, api_secret)
            
            # Get ticker data
            ticker_data = api.get_ticker("DOGE_JPY")
            balance_data = api.get_account_balance() if api_key and api_secret else None
            
            dashboard_data = {
                'ticker': ticker_data,
                'balance': balance_data,
                'status': 'running' if api_key and api_secret else 'not_configured'
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
