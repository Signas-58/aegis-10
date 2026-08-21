# Implementation & Testing Roadmap

This document outlines the milestones and roadmap phases for building, testing, and optimizing the **Deriv Multipliers Scalping Bot**.

---

## Roadmap Phases

### Phase 1: Foundation
- **Target Timeline**: August 2026
- **Deliverables & Benchmarks**:
  - Set up modular file structure.
  - Implement system configuration (`config.py`).
  - Create WebSocket connection test script with 15-second heartbeat ping and 10-minute session auto-shutdown timer.

### Phase 2: Indicators & Signals
- **Target Timeline**: August 2026
- **Deliverables & Benchmarks**:
  - Implement historical candle backfill fetching (50 bars).
  - Subscribe to and aggregate live stream candle data.
  - Build the indicators engine to calculate dynamic 20-period EMA and 14-period RSI values on the event stream.

### Phase 3: Execution & Risk
- **Target Timeline**: September 2026
- **Deliverables & Benchmarks**:
  - Integrate multiplier contract proposals and order execution.
  - Build state persistence mechanism using `active_trade.json`.
  - Design and implement the shifting Stop-Loss / Break-Even trailing management engine.

### Phase 4: Demo Paper Testing
- **Target Timeline**: September–October 2026
- **Deliverables & Benchmarks**:
  - Run the bot on the Deriv Demo account under real-time market conditions.
  - Validate the 10-minute session execution limit, logging system, and connection stability/recovery.

### Phase 5: Optimization
- **Target Timeline**: October 2026
- **Deliverables & Benchmarks**:
  - Analyze trade output logs (`trading_log.csv`).
  - Tune RSI boundaries and entry constraints to maintain a >60% win rate.

### Phase 6: Micro Deployment
- **Target Timeline**: November / December 2026
- **Deliverables & Benchmarks**:
  - (Optional) Micro-deployment to a real account with minimal balance ($20.00 to $50.00) using tiny $0.35 stakes.
