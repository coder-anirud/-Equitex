# Equitex

**A Python prototype for rule-based stock paper trading with Alpaca.**

Equitex explores how moving averages, relative strength index (RSI), volume, and daily market-regime filters can be combined into an automated paper-trading loop.

## How it works

For each configured symbol, the bot fetches daily price data, computes indicators, and follows a strategy priority:

1. Check for a daily pullback within an upward trend.
2. If the daily regime is `RISK_OFF`, consider a defensive dual-moving-average signal.
3. If the regime is `RISK_ON`, evaluate a five-minute moving-average crossover, then a breakout signal, then an RSI signal.

The first actionable signal takes priority. The current symbols are `TSLA`, `NVDA`, and `GME`; configuration is at the top of [main/main.py](main/main.py).

## Setup

Use Python 3.11 or later and an Alpaca paper-trading account with market-data access.

```bash
git clone https://github.com/coder-anirud/-Equitex.git
cd ./-Equitex
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Provide your own paper-account credentials through environment variables:

```bash
export APCA_API_KEY_ID="your-paper-api-key"
export APCA_API_SECRET_KEY="your-paper-api-secret"
python main/main.py
```

The script reads these variables directly from the environment. It does not automatically load a `.env` file. Its API endpoint is fixed to Alpaca’s paper-trading service.

Running the script can submit simulated market orders and close existing paper positions for the configured symbols. Use a dedicated paper account for experiments. Press **Ctrl+C** to stop the loop.

## Implementation details

| Area | Current behavior |
| --- | --- |
| Data | Daily bars and five-minute bars requested with the IEX feed |
| Indicators | Moving averages, RSI, average volume, rolling highs and lows |
| Regime | Price relative to the daily 200-period average, 50/200-period trend, and slope of the 200-period average |
| Position sizing | Account-equity-based sizing; defensive entries use a notional exposure fraction |
| Execution | Market orders through the Alpaca paper API |
| Schedule | Five-minute cycles on weekdays, 9:30–16:00 according to the computer’s local clock |

## Repository guide

| Path | Purpose |
| --- | --- |
| [main/main.py](main/main.py) | Configuration, data fetching, indicators, signals, position sizing, and execution loop |
| [requirements.txt](requirements.txt) | Python dependencies derived from the source imports |

## Current limitations

- No backtest, benchmark comparison, or verified performance results are included.
- Parameters named for stops are used for position sizing; the implementation does not place broker-side stop-loss or trailing-stop orders.
- Position sizing does not enforce a portfolio-wide exposure cap.
- The schedule uses the computer’s local time and does not check exchange holidays, early closes, or daylight-saving differences.
- Strategies share account positions rather than maintaining separate strategy portfolios.
- The program begins its execution loop when the module is run or imported.

This is an experimental paper-trading project. Dependency compatibility and API behavior need to be verified in the target environment before use.
