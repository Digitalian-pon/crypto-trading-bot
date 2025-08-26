import sqlite3
import sys
import os
sys.path.append('.')

# Direct database manipulation to fix user setup
db_path = "instance/crypto_trader.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get the API credentials from config
    api_key = "FXhblJAz9Ql0G3pCo5p/+S9zkFw6r2VC"
    api_secret = "/YiZoJlRybHnKAO78go6Jt9LKQOS/EwEEe47UyEl6YbXo7XA84fL+Q/k3AEJeCBo"
    
    print("Updating user with API credentials...")
    
    # Update user with API credentials
    cursor.execute("UPDATE user SET api_key = ?, api_secret = ? WHERE username = ?", 
                   (api_key, api_secret, 'trading_user'))
    
    # Make sure trading is enabled
    cursor.execute("UPDATE trading_settings SET trading_enabled = 1 WHERE user_id = 1")
    
    conn.commit()
    
    # Verify the changes
    cursor.execute("SELECT id, username, api_key IS NOT NULL as has_api FROM user WHERE username = 'trading_user'")
    user_info = cursor.fetchone()
    print(f"User info: {user_info}")
    
    cursor.execute("SELECT user_id, trading_enabled, currency_pair FROM trading_settings WHERE user_id = 1")
    settings = cursor.fetchone()
    print(f"Trading settings: {settings}")
    
    conn.close()
    print("Database updated successfully!")
else:
    print("Database not found!")