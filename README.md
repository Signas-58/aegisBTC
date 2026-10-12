<p align="center">
  <img src="assets/logo.jpg" alt="Aegis Logo" width="220" />
</p>

# Aegis-Weltrade: AI-Enhanced Multi-Profile Algorithmic Trading Engine

![Aegis](https://img.shields.io/badge/Aegis--Weltrade-Multi--Profile%20AI-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![MetaTrader5](https://img.shields.io/badge/MetaTrader-5-green.svg)
![Scikit-Learn](https://img.shields.io/badge/scikit--learn-Random%20Forest-orange.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

**Aegis-Weltrade** is a profile-driven, AI-filtered multi-timeframe algorithmic trading engine engineered for **EURUSD** on **Weltrade MetaTrader 5 (MT5)**. 

Built using institutional software engineering standards, Aegis provides a **Profile-Driven Architecture** that allows you to seamlessly switch between **10–45 minute Intraday Momentum Expansion trades**, **1-Minute Micro-Scalps**, or **Strict 60-Minute ICT Silver Bullet windows** without modifying execution logic or causing code drift.

---

## 🏛️ The 3 Operational Profiles at a Glance

| Parameter | Profile 1: `EXPANSION_M5` (Recommended Default) | Profile 2: `SCALP_M1` (Micro-Scalper) | Profile 3: `SILVER_BULLET_PURE` (Strict 60m Windows) |
| :--- | :--- | :--- | :--- |
| **Typical Hold Time** | **10 to 45 minutes** | 2 to 12 minutes | 10 to 30 minutes |
| **Trigger Chart** | **5-Minute (`M5`)** | 1-Minute (`M1`) | 3-Minute (`M3`) |
| **Structure Chart** | **15-Minute (`M15`)** | 3-Minute (`M3`) | 3-Minute (`M3`) |
| **Macro Trend** | **1-Hour (`H1`)** | 15-Minute (`M15`) | 1-Hour (`H1`) |
| **Session Windows (CAT)** | **09:00–12:30 & 14:30–18:00** | 09:00–12:00 & 15:00–18:00 | **10:00–11:00 & 16:00–17:00** |
| **Hard Stop Loss** | **15.0 pips ($1.50)** | 10.0 pips ($1.00) | 12.0 pips ($1.20) |
| **Take Profit Target** | **30.0 pips ($3.00 - 1:2 R:R)** | 15.0 pips ($1.50) | 24.0 pips ($2.40 - 1:2 R:R) |
| **Break-Even Trigger** | **+12.0 pips** | +6.0 pips | +10.0 pips |
| **Ratchet Step** | **+6.0 pips** | +4.0 pips | +5.0 pips |
| **Stagnation Time-Stop** | **45 minutes (2700s)** | 20 minutes (1200s) | 30 minutes (1800s) |
| **AI Lookback & Target** | **1500 M5 bars / 15 pips** | 1000 M1 bars / 5 pips | 1200 M3 bars / 12 pips |
| **Magic Number** | **800827** | 800826 | 800828 |
| **Max Daily Loss** | **$4.50** | $3.00 | $3.60 |

---

## 🌟 Why `EXPANSION_M5` Solves the Small-Account Scalping Trap

1. **The "Spread Tax" is Drastically Reduced:** On 1-minute scalping with a 10-pip target, a 1.2-pip spread eats 12% of your trade before commissions. On `EXPANSION_M5` with a 30-pip target, that same 1.2-pip spread is only **4% of your trade**.
2. **True 1:2 Risk-to-Reward Expectancy:** Risking 15 pips ($1.50) to make 30 pips ($3.00) means you stay comfortably profitable with just a **45% win rate**.
3. **No Wick Churn:** 5-minute candles filter out random tick spikes and broker spread anomalies, giving Fair Value Gaps (FVGs) and trend momentum room to breathe.

---

## 🧩 Modular System Architecture (7 Files)

1. **[`config.py`](file:///c:/Workspace/aegisBTC/config.py):** Centralized multi-profile dictionary (`PROFILES`), active mode selector (`ACTIVE_MODE`), and dynamic parameter exporter.
2. **[`mt5_bridge.py`](file:///c:/Workspace/aegisBTC/mt5_bridge.py):** Auto-reconnecting MT5 bridge, dynamic filling mode solver (resolves 10030 errors), rolling 20-MA relative spread filter, and server-side SL modify.
3. **[`ai_scanner.py`](file:///c:/Workspace/aegisBTC/ai_scanner.py):** Profile-adaptive `scikit-learn` Random Forest Classifier with profile-namespaced model caching (`models/regime_rf_{MODE}.joblib`).
4. **[`strategy.py`](file:///c:/Workspace/aegisBTC/strategy.py):** Completed bar-close (`[-2]`) evaluation, multi-timeframe FVG imbalance detection, EMA crossovers, and 100-point confluence scoring.
5. **[`risk_engine.py`](file:///c:/Workspace/aegisBTC/risk_engine.py):** Magic-filtered concurrency lock, delayed break-even ratchets, step-ratchet trailing, stagnation time-stops, rollover force-closes, and daily drawdown circuit breakers.
6. **[`telemetry.py`](file:///c:/Workspace/aegisBTC/telemetry.py):** Non-blocking HTTP Telegram notifications tagging the active profile in every alert.
7. **[`main.py`](file:///c:/Workspace/aegisBTC/main.py):** Command-line profile selector (`--mode`), historical pre-training pipeline, and continuous live event loop.

---

## 🚀 Quick Start Guide

### 1. Configure Credentials (`.env`)
Create or edit your `.env` file in the project root:
```env
WELTRADE_LOGIN=YourAccountNumber
WELTRADE_PASSWORD=YourPassword
WELTRADE_SERVER=Weltrade-Live
SYMBOL=EURUSD
LOT_SIZE=0.01

# Optional Telegram Push Notifications
ENABLE_TELEGRAM=True
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=987654321
```

### 2. Run Self-Validation Tests
```bash
python main.py --validate
python -m unittest discover -s tests
```

### 3. Launch the Live Trading Engine
Run the launcher menu:
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

## 🛡️ Risk Controls & Circuit Breakers

* **1-Trade Concurrency Lock:** Queries open positions by magic number to guarantee never more than 1 active trade per profile.
* **Delayed Break-Even Ratchet:** At +12.0 pips float profit on M5 (+6.0 pips on M1), SL is moved to entry price ($0.00 risk).
* **Step-Ratchet Trailing:** For every additional +6.0 pips beyond break-even, the SL is advanced forward by +6.0 pips.
* **45-Minute Stagnation Exit:** If trade duration reaches 45 minutes and profit $\ge 0$, closes immediately to free capital.
* **Rollover & Weekend Blackout:** Force-closes active positions at 22:30 CAT before rollover spread spikes; blocks entries 22:45–00:30 CAT and Fridays after 21:00 CAT.
* **Daily Drawdown Kill-Switch:** Halts all trading if cumulative daily loss reaches -$4.50 on M5 (-$3.00 on M1).
