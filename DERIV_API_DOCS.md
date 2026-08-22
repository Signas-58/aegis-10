# Deriv API Protocol Reference Specifications (Aegis-10)

Last updated: 2026-08-22

## 1. OTP Rest Handshake Sequence
For unified options trading accounts (`DOT` or `ROT` prefix), WebSocket authentication requires obtaining a single-use OTP.
- **REST Endpoints**: `POST https://api.derivws.com/trading/v1/options/accounts/{accountId}/otp`
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

## 3. Market Data Subscription (30-Second Candles)
- Fetch history and subscribe to live 30-second candle updates:
  ```json
  {
    "ticks_history": "R_10",
    "adjust_start_time": 1,
    "count": 50,
    "end": "latest",
    "style": "candles",
    "granularity": 30,
    "subscribe": 1,
    "req_id": 2
  }
  ```

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
    "underlying_symbol": "R_10",
    "limit_order": {
      "stop_loss": 0.75
    },
    "req_id": 3
  }
  ```

- **Executing Proposal Order**:
  ```json
  {
    "buy": "<PROPOSAL_ID>",
    "price": 1.00,
    "req_id": 4
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
    "req_id": 5
  }
  ```

- **Market Close Command**:
  ```json
  {
    "sell": "<CONTRACT_ID>",
    "price": 0,
    "req_id": 6
  }
  ```
