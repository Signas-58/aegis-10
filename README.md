# Deriv Multipliers Scalping Bot (Aegis-10)

<p align="center">
  <img src="logo.jpg" alt="Deriv Multipliers Scalping Bot Logo" width="250" />
</p>

<p align="center">
  <strong>Version: 0.9.8-mtf</strong><br>
  <em>Status: Pre-Production / Dev (Smart Money & MTF Upgrades)</em>
</p>

---

## Project Overview

**Aegis-10** is an automated algorithmic trading bot designed to scalp low-volatility synthetic indices (`R_25`) via the official Deriv WebSocket API. 

The bot executes a top-down Multi-Timeframe (15m / 5m / 1m) Smart Money & Liquidity strategy utilizing trend filters, ADX volatility safeguards, key HTF level mappings, sell-side/buy-side liquidity sweep detections, and a post-loss quarantine system.

---

## Core Specifications & Features

- **Multi-Timeframe Structure**:
  - *Macro Buffer (15m)*: Used for trend direction gates and swing high/low key level mappings.
  - *Structure Buffer (5m)*: Used for ADX trend strength filtering and liquidity sweep detection.
  - *Trigger Buffer (1m)*: Precision entry execution signals.
- **Top-Down 5-Layer Confluence Engine**:
  1. **EMA Trend Gate (15m)**: Calculates EMA-200 to enforce macro trend direction (`MULTUP` / `MULTDOWN`).
  2. **ADX Volatility Gate (5m)**: Calculated over a 14-period window. Blocks all execution if `ADX < 22` to avoid sideways market consolidation.
  3. **Proximity Guard (15m)**: Blocks entries if current spot price is within `$0.50 USD` of HTF support/resistance levels.
  4. **Liquidity Sweep Detection (5m)**: Detects sell-side/buy-side liquidity sweeps when candles wick past HTF support/resistance but close back inside the range.
  5. **Precision Entry Trigger (1m)**: Enforces entry when the price closes above/below 1m EMA-20 and 1m RSI-14 crossed the 50 level.
- **Dynamic Ratchet Trailing Engine**:
  - *Break-Even*: Shifts stop floor to `$0.00` once peak PnL reaches `+$0.50`.
  - *Dynamic Trailing*: Stop floor trails exactly `-$0.50` behind peak PnL once peak PnL reaches `+$1.00`.
- **System Circuit Breakers & Cooldowns**:
  - Standard Win Cooldown: Standard 30-second pause after winning trade.
  - **10-Minute Loss Quarantine (`600s`)**: Active immediately after any losing trade to let hostile market conditions clear.
  - Max limits: Emergency halt on 4 consecutive losses or `$3.00` daily cap.
  - Session Limit: Max 8 hours runtime countdown (`MAX_RUNTIME_MINUTES = 480`).

---

## Workspace Directory Structure

```text
aegis-10/
├── config.py             # System parameters & risk thresholds
├── main.py               # Orchestrator, connection handlers, and trade state recovery
├── strat.py              # Technical indicators & multi-timeframe signal filters
├── engine.py             # Trailing stop ratchet calculator
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
   *Windows Feature: Running python main.py automatically pops open a new Command Prompt window displaying the trade stream, exiting the background console cleanly.*
4. **Graceful Shutdown**:
   Press **`Ctrl + C`** in your visible Command Prompt window at any time. The bot will automatically execute a market close order on any open trade before disconnecting and exiting.
