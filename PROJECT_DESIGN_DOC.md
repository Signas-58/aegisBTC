# Aegis-BTC: Multi-Timeframe Smart Money & Dynamic Risk Engine for Bitcoin Multipliers

## Executive Summary
Aegis-BTC is an automated algorithmic trading engine built for Deriv Bitcoin Multipliers (`cryBTCUSD`). Designed specifically for small-capital accounts ($20 balance), it combines top-down Multi-Timeframe (MTF) market structure analysis, 5-minute liquidity sweep detection, machine-regime classification, and dynamic Average True Range (ATR) proximity filtering with a 100-point probability scoring matrix.

---

## 1. System Architecture & Multi-Timeframe (MTF) Pipeline

Aegis-BTC evaluates market conditions top-down across three distinct candle horizons before placing any order:

```
[15-Min Macro Stream (granularity: 900)]
└── Computes 15m EMA-200 Directional Bias & 20-Period Swing Support/Resistance
│
[5-Min Structure Stream (granularity: 300)]
└── Calculates ADX-14 Trend Strength, ATR-14 Volatility & Liquidity Sweeps
│
[1-Min Trigger Stream (granularity: 60)]
└── Verifies EMA-20 Crossover & RSI-14 Momentum Confluence
```

### Timeframe Execution Matrix

| Timeframe | Function | Primary Technicals |
| :--- | :--- | :--- |
| **15-Minute** | Macro Direction & Hard Levels | EMA-200, Swing High (Resistance), Swing Low (Support) |
| **5-Minute** | Regime, Volatility & Sweeps | ADX-14, ATR-14, Liquidity Sweep Wicks |
| **1-Minute** | Precision Entry Confirmation | EMA-20, RSI-14 |

---

## 2. Market Regime & Intelligence Scoring Engine (`intelligence.py`)

Aegis-BTC avoids rigid binary switches by utilizing a **100-Point Probability Matrix**. An entry order is generated **only if the total score is ≥ 75%**.

### Regime Classifier
* **`REGIME_TRENDING`:** 5m ADX ≥ 20 and 5m ADX slope > 0.
* **`REGIME_CONSOLIDATING`:** 5m ADX < 20 and ATR ratio ≤ 1.0.
* **`REGIME_HIGH_RISK`:** 5m ATR ratio > 1.8 (Extreme market volatility). **Execution Rule:** Force `NO_SIGNAL` immediately.

### 100-Point Confluence Scoring Breakdown

| Vector | Scoring Criteria | Max Points |
| :--- | :--- | :--- |
| **1. Macro Trend** | Price > 15m EMA-200 (`MULTUP`) or Price < 15m EMA-200 (`MULTDOWN`) | **25 Pts** |
| **2. Regime Quality** | `REGIME_TRENDING` (25 pts) OR `REGIME_CONSOLIDATING` with ADX ≥ 18 (15 pts) | **25 Pts** |
| **3. Liquidity Setup** | Active 5m Liquidity Sweep (25 pts) OR Clearance ≥ 1.0x ATR to Key Level (15 pts) | **25 Pts** |
| **4. Trigger Precision**| 1m Close vs EMA-20 & RSI-14 > 50 (or < 50 for `MULTDOWN`) | **25 Pts** |

---

## 3. Position Management & Trailing Ratchet Engine (`engine.py`)

### $0.25 Step / $0.50 Gap Ratchet Mechanics
Position management runs real-time via WebSocket `proposal_open_contract` updates:

* **Initial State:** Hard server-side Stop Loss registered at `-$0.75` USD.
* **Break-Even Trigger:** When peak profit reaches `+$0.50`, the active SL floor ratchets to **`$0.00`** (Zero Risk).
* **Profit Locking Ladder:** Once peak profit reaches `+$0.75`, the SL floor advances in **`$0.25` steps**, maintaining a maximum **`$0.50` trailing gap** behind peak profit.

```
Peak PnL Reached    Active SL Floor    Guaranteed Net Profit
----------------   -----------------   ---------------------
+$0.50               $0.00             Break-Even ($0.00)
+$0.75              +$0.25            +$0.25 Locked
+$1.00              +$0.50            +$0.50 Locked
+$1.25              +$0.75            +$0.75 Locked
+$1.50              +$1.00            +$1.00 Locked
```

---

## 4. Risk Envelope & Account Protection

```python
# Balance & Capital Rules ($20 Account Safeguards)
ACCOUNT_BALANCE = 20.00
STAKE_USD = 1.00  # Fixed stake per trade
MULTIPLIER_LEVERAGE = 100  # Leverage capped at x100 to absorb BTC wicks
HARD_STOP_LOSS_USD = 0.75  # Native server-side SL limit

# Cooldowns & Circuit Breakers
COOLDOWN_WIN_SECONDS = 30  # Standard wait after a winning trade
COOLDOWN_LOSS_QUARANTINE = 600  # 10-Minute Quarantine post-loss
MAX_CONSECUTIVE_LOSSES = 4  # Emergency session termination
MAX_DAILY_LOSS_USD = 3.00  # Daily Drawdown cap (15% of $20 balance)
```
