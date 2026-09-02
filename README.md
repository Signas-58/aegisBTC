<p align="center">
  <img src="assets/logo.jpg" alt="Aegis-BTC Logo" width="220" />
</p>

# Aegis-BTC: Bitcoin Multipliers & MetaTrader 5 Algorithmic Trading Engine

![Aegis-BTC](https://img.shields.io/badge/Aegis--BTC-MT5%20%26%20Deriv-orange.svg)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![MetaTrader5](https://img.shields.io/badge/MetaTrader-5-green.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

**Aegis-BTC** is an automated, high-probability multi-timeframe algorithmic trading engine engineered for **Bitcoin Trading (`BTCUSD`)** across **Weltrade MetaTrader 5 (MT5)** and **Deriv Multipliers**. Designed for small-capital protection ($20 balance profile) with institutional risk parameters.

---

## 🌟 Core Features

- **Dual Broker Engine**:
  - **MetaTrader 5 (`mt5_client.py`)**: Direct C++ binary connection to **Weltrade** (or Deriv MT5). Sub-20ms order execution (`ORDER_TYPE_BUY` / `ORDER_TYPE_SELL`), direct memory candle ingestion, and zero token friction.
  - **Deriv WebSocket (`deriv_client.py`)**: Async WebSocket stream listener with REST Bearer authorization.
- **Multi-Timeframe Intelligence Matrix**: Integrates 15m (Macro EMA-200 & Swings), 5m (Structure/ADX/ATR/Liquidity Sweeps), and 1m (Trigger EMA-20 & RSI-14) streams with a **100-Point Probability Matrix** (minimum 75% required for execution).
- **Dynamic ATR Proximity Guard**: Volatility-adjusted key level clearance checks (`0.5x 5m ATR`).
- **Step-Ratchet Trailing Engine**: 
  - Server-side hard SL at `-$0.75`.
  - Shift SL floor to `$0.00` (Break-Even) at `+$0.50` PnL.
  - Advance in `+$0.25` steps maintaining a `$0.50` trailing gap once peak PnL > `+$0.75`.
- **Standalone Visible Desktop UI**: Auto-spawns an interactive PowerShell window on startup with live tick streaming, market regime status, setup scores, and signal notifications.
- **Circuit Breakers & Safeguards**:
  - **Stake / Lot Volume**: Fixed `$1.00` stake / `0.01` micro lot.
  - **Leverage**: Capped `x100` multiplier leverage to resist BTC wicks.
  - **Loss Quarantine**: 600 seconds (10 minutes) cooldown after any losing trade.
  - **Max Consecutive Losses**: 4 consecutive losses circuit breaker.
  - **Daily Drawdown Limit**: `$3.00` max daily drawdown (15% account protection).

---

## 📂 Project Architecture

```
aegisBTC/
├── config.py                 # System parameters, symbol, MT5 & Deriv settings
├── mt5_client.py             # MetaTrader 5 (Weltrade / MT5) client & order execution
├── deriv_client.py           # Async WebSocket client & candle streaming
├── indicators.py             # TA computation library (EMA, RSI, ADX, ATR, Swing Levels)
├── intelligence.py           # 100-Point Confluence matrix and regime classification
├── strat.py                  # MTF Candle processor, Dynamic ATR proximity guard, liquidity sweeps
├── engine.py                 # Position management, step-ratchet trailing, native SL handshake
├── main.py                   # CLI entrypoint (--live, --test, --validate)
├── start_live_bot.bat        # 1-Click interactive desktop terminal launcher
├── PROJECT_DESIGN_DOC.md     # System architecture specification
└── tests/
    └── test_aegis_btc.py     # Test suite verifying indicator math, matrix scoring, and risk rules
```

---

## 🚀 Getting Started

### 1. Installation

Clone or navigate to the repository directory:
```bash
git clone https://github.com/Signas-58/aegisBTC.git
cd aegisBTC
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configuration

Create your `.env` configuration file from the template:
```bash
cp .env.example .env
```

Edit `.env` and set your **Weltrade MT5** (or Deriv) login details:
```env
# MetaTrader 5 (Weltrade / MT5) Configuration
MT5_ACCOUNT=your_weltrade_account_number
MT5_PASSWORD=your_weltrade_password
MT5_SERVER=Weltrade-Live
MT5_SYMBOL=BTCUSD
MT5_VOLUME=0.01

# Deriv API Configuration
DERIV_APP_ID=1089
DERIV_TOKEN=your_deriv_token
DERIV_ACCOUNT_ID=DOT93113459
DERIV_SYMBOL=cryBTCUSD
MULTIPLIER_LEVERAGE=100
```

---

## 💻 Operating Modes

### 1-Click Desktop Launcher (Recommended)
Double-click **`start_live_bot.bat`** to open a visible, interactive desktop terminal window.

### Self-Validation Mode
Verify system configuration, math calculations, and risk engine rules:
```bash
python main.py --validate
```

### Dry-Run Simulation Mode
Test strategy analysis and step-ratchet execution using simulated tick sequences:
```bash
python main.py --test
```

### Live Bot Execution Mode
Run live MTF scanner and sub-20ms automated trade execution:
```bash
python main.py --live
```

---

## 🧪 Running Unit Tests

Run the full automated test suite using `unittest` or `pytest`:
```bash
python -m unittest discover -s tests
```

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for details.
