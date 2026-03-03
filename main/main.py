import time
import pandas as pd
from datetime import datetime
from alpaca_trade_api.rest import REST, TimeFrame, TimeFrameUnit
from datetime import datetime, timedelta, timezone
# ==========================
# CONFIG
# version 2 config with ml modeling that predicts the path of the price, therefore. We are able to accuratly get the x


# ==========================






API_KEY = "PKK4PBNTPFR6D424HJIY7ASMBO"
API_SECRET = "6xuRBXP1DuU6xf3oqXgMxHUk681cnX6eH6EugPyrF1qz"
BASE_URL = "https://paper-api.alpaca.markets"

SYMBOLS = ["TSLA", "NVDA", "GME"]

# Percentage risk per trade
RISK_PER_TRADE = 0.03  # 7%
# Stop % per strategy
TRAILING_STOP_MA = 0.09
STOP_RSI = 0.03
STOP_BREAKOUT = 0.07
MAX_DEFENSIVE_EXPOSURE = 0.25  # for dual MA
STOP_PULLBACK = 0.07
PULLBACK_RSI_LOW = 35
PULLBACK_RSI_HIGH = 45
RSI_EXIT_OVERBOUGHT = 65

# ==========================
# ALPACA CONNECTION
# ==========================
api = REST(API_KEY, API_SECRET, BASE_URL)

#convert to alpaca timeframe
def to_rfc3339(dt: datetime) -> str:
    # Ensure UTC + RFC3339 format
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")
# ==========================
# DATA FETCHING
# ==========================

def get_daily_data(symbol, days=700):
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

        bars = api.get_bars(
            symbol,
            TimeFrame.Day,
            start=to_rfc3339(start),
            end=to_rfc3339(end),
            feed="iex"
        ).df

        if bars is None or bars.empty:
            print(f"{symbol}: fetched 0 daily candles (raw)")
            return pd.DataFrame()

        if "symbol" in bars.columns:
            bars = bars[bars["symbol"] == symbol]

        bars["MA50D"]  = bars["close"].rolling(50,  min_periods=50).mean()
        bars["MA200D"] = bars["close"].rolling(200, min_periods=200).mean()
        bars["RSI14D"] = compute_rsi(bars["close"], 14)
        bars["VOL20D"] = bars["volume"].rolling(20, min_periods=20).mean()


        # Keep only rows where everything needed exists
        bars = bars.dropna(subset=["MA50D", "MA200D", "RSI14D", "VOL20D"])

        print(f"{symbol}: daily raw={len(bars)} (post-indicators)")
        return bars

    except Exception as e:
        print(f"Daily data error for {symbol}: {e}")
        return pd.DataFrame()

def get_intraday_data(symbol, limit=300):
    try:
        bars = api.get_bars(
            symbol,
            TimeFrame(5, TimeFrameUnit.Minute),
            limit=limit,
            feed="iex"
        ).df

        if bars.empty:
            print(f"{symbol}: fetched 0 intraday candles")
            return pd.DataFrame()

        if "symbol" in bars.columns:
            bars = bars[bars["symbol"] == symbol]

        bars["MA20"] = bars["close"].rolling(20).mean()
        bars["MA50"] = bars["close"].rolling(50).mean()
        bars["RSI"] = compute_rsi(bars["close"], 14)
        bars["VOL20"] = bars["volume"].rolling(20).mean()
        bars["HIGH20"] = bars["high"].rolling(20).max()
        bars["LOW10"] = bars["low"].rolling(10).min()

        bars = bars.dropna()

        print(f"{symbol}: fetched {len(bars)} intraday candles")
        return bars

    except Exception as e:
        print(f"Intraday data error for {symbol}: {e}")
        return pd.DataFrame()

# ==========================
# RSI CALCULATION
# ==========================
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ==========================
# ACCOUNT & POSITION UTILITIES
# ==========================
def equity():
    return float(api.get_account().equity)

def risk_position(entry, stop_pct, risk_pct):
    stop_price = entry * (1 - stop_pct)
    risk_dollars = equity() * risk_pct
    risk_per_share = abs(entry - stop_price)
    if risk_per_share == 0:
        return 0
    return int(risk_dollars // risk_per_share)

def has_position(symbol):
    positions = api.list_positions()
    for p in positions:
        if p.symbol == symbol:
            return int(p.qty)
    return 0

# ==========================
# STRATEGIES
# ==========================
def ma_trend_strategy(df):
    if len(df) < 2:
        return "HOLD"

    t, y = df.iloc[-1], df.iloc[-2]

    if y.MA20 <= y.MA50 and t.MA20 > t.MA50:
        return "BUY"

    if y.MA20 >= y.MA50 and t.MA20 < t.MA50:
        return "SELL"

    return "HOLD"

def dual_ma_cash_filter_from_daily(daily_df):
    if len(daily_df) < 1:
        return "HOLD"
    t = daily_df.iloc[-1]
    if t.close > t.MA200D and t.MA50D > t.MA200D:
        return "BUY"
    if t.close < t.MA200D or t.MA50D < t.MA200D:
        return "SELL"
    return "HOLD"

def rsi_strategy(df):
    t = df.iloc[-1]
    if t.RSI < 30:
        return "BUY"
    if t.RSI > 55:
        return "SELL"
    return "HOLD"

def breakout_strategy(df):
    if len(df) < 2:
        return "HOLD"
    today, prev = df.iloc[-1], df.iloc[-2]
    if today.close > prev.HIGH20 and today.volume > today.VOL20:
        return "BUY"
    if today.close < today.LOW10:
        return "SELL"
    return "HOLD"

def market_regime(daily_df):
    """
    "RISK_ON" or "RISK_OFF"
    """
    if len(daily_df) < 210:
        return "RISK_OFF"

    today = daily_df.iloc[-1]
    ma200_now = today.MA200D
    ma200_prev = daily_df.iloc[-6].MA200D  # ~1 week ago

    risk_on = (
        today.close > today.MA200D and
        today.MA50D > today.MA200D and
        ma200_now > ma200_prev
    )

    return "RISK_ON" if risk_on else "RISK_OFF"

def pullback_in_trend_signal(daily_df):
    """
    Returns: "BUY", "SELL", "HOLD"
    Based on your design spec, daily timeframe.
    """
    if len(daily_df) < 2:
        return "HOLD"

    today = daily_df.iloc[-1]

    trend_ok = (
        today.close > today.MA200D and
        today.MA50D > today.MA200D and
        today.close >= today.MA50D
    )

    pullback_ok = (PULLBACK_RSI_LOW <= today.RSI14D <= PULLBACK_RSI_HIGH)

    volume_ok = (today.volume >= today.VOL20D)  # simple confirmation; you can relax this

    if trend_ok and pullback_ok and volume_ok:
        return "BUY"

    # Exits:
    if today.close < today.MA50D:
        return "SELL"
    if today.RSI14D > RSI_EXIT_OVERBOUGHT:
        return "SELL"

    return "HOLD"

def execute_defensive_notional(symbol, signal, max_exposure_pct, tag):
    position = has_position(symbol)

    try:
        price = api.get_latest_trade(symbol).price
    except Exception:
        hist = api.get_bars(symbol, TimeFrame(1, TimeFrameUnit.Minute), limit=1, feed="iex").df
        if hist.empty:
            print(f"{datetime.now()} | {tag} | {symbol}: No fallback price")
            return
        price = hist.iloc[-1].close

    if signal == "BUY" and position == 0:
        dollars = equity() * max_exposure_pct
        qty = int(dollars // price)
        if qty > 0:
            api.submit_order(symbol=symbol, qty=qty, side="buy", type="market", time_in_force="day")
            print(f"{datetime.now()} | {tag} | {symbol}: BUY {qty} @ {price:.2f} (notional)")
        else:
            print(f"{datetime.now()} | {tag} | {symbol}: BUY signal but qty=0")
    elif signal == "SELL" and position > 0:
        api.close_position(symbol)
        print(f"{datetime.now()} | {tag} | {symbol}: SELL @ {price:.2f}")
    else:
        print(f"{datetime.now()} | {tag} | {symbol}: HOLD")


# ==========================
# EXECUTION
# ==========================
def execute(symbol, signal, stop_pct, risk_pct, tag):
    position = has_position(symbol)

    # --- price fetch with fallback ---
    try:
        price = api.get_latest_trade(symbol).price
    except Exception:
        hist = api.get_bars(symbol, TimeFrame(1, TimeFrameUnit.Minute), limit=1, feed="iex").df
        if hist.empty:
            print(f"{datetime.now()} | {tag} | {symbol}: No fallback price")
            return
        price = hist.iloc[-1].close

    # --- execution logic ---
    if signal == "BUY" and position == 0:
        if tag == "TEST_BUY":
            qty = 1
        else:
            qty = risk_position(price, stop_pct, risk_pct)
        if qty > 0:
            api.submit_order(
                symbol=symbol,
                qty=qty,
                side="buy",
                type="market",
                time_in_force="day"
            )
            print(f"{datetime.now()} | {tag} | {symbol}: BUY {qty} @ {price:.2f}")
        else:
            print(f"{datetime.now()} | {tag} | {symbol}: BUY signal but qty=0")
    elif signal == "SELL" and position > 0:
        api.close_position(symbol)
        print(f"{datetime.now()} | {tag} | {symbol}: SELL @ {price:.2f}")
    else:
        print(f"{datetime.now()} | {tag} | {symbol}: HOLD")

# ==========================
# MAIN FUNCTION
# ==========================
def main():
    for symbol in SYMBOLS:
        daily = get_daily_data(symbol, days=700)
        if daily.empty:
            print(f"{symbol}: No daily data")
            continue

        regime = market_regime(daily)

        # Always allow Pullback-in-Trend (medium risk / consistent) but you can also gate it
        pull_sig = pullback_in_trend_signal(daily)
        if pull_sig != "HOLD":
            execute(symbol, pull_sig, STOP_PULLBACK, RISK_PER_TRADE, f"PULLBACK_{regime}")
            continue

        if regime == "RISK_OFF":
            # Defensive only
            # (Fix your DUAL_MA sizing separately — right now it can’t buy with stop_pct=0.0)
            dual_sig = dual_ma_cash_filter_from_daily(daily)  # you should update this to use MA50D/MA200D
            if dual_sig != "HOLD":
                execute_defensive_notional(symbol, dual_sig, MAX_DEFENSIVE_EXPOSURE, "DUAL_MA_DEFENSIVE")
            else:
                print(f"{datetime.now()} | DEFENSIVE | {symbol}: HOLD")
            continue

        # RISK_ON: allow your higher-risk signals
        intraday = get_intraday_data(symbol)  # your 5-min
        if intraday.empty:
            print(f"{symbol}: No intraday data")
            continue

        sig = ma_trend_strategy(intraday)
        if sig != "HOLD":
            execute(symbol, sig, TRAILING_STOP_MA, RISK_PER_TRADE, "MA_TREND_5M")
            continue

        sig = breakout_strategy(intraday)
        if sig != "HOLD":
            execute(symbol, sig, STOP_BREAKOUT, RISK_PER_TRADE, "BREAKOUT_5M")
            continue

        sig = rsi_strategy(intraday)
        if sig != "HOLD":
            execute(symbol, sig, STOP_RSI, RISK_PER_TRADE, "RSI_5M")
            continue

        print(f"{datetime.now()} | RISK_ON | {symbol}: HOLD")

# ==========================
# RUN BOT EVERY 5 MIN DURING MARKET HOURS
# ==========================
print("🚀 BOT LIVE — streaming stocks & paper trading now")

while True:
    now = datetime.now()
    if now.weekday() < 5 and (now.hour > 9 or (now.hour == 9 and now.minute >= 30)) and now.hour < 16:  # Mon-Fri, 9:30-16
        print(f"\nRunning bot cycle at {now}")
        try:
            main()
        except Exception as e:
            print("ERROR:", e)
        time.sleep(300)  # Optimal Intervals
    else:
        print("Market closed — sleeping 10 minutes")
        time.sleep(600)