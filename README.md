# Deriv Multipliers Scalping Bot (Aegis-10)

<p align="center">
  <img src="logo.jpg" alt="Deriv Multipliers Scalping Bot Logo" width="250" />
</p>

<p align="center">
  <strong>Version: 0.9.5-beta</strong><br>
  <em>Status: Pre-Production / Dev</em>
</p>

---

## Project Overview

**Aegis-10** is an automated algorithmic trading bot designed to scalp low-volatility synthetic indices (`R_25`) via the official Deriv WebSocket API. 


The bot targets trend-following trade signals using Multiplier contracts, optimized specifically for small account balances ($20.00 initial capital) using native server protection limits, an uncapped dynamic trailing profit ratchet engine, and strict daily risk controls.

---

## Core Specifications & Features

- **Trading Strategy**: 1-Minute timeframe charting (granularity: 60) using a 20-period EMA for trend filtering and a 14-period RSI for momentum crossovers at the 50 level.
- **Capital Protection**: Native server-side Stop-Loss set at `$0.75 USD` per trade.
- **Uncapped Dynamic Trailing Engine**: 
  - *Break-Even*: Shifts stop floor to `$0.00` when PnL $\ge$ `+$0.50`.
  - *Dynamic Trailing*: Stop floor trails exactly `$0.50` behind peak PnL once peak PnL $\ge$ `+$1.00`.
- **System Circuit Breakers**: Halts operations immediately if **consecutive losses $\ge$ 4** or **cumulative daily loss $\ge$ $3.00 USD**.
- **Session Limits**: An 8-hour maximum runtime (`MAX_RUNTIME_MINUTES = 480`) with graceful shutdown to manage existing positions.
- **Connection Reliability**: 15-second heartbeat pinging, dynamic REST-based OTP token generation, and robust crash recovery using local state persistence (`active_trade.json`).

---

## Workspace Directory Structure

```text
aegis-10/
├── config.py             # System parameters & risk thresholds
├── main.py               # Orchestrator, connection handlers, and trade state recovery
├── engine.py             # Technical indicators & trailing stop ratchet logic
├── websocket_client.py   # OTP WebSocket connection handshake client
├── active_trade.json     # Dynamic crash recovery state persistence
└── trading_log.csv       # Completed trade logs
```

---

## How to Launch & Use

1. **Verify your credentials in `.env`**:
   Ensure you have configured your token, account ID, and developer portal App ID:
   ```env
   DERIV_TOKEN=pat_xxx
   DERIV_APP_ID=32hxfkzWYA2IiQoReM03s
   DERIV_ACCOUNT_ID=DOT93113459
   ```
2. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```
3. **Run the application**:
   ```powershell
   python main.py
   ```
4. **Graceful Shutdown**:
   Press **`Ctrl + C`** in your terminal at any time. The bot will automatically execute a market close order on any open trade before disconnecting and exiting.

---

## Repository Documentation

- 📘 **[Project Design & Technical Plan](file:///c:/Workspace/aegis-10/PROJECT_DESIGN_DOC.md)**: Detailed specifications, system architecture, strategy logic, and risk controls.
- 🔌 **[Deriv WebSocket API Protocol Reference](file:///c:/Workspace/aegis-10/DERIV_API_DOCS.md)**: JSON payloads, request/response tracking schemas, and endpoints.
- 🗺️ **[Implementation & Testing Roadmap](file:///c:/Workspace/aegis-10/ROADMAP.md)**: Milestone deliverables from foundation layout to paper testing and live execution.
