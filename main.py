# 🚀 Advanced Alpaca Crypto Trading Bot with Trailing Stop, Take-Profit, and Backtest

# ========================
# 🔧 INSTALL REQUIRED LIBRARIES
# ========================
!pip uninstall -y alpaca-trade-api > /dev/null
!pip install -q "alpaca-py>=0.18.1" pandas numpy ta matplotlib yfinance

# ========================
# 📚 IMPORT LIBRARIES
# ========================
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.timeframe import TimeFrame

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import matplotlib.pyplot as plt
import yfinance as yf
import time
import uuid

from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
from IPython.display import clear_output
# ========================
# 🔑 USER CONFIGURATION
# ========================
API_KEY = ""
SECRET_KEY = ""
SYMBOL = "ETH/USD"
MODE = "LIVE"  # or "BACKTEST" or "LIVE"
INITIAL_CAPITAL = 10000
RISK_PER_TRADE = 0.02
BAR_INTERVAL = 15  # in minutes
SMA_SHORT = 20
SMA_LONG = 50
RSI_PERIOD = 14
ATR_PERIOD = 14
REAL_TRADING = False  # For Alpaca paper/live switch

TAKE_PROFIT_PCT = 0.05  # 5% take profit
TRAIL_STOP_PCT = 0.025  # 2.5% trailing stop
# ========================
# 🨠 HELPER FUNCTIONS
# ========================
crypto_client = CryptoHistoricalDataClient()
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=not REAL_TRADING)

in_position = False
entry_price = 0
highest_price = 0


def get_crypto_data(symbol, limit=100):
    timeframe = TimeFrame.Minute
    try:
        request = CryptoBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=timeframe,
            start=datetime.utcnow() - timedelta(minutes=limit * BAR_INTERVAL)
        )
        bars = crypto_client.get_crypto_bars(request).df
        bars = bars.reset_index()
        bars = bars[bars['symbol'] == symbol]
        bars = bars.set_index('timestamp')
        bars_resampled = bars.resample(f'{BAR_INTERVAL}min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'trade_count': 'sum',
            'vwap': 'mean'
        }).dropna()
        return bars_resampled
    except Exception as e:
        print(f"Error fetching crypto bars: {e}")
        return pd.DataFrame()

# ========================
# 🔄 STRATEGY FUNCTIONS
# ========================
def calculate_indicators(df):
    df['sma_short'] = df['close'].rolling(SMA_SHORT).mean()
    df['sma_long'] = df['close'].rolling(SMA_LONG).mean()
    df['rsi'] = RSIIndicator(df['close'], RSI_PERIOD).rsi()
    df['atr'] = AverageTrueRange(df['high'], df['low'], df['close'], ATR_PERIOD).average_true_range()
    return df.dropna()

def generate_signal(df):
    last = df.iloc[-1]
    if last['sma_short'] > last['sma_long'] and last['rsi'] > 50:
        return 'BUY'
    elif last['sma_short'] < last['sma_long'] and last['rsi'] < 50:
        return 'SELL'
    else:
        return 'HOLD'

# ========================
# 💵 RISK & TRADE EXECUTION
# ========================
def calculate_position_size(equity, price, atr):
    risk_amount = equity * RISK_PER_TRADE
    position_size = risk_amount / (1.5 * atr)
    notional_value = position_size * price
    return round(notional_value, 2)

def execute_trade(signal, symbol, current_price, atr):
    global in_position, entry_price, highest_price

    if signal == 'BUY' and not in_position:
        equity = float(trading_client.get_account().equity)
        notional = calculate_position_size(equity, current_price, atr)
        if REAL_TRADING:
            order = MarketOrderRequest(
                symbol=symbol,
                notional=notional,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.GTC
            )
            trading_client.submit_order(order)
        in_position = True
        entry_price = current_price
        highest_price = current_price
        print(f"✅ BUY Order placed at ${current_price:.2f} for ${notional}")

    elif in_position:
        highest_price = max(highest_price, current_price)
        take_profit_price = entry_price * (1 + TAKE_PROFIT_PCT)
        stop_loss_price = highest_price * (1 - TRAIL_STOP_PCT)

        if current_price >= take_profit_price:
            close_position(symbol)
            print(f"🎯 TAKE PROFIT hit at ${current_price:.2f}")

        elif current_price <= stop_loss_price:
            close_position(symbol)
            print(f"🔻 TRAILING STOP LOSS hit at ${current_price:.2f}")


def close_position(symbol):
    global in_position, entry_price, highest_price
    try:
        position = trading_client.get_open_position(symbol)
        qty = position.qty
        order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC
        )
        if REAL_TRADING:
            trading_client.submit_order(order)
        print(f"✅ Position closed for {qty} units")
    except Exception as e:
        print("⚠️ No open position to close or error occurred.", str(e))
    in_position = False
    entry_price = 0
    highest_price = 0

# ========================
# ⏰ LIVE LOOP
# ========================
def live_loop():
    while True:
        clear_output(wait=True)
        print(f"⏳ Checking at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

        data = get_crypto_data(SYMBOL, limit=100)
        if data.empty or len(data) < SMA_LONG:
            print("⚠️ Not enough data. Skipping...")
            time.sleep(60 * BAR_INTERVAL)
            continue

        data = calculate_indicators(data)
        signal = generate_signal(data)
        current_price = data.iloc[-1]['close']
        atr = data.iloc[-1]['atr']

        print(f"📡 Signal: {signal}")
        print(f"Current Price: ${current_price:.2f}")

        execute_trade(signal, SYMBOL, current_price, atr)

        time.sleep(60 * BAR_INTERVAL)

# Uncomment below to start live trading
live_loop()
