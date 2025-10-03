"""
Enhanced Dashboard Route - Web UI integration for the Enhanced AI Controller
統合ダッシュボードルート - Enhanced AIコントローラー用WebUI統合
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import current_user, login_required
import logging
import json
import datetime
from typing import Dict, List, Optional

# Local imports
from models import User, TradingSettings, Trade, db
from services.enhanced_ai_controller import EnhancedAIController
from services.gmo_api import GMOCoinAPI

logger = logging.getLogger(__name__)

# Create blueprint
enhanced_dashboard_bp = Blueprint('enhanced_dashboard', __name__, url_prefix='/enhanced')

# Global AI controller instance
ai_controller = None

@enhanced_dashboard_bp.route('/')
def dashboard():
    """
    Enhanced dashboard showing AI controller status and performance
    統合ダッシュボード - AIコントローラーのステータスとパフォーマンス表示
    """
    try:
        # Get or create default user
        user = _get_or_create_default_user()
        
        # Initialize AI controller if needed
        global ai_controller
        if ai_controller is None:
            ai_controller = _initialize_ai_controller(user)
        
        # Get current market data
        market_data = _get_current_market_data(user)
        
        # Get AI performance metrics
        performance = ai_controller.get_performance_metrics() if ai_controller else {}
        
        # Get recent trades
        recent_trades = _get_recent_trades(user.id)
        
        # Get trading status
        trading_status = _get_trading_status(user)
        
        dashboard_data = {
            'user': user,
            'market_data': market_data,
            'performance': performance,
            'recent_trades': recent_trades,
            'trading_status': trading_status,
            'ai_active': ai_controller is not None
        }
        
        return render_template('enhanced_dashboard.html', **dashboard_data)
        
    except Exception as e:
        logger.error(f'Dashboard error: {str(e)}')
        return render_template('error.html', error=str(e)), 500

@enhanced_dashboard_bp.route('/api/market-data')
def api_market_data():
    """
    API endpoint for real-time market data
    リアルタイム市場データのAPIエンドポイント
    """
    try:
        user = _get_or_create_default_user()
        market_data = _get_current_market_data(user)
        
        return jsonify({
            'success': True,
            'data': market_data,
            'timestamp': datetime.datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f'Market data API error: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@enhanced_dashboard_bp.route('/api/trading-signal')
def api_trading_signal():
    """
    API endpoint for current trading signal
    現在の取引シグナルのAPIエンドポイント
    """
    try:
        user = _get_or_create_default_user()
        
        global ai_controller
        if ai_controller is None:
            ai_controller = _initialize_ai_controller(user)
        
        if ai_controller:
            # Get market data for signal analysis
            df = ai_controller._get_market_data_for_optimization()
            if df is not None and len(df) > 0:
                signal = ai_controller.get_trade_signal(df)
                current_price = df['close'].iloc[-1]
                
                # Get technical indicators for display
                indicators = {}
                if len(df) > 0:
                    last_row = df.iloc[-1]
                    indicators = {
                        'rsi': round(last_row.get('rsi_14', 0), 2),
                        'macd': round(last_row.get('macd_line', 0), 6),
                        'macd_signal': round(last_row.get('macd_signal', 0), 6),
                        'ema_12': round(last_row.get('ema_12', 0), 2),
                        'ema_26': round(last_row.get('ema_26', 0), 2),
                        'bb_upper': round(last_row.get('bb_upper', 0), 2),
                        'bb_lower': round(last_row.get('bb_lower', 0), 2),
                        'volume': int(last_row.get('volume', 0))
                    }
                
                return jsonify({
                    'success': True,
                    'signal': signal,
                    'current_price': current_price,
                    'indicators': indicators,
                    'timestamp': datetime.datetime.utcnow().isoformat()
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'No market data available'
                })
        else:
            return jsonify({
                'success': False,
                'error': 'AI controller not initialized'
            })
        
    except Exception as e:
        logger.error(f'Trading signal API error: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@enhanced_dashboard_bp.route('/api/execute-trade', methods=['POST'])
def api_execute_trade():
    """
    API endpoint for manual trade execution
    手動取引実行のAPIエンドポイント
    """
    try:
        data = request.get_json()
        signal = data.get('signal', '').upper()
        
        if signal not in ['BUY', 'SELL']:
            return jsonify({
                'success': False,
                'error': 'Invalid signal. Must be BUY or SELL.'
            }), 400
        
        user = _get_or_create_default_user()
        
        global ai_controller
        if ai_controller is None:
            ai_controller = _initialize_ai_controller(user)
        
        if ai_controller:
            # Get current market data
            df = ai_controller._get_market_data_for_optimization()
            if df is not None and len(df) > 0:
                current_price = df['close'].iloc[-1]
                
                # Execute trade
                success = ai_controller.execute_trade(signal, current_price, df)
                
                if success:
                    return jsonify({
                        'success': True,
                        'message': f'{signal} order executed successfully',
                        'price': current_price
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Trade execution failed'
                    })
            else:
                return jsonify({
                    'success': False,
                    'error': 'No market data available for trade execution'
                })
        else:
            return jsonify({
                'success': False,
                'error': 'AI controller not initialized'
            })
        
    except Exception as e:
        logger.error(f'Trade execution API error: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@enhanced_dashboard_bp.route('/api/start-ai')
def api_start_ai():
    """
    API endpoint to start AI trading
    AI取引開始のAPIエンドポイント
    """
    try:
        user = _get_or_create_default_user()
        
        global ai_controller
        if ai_controller is None:
            ai_controller = _initialize_ai_controller(user)
        
        if ai_controller:
            # Update trading settings to enabled
            if user.settings:
                user.settings.trading_enabled = True
                db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'AI trading started successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to initialize AI controller'
            })
        
    except Exception as e:
        logger.error(f'Start AI API error: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@enhanced_dashboard_bp.route('/api/stop-ai')
def api_stop_ai():
    """
    API endpoint to stop AI trading
    AI取引停止のAPIエンドポイント
    """
    try:
        user = _get_or_create_default_user()
        
        if user.settings:
            user.settings.trading_enabled = False
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'AI trading stopped successfully'
        })
        
    except Exception as e:
        logger.error(f'Stop AI API error: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@enhanced_dashboard_bp.route('/settings')
def settings():
    """
    Enhanced settings page for AI controller configuration
    AIコントローラー設定ページ
    """
    try:
        user = _get_or_create_default_user()
        
        return render_template('enhanced_settings.html', user=user)
        
    except Exception as e:
        logger.error(f'Settings page error: {str(e)}')
        return render_template('error.html', error=str(e)), 500

@enhanced_dashboard_bp.route('/settings', methods=['POST'])
def update_settings():
    """
    Update AI controller settings
    AIコントローラー設定更新
    """
    try:
        user = _get_or_create_default_user()
        
        # Get form data
        currency_pair = request.form.get('currency_pair', 'DOGE_JPY')
        timeframe = request.form.get('timeframe', '5m')
        trading_enabled = request.form.get('trading_enabled') == 'on'
        risk_level = request.form.get('risk_level', 'medium')
        stop_loss = float(request.form.get('stop_loss_percentage', 3.0))
        take_profit = float(request.form.get('take_profit_percentage', 5.0))
        
        # Update settings
        if user.settings:
            user.settings.currency_pair = currency_pair
            user.settings.timeframe = timeframe
            user.settings.trading_enabled = trading_enabled
            user.settings.risk_level = risk_level
            user.settings.stop_loss_percentage = stop_loss
            user.settings.take_profit_percentage = take_profit
        else:
            # Create new settings
            settings = TradingSettings(
                user_id=user.id,
                currency_pair=currency_pair,
                timeframe=timeframe,
                trading_enabled=trading_enabled,
                risk_level=risk_level,
                stop_loss_percentage=stop_loss,
                take_profit_percentage=take_profit
            )
            db.session.add(settings)
        
        db.session.commit()
        
        # Reinitialize AI controller with new settings
        global ai_controller
        ai_controller = _initialize_ai_controller(user)
        
        flash('Settings updated successfully', 'success')
        return redirect(url_for('enhanced_dashboard.settings'))
        
    except Exception as e:
        logger.error(f'Settings update error: {str(e)}')
        flash(f'Error updating settings: {str(e)}', 'error')
        return redirect(url_for('enhanced_dashboard.settings'))

def _get_or_create_default_user():
    """Get or create default user for AI trading"""
    try:
        user = User.query.filter_by(username='ai_trader').first()
        
        if not user:
            # Create default user
            user = User(
                username='ai_trader',
                email='ai@trader.com'
            )
            db.session.add(user)
            db.session.commit()
            
            # Create default settings
            settings = TradingSettings(
                user_id=user.id,
                currency_pair='DOGE_JPY',
                timeframe='5m',
                trading_enabled=False,
                risk_level='medium',
                stop_loss_percentage=3.0,
                take_profit_percentage=5.0
            )
            db.session.add(settings)
            db.session.commit()
            
            logger.info('Created default AI trader user')
        
        return user
        
    except Exception as e:
        logger.error(f'Error getting/creating default user: {str(e)}')
        raise

def _initialize_ai_controller(user):
    """Initialize AI controller with user settings"""
    try:
        if not user.settings:
            logger.warning('User has no settings, cannot initialize AI controller')
            return None
        
        # Load API credentials from environment or config
        from config import load_config
        config = load_config()
        
        api_key = user.api_key or config['api_credentials'].get('api_key', '')
        api_secret = user.api_secret or config['api_credentials'].get('api_secret', '')
        
        if not api_key or not api_secret:
            logger.error('No API credentials available for AI controller')
            return None
        
        # Initialize Enhanced AI Controller
        ai_controller = EnhancedAIController(
            user=user,
            product_code=user.settings.currency_pair,
            use_percent=0.05,  # 5% position sizing
            duration=user.settings.timeframe,
            past_period=100,
            stop_limit_percent=user.settings.stop_loss_percentage / 100
        )
        
        logger.info(f'AI controller initialized for user {user.username}')
        return ai_controller
        
    except Exception as e:
        logger.error(f'AI controller initialization error: {str(e)}')
        return None

def _get_current_market_data(user):
    """Get current market data for dashboard display"""
    try:
        if not user.settings:
            return {}
        
        # Load API credentials
        from config import load_config
        config = load_config()
        
        api_key = user.api_key or config['api_credentials'].get('api_key', '')
        api_secret = user.api_secret or config['api_credentials'].get('api_secret', '')
        
        if not api_key or not api_secret:
            return {}
        
        api_client = GMOCoinAPI(api_key, api_secret)
        
        # Get ticker data
        ticker = api_client.get_ticker(user.settings.currency_pair)
        
        # Get account balance
        balance_response = api_client.get_account_balance()
        
        market_data = {
            'symbol': user.settings.currency_pair,
            'current_price': 0,
            'change_24h': 0,
            'volume_24h': 0,
            'balance_jpy': 0,
            'balance_crypto': 0
        }
        
        if ticker and 'data' in ticker:
            data = ticker['data'][0] if ticker['data'] else {}
            market_data.update({
                'current_price': float(data.get('last', 0)),
                'change_24h': 0,  # GMO doesn't provide this directly
                'volume_24h': float(data.get('volume', 0))
            })
        
        if balance_response and 'data' in balance_response:
            for asset in balance_response['data']:
                if asset['symbol'] == 'JPY':
                    market_data['balance_jpy'] = float(asset['available'])
                elif asset['symbol'] == user.settings.currency_pair.split('_')[0]:
                    market_data['balance_crypto'] = float(asset['available'])
        
        return market_data
        
    except Exception as e:
        logger.error(f'Market data fetch error: {str(e)}')
        return {}

def _get_recent_trades(user_id, limit=10):
    """Get recent trades for dashboard display"""
    try:
        trades = Trade.query.filter_by(user_id=user_id)\
                           .order_by(Trade.timestamp.desc())\
                           .limit(limit)\
                           .all()
        
        trade_list = []
        for trade in trades:
            trade_dict = {
                'id': trade.id,
                'currency_pair': trade.currency_pair,
                'trade_type': trade.trade_type,
                'amount': trade.amount,
                'price': trade.price,
                'timestamp': trade.timestamp.isoformat(),
                'status': trade.status,
                'profit_loss': trade.profit_loss or 0
            }
            trade_list.append(trade_dict)
        
        return trade_list
        
    except Exception as e:
        logger.error(f'Recent trades fetch error: {str(e)}')
        return []

def _get_trading_status(user):
    """Get current trading status"""
    try:
        status = {
            'trading_enabled': False,
            'ai_active': False,
            'open_positions': 0,
            'last_trade': None
        }
        
        if user.settings:
            status['trading_enabled'] = user.settings.trading_enabled
        
        # Check for open positions
        open_trades = Trade.query.filter_by(user_id=user.id, status='open').count()
        status['open_positions'] = open_trades
        
        # Get last trade
        last_trade = Trade.query.filter_by(user_id=user.id)\
                               .order_by(Trade.timestamp.desc())\
                               .first()
        
        if last_trade:
            status['last_trade'] = last_trade.timestamp.isoformat()
        
        # Check if AI controller is active
        global ai_controller
        status['ai_active'] = ai_controller is not None
        
        return status
        
    except Exception as e:
        logger.error(f'Trading status fetch error: {str(e)}')
        return {
            'trading_enabled': False,
            'ai_active': False,
            'open_positions': 0,
            'last_trade': None
        }