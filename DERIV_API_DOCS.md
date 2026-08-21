# Deriv WebSocket API Protocol - Reference Specifications

## 1. Connection & Ping Rules
- **Endpoint Base URL**: `wss://ws.derivws.com/websockets/v3?app_id=1089` (or dynamic configuration)
- **Heartbeat Ping Request (Every 15 Seconds)**:
  ```json
  {
    "ping": 1,
    "req_id": 1
  }
  ```

---

## 2. Market Data Subscription (1-Minute Candles)
- Fetch history and subscribe to live 1-minute candle updates:
  ```json
  {
    "ticks_history": "R_10",
    "adjust_start_time": 1,
    "count": 50,
    "end": "latest",
    "style": "candles",
    "granularity": 60,
    "subscribe": 1,
    "req_id": 2
  }
  ```

---

## 3. Order Execution (Multipliers)
- **Proposal Request for Multiplier**:
  ```json
  {
    "proposal": 1,
    "amount": 0.50,
    "basis": "stake",
    "contract_type": "MULTUP",
    "currency": "USD",
    "multiplier": 100,
    "symbol": "R_10",
    "req_id": 3
  }
  ```
- **Executing Proposal Order**:
  ```json
  {
    "buy": "<PROPOSAL_ID>",
    "price": 0.50,
    "req_id": 4
  }
  ```

---

## 4. Active Position Monitoring & Closing
- **Subscribing to Open Position Updates / Track Live PnL**:
  ```json
  {
    "proposal_open_contract": 1,
    "contract_id": "<CONTRACT_ID>",
    "subscribe": 1,
    "req_id": 5
  }
  ```
- **Send Manual Close Command (When Trailing SL or Target PnL is hit)**:
  ```json
  {
    "sell": "<CONTRACT_ID>",
    "price": 0,
    "req_id": 6
  }
  ```
