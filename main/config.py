import time
import pandas as pd
from datetime import datetime
from alpaca_trade_api.rest import REST, TimeFrame, TimeFrameUnit
from datetime import datetime, timedelta, timezone

API_KEY = "PKK4PBNTPFR6D424HJIY7ASMBO"
API_SECRET = "6xuRBXP1DuU6xf3oqXgMxHUk681cnX6eH6EugPyrF1qz"
BASE_URL = "https://paper-api.alpaca.markets"

SYMBOLS = ["TSLA", "NVDA", "GME"]

def alpaca():
    return REST(API_KEY, API_SECRET,BASE_URL, paper_trading = True)

