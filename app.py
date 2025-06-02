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

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Import routes and register blueprints
with app.app_context():
    # Import and register blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.settings import settings_bp
    from routes.api import api_bp
    from routes.logs import logs_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(logs_bp)
    
    # Import models to ensure they're registered with SQLAlchemy
    import models
    
    # Create all database tables
    db.create_all()
    
    from models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # 自動的にトレーディングボットを起動するコード
    from models import User, TradingSettings
    from services.trading_bot import TradingBot
    from sqlalchemy.orm import scoped_session, sessionmaker
    import threading
    
    def start_trading_bots():
        """アプリケーション起動時にアクティブな全ユーザーのトレーディングボットを起動"""
        logger.info("Checking for users with active trading settings...")
        
        try:
            # 取引が有効になっているすべてのユーザーを検索
            active_settings = TradingSettings.query.filter_by(trading_enabled=True).all()
            logger.info(f"Found {len(active_settings)} users with trading enabled")
            
            # 各ユーザーのトレーディングボットを起動
            for settings in active_settings:
                user = User.query.get(settings.user_id)
                if not user:
                    logger.warning(f"User not found for settings ID {settings.id}")
                    continue
                    
                if not user.api_key or not user.api_secret:
                    logger.warning(f"API credentials not set for user {user.username}")
                    continue
                
                logger.info(f"Starting trading bot for user: {user.username}, pair: {settings.currency_pair}")
                
                # 新しいセッションを作成
                from sqlalchemy.orm import scoped_session, sessionmaker
                engine = db.get_engine()
                Session = scoped_session(sessionmaker(bind=engine))
                session = Session()
                
                # 新しいセッションでユーザーとその設定を再取得
                user_fresh = session.query(User).get(user.id)
                
                if not user_fresh:
                    logger.error(f"Failed to retrieve user {user.username} with fresh session")
                    continue
                
                # トレーディングボットを作成（新しいセッションオブジェクトで）
                trading_bot = TradingBot(user_fresh, user_fresh.api_key, user_fresh.api_secret)
                trading_bot.set_db_session(session)
                
                # ボットを起動
                success = trading_bot.start()
                if success:
                    logger.info(f"Trading bot started successfully for user {user.username}")
                else:
                    logger.error(f"Failed to start trading bot for user {user.username}")
                
        except Exception as e:
            logger.error(f"Error starting trading bots: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    # アプリケーション起動時にボットを起動（アプリケーションコンテキスト内で実行）
    def start_bots_with_app_context():
        with app.app_context():
            start_trading_bots()
    
    threading.Thread(target=start_bots_with_app_context, daemon=True).start()
    
    logger.info("Application initialized successfully")
