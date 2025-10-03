"""
Enhanced Flask Application - Complete integration of AI trading system
統合Flaskアプリケーション - AI取引システムの完全統合
"""

import os
import logging
import threading
import time
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager

# Import integrated configuration
from integration_config import get_integrated_config, get_ai_config
from config import load_config

# Enhanced AI Controller
from services.enhanced_ai_controller import EnhancedAIController
from services.ml_integration import EnhancedMLModel

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()

def create_enhanced_app():
    """
    Create enhanced Flask application with full AI integration
    完全AI統合の拡張Flaskアプリケーションを作成
    """
    app = Flask(__name__)
    
    # Load integrated configuration
    integrated_config = get_integrated_config()
    ai_config = get_ai_config()
    
    # Configure Flask app
    app.secret_key = os.environ.get("SESSION_SECRET", "enhanced-ai-trading-secret-key")
    
    # Database configuration
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "instance", "enhanced_crypto_trader.db")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Ensure instance directory exists
    db_dir = os.path.join(basedir, "instance")
    os.makedirs(db_dir, exist_ok=True)
    
    # Store AI configuration in app config
    app.config["AI_CONFIG"] = ai_config
    app.config["INTEGRATED_CONFIG"] = integrated_config
    
    # Initialize database
    db.init_app(app)
    
    # Initialize Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    with app.app_context():
        # Initialize models
        import models
        models.init_db(db)
        
        # Create all database tables
        db.create_all()
        
        # Import model classes
        from models import User, TradingSettings
        
        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))
        
        # Register blueprints
        register_blueprints(app)
        
        # Initialize and start enhanced AI system
        if ai_config.trading_enabled:
            start_enhanced_ai_system(app)
        
        logger.info('Enhanced Flask application created successfully')
    
    return app

def register_blueprints(app):
    """Register all blueprints"""
    try:
        # Enhanced dashboard blueprint
        from routes.enhanced_dashboard import enhanced_dashboard_bp
        app.register_blueprint(enhanced_dashboard_bp)
        
        # Original routes (for backward compatibility)
        try:
            from routes.public_dashboard import public_dashboard_bp
            app.register_blueprint(public_dashboard_bp)
        except ImportError:
            logger.info('Original public dashboard not available')
        
        try:
            from routes.api import api_bp
            app.register_blueprint(api_bp)
        except ImportError:
            logger.info('Original API routes not available')
        
        logger.info('Blueprints registered successfully')
        
    except Exception as e:
        logger.error(f'Blueprint registration error: {str(e)}')

def start_enhanced_ai_system(app):
    """Start the enhanced AI trading system"""
    try:
        ai_config = app.config["AI_CONFIG"]
        
        # Create or get default user
        from models import User, TradingSettings, db
        
        user = User.query.filter_by(username='enhanced_ai_trader').first()
        if not user:
            # Create enhanced AI trader user
            user = User(
                username='enhanced_ai_trader',
                email='enhanced.ai@trader.com',
                api_key=ai_config.api_key,
                api_secret=ai_config.api_secret
            )
            db.session.add(user)
            db.session.commit()
            
            # Create trading settings
            settings = TradingSettings(
                user_id=user.id,
                currency_pair=ai_config.currency_pair,
                timeframe=ai_config.timeframe,
                trading_enabled=ai_config.trading_enabled,
                risk_level=ai_config.risk_level,
                stop_loss_percentage=ai_config.stop_loss_percentage,
                take_profit_percentage=ai_config.take_profit_percentage
            )
            db.session.add(settings)
            db.session.commit()
            
            logger.info('Enhanced AI trader user created')
        
        # Update user credentials and settings
        if ai_config.api_key:
            user.api_key = ai_config.api_key
        if ai_config.api_secret:
            user.api_secret = ai_config.api_secret
        
        if user.settings:
            user.settings.currency_pair = ai_config.currency_pair
            user.settings.timeframe = ai_config.timeframe
            user.settings.trading_enabled = ai_config.trading_enabled
            user.settings.risk_level = ai_config.risk_level
            user.settings.stop_loss_percentage = ai_config.stop_loss_percentage
            user.settings.take_profit_percentage = ai_config.take_profit_percentage
        
        db.session.commit()
        
        # Initialize Enhanced AI Controller
        enhanced_ai = EnhancedAIController(
            user=user,
            product_code=ai_config.product_code,
            use_percent=ai_config.use_percent,
            duration=ai_config.duration,
            past_period=ai_config.past_period,
            stop_limit_percent=ai_config.stop_limit_percent
        )
        
        # Store in app context for access by routes
        app.config["ENHANCED_AI_CONTROLLER"] = enhanced_ai
        
        # Start trading loop in background thread
        if ai_config.trading_enabled:
            trading_thread = threading.Thread(
                target=enhanced_trading_loop,
                args=(app, enhanced_ai, ai_config),
                daemon=True
            )
            trading_thread.start()
            logger.info('Enhanced AI trading loop started')
        
        logger.info('Enhanced AI system initialized successfully')
        
    except Exception as e:
        logger.error(f'Enhanced AI system initialization error: {str(e)}')

