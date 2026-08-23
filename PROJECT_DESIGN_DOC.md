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

### 5-Layer Confluence Engine (`strat.py`)

A signal must sequentially pass all five logic layers to trigger entry:

1. **Layer 1: 15m Trend Gate**:
   - Calculates EMA-200 on 15m candles.
   - Bullish: 15m Close > 15m EMA-200 (Allows `MULTUP` entries only).
   - Bearish: 15m Close < 15m EMA-200 (Allows `MULTDOWN` entries only).
2. **Layer 2: 5m ADX Volatility Filter**:
   - Calculates 14-period ADX on 5m candles.
   - Halt Rule: Blocks signal if `ADX < 18` to catch early trend momentum.
3. **Layer 3: 15m Key Level Mapping & Proximity Guard**:
   - Maps `HTF_RESISTANCE` (highest high of last 20 15m candles) and `HTF_SUPPORT` (lowest low of last 20 15m candles).
   - Proximity Rule:
     - Block LONG if `HTF_RESISTANCE - Current_Price < 0.25 USD`.
     - Block SHORT if `Current_Price - HTF_SUPPORT < 0.25 USD`.
4. **Layer 4: 5m Liquidity Sweep Detection**:
   - *Bullish Sweep*: 5m candle wick dips below `HTF_SUPPORT` but body closes above it (Sell-side liquidity grab). Sets 5m bias to bullish.
   - *Bearish Sweep*: 5m candle wick spikes above `HTF_RESISTANCE` but body closes below it (Buy-side liquidity grab). Sets 5m bias to bearish.
5. **Layer 5: Trigger Confluence**:
   - Evaluated at the start of a new 1-minute candle:
     - `MULTUP` (Long): `(1m Close > 1m EMA-20 AND 1m RSI-14 > 50) OR (5m Bullish Liquidity Sweep active)`.
     - `MULTDOWN` (Short): `(1m Close < 1m EMA-20 AND 1m RSI-14 < 50) OR (5m Bearish Liquidity Sweep active)`.

---

## 4. Dynamic Risk Management & Circuit Breakers

### Capital Allocation Controls
- **Base Stake per Trade**: `$1.00 USD` (Deriv Multipliers minimum requirement).
- **Hard Stop-Loss (Native Server)**: `$0.75 USD` (native parameters sent in proposal payload).
- **Take-Profit Ceiling**: Uncapped (None).

### Trailing Stop-Loss Floor Ratchet Engine
- **Stage 0 (Entry)**: Native server Stop-Loss at -$0.75.
- **Stage 1 (Break-Even)**: Shift floor to `$0.00` once peak PnL reaches `+$0.50`.
- **Stage 2 (Dynamic Trail)**: Floor trails exactly `-$0.50` behind peak PnL once peak PnL reaches `+$1.00`.
- **Execution**: Issue immediate market close command if PnL drops to or below the current stop-loss floor.

### System Circuit Breakers
- **Daily Drawdown Cap**: Terminate program if total cumulative daily loss reaches `$3.00 USD`.
- **Consecutive Loss Stop**: Terminate program if consecutive losses reach `4`.
- **Post-Trade Reset & Quarantine**:
  - *Win Cooldown*: Standard 30-second pause after winning trade.
  - *Loss Quarantine*: Enforce a **3-minute loss quarantine** (`180s`) after any losing trade to allow adverse market structures to clear.

- **8-Hour Session Timer (`MAX_RUNTIME_MINUTES = 480`)**:
  - The bot automatically shuts down after 8 hours of session runtime. If a trade is open, it halts new signal scanning and waits to close the position cleanly before exiting.
