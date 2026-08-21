# Deriv Multipliers Scalping Bot - Design & Technical Plan

Last updated: 2026-08-21

## 1. Executive Overview & Project Goals
This document defines the complete technical, architectural, and operational specifications for an automated algorithmic trading bot designed to scalp low-volatility synthetic indices via the Deriv WebSocket API.

The primary objective is to execute high-probability, short-duration trades targeting micro-profits ($\ge$ $0.50) using Deriv Multiplier contracts, optimized specifically for small account balances ($20.00 initial capital).

### Core Goals
- **Capital Protection First**: Enforce hard circuit breakers, dynamic break-even stop-losses, and strict daily loss caps to protect small account equity.
- **Low Latency Execution**: Utilize direct WebSocket connections for real-time market data streaming and instant market order placement.
- **Frictionless AI Implementation**: Provide a structured specification file that AI development agents (like Antigravity) can read and execute step-by-step.

---

## 2. Technical Architecture & Module Design

The project follows a modular, asynchronous Python architecture using `asyncio` and `websockets`.

### Directory Structure
```text
deriv-scalper-bot/
├── config.py             # System configuration, API keys, risk parameters
├── websocket_client.py   # Connection management, pings, request tracking
├── data_processor.py     # Candle aggregation, historical backfill, indicators
├── strategy.py           # Signal generation (EMA + RSI logic)
├── risk_manager.py       # Trailing SL engine, drawdown limits, circuit breakers
├── execution.py          # Contract proposal creation, order execution, position tracking
├── state_manager.py      # Active trade recovery (active_trade.json)
├── main.py               # Application lifecycle, 10-minute timer, event loop
├── requirements.txt      # Python dependencies
└── active_trade.json     # Dynamic local state persistence file
```

### Dependency Stack (`requirements.txt`)
- `websockets>=12.0` (Asynchronous WebSocket client)
- `pandas>=2.0.0` (DataFrame candle handling)
- `pandas-ta>=0.3.14b` (Technical indicator calculation)
- `asyncio` (Native Python async runtime)

---

## 3. Trading Strategy & Indicator Specifications

### Market Parameters
- **Target Instrument**: Volatility 10 Index (`R_10`) — Selected for smooth, predictable price action.
- **Contract Type**: Multipliers (`MULTUP` / `MULTDOWN`) — Allows micro-stakes with manual API close capabilities.
- **Timeframe**: 1-Minute (M1) candles (granularity: 60).
- **Multiplier Factor**: $100\times$.

### Cold-Start Indicator Backfill
On application startup, the bot must request 50 historical 1-minute candles via the Deriv API before listening to live signals. This prevents indicator calculation delay on boot.

### Indicator Definitions
- **Exponential Moving Average (EMA-20)**: Calculated on candle close prices over a 20-period window.
- **Relative Strength Index (RSI-14)**: Calculated on candle close prices over a 14-period window.

### Trade Entry Logic
- **LONG Signal (`MULTUP`)**:
  - Current candle Close Price > 20-EMA.
  - RSI(14) crosses ABOVE 30 from oversold territory within the last 2 candles.
  - No open position exists in `active_trade.json`.
- **SHORT Signal (`MULTDOWN`)**:
  - Current candle Close Price < 20-EMA.
  - RSI(14) crosses BELOW 70 from overbought territory within the last 2 candles.
  - No open position exists in `active_trade.json`.

---

## 4. Dynamic Risk Management & Circuit Breakers

### Capital Allocation Controls
- **Account Balance Target**: $20.00 (Demo).
- **Stake per Trade**: $0.35 to $0.50 (Max 2.5% of $20 account).
- **Max Concurrent Positions**: 1 trade.

### Shifting Stop-Loss Engine (Break-Even Logic)
The risk manager monitors active trade profit/loss (PnL) in real time and adjusts trade safety thresholds dynamically:

| Trade Stage | Unrealized PnL Condition | Action / Stop-Loss Floor | Resulting Risk State |
| :--- | :--- | :--- | :--- |
| **Stage 0 (Entry)** | PnL < +$0.50 | Initial Hard Stop-Loss set at -$2.00 | Max risk = -$2.00 |
| **Stage 1 (Break-Even)** | PnL $\ge$ +$0.50 | Move Stop-Loss to $0.00 (Entry Price) | Risk-Free Trade |
| **Stage 2 (Lock Profit)** | PnL $\ge$ +$1.00 | Shift Stop-Loss to lock in +$0.50 profit | Guaranteed +$0.50 gain |
| **Stage 3 (Trailing)** | PnL > +$1.00 | Trail Stop-Loss $0.50 behind peak PnL | Profits allowed to run |

### System Circuit Breakers
- **Daily Drawdown Cap**: If cumulative account loss reaches -$2.00 (10% of $20 balance) within 24 hours, halt all operations immediately.
- **Consecutive Loss Stop**: Pause trading for 4 hours after 3 consecutive losing trades.
- **10-Minute Safety Timer (`MAX_RUNTIME_MINUTES = 10`)**:
  - The bot runs for a maximum of 10 minutes per session.
  - **Graceful Shutdown Rule**: If the timer expires while a trade is active, the bot stops analyzing new entry signals but remains connected to manage and safely exit the open trade via the Trailing SL engine before shutting down.

---

## 5. System Reliability & API Protocol

### Heartbeat Maintenance
- Send a `{"ping": 1}` request every 15 seconds over the WebSocket to maintain an active connection.

### Asynchronous Request Mapping
- Every outgoing JSON payload must contain an auto-incrementing integer key: `"req_id": <int>`.
- Incoming responses must be matched against their corresponding `req_id` to handle asynchronous execution correctly.

### State Persistence & Crash Recovery
- Maintain a local file named `active_trade.json`.
- Upon placing a buy order, record: `contract_id`, `entry_price`, `stake`, `contract_type`, and `timestamp`.
- On startup, `state_manager.py` checks `active_trade.json`. If an unclosed trade ID exists, the bot immediately reconnects to track that contract ID instead of opening a duplicate order.

### API Ceiling & Slippage Protection
- **Poll Rate**: Query open contract status (`proposal_open_contract`) no more than once per second to respect Deriv's 360 request/minute ceiling.
- **Slippage Filter**: If bid-ask spread exceeds $1.5\times$ the rolling 100-tick average, reject entry signals.
