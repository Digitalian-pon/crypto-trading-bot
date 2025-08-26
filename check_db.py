from models import User, TradingSettings
from app import db

with db.app.app_context():
    print('Checking database...')
    users = User.query.all()
    print(f'Found {len(users)} users')
    
    for u in users:
        print(f'User: {u.username}, API: {bool(u.api_key)}, Settings: {bool(u.settings)}')
        if u.settings:
            print(f'  Trading enabled: {u.settings.trading_enabled}, Currency: {u.settings.currency_pair}')