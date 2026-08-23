# Deriv Multipliers Scalping Bot - Design & Technical Plan (Aegis-10)

Last updated: 2026-08-23

## 1. Executive Overview & Project Goals
This document defines the complete technical, architectural, and operational specifications for the refactored **Aegis-10** automated algorithmic trading bot. The bot executes a disciplined trend-following strategy on the Volatility 25 Index (`R_25`) utilizing Multi-Timeframe (MTF) analysis and Smart Money Concepts.

The primary objective is to capture high-probability trade setups using a 5-layer analysis filter, server-side protection limits, an uncapped dynamic trailing profit ratchet engine, and strict safety circuit breakers.

### Core Upgrades (v0.9.5-beta to v0.9.8-mtf)
- **Multi-Timeframe Structure**: Analyzes the market across 15m (Macro), 5m (Structure), and 1m (Trigger) horizons.
- **Smart Money Concepts**: Maps key support/resistance levels and detects wicking liquidity sweeps.
- **Volatility Filtering**: Restricts execution to trend phases via 5m ADX thresholds.
- **Risk Quarantine**: Implements a 10-minute loss quarantine cooldown to prevent over-trading in bad market states.

---

## 2. Technical Architecture & Module Design

The codebase uses a consolidated asynchronous architecture:

```text
aegis-10/
├── config.py             # System parameters & risk thresholds
├── main.py               # Asynchronous WebSocket orchestrator & order execution
├── strat.py              # Technical indicators & multi-timeframe signal filters
├── engine.py             # Trailing stop ratchet calculator
├── websocket_client.py   # Verified OTP connection client
├── active_trade.json     # Dynamic crash recovery state persistence
└── trading_log.csv       # Completed trade logs
```

- **Removed Files**: Outdated modular files (`data_processor.py`, `strategy.py`, `risk_manager.py`, `execution.py`, `state_manager.py`) are deleted.

---

## 3. Trading Strategy & Indicator Specifications

### Multi-Timeframe Buffers
The bot maintains three historical candle buffers for `R_25`:
1. **Macro Buffer (15m)**: minimum 200 candles for EMA-200 and swing level mapping.
2. **Structure Buffer (5m)**: minimum 50 candles for ADX-14 calculation and sweep detection.
3. **Trigger Buffer (1m)**: minimum 50 candles for precision EMA-20 / RSI-14 entry signals.

### Smart Scanning & regime Classification (`intelligence.py`)
To prevent over-trading in sideways chop or extreme chaotic volatility, the bot calculates 14-period ATR ratio and ADX slope on 5m candles to classify the market state:
- **`REGIME_HIGH_RISK`**: ATR ratio > 1.8 (Extreme volatility spikes). *Rule*: Pauses execution instantly, returning `NO_SIGNAL`.
- **`REGIME_TRENDING`**: 5m ADX >= 20 and ADX slope > 0. (Ideal conditions).
- **`REGIME_CONSOLIDATING`**: 5m ADX < 20 and ATR ratio <= 1.0. (Sideways market).
- **`REGIME_NORMAL`**: Default fallback state.

### 100-Point Confluence Scoring Matrix
A trade setup is evaluated across 4 weighted vectors to calculate a dynamic probability score (0 to 100%):
1. **Vector 1: Macro Trend Alignment (25 Points)**: Price aligns with the 15m EMA-200.
2. **Vector 2: Volatility & Regime Quality (25 Points)**: Setup occurs in `REGIME_TRENDING` (25 pts), or in `REGIME_CONSOLIDATING` with ADX >= 18 (15 pts).
3. **Vector 3: Liquidity & Key Level Setup (25 Points)**: Active 5m liquidity sweep detected (25 pts), or distance to HTF key level >= 1.00 USD (15 pts).
4. **Vector 4: Trigger Momentum Precision (25 Points)**: 1m trigger candle crossover meets indicators (EMA-20 and RSI-14 vs 50).

*Execution Rule*: A trade executes only if `total_score >= 75` and the 1m trigger crossover is **MANDATORY** (`Trigger == True`).


---

## 4. Dynamic Risk Management & Circuit Breakers

### Capital Allocation Controls
- **Base Stake per Trade**: `$1.00 USD` (Deriv Multipliers minimum requirement).
- **Hard Stop-Loss (Native Server)**: `$0.75 USD` (native parameters sent in proposal payload).
- **Take-Profit Ceiling**: Uncapped (None).

### Trailing Stop-Loss Floor Ratchet Engine
- **Stage 0 (Entry)**: Native server Stop-Loss at -$0.75.
- **Stage 1 (Step-Ladder Phase)**:
  - Shift floor to `$0.00` once peak PnL reaches `+$0.50` (Break-Even).
  - Shift floor to `+$0.25` once peak PnL reaches `+$0.75` (Locks in $0.25 profit).
- **Stage 2 (Continuous Trailing Phase)**:
  - Once peak PnL reaches `+$1.00` or above, the stop-loss floor trails exactly `-$0.50` behind peak PnL (e.g. `peak_pnl - 0.50` on a continuous cent-by-cent basis).
- **Execution & Server SL Isolation**: If `current_sl_floor < 0.00` (initial Stage 0 setup), the bot does NOT send manual WebSocket sell commands, allowing Deriv's native server-side SL to trigger. Manual Python WebSocket sell commands are strictly isolated to Stage 1 and Stage 2 (`current_sl_floor >= 0.00`). If a sell request returns `"The contract has expired"` or the POC response flags `is_expired`/`is_sold`, the bot immediately concludes the trade cleanly.
- **Server-Side Sync Safeguard**: To prevent losses due to connection dropout or bot latency, the bot syncs the updated stop-loss limits to the Deriv servers in real time using the `contract_update` API. For profit-locking levels (where positive stops are rejected by the API), the server stop-loss is set to `$0.10` (the minimum limit supported by the Deriv API) to guarantee near-break-even protection.

### System Circuit Breakers
- **Daily Drawdown Cap**: Terminate program if total cumulative daily loss reaches `$3.00 USD`.
- **Consecutive Loss Stop**: Terminate program if consecutive losses reach `4`.
- **Post-Trade Reset & Quarantine**:
  - *Win Cooldown*: Standard 30-second pause after winning trade.
  - *Loss Quarantine*: Enforce a **10-minute loss quarantine** (`600s`) after any losing trade to allow adverse market structures to clear.


- **8-Hour Session Timer (`MAX_RUNTIME_MINUTES = 480`)**:
  - The bot automatically shuts down after 8 hours of session runtime. If a trade is open, it halts new signal scanning and waits to close the position cleanly before exiting.
