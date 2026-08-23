# Deriv API Protocol Reference Specifications (Aegis-10)

Last updated: 2026-08-23

## 1. OTP REST Handshake Sequence
For unified options trading accounts (`DOT` or `ROT` prefix), WebSocket authentication requires obtaining a single-use OTP.
- **REST Endpoint**: `POST https://api.derivws.com/trading/v1/options/accounts/{accountId}/otp`
- **Headers**:
  ```http
  Authorization: Bearer <DERIV_API_TOKEN>
  Deriv-App-ID: 32hxfkzWYA2IiQoReM03s
  Content-Type: application/json
  ```
- **Body**: `{}`
- **Response**:
  ```json
  {
    "status": 200,
    "data": {
      "url": "wss://api.derivws.com/trading/v1/options/ws/demo?otp=<SHORT_LIVED_TOKEN>"
    }
  }
  ```

---

## 2. WebSocket Connection & Heartbeat Pings
- **Heartbeat Ping Request (Every 15 Seconds)**:
  ```json
  {
    "ping": 1,
    "req_id": 1
  }
  ```

---

## 3. Multi-Timeframe Candle Subscriptions
To support multi-timeframe analysis, Aegis-10 issues three separate `ticks_history` subscription requests:

### 15-Minute Macro Subscription
```json
{
  "ticks_history": "R_25",
  "adjust_start_time": 1,
  "count": 50,
  "end": "latest",
  "style": "candles",
  "granularity": 900,
  "subscribe": 1,
  "req_id": 2
}
```

### 5-Minute Structure Subscription
```json
{
  "ticks_history": "R_25",
  "adjust_start_time": 1,
  "count": 50,
  "end": "latest",
  "style": "candles",
  "granularity": 300,
  "subscribe": 1,
  "req_id": 3
}
```

### 1-Minute Trigger Subscription
```json
{
  "ticks_history": "R_25",
  "adjust_start_time": 1,
  "count": 50,
  "end": "latest",
  "style": "candles",
  "granularity": 60,
  "subscribe": 1,
  "req_id": 4
}
```

*Note: In incoming tick messages (`msg_type: "ohlc"`), route variables to the appropriate timeframe buffers by matching the `data.get("ohlc", {}).get("granularity")` field.*

---

## 4. Multipliers Proposal Payload (Native Server SL)
- **Proposal Request with native Stop-Loss**:
  ```json
  {
    "proposal": 1,
    "amount": 1.00,
    "basis": "stake",
    "contract_type": "MULTUP",
    "currency": "USD",
    "multiplier": 400,
    "underlying_symbol": "R_25",
    "limit_order": {
      "stop_loss": 0.75
    },
    "req_id": 5
  }
  ```

- **Executing Proposal Order**:
  ```json
  {
    "buy": "<PROPOSAL_ID>",
    "price": 1.00,
    "req_id": 6
  }
  ```

---

## 5. Active Position Monitoring & Market Close
- **Subscribing to Open Position Updates**:
  ```json
  {
    "proposal_open_contract": 1,
    "contract_id": "<CONTRACT_ID>",
    "subscribe": 1,
    "req_id": 7
  }
  ```

- **Market Close Command**:
  ```json
  {
    "sell": "<CONTRACT_ID>",
    "price": 0,
    "req_id": 8
  }
  ```
