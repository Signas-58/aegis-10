import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Configuration
DERIV_TOKEN = os.getenv("DERIV_TOKEN", "")
APP_ID = os.getenv("DERIV_APP_ID", "1089")  # Default app_id
WS_ENDPOINT = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"

# Account & Demo Configuration
IS_DEMO = True  # Hard safety limit

# Trading Parameters
SYMBOL = "R_10"  # Volatility 10 Index
GRANULARITY = 60  # 1-minute candles
MULTIPLIER = 100  # Multiplier factor
DEFAULT_STAKE = 0.35  # Stake per trade ($0.35 to $0.50)

# Risk Engine Constants
INITIAL_STOP_LOSS = -2.00  # Hard Stop-Loss cap
DAILY_LOSS_LIMIT = 2.00  # 10% of $20 account balance
CONSECUTIVE_LOSS_LIMIT = 3
PAUSE_DURATION_SECONDS = 4 * 60 * 60  # 4 hours in seconds

# Shifting SL Trailing Logic Parameters
STAGE_1_TRIGGER = 0.50  # Un-realized PnL to trigger break-even
STAGE_2_TRIGGER = 1.00  # Un-realized PnL to lock in profit
STAGE_2_LOCK_PROFIT = 0.50  # Profit to lock in at stage 2
TRAILING_SL_DISTANCE = 0.50  # Trail stop-loss $0.50 behind peak PnL

# Connection & Execution Limits
PING_INTERVAL = 15  # Send heartbeat ping every 15 seconds
MAX_RUNTIME_MINUTES = 10  # Maximum session runtime
POLL_INTERVAL = 1.0  # Max 1 open contract poll per second
COLD_START_CANDLES = 50  # Number of historical candles to fetch on startup
SLIPPAGE_THRESHOLD_MULTIPLIER = 1.5  # Reject signal if spread > 1.5x average
