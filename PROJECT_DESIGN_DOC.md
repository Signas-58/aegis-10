# Deriv Multipliers Scalping Bot - Design & Technical Plan (Aegis-10)

Last updated: 2026-08-22

## 1. Executive Overview & Project Goals
This document defines the complete technical, architectural, and operational specifications for an automated algorithmic trading bot designed to scalp synthetic indices via the Deriv WebSocket API.

The primary objective is to execute high-probability, short-duration trend-following trades using Deriv Multiplier contracts, optimized specifically for small account balances ($20.00 initial capital).

### Core Goals
- **Capital Protection First**: Enforce hard circuit breakers, native server-side stop-losses, and strict daily loss caps to protect small account equity.
- **Low Latency Execution**: Utilize direct WebSocket connections for real-time market data streaming and instant market order placement.
- **Dynamic Trailing Profit Capture**: Implement an uncapped trailing stop ratchet engine that locks in gains and lets winners run.

---

## 2. Technical Architecture & Module Design

The project follows a consolidated Python architecture using `asyncio` and `websockets` for maximum responsiveness and ease of maintenance.

### Directory Structure
```text
aegis-10/
├── .env                  # local API configuration (DERIV_APP_ID, DERIV_API_TOKEN, etc.)
├── .env.example          # git template
├── .gitignore            # local ignores
├── config.py             # System parameters & risk thresholds
├── main.py               # Orchestrator, connection handlers, and trade state recovery
├── engine.py             # Technical indicators & trailing stop ratchet logic
├── active_trade.json     # State tracking file for active orders (crash recovery)
├── trading_log.csv       # Audit log of executed trades
├── PROJECT_DESIGN_DOC.md # Complete project architectural documentation
└── DERIV_API_DOCS.md     # Deriv API WebSocket reference & schema documentation
```

### Dependency Stack (`requirements.txt`)
- `websockets>=12.0` (Asynchronous WebSocket client)
- `pandas>=2.0.0` (DataFrame candle handling)
- `pandas-ta>=0.3.14b` (Technical indicator calculation)
- `python-dotenv>=1.0.0` (Environment config management)

---

## 3. Trading Strategy & Indicator Specifications

### Market Parameters
- **Target Instrument**: Volatility 10 Index (`R_10`).
- **Contract Type**: Multipliers (`MULTUP` / `MULTDOWN`).
- **Timeframe**: 30-Second candles (granularity: 30).
- **Multiplier Factor**: $400\times$.

### Cold-Start Indicator Backfill
On application startup, the bot requests 50 historical 30-second candles via the Deriv API to initialize indicator history.

### Indicator Definitions
- **Exponential Moving Average (EMA-20)**: Period: 20, calculated on candle close.
- **Relative Strength Index (RSI-14)**: Period: 14, calculated on candle close.

### Trade Entry Logic
- **LONG Signal (`MULTUP`)**:
  - Close Price > EMA-20.
  - RSI(14) crosses ABOVE 50 (prev <= 50, curr > 50) at completed candle close.
- **SHORT Signal (`MULTDOWN`)**:
  - Close Price < EMA-20.
  - RSI(14) crosses BELOW 50 (prev >= 50, curr < 50) at completed candle close.

- **Scanning Mode**: Stay in scanning mode indefinitely until a valid signal occurs.

---

## 4. Dynamic Risk Management & Circuit Breakers

### Capital Allocation Controls
- **Base Stake per Trade**: $1.00 USD (minimum requirement for Multipliers on R_10).
- **Hard Stop-Loss (Native Server)**: $0.75 USD.
- **Take-Profit Ceiling**: Uncapped (None).

### Dynamic Trailing Stop-Loss Floor Ratchet Engine
The risk manager monitors active trade profit/loss (PnL) in real time and adjusts trade safety thresholds dynamically:

| Trade Stage | Unrealized PnL Condition | Action / Stop-Loss Floor | Resulting Risk State |
| :--- | :--- | :--- | :--- |
| **Stage 0 (Entry)** | PnL < +$0.50 | Native Server Stop-Loss at -$0.75 | Max risk = -$0.75 |
| **Stage 1 (Break-Even)** | PnL $\ge$ +$0.50 | Shift Stop-Loss Floor to $0.00 | Risk-Free Trade |
| **Stage 2 (Dynamic Trail)**| PnL $\ge$ +$1.00 | Floor trails exactly $0.50 behind peak PnL | Profits allowed to run |

### System Circuit Breakers
- **Daily Drawdown Cap**: Halt bot execution immediately if total cumulative daily loss reaches `$3.00 USD`.
- **Consecutive Loss Stop**: Halt bot execution immediately if consecutive losses reach `4`.
- **8-Hour Session Timer (`MAX_RUNTIME_MINUTES = 480`)**:
  - The bot runs for a maximum of 8 hours per session.
  - **Graceful Shutdown**: If the timer expires while a trade is active, the bot stops analyzing new signals but remains connected to manage and safely exit the open trade via the Trailing SL engine.
- **Cooldown Interval**: Wait exactly 30 seconds (1 candle period) after a trade closes before scanning for new entries.
