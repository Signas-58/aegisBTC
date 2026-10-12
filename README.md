<p align="center">
  <img src="assets/logo.jpg" alt="Aegis Logo" width="220" />
</p>

# Aegis-Weltrade: AI-Enhanced EURUSD High-Win-Rate Algorithmic Trading Engine

![Aegis](https://img.shields.io/badge/Aegis--Weltrade-AI%20EURUSD%20Master-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![MetaTrader5](https://img.shields.io/badge/MetaTrader-5-green.svg)
![Scikit-Learn](https://img.shields.io/badge/scikit--learn-Random%20Forest-orange.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

**Aegis-Weltrade** is an automated, AI-filtered multi-timeframe algorithmic trading engine engineered for **EURUSD** on **Weltrade MetaTrader 5 (MT5)**. 

Built to eliminate over-trading, spread churn, and false-breakout tick traps through institutional execution guards: **Machine Learning Market Regime Classification**, **completed bar-close evaluation (`[-2]`)**, **dynamic relative spread filtering**, **ICT session time gates**, **single-trade lock**, **daily rollover & weekend blackouts**, and **Telegram mobile telemetry**.

---

## 🌟 Why EURUSD Over Gold (`XAUUSD`) & Bitcoin?

| Metric | Gold (`XAUUSD`) | EURUSD (Weltrade) | Why It Matters |
| :--- | :--- | :--- | :--- |
| **Typical Spread** | 25 – 40 points ($0.25 – $0.40) | **0.2 – 0.8 pips ($0.02 – $0.08)** | You don't start deep in the hole on entry |
| **1m Candle Volatility** | $2.00 – $5.00 stop-hunting wicks | **Smooth, technical candle expansion** | Respects support, resistance, and market structure |
| **Break-Even Efficiency** | Often wicked out within seconds | **Locks Break-Even cleanly at +6 pips** | High conversion of open profit into risk-free trades |
| **Target Scalp Duration** | 2 seconds – 3 minutes (churn) | **3 – 12 minutes** | Gives market time to deliver directional momentum |

---

## 🛡️ Core Production Safeguards & AI Architecture

### 1. 🧠 AI Market Regime Classifier (`ai_scanner.py`)
* **Expansion vs. Chop Filter:** Rather than trying to predict noisy 1m direction, a lightweight `scikit-learn` **Random Forest Classifier** (`n_estimators=50, max_depth=5`) classifies market conditions into:
  - **Expansion State ($\ge 70\%$ confidence):** Strong momentum expansion setup approved.
  - **Chop State ($< 70\%$ confidence):** Sideways range with high stop-out risk blocked.
* **Feature Vector:** Computes 10-period volatility, High-Low range ratio, EMA-8 vs. EMA-21 spread distance, and relative candle expansion.
* **Instant Startup:** Ingests 1,000 historical M1 candles on startup in $< 0.3\text{ seconds}$ and caches the model to disk (`aegis_ai_regime_model.joblib`).

### 2. 📊 Dynamic Relative Spread Filter
* **Absolute Cap:** Orders blocked if live spread $> 1.2\text{ pips}$.
* **Relative Volatility Shock Filter:** Orders blocked if current spread exceeds **$1.5\times$ the rolling 20-candle average spread**. Protects against news shocks and sudden liquidity drains.

### 3. 🛑 Rollover & Weekend Blackout Guards
* **Daily Rollover Blackout (22:45 to 00:30 CAT):** Halts trade execution during the nightly bank settlement rollover when broker spreads widen to 3–5+ pips.
* **Friday Weekend Close (Fridays at 21:00 CAT):** Halts execution before the weekend to avoid Sunday market open gap risk.

### 4. 📱 Real-Time Telegram Mobile Telemetry (`telemetry.py`)
* Dispatches non-blocking instant push alerts to your phone via Telegram Bot:
  - 🚀 **Order Executed:** Ticket ID, direction, entry, SL, TP, score, and AI confidence.
  - 🛡️ **Break-Even Triggered:** Position moved to Entry ($0.00 risk).
  - 📈 **Profit Locked (Step Ratchet):** Locked floor, server SL, peak PnL.
  - 💰 **Trade Closed:** Net PnL, duration, and exit reason.
  - 🚨 **Daily Kill-Switch:** Alert if daily loss limit (-$3.00) is hit.

### 5. 🎯 Bar-Close Evaluation Guard (`index [-2]`)
* **Never trades live forming ticks (`[-1]`):** Forming candles repaint continuously until the minute ends, causing false breakouts.
* **Strict Confirmation:** Signals, 1m EMA-8 / EMA-21 crossovers, and 1m ADX momentum are evaluated **strictly on the completed closed candle (`[-2]`)**.

### 6. ⏰ Institutional Session Time Gates (CAT / UTC+2)
* Volume and liquidity peak during major institutional sessions:
  - **London Session Open Window:** `09:00 – 12:00 CAT`
  - **New York Session Open Window:** `15:00 – 18:00 CAT`
* When `STRICT_SILVER_BULLET_GATE = True`, trades are restricted exclusively to these high-win-rate windows.

### 7. ⚖️ 4-Vector 100-Point Confluence Scoring Matrix
Orders fire only when total confluence score $\ge 80$ AND AI Confidence $\ge 0.70$:
1. **Session Gate (Pass/Fail):** Score `0` outside London/NY windows.
2. **15m Macro Trend Alignment (25 Pts):** Price above 15m EMA-200 for BUY, below for SELL.
3. **3m Fair Value Gap Imbalance (25 Pts):** Clean displacement gap on completed 3m candles (`Low[i] > High[i-2]` for Bullish, `High[i] < Low[i-2]` for Bearish).
4. **1m Bar-Close Momentum (25 Pts):** Completed bar `[-2]` 1m EMA-8 aligned above EMA-21 for BUY, below for SELL.
5. **1m ADX Acceleration (25 Pts):** 1m ADX $\ge 22.0$ with positive slope across the last 3 closed candles (`ADX[-2] > ADX[-3] > ADX[-4]`).

### 8. 🛡️ Micro-Risk Pip Ratchet & Stagnation Time-Stop
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
├── config.py                 # EURUSD settings, session windows, AI thresholds, risk limits
├── mt5_client.py             # MT5 bridge: relative spread filter, order routing, SL ratcheting
├── ai_scanner.py             # Random Forest market regime classifier (scikit-learn)
├── telemetry.py              # Non-blocking Telegram mobile alert dispatcher
├── deriv_client.py           # Async WebSocket client (Deriv Multipliers fallback)
├── indicators.py             # TA computation library (EMA, RSI, ADX, ATR, Swing Levels)
├── intelligence.py           # 100-Point quantitative confluence matrix & regime classification
├── strat.py                  # MTF Candle processor, bar-close evaluator [-2], 3m FVG detector
├── engine.py                 # Risk state machine, step-ratchet trailing, stagnation time-stop
├── main.py                   # Event loop orchestrator, visible terminal UI, self-validation
├── start_live_bot.bat        # 1-Click interactive desktop terminal launcher
├── PROJECT_DESIGN_DOC.md     # Engineering specification document
└── tests/
    └── test_aegis_btc.py     # Automated test suite (11 test cases covering indicators, AI, and risk)
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

Configure your **Weltrade MT5** credentials and optional **Telegram Bot** settings in `.env`:
```env
# MetaTrader 5 (Weltrade / MT5) Configuration
MT5_ACCOUNT=your_weltrade_account_number
MT5_PASSWORD=your_weltrade_password
MT5_SERVER=Weltrade-Live
MT5_SYMBOL=EURUSD
MT5_VOLUME=0.01

# Asset Selection
SYMBOL=EURUSD

# Optional Telegram Mobile Telemetry
ENABLE_TELEGRAM=True
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_CHAT_ID=your_chat_id
```

---

## 💻 Operating Modes

Aegis-Weltrade supports **3 Strategy Execution Modes**:
* **Option 1: EURUSD Master Strategy (`--mode master` or `--mode eurusd`) [Default]**:
  15m Macro Trend + 3m FVG + 1m Bar-Close Momentum (`[-2]`) with AI Random Forest regime filter.
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
*All 11 test cases validate indicators, market regimes, EURUSD Master scoring, step-ratchet trailing, AI Random Forest expansion prediction, and Telegram telemetry.*

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for details.
