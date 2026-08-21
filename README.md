# Deriv Multipliers Scalping Bot (Aegis-10)

<p align="center">
  <img src="logo.jpg" alt="Deriv Multipliers Scalping Bot Logo" width="250" />
</p>

---

## Project Overview

**Aegis-10** is an automated algorithmic trading bot designed to scalp low-volatility synthetic indices (`R_10`) via the official Deriv WebSocket API. 

The bot targets micro-profits (targeting $\ge$ \$0.50 per trade) using Multiplier contracts, optimized specifically for small account balances (\$20.00 initial capital) using strict, dynamic risk management rules.

---

## Core Specifications & Features

- **Trading Strategy**: 1-Minute timeframe (M1) using 20-period EMA for trend filtering and 14-period RSI for momentum entry.
- **Capital Protection**: Initial hard stop-loss of -\$2.00, shifting stop-loss (break-even engine), daily loss limit of -\$2.00, and a 3-consecutive-loss circuit breaker.
- **Connection Reliability**: 15-second heartbeat pinging, asynchronous request mapping via `req_id`, and robust crash recovery using local state persistence (`active_trade.json`).
- **Session Limits**: A 10-minute maximum runtime (`MAX_RUNTIME_MINUTES = 10`) with graceful shutdown to manage existing positions.

---

## Repository Documentation

- 📘 **[Project Design & Technical Plan](file:///c:/Workspace/aegis-10/PROJECT_DESIGN_DOC.md)**: Detailed specifications, system architecture, strategy logic, and risk controls.
- 🔌 **[Deriv WebSocket API Protocol Reference](file:///c:/Workspace/aegis-10/DERIV_API_DOCS.md)**: JSON payloads, request/response tracking schemas, and endpoints.
- 🗺️ **[Implementation & Testing Roadmap](file:///c:/Workspace/aegis-10/ROADMAP.md)**: Milestone deliverables from foundation layout to paper testing and live execution.
- 🖼️ **[Logo Asset](file:///c:/Workspace/aegis-10/logo.jpg)**: Project logo and thumbnail resource.
