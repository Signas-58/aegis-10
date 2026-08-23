import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API & Market Connection Specs
APP_ID = os.getenv("DERIV_APP_ID", "32hxfkzWYA2IiQoReM03s")  # Verified Developer App ID
DERIV_TOKEN = os.getenv("DERIV_API_TOKEN", os.getenv("DERIV_TOKEN", ""))
DERIV_ACCOUNT_ID = os.getenv("DERIV_ACCOUNT_ID", "DOT93113459")

WS_ENDPOINT = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
OTP_REST_ENDPOINT = f"https://api.derivws.com/trading/v1/options/accounts/{DERIV_ACCOUNT_ID}/otp"

IS_DEMO = True  # Hard safety limit
SYMBOL = "R_25"  # Volatility 25 Index
CONTRACT_TYPE_UP = "MULTUP"
CONTRACT_TYPE_DOWN = "MULTDOWN"

# Multi-Timeframe Ingestion Settings
TF_MACRO = 900  # 15-Minute Candles (Macro Horizon)
TF_STRUCTURE = 300  # 5-Minute Candles (Structure & Liquidity Horizon)
TF_TRIGGER = 60  # 1-Minute Candles (Precision Trigger Horizon)

# Strategy & Filter Thresholds
EMA_MACRO_PERIOD = 200  # 15m Trend Direction Gate
ADX_MIN_THRESHOLD = 22  # Minimum 5m ADX required to trade (Blocks chop)
PROXIMITY_GUARD_USD = 0.50  # Minimum distance required from 15m Support/Resistance

# Position & Trailing Execution Specs
STAKE = 1.00  # Deriv Multipliers API minimum requirement
HARD_STOP_LOSS_USD = 0.75  # Native Deriv Server-Side Stop Loss Limit
TAKE_PROFIT_USD = None  # UNCAPPED Profit potential

BREAK_EVEN_TRIGGER = 0.50  # Shift internal SL floor to $0.00 at +$0.50 PnL
DYNAMIC_TRAIL_START = 1.00  # Enable dynamic continuous trailing at +$1.00 PnL
TRAILING_OFFSET_USD = 0.50  # SL floor trails $0.50 behind peak PnL

# Safety Cooldowns & Circuit Breakers
COOLDOWN_AFTER_WIN_SECONDS = 30  # Standard 1-candle wait after winning trade
COOLDOWN_AFTER_LOSS_SECONDS = 600  # 10-Minute Loss Quarantine (Settles bad market state)
MAX_CONSECUTIVE_LOSSES = 4  # Emergency halt after 4 consecutive losses
MAX_DAILY_LOSS_USD = 3.00  # Emergency halt on $3.00 total session loss
MAX_RUNTIME_MINUTES = 480  # 8-Hour Session Time Limit

# Connection & Execution Limits
PING_INTERVAL = 15  # Send heartbeat ping every 15 seconds
POLL_INTERVAL = 1.0  # Max 1 open contract poll per second
SLIPPAGE_THRESHOLD_MULTIPLIER = 1.5  # Reject signal if spread > 1.5x average
