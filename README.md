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
- **Smart Scanning & Regime Classifier**:
  - Calculates 14-period ATR ratio and ADX slope on 5m candles to classify market regimes: `REGIME_TRENDING`, `REGIME_CONSOLIDATING`, or `REGIME_HIGH_RISK`.
  - **High-Risk Safety Switch**: Halts scan instantly under `REGIME_HIGH_RISK` (ATR ratio > 1.8) to prevent trading during chaotic market noise.
- **100-Point Confluence Scoring Matrix**:
  - Dynamically evaluates setups across 4 weighted vectors: Macro Trend (25 pts), Volatility/Regime Quality (25 pts), Liquidity sweeps/key levels (25 pts), and Precision Trigger momentum (25 pts).
  - Trade executes only if `total_score >= 75` and the 1m trigger crossover is `True` (Mandatory).


- **Dynamic Ratchet Trailing Engine**:
  - *Phase 1 (Stepped Floor under $1.00)*:
    - Shifts stop floor to `$0.00` (Break-Even) once peak PnL reaches `+$0.50`.
    - Shifts stop floor to `+$0.25` (Locks in profit) once peak PnL reaches `+$0.75`.
  - *Phase 2 (Continuous Trail above $1.00)*:
    - Once peak PnL reaches `+$1.00`, stop floor trails continuously cent-by-cent exactly `-$0.50` behind peak PnL (`peak_pnl - 0.50`).
  - *Server-Side Sync Safeguard*: Updates are transmitted in real time to the Deriv server using `contract_update`. If in profit (where positive stops are invalid on the server), it clamps at `$0.10` risk (the minimum limit supported by the Deriv API) to guarantee near-break-even protection in case of bot dropouts.


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
