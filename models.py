import datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# DBインスタンスを直接インポートせず、後で設定
db = None

def init_db(database):
    """Initialize database instance"""
    global db
    db = database

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    api_key = db.Column(db.String(256))
    api_secret = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    settings = db.relationship('TradingSettings', backref='user', lazy=True, uselist=False)
    trades = db.relationship('Trade', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class TradingSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    currency_pair = db.Column(db.String(20), default='DOGE_JPY')
    trading_enabled = db.Column(db.Boolean, default=False)
    investment_amount = db.Column(db.Float, default=0.0)
    risk_level = db.Column(db.String(20), default='medium')  # low, medium, high
    stop_loss_percentage = db.Column(db.Float, default=3.0)  # 3% default stop loss
    take_profit_percentage = db.Column(db.Float, default=5.0)  # 5% default take profit
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f'<TradingSettings {self.user_id}>'

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    currency_pair = db.Column(db.String(20), nullable=False)
    trade_type = db.Column(db.String(4), nullable=False)  # buy or sell
    amount = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    status = db.Column(db.String(20), default='open')  # open, closed, cancelled
    closing_price = db.Column(db.Float)
    profit_loss = db.Column(db.Float)
    indicators_data = db.Column(db.JSON)  # Store indicators values at trade time
    closed_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<Trade {self.id} {self.trade_type} {self.currency_pair}>'

class MarketData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    currency_pair = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    open_price = db.Column(db.Float, nullable=False)
    high_price = db.Column(db.Float, nullable=False)
    low_price = db.Column(db.Float, nullable=False)
    close_price = db.Column(db.Float, nullable=False)
    volume = db.Column(db.Float, nullable=False)
    
    def __repr__(self):
        return f'<MarketData {self.currency_pair} {self.timestamp}>'
