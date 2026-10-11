<p align="center">
  <img src="assets/logo.jpg" alt="Aegis Logo" width="220" />
</p>

# Aegis-Weltrade: EURUSD High-Win-Rate Algorithmic Trading Engine

![Aegis](https://img.shields.io/badge/Aegis--Weltrade-EURUSD%20Master-blue.svg)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![MetaTrader5](https://img.shields.io/badge/MetaTrader-5-green.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

**Aegis-Weltrade** is an automated, institutionally aligned multi-timeframe algorithmic trading engine engineered for **EURUSD** (and crypto/indices) on **Weltrade MetaTrader 5 (MT5)**. 

Built specifically to eliminate over-trading, spread churn, and false-breakout tick traps through strict execution guards: **completed bar-close evaluation (`[-2]`)**, **real-time spread filtering**, **ICT session time gates**, **single-trade lock**, and a **20-minute stagnation time-stop**.

---

## 🌟 Why EURUSD Over Gold (`XAUUSD`) & Bitcoin?

| Metric | Gold (`XAUUSD`) | EURUSD (Weltrade) | Why It Matters |
| :--- | :--- | :--- | :--- |
| **Typical Spread** | 25 – 40 points ($0.25 – $0.40) | **0.2 – 0.8 pips ($0.02 – $0.08)** | You don't start deep in the hole on entry |
| **1m Candle Volatility** | $2.00 – $5.00 stop-hunting wicks | **Smooth, technical candle expansion** | Respects support, resistance, and market structure |
| **Break-Even Efficiency** | Often wicked out within seconds | **Locks Break-Even cleanly at +6 pips** | High conversion of open profit into risk-free trades |
| **Target Scalp Duration** | 2 seconds – 3 minutes (churn) | **3 – 12 minutes** | Gives market time to deliver directional momentum |

---

## 🛡️ Core Architectural Execution Guards

### 1. Bar-Close Evaluation Guard (`index [-2]`)
* **Never trades live forming ticks (`[-1]`):** Forming candles repaint continuously until the minute ends, causing false breakouts.
* **Strict Confirmation:** Signals, 1m EMA-8 / EMA-21 crossovers, and 1m ADX momentum are evaluated **strictly on the completed closed candle (`[-2]`)**.

### 2. Real-Time Max Spread Guard (`≤ 1.2 pips`)
* Before transmitting any order to MT5, the bridge measures the live bid-ask spread:
  $$\text{Spread (pips)} = \frac{\text{Ask} - \text{Bid}}{\text{Point} \times 10}$$
* If spread exceeds `1.2 pips` (e.g. during rollover or high-impact news spikes), order execution is **instantly blocked**.

### 3. Institutional Session Time Gates (CAT / UTC+2)
* Volume and liquidity peak during major institutional sessions:
  - **London Session Open Window:** `09:00 – 12:00 CAT`
  - **New York Session Open Window:** `15:00 – 18:00 CAT`
* When `STRICT_SILVER_BULLET_GATE = True`, trades are restricted exclusively to these high-win-rate windows.

### 4. 4-Vector 100-Point Confluence Scoring Matrix
Orders fire only when total confluence score $\ge 80$:
1. **Session Gate (Pass/Fail):** Score `0` outside London/NY windows.
2. **15m Macro Trend Alignment (25 Pts):** Price above 15m EMA-200 for BUY, below for SELL.
3. **3m Fair Value Gap Imbalance (25 Pts):** Clean displacement gap on completed 3m candles (`Low[i] > High[i-2]` for Bullish, `High[i] < Low[i-2]` for Bearish).
4. **1m Bar-Close Momentum (25 Pts):** Completed bar `[-2]` 1m EMA-8 aligned above EMA-21 for BUY, below for SELL.
5. **1m ADX Acceleration (25 Pts):** 1m ADX $\ge 22.0$ with positive slope across the last 3 closed candles (`ADX[-2] > ADX[-3] > ADX[-4]`).

### 5. Micro-Risk Pip Ratchet & Stagnation Time-Stop
Forex 5-digit precision calculations ($1\text{ pip} = 0.00010$; on $0.01$ lot, $1\text{ pip} = \$0.10$):
* **Hard Stop Loss:** `10.0 pips` ($1.00 max risk per trade).
* **Fast Break-Even:** `+6.0 pips` (moves SL to Entry / $0.00 risk at +$0.60 profit).
* **Step-Ratchet Trailing:** `+4.0 pips` (advances SL forward by +$0.40 every 4 pips of additional expansion).
* **20-Minute Stagnation Time-Stop:** If an active trade remains open for $\ge 20\text{ minutes}$ (`1200s`) and PnL $\ge 0$, it triggers a market exit to release capital before chop or session roll.
* **10-Minute Loss Quarantine:** 600-second pause after any SL hit before scanning for new trades.
* **Daily Drawdown Kill Switch:** Halts all bot operations if daily realized loss reaches `-$3.00`.

---

## 📂 Project Architecture

```
aegisBTC/
├── config.py                 # EURUSD settings, session windows, pip parameters, risk thresholds
├── mt5_client.py             # MT5 bridge: spread guard, filling-mode resolver, pip order routing, SL ratcheting
├── deriv_client.py           # Async WebSocket client (Deriv Multipliers fallback)
├── indicators.py             # TA computation library (EMA, RSI, ADX, ATR, Swing Levels)
├── intelligence.py           # 100-Point quantitative confluence matrix & regime classification
├── strat.py                  # MTF Candle processor, bar-close evaluator [-2], 3m FVG detector
├── engine.py                 # Risk state machine, step-ratchet trailing, stagnation time-stop
├── main.py                   # Event loop orchestrator, visible terminal UI, self-validation
├── start_live_bot.bat        # 1-Click interactive desktop terminal launcher
├── PROJECT_DESIGN_DOC.md     # Engineering specification document
└── tests/
    └── test_aegis_btc.py     # Automated test suite (9 test cases covering indicators, math, and engine)
```

---

## 🚀 Getting Started

### 1. Installation

Clone the repository and install dependencies:
```bash
git clone https://github.com/Signas-58/aegisBTC.git
cd aegisBTC
pip install -r requirements.txt
```

### 2. Configuration (`.env`)

Configure your **Weltrade MT5** credentials in `.env`:
```env
# MetaTrader 5 (Weltrade / MT5) Configuration
MT5_ACCOUNT=your_weltrade_account_number
MT5_PASSWORD=your_weltrade_password
MT5_SERVER=Weltrade-Live
MT5_SYMBOL=EURUSD
MT5_VOLUME=0.01

# Asset Selection
SYMBOL=EURUSD
```

---

## 💻 Operating Modes

Aegis-Weltrade supports **3 Strategy Execution Modes**:
* **Option 1: EURUSD Master Strategy (`--mode master` or `--mode eurusd`) [Default]**:
  15m Macro Trend + 3m FVG + 1m Bar-Close Momentum (`[-2]`) with London/NY session gates.
* **Option 2: Aegis Classic (`--mode classic`)**:
  24/7 Multi-Timeframe Liquidity Sweep & Momentum Engine.
* **Option 3: ICT Silver Bullet Hybrid (`--mode hybrid`)**:
  CAT Session windows (09:00, 16:00, 20:00 CAT) with 3m FVG sweep-displacement scoring.

### 1-Click Desktop Launcher
Double-click **`start_live_bot.bat`** to open the interactive desktop trading terminal:
```
================================================================================
    AEGIS-WELTRADE MULTI-STRATEGY LAUNCHER
================================================================================
  Select Strategy Execution Mode:
    [1] Option 1: EURUSD Master Strategy (15m Macro + 3m FVG + 1m Bar-Close Momentum) [Default]
    [2] Option 2: Aegis Classic Strategy (24/7 MTF Sweep & Momentum)
    [3] Option 3: ICT Silver Bullet Hybrid Strategy (CAT Timing + 3m FVG)
================================================================================
```

### Self-Validation Checks
Verify math calculations, indicator precision, and risk engine rules:
```bash
python main.py --validate
```

### Dry-Run Simulation Mode
Test strategy analysis, Break-Even locking, and step-ratchet trailing using synthetic tick sequences:
```bash
python main.py --test
```

### Live Bot Execution
Run live automated trading on Weltrade MT5:
```bash
python main.py --live
```

---

## 🧪 Automated Testing

Run the automated test suite:
```bash
python -m unittest discover -s tests
```
*All 9 test cases validate indicator formulas, regime classification, EURUSD Master confluence scoring, step-ratchet trailing, server-side SL sync, and stagnation time-stops.*

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for details.