def enhanced_trading_loop(app, enhanced_ai: EnhancedAIController, ai_config):
    """Enhanced trading loop with full AI capabilities"""
    logger.info('Enhanced trading loop started')
    
    try:
        # Initialize enhanced ML model
        ml_model = EnhancedMLModel()
        
        # Load saved model state if available
        ml_model.load_model_state()
        
        trading_cycle_count = 0
        
        while True:
            try:
                with app.app_context():
                    # Check if trading is still enabled
                    from models import User
                    user = User.query.filter_by(username='enhanced_ai_trader').first()
                    
                    if not user or not user.settings or not user.settings.trading_enabled:
                        logger.info('Trading disabled, pausing loop')
                        time.sleep(60)  # Check every minute
                        continue
                    
                    # Run enhanced trading cycle
                    logger.info(f'Starting enhanced trading cycle #{trading_cycle_count + 1}')
                    
                    # Get market data for ML prediction
                    df = enhanced_ai._get_market_data_for_optimization()
                    
                    if df is not None and len(df) > 10:
                        # Get enhanced ML prediction with optimization
                        ml_prediction = ml_model.predict_with_optimization(df, optimize_params=True)
                        
                        logger.info(f'Enhanced ML prediction: {ml_prediction}')
                        
                        # Get traditional AI signal
                        traditional_signal = enhanced_ai.get_trade_signal(df)
                        
                        # Combine predictions for final decision
                        final_decision = combine_ai_predictions(ml_prediction, traditional_signal)
                        
                        logger.info(f'Traditional signal: {traditional_signal}, Final decision: {final_decision}')
                        
                        # Execute trade if decision is not HOLD
                        if final_decision != 'HOLD':
                            current_price = df['close'].iloc[-1]
                            success = enhanced_ai.execute_trade(final_decision, current_price, df)
                            
                            if success:
                                logger.info(f'Enhanced trade executed successfully: {final_decision} at {current_price}')
                                
                                # Save ML model state after successful trade
                                ml_model.save_model_state()
                            else:
                                logger.warning(f'Trade execution failed: {final_decision}')
                    else:
                        logger.warning('Insufficient market data for enhanced trading cycle')
                    
                    trading_cycle_count += 1
                    
                    # Periodic ML model optimization (every 24 hours)
                    if trading_cycle_count % 1440 == 0:  # Assuming 1-minute cycles
                        logger.info('Running periodic ML model optimization')
                        try:
                            ml_model.optimize_trading_parameters(df)
                            ml_model.save_model_state()
                        except Exception as opt_e:
                            logger.error(f'ML optimization error: {str(opt_e)}')
                
            except Exception as cycle_e:
                logger.error(f'Enhanced trading cycle error: {str(cycle_e)}')
            
            # Wait for next cycle based on configuration
            time.sleep(ai_config.trade_interval)
    
    except Exception as e:
        logger.error(f'Enhanced trading loop error: {str(e)}')

def combine_ai_predictions(ml_prediction: dict, traditional_signal: str) -> str:
    """
    Combine ML prediction with traditional AI signal for final decision
    ML予測と従来のAIシグナルを組み合わせて最終判定
    """
    try:
        # Weight factors
        ml_weight = 0.6
        traditional_weight = 0.4
        
        # Convert traditional signal to numeric
        traditional_numeric = {
            'BUY': 1,
            'SELL': 0,
            'HOLD': 0.5
        }.get(traditional_signal, 0.5)
        
        # Get ML prediction values
        ml_prediction_value = ml_prediction.get('prediction', 0)
        ml_probability = ml_prediction.get('probability', 0.5)
        ml_confidence = ml_prediction.get('confidence', 0.5)
        
        # Calculate combined score
        ml_score = ml_prediction_value * ml_probability * ml_confidence
        traditional_score = traditional_numeric
        
        combined_score = (ml_score * ml_weight) + (traditional_score * traditional_weight)
        
        # Decision thresholds
        buy_threshold = 0.65
        sell_threshold = 0.35
        
        if combined_score >= buy_threshold:
            return 'BUY'
        elif combined_score <= sell_threshold:
            return 'SELL'
        else:
            return 'HOLD'
            
    except Exception as e:
        logger.error(f'AI prediction combination error: {str(e)}')
        return 'HOLD'

def create_routes(app):
    """Create additional routes for enhanced functionality"""
    
    @app.route('/')
    def index():
        """Redirect to enhanced dashboard"""
        from flask import redirect, url_for
        return redirect(url_for('enhanced_dashboard.dashboard'))
    
    @app.route('/health')
    def health_check():
        """Health check endpoint"""
        from flask import jsonify
        
        try:
            ai_config = app.config.get("AI_CONFIG")
            enhanced_ai = app.config.get("ENHANCED_AI_CONTROLLER")
            
            return jsonify({
                'status': 'healthy',
                'trading_enabled': ai_config.trading_enabled if ai_config else False,
                'ai_controller_active': enhanced_ai is not None,
                'timestamp': time.time()
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e),
                'timestamp': time.time()
            }), 500
    
    @app.route('/config')
    def show_config():
        """Show current configuration (for debugging)"""
        from flask import jsonify
        
        try:
            integrated_config = app.config.get("INTEGRATED_CONFIG")
            if integrated_config:
                config_dict = integrated_config.export_settings()
                # Remove sensitive information
                if 'api_credentials' in config_dict:
                    config_dict['api_credentials'] = {'api_key': '***', 'api_secret': '***'}
                return jsonify(config_dict)
            else:
                return jsonify({'error': 'Configuration not available'}), 500
        except Exception as e:
            return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run enhanced application
    app = create_enhanced_app()
    
    # Add additional routes
    create_routes(app)
    
    # Get configuration
    ai_config = get_ai_config()
    
    # Run application
    port = int(os.environ.get('PORT', 5000))
    debug = not ai_config.trading_enabled  # Don't run debug mode with live trading
    
    logger.info(f'Starting enhanced AI trading application on port {port}')
    logger.info(f'Trading enabled: {ai_config.trading_enabled}')
    logger.info(f'Currency pair: {ai_config.currency_pair}')
    logger.info(f'Timeframe: {ai_config.timeframe}')
    logger.info(f'Paper trading: {ai_config.paper_trade}')
    
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)