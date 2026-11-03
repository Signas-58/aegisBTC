<p align="center">
  <img src="assets/logo.jpg" alt="Aegis Logo" width="220" />
</p>

# Aegis-Weltrade: AI-Enhanced Multi-Profile Algorithmic Trading Engine

![Aegis](https://img.shields.io/badge/Aegis--Weltrade-Multi--Profile%20AI-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![MetaTrader5](https://img.shields.io/badge/MetaTrader-5-green.svg)
![Scikit-Learn](https://img.shields.io/badge/scikit--learn-v1.9.1-orange.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

**Aegis-Weltrade** is a profile-driven, AI-filtered multi-timeframe algorithmic trading engine engineered for **EURUSD** on **Weltrade MetaTrader 5 (MT5)**. 

Built using institutional software engineering standards, Aegis provides a **Profile-Driven Architecture** that allows you to seamlessly switch between **10–45 minute Intraday Momentum Expansion trades**, **1-Minute Micro-Scalps**, or **Strict 60-Minute ICT Silver Bullet windows** without modifying execution logic or causing code drift.

---

## 🏛️ The 4 Operational Profiles at a Glance

| Parameter | Profile 1: `MULTI_ASSET_ENSEMBLE` (Default - High Frequency Target) | Profile 2: `EXPANSION_M5` (Single Pair) | Profile 3: `SCALP_M1` (Micro-Scalper) | Profile 4: `SILVER_BULLET_PURE` (Strict 60m Windows) |
| :--- | :--- | :--- | :--- | :--- |
| **Target Assets** | **`EURUSD`, `GBPUSD`, `USDJPY`** | `EURUSD` | `EURUSD` | `EURUSD` |
| **Typical Target Frequency**| **~1 High-Conviction Trade/Hour** | 1 to 3 Trades/Day | 3 to 8 Trades/Day | 0 to 2 Trades/Day |
| **Global Portfolio Lock** | **Strict 1 Position across account** | 1 Position | 1 Position | 1 Position |
| **AI Voting Committee** | **Dual-AI (Random Forest + HistGradientBoosting)** | Random Forest | Random Forest | Random Forest |
| **Typical Hold Time** | **10 to 35 minutes** | 10 to 45 minutes | 2 to 12 minutes | 10 to 30 minutes |
| **Trigger Chart** | **5-Minute (`M5`) Bar-Close** | 5-Minute (`M5`) | 1-Minute (`M1`) | 3-Minute (`M3`) |
| **Structure Chart** | **15-Minute (`M15`)** | 15-Minute (`M15`) | 3-Minute (`M3`) | 3-Minute (`M3`) |
| **Macro Trend** | **1-Hour (`H1`)** | 1-Hour (`H1`) | 15-Minute (`M15`) | 1-Hour (`H1`) |
| **Session Windows (CAT)** | **08:00–20:00 (Extended Institutional)** | 09:00–12:30 & 14:30–18:00 | 09:00–12:00 & 15:00–18:00 | 10:00–11:00 & 16:00–17:00 |
| **Hard Stop Loss** | **12.0 pips ($1.20)** | 15.0 pips ($1.50) | 10.0 pips ($1.00) | 12.0 pips ($1.20) |
| **Take Profit Target** | **24.0 pips ($2.40 - 1:2 R:R)** | 30.0 pips ($3.00 - 1:2 R:R) | 15.0 pips ($1.50) | 24.0 pips ($2.40 - 1:2 R:R) |
| **Break-Even Trigger** | **+8.0 pips** | +12.0 pips | +6.0 pips | +10.0 pips |
| **Ratchet Step** | **+4.0 pips** | +6.0 pips | +4.0 pips | +5.0 pips |
| **Stagnation Time-Stop** | **35 minutes (2100s)** | 45 minutes (2700s) | 20 minutes (1200s) | 30 minutes (1800s) |
| **AI Lookback & Target** | **1500 M5 bars / 12 pips** | 1500 M5 bars / 15 pips | 1000 M1 bars / 5 pips | 1200 M3 bars / 12 pips |
| **Magic Number** | **800830** | 800827 | 800826 | 800828 |
| **Max Daily Loss** | **$4.00** | $4.50 | $3.00 | $3.60 |

---

## 🌟 Why `EXPANSION_M5` Solves the Small-Account Scalping Trap

1. **The "Spread Tax" is Drastically Reduced:** On 1-minute scalping with a 10-pip target, a 1.2-pip spread eats 12% of your trade before commissions. On `EXPANSION_M5` with a 30-pip target, that same 1.2-pip spread is only **4% of your trade**.
2. **True 1:2 Risk-to-Reward Expectancy:** Risking 15 pips ($1.50) to make 30 pips ($3.00) means you stay comfortably profitable with just a **45% win rate**.
3. **No Wick Churn:** 5-minute candles filter out random tick spikes and broker spread anomalies, giving Fair Value Gaps (FVGs) and trend momentum room to breathe.
4. **Zero Latency Impact:** Python order execution takes 20–100ms. On 1-minute charts, 100ms lag can cause 1-pip slippage; on 5-minute charts, it is completely negligible.

---

## 🧠 Machine Learning Engine: Dual-AI Committee Consensus

Aegis uses a **Dual-AI Voting Committee** (`ai_ensemble.py`) built directly on `scikit-learn` without heavy C++ dependencies:

1. **Random Forest Classifier (`RandomForestClassifier`):** Focuses on bagging trees to filter out consolidation noise, sideways churn, and spread traps.
2. **HistGradientBoosting Classifier (`HistGradientBoostingClassifier`):** Uses binned gradient boosting to identify directional displacement, volume surges, and volatility expansions.

* **Consensus Gate Rule:** Both models must vote in agreement ($\ge 65\%$ confidence) before an entry order is authorized.
* **Per-Symbol & Profile Weight Caching:** Models are automatically cached per symbol and profile in `models/`:
  - `models/ensemble_EURUSD_MULTI_ASSET_ENSEMBLE.joblib`
  - `models/ensemble_GBPUSD_MULTI_ASSET_ENSEMBLE.joblib`
  - `models/ensemble_USDJPY_MULTI_ASSET_ENSEMBLE.joblib`
* **Feature Vector:**
  1. Normalized candle returns & 10-period rolling volatility (`std() * 1000.0`).
  2. High-Low range ratio relative to candle close (`(high - low) / close`).
  3. EMA distance spread (`(EMA_8 - EMA_21) / close`).
  4. Candle range expansion ratio (current range vs. 10-period moving average).
  5. Relative Volume (current tick volume vs. 20-period volume MA).

---

## ⏱️ Live Diagnostic Heartbeat & Telemetry

To solve the classic algorithmic trading issue where **"a silent script looks identical to a crashed script"**, Aegis logs an instant diagnostic heartbeat on every closed candle across all active assets:

```text
⏱️ [09:05:01] MULTI_ASSET_ENSEMBLE | EURUSD | Score: 25/100 | AI Conf: 34.2% | Spread: 0.6p | Status: ⏳ Score Low (25/100) | AI Low (34.2%)
⏱️ [09:05:02] MULTI_ASSET_ENSEMBLE | GBPUSD | Score: 50/100 | AI Conf: 58.1% | Spread: 0.7p | Status: ⏳ Score Low (50/100) | AI Low (58.1%)
⏱️ [09:05:03] MULTI_ASSET_ENSEMBLE | USDJPY | Score: 100/100 | AI Conf: 81.0% | Spread: 0.8p | Status: ⚡ EXECUTING BUY ORDER #800830
```

* **Instant Startup Telegram Alert:** Dispatches an instant Telegram status ping on startup confirming profile, magic number, targets, and active symbols.
* **Strict Global Portfolio Lock:** Enforces `MAX_PORTFOLIO_POSITIONS = 1` globally across the entire account to safeguard small balance accounts ($50–$100).

---

## 🧩 Modular System Architecture

```
aegisBTC/
├── config.py           # Multi-profile dictionary & dynamic configuration exporter
├── ai_ensemble.py      # Dual-AI Committee (RandomForest + HistGradientBoosting)
├── ai_scanner.py       # Backward-compatible AI scanner wrapper
├── mt5_bridge.py       # Multi-symbol MT5 bridge, filling solver, spread filter & order routing
├── strategy.py         # Completed bar [-2] confluence scoring (Macro, FVG, EMA, ADX)
├── risk_engine.py      # Concurrency lock, pips math (EUR/USD/JPY), ratchets & kill-switch
├── telemetry.py        # Non-blocking HTTP Telegram alerts tagged by active profile
├── main.py             # CLI parser (--mode), sequential multi-asset scanner & heartbeat
├── start_live_bot.bat  # Interactive Windows desktop launcher menu (options 1 to 4)
└── models/             # Cached Dual-AI weights (*.joblib)
```

1. **[`config.py`](file:///c:/Workspace/aegisBTC/config.py):** Centralized multi-profile dictionary (`PROFILES`), active mode selector (`ACTIVE_MODE`), and dynamic parameter exporter.
2. **[`mt5_bridge.py`](file:///c:/Workspace/aegisBTC/mt5_bridge.py):** Auto-reconnecting MT5 bridge, dynamic filling mode solver (resolves 10030 errors), rolling 20-MA relative spread filter, and server-side SL modify.
3. **[`ai_scanner.py`](file:///c:/Workspace/aegisBTC/ai_scanner.py):** Profile-adaptive `scikit-learn` Random Forest Classifier with profile-namespaced model caching.
4. **[`strategy.py`](file:///c:/Workspace/aegisBTC/strategy.py):** Completed bar-close (`[-2]`) evaluation, multi-timeframe FVG imbalance detection, EMA crossovers, and 100-point confluence scoring.
5. **[`risk_engine.py`](file:///c:/Workspace/aegisBTC/risk_engine.py):** Magic-filtered concurrency lock, delayed break-even ratchets, step-ratchet trailing, stagnation time-stops, rollover force-closes, and daily drawdown circuit breakers.
6. **[`telemetry.py`](file:///c:/Workspace/aegisBTC/telemetry.py):** Non-blocking HTTP Telegram notifications tagging the active profile in every alert.
7. **[`main.py`](file:///c:/Workspace/aegisBTC/main.py):** Command-line profile selector (`--mode`), historical pre-training pipeline, and continuous live event loop.

---

## 🛡️ Risk Controls & Circuit Breakers

* **1-Trade Concurrency Lock:** Queries open positions by magic number to guarantee never more than 1 active trade per profile.
* **Delayed Break-Even Ratchet:** At +12.0 pips float profit on M5 (+6.0 pips on M1), SL is moved to entry price ($0.00 risk).
* **Step-Ratchet Trailing:** For every additional +6.0 pips beyond break-even, the SL is advanced forward by +6.0 pips.
* **45-Minute Stagnation Exit:** If trade duration reaches 45 minutes and profit $\ge 0$, closes immediately to free capital.
* **Rollover & Weekend Blackout:** Force-closes active positions at 22:30 CAT before rollover spread spikes; blocks entries 22:45–00:30 CAT and Fridays after 21:00 CAT.
* **Daily Drawdown Kill-Switch:** Halts all trading if cumulative daily loss reaches -$4.50 on M5 (-$3.00 on M1).

---

## 🚀 Quick Start Guide

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```
*(Verified packages: `scikit-learn==1.9.1`, `joblib==1.6.0`, `MetaTrader5`, `pandas`, `numpy`, `requests`)*

### 2. Configure Credentials (`.env`)
Create or edit your `.env` file in the project root:
```env
WELTRADE_LOGIN=YourAccountNumber
WELTRADE_PASSWORD=YourPassword
WELTRADE_SERVER=Weltrade-Live
SYMBOL=EURUSD
LOT_SIZE=0.01

# Optional Mobile Telegram Push Notifications
ENABLE_TELEGRAM=True
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=987654321
```

### 3. Run Self-Validation Tests
```bash
python main.py --validate
python -m unittest discover -s tests
```

### 4. Launch the Live Trading Engine
Run the interactive launcher:
```cmd
start_live_bot.bat
```
Or run directly from PowerShell specifying your profile:
```bash
# Recommended default: 10-45 min intraday momentum expansion
python main.py --live --mode EXPANSION_M5

# 1-minute micro-scalper
python main.py --live --mode SCALP_M1

# Strict 60-minute ICT Silver Bullet windows
python main.py --live --mode SILVER_BULLET_PURE
```

---

## 📱 Setting Up Free Telegram Alerts

1. Open Telegram and search for `@BotFather`.
2. Send `/newbot`, follow prompts, and copy your **Bot Token**.
3. Search for `@userinfobot` on Telegram, tap Start, and copy your **Id** (`Chat ID`).
4. Paste them into your `.env` file:
   ```env
   ENABLE_TELEGRAM=True
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
   TELEGRAM_CHAT_ID=987654321
   ```
5. You will now receive instant push alerts on your phone for entries, break-even shifts, profit-locking ratchets, trade exits, and kill-switch activations!
