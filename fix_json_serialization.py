#!/usr/bin/env python3
"""
Fix JSON Serialization Issue in Trading Bot
Timestamp objects cannot be serialized to JSON - need conversion to strings
"""
import sys
import os
from datetime import datetime

def apply_json_serialization_fix():
    """Apply the fix to fixed_trading_loop.py"""
    file_path = 'fixed_trading_loop.py'

    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Find the _execute_trade method and add the fix
        old_execute_trade = '''    def _execute_trade(self, symbol, trade_type, current_price, indicators_data):
        """Execute a new trade"""
        logger.info(f"Executing {trade_type} trade for {symbol} at {current_price}")

        try:
            # Get available balance'''

        new_execute_trade = '''    def _execute_trade(self, symbol, trade_type, current_price, indicators_data):
        """Execute a new trade"""
        logger.info(f"Executing {trade_type} trade for {symbol} at {current_price}")

        try:
            # Convert pandas Timestamp objects to strings to avoid JSON serialization errors
            if isinstance(indicators_data, dict):
                clean_indicators_data = {}
                for key, value in indicators_data.items():
                    if hasattr(value, 'strftime'):  # Check if it's a datetime-like object
                        clean_indicators_data[key] = str(value)
                    elif hasattr(value, 'item'):  # Check if it's a numpy scalar
                        clean_indicators_data[key] = value.item()
                    else:
                        clean_indicators_data[key] = value
                indicators_data = clean_indicators_data

            # Get available balance'''

        if old_execute_trade in content:
            content = content.replace(old_execute_trade, new_execute_trade)

            with open(file_path, 'w') as f:
                f.write(content)

            print("✅ JSON serialization fix applied to fixed_trading_loop.py")
            return True
        else:
            print("⚠️ Pattern not found - file may already be modified or different")
            return False

    except Exception as e:
        print(f"❌ Error applying fix: {e}")
        return False

if __name__ == '__main__':
    print("=== JSON シリアライゼーション修正 ===")
    success = apply_json_serialization_fix()
    if success:
        print("修正が正常に適用されました")
    else:
        print("修正の適用に失敗しました")