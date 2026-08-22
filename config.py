import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Connection Settings
APP_ID = os.getenv("DERIV_APP_ID", "32hxfkzWYA2IiQoReM03s")  # Default verified App ID
# Support both token key names for convenience
DERIV_TOKEN = os.getenv("DERIV_API_TOKEN", os.getenv("DERIV_TOKEN", ""))
DERIV_ACCOUNT_ID = os.getenv("DERIV_ACCOUNT_ID", "DOT93113459")  # Active Demo ID

WS_ENDPOINT = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
OTP_REST_ENDPOINT = f"https://api.derivws.com/trading/v1/options/accounts/{DERIV_ACCOUNT_ID}/otp"

# Account & Demo Configuration
IS_DEMO = True  # Hard safety limit
SYMBOL = "R_10"  # Volatility 10 Index
CONTRACT_TYPE_UP = "MULTUP"  # Multipliers Bullish Entry
CONTRACT_TYPE_DOWN = "MULTDOWN"  # Multipliers Bearish Entry
MULTIPLIER = 400  # Default Multiplier Factor (Accepts 400, 1000, 2000, 3000, 4000)

# Session & Timeframe Mechanics
CANDLE_GRANULARITY = 60  # 1-Minute Charting (Minimum granularity supported by Options API v2)

MAX_RUNTIME_MINUTES = 480  # 8-Hour Maximum Session Limit (Auto-Shutdown)
COOLDOWN_SECONDS = 30  # 1 Candle Wait Period After Trade Close

# Per-Trade Position & Risk Parameters
STAKE = 1.00  # Stake amount ($1.00 USD minimum for Multipliers on R_10)
HARD_STOP_LOSS_USD = 0.75  # Native Deriv Server Stop Loss Limit ($0.75 Max Risk)
TAKE_PROFIT_USD = None  # UNCAPPED: No fixed TP ceiling

# Dynamic Trailing Stop-Loss Floor Ratchet Engine
BREAK_EVEN_TRIGGER = 0.50  # Move SL floor to $0.00 when PnL >= +$0.50
DYNAMIC_TRAIL_START = 1.00  # Enable continuous trailing when PnL >= +$1.00
TRAILING_OFFSET_USD = 0.50  # SL floor trails exactly $0.50 behind peak PnL

# Daily Safety Circuit Breakers
MAX_CONSECUTIVE_LOSSES = 4  # Emergency halt after 4 consecutive losses
MAX_DAILY_LOSS_USD = 3.00  # Emergency halt on $3.00 total cumulative loss ($0.75 x 4)

# Connection & Execution Limits
PING_INTERVAL = 15  # Send heartbeat ping every 15 seconds
POLL_INTERVAL = 1.0  # Max 1 open contract poll per second
COLD_START_CANDLES = 50  # Number of historical candles to fetch on startup
SLIPPAGE_THRESHOLD_MULTIPLIER = 1.5  # Reject signal if spread > 1.5x average
