import sqlite3
import os

db_path = "instance/crypto_trader.db"

if os.path.exists(db_path):
    print(f"Database exists at: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables: {[t[0] for t in tables]}")
    
    # Check users
    try:
        cursor.execute("SELECT id, username, api_key IS NOT NULL as has_api FROM user;")
        users = cursor.fetchall()
        print(f"Users: {users}")
        
        # Check trading settings
        cursor.execute("SELECT user_id, trading_enabled, currency_pair FROM trading_settings;")
        settings = cursor.fetchall()
        print(f"Trading settings: {settings}")
        
        # Check trades
        cursor.execute("SELECT id, user_id, currency_pair, trade_type, status FROM trade ORDER BY timestamp DESC LIMIT 10;")
        trades = cursor.fetchall()
        print(f"Recent trades: {trades}")
        
    except Exception as e:
        print(f"Error querying database: {e}")
    
    conn.close()
else:
    print(f"Database not found at: {db_path}")