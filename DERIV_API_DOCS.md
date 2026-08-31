# Deriv API Specification: Aegis-BTC Multiplier Engine

## Overview
This document specifies the Deriv WebSocket API endpoints, JSON request/response payloads, error handling, and symbol configuration required for automated execution of **Bitcoin Multipliers (`cryBTCUSD`)**.

---

## 1. Connection & Data Ingestion

### Endpoint & Authentication
* **WebSocket URL:** `wss://ws.derivws.com/websockets/v3?app_id={APP_ID}`
* **Auth Request Payload:**
```json
{
  "authorize": "YOUR_DERIV_API_TOKEN"
}
```

### Multi-Timeframe OHLC Candle Subscription (`ticks_history`)

Fetch and maintain candle streams for `cryBTCUSD` across three granularities:

```json
{
  "ticks_history": "cryBTCUSD",
  "adjust_start_time": 1,
  "count": 200,
  "end": "latest",
  "granularity": 900,
  "style": "candles",
  "subscribe": 1
}
```

*(Repeat for `granularity: 300` [5-Minute] and `granularity: 60` [1-Minute]).*

---

## 2. Trade Execution Payloads

### Step 1: Proposal Request

Submit proposal payload with a fixed `$1.00` stake, `x100` multiplier leverage, and server-side hard stop-loss:

```json
{
  "proposal": 1,
  "amount": 1.00,
  "basis": "stake",
  "contract_type": "MULTUP",
  "currency": "USD",
  "symbol": "cryBTCUSD",
  "multiplier": 100,
  "limit_order": {
    "stop_loss": 0.75
  }
}
```

### Step 2: Contract Purchase Payload

Purchase the validated proposal ID immediately upon receiving the proposal response:

```json
{
  "buy": "PROPOSAL_ID_STRING",
  "price": 1.00
}
```

### Step 3: Open Contract Tracking (`proposal_open_contract`)

Subscribe to real-time status updates for the open contract:

```json
{
  "proposal_open_contract": 1,
  "contract_id": 10277534459,
  "subscribe": 1
}
```

---

## 3. Server-Side SL & Native Handshake Protocols

### Auto-Closed Contract Detection

When Deriv's server triggers the native `$0.75` hard stop loss, the server automatically settles and expires the contract.

To prevent **"Zombie Contract" execution loops** (`Failed to close: The contract has expired`), Python must handle state changes as follows:

```python
def handle_poc_message(response):
    poc = response.get("proposal_open_contract", {})

    # 1. Check if contract is already sold or expired on Deriv's backend
    if poc.get("is_sold") == 1 or poc.get("is_expired") == 1:
        log_info("[SERVER AUTO-CLOSE] Contract closed natively by Deriv server.")
        unsubscribe_poc(poc.get("contract_id"))
        trigger_post_loss_quarantine(duration=600)
        return

    # 2. Check for Manual Sell Response Errors
    if "error" in response:
        if "contract has expired" in response["error"]["message"].lower():
            log_warning(
                "[SYNC NOTICE] Contract expired during sell request. Force-clearing trade state."
            )
            trigger_post_loss_quarantine(duration=600)
            return
```

### Manual Market Close Request

Only send manual WS sell requests when the local step-ratchet stop-loss floor has moved to Break-Even or Profit Lock (`current_sl_floor >= 0.00`):

```json
{
  "sell": 10277534459,
  "price": 0.00
}
```

---

## 4. API Error Code Reference

| Error Code / Message | Cause | Engine Resolution |
| --- | --- | --- |
| `Contract expired` | Native Server SL hit before manual WS sell arrived | Immediately stop sell retry loop; initiate 600s quarantine. |
| `Market closed` | Crypto maintenance window | Pause scanner for 15 minutes; retry ping connection. |
| `InvalidSymbol` | Incorrect BTC symbol code | Verify asset symbol is set to `"cryBTCUSD"` (or `"BTCUSD"`). |
| `InsufficientBalance` | Account balance dipped below stake requirement | Halt execution; trigger emergency email/logger alert. |
