import sqlite3
import os
from datetime import datetime

db_path = "instance/crypto_trader.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check all trades with detailed info
    cursor.execute("""
        SELECT id, user_id, currency_pair, trade_type, amount, price, 
               status, closing_price, profit_loss, timestamp, closed_at
        FROM trade 
        ORDER BY timestamp DESC 
        LIMIT 20
    """)
    trades = cursor.fetchall()
    
    print(f"Found {len(trades)} trades:")
    print("-" * 100)
    
    for trade in trades:
        trade_id, user_id, currency_pair, trade_type, amount, price, status, closing_price, profit_loss, timestamp, closed_at = trade
        print(f"ID: {trade_id}")
        print(f"  Type: {trade_type.upper()} {currency_pair}")
        print(f"  Amount: {amount}")
        print(f"  Entry Price: {price}")
        print(f"  Status: {status}")
        if closing_price:
            print(f"  Closing Price: {closing_price}")
        if profit_loss:
            print(f"  P/L: {profit_loss}")
        print(f"  Opened: {timestamp}")
        if closed_at:
            print(f"  Closed: {closed_at}")
        print("-" * 50)
    
    # Count open trades
    cursor.execute("SELECT COUNT(*) FROM trade WHERE status = 'open'")
    open_count = cursor.fetchone()[0]
    print(f"\nOpen trades: {open_count}")
    
    conn.close()
else:
    print("Database not found!")