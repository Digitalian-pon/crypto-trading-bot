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
    from routes.auth import auth_bp
    from routes.public_dashboard import public_dashboard_bp
    from routes.settings import settings_bp
    from routes.api import api_bp
    from routes.logs import logs_bp
    from routes.status import status_bp
    
    app.register_blueprint(public_dashboard_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(status_bp)
    
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
    from routes.status import status_bp
    app.register_blueprint(status_bp, name='system_status')
    
    # Register dashboard routes
    from routes.dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp, name='dashboard_routes')
    
    # Register API routes
    from routes.api import api_bp
    app.register_blueprint(api_bp, name='api_routes')
    
    # Register trading API routes (delayed import to avoid circular imports)
    try:
        from routes.trading_api import trading_api_bp
        app.register_blueprint(trading_api_bp, name='trading_api_routes')
    except ImportError as e:
        logger.warning(f"Trading API routes not available: {e}")
    
    # Register auth routes
    from routes.auth import auth_bp
    app.register_blueprint(auth_bp, name='auth_routes')
    
    # Register test chart routes
    from routes.test_chart import test_chart_bp
    app.register_blueprint(test_chart_bp, name='test_chart_routes')
    
    # Add direct dashboard route for external VPS access
    from routes.dashboard import index as dashboard_index
    app.add_url_rule('/dashboard', 'direct_dashboard', dashboard_index, methods=['GET'])
    
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
    
    logger.info("Application initialized successfully")
