import sqlite3

conn = sqlite3.connect('instance/crypto_trader.db')
cursor = conn.cursor()

# Check for any active positions/trades
cursor.execute("SELECT COUNT(*) FROM trade WHERE status != 'closed'")
active_trades = cursor.fetchone()[0]
print(f'Active trades in DB: {active_trades}')

cursor.execute("SELECT id, trade_type, amount, price, status, timestamp FROM trade ORDER BY timestamp DESC LIMIT 5")
recent_trades = cursor.fetchall()
print(f'Recent trades: {recent_trades}')

# Check GMO exchange positions
try:
    from services.gmo_api import GMOCoinAPI
    
    # Read API credentials from setting.ini
    import configparser
    config = configparser.ConfigParser()
    config.read('setting.ini')
    
    api_key = config.get('api_credentials', 'api_key')
    api_secret = config.get('api_credentials', 'api_secret')
    
    api = GMOCoinAPI(api_key, api_secret)
    
    # Check account balance
    balance = api.get_account_balance()
    print(f'Account balance: {balance}')
    
    # Check margin account and leverage positions
    margin_account = api.get_margin_account()
    print(f'Margin account: {margin_account}')
    
    # Check positions without symbol filter
    positions = api.get_positions()
    print(f'All Positions: {positions}')
    
    # Check specific DOGE positions if any exist
    try:
        doge_positions = api.get_positions(symbol='DOGE_JPY')
        print(f'DOGE_JPY Positions: {doge_positions}')
    except:
        print('Could not filter by DOGE_JPY symbol')
    
except Exception as e:
    print(f'Error checking GMO positions: {e}')

conn.close()