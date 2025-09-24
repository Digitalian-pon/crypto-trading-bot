#!/usr/bin/env python3
"""Test adaptive indicator parameters"""

import pandas as pd
import numpy as np
from services.technical_indicators import TechnicalIndicators

# Create sample data
np.random.seed(42)
dates = pd.date_range('2025-01-01', periods=100, freq='5T')

# Volatile market data
volatile_data = pd.DataFrame({
    'close': 35 + np.random.randn(100) * 2,
    'high': 36 + np.random.randn(100) * 2,
    'low': 34 + np.random.randn(100) * 2,
}, index=dates)

# Trending market data
trending_data = pd.DataFrame({
    'close': np.linspace(30, 40, 100) + np.random.randn(100) * 0.5,
    'high': np.linspace(31, 41, 100) + np.random.randn(100) * 0.5,
    'low': np.linspace(29, 39, 100) + np.random.randn(100) * 0.5,
}, index=dates)

# Ranging market data
ranging_data = pd.DataFrame({
    'close': 35 + np.sin(np.linspace(0, 8*np.pi, 100)) * 0.5 + np.random.randn(100) * 0.2,
    'high': 35.5 + np.sin(np.linspace(0, 8*np.pi, 100)) * 0.5 + np.random.randn(100) * 0.2,
    'low': 34.5 + np.sin(np.linspace(0, 8*np.pi, 100)) * 0.5 + np.random.randn(100) * 0.2,
}, index=dates)

print("=" * 60)
print("ADAPTIVE INDICATOR PARAMETERS TEST")
print("=" * 60)

for name, df in [('Volatile', volatile_data), ('Trending', trending_data), ('Ranging', ranging_data)]:
    print(f"\n{name} Market Test:")
    print("-" * 40)

    df_with_indicators = TechnicalIndicators.add_all_indicators(df.copy())
    regime = df_with_indicators['market_regime'].iloc[-1]

    print(f"  Market Regime: {regime}")
    print(f"  RSI: {df_with_indicators['rsi_14'].iloc[-1]:.2f}")
    print(f"  MACD Line: {df_with_indicators['macd_line'].iloc[-1]:.4f}")
    print(f"  BB Upper: {df_with_indicators['bb_upper'].iloc[-1]:.2f}")
    print(f"  BB Lower: {df_with_indicators['bb_lower'].iloc[-1]:.2f}")
    print(f"  BB Width: {(df_with_indicators['bb_upper'].iloc[-1] - df_with_indicators['bb_lower'].iloc[-1]):.2f}")

print("\n" + "=" * 60)
print("Test completed successfully!")
print("=" * 60)