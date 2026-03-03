import time
import pandas as pd
from datetime import datetime
from alpaca_trade_api.rest import REST, TimeFrame, TimeFrameUnit
from datetime import datetime, timedelta, timezone
from main.config import alpaca

api = alpaca()

def to_rfc3339(dt: datetime) -> str:
    # Ensure UTC + RFC3339 format
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")

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

        # bars["MA50D"]  = bars["close"].rolling(50,  min_periods=50).mean()
        # bars["MA200D"] = bars["close"].rolling(200, min_periods=200).mean()
        # bars["RSI14D"] = compute_rsi(bars["close"], 14)
        # bars["VOL20D"] = bars["volume"].rolling(20, min_periods=20).mean()


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

        # bars["MA20"] = bars["close"].rolling(20).mean()
        # bars["MA50"] = bars["close"].rolling(50).mean()
        # bars["RSI"] = compute_rsi(bars["close"], 14)
        # bars["VOL20"] = bars["volume"].rolling(20).mean()
        # bars["HIGH20"] = bars["high"].rolling(20).max()
        # bars["LOW10"] = bars["low"].rolling(10).min()

        bars = bars.dropna()

        print(f"{symbol}: fetched {len(bars)} intraday candles")
        return bars

    except Exception as e:
        print(f"Intraday data error for {symbol}: {e}")
        return pd.DataFrame()

