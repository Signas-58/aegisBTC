<p align="center">
  <img src="assets/logo.jpg" alt="Aegis-BTC Logo" width="220" />
</p>

# Aegis-BTC: Bitcoin Multipliers Trading Engine

![Aegis-BTC](https://img.shields.io/badge/Aegis--BTC-Deriv%20Crypto%20Multipliers-orange.svg)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

**Aegis-BTC** is an automated, high-probability algorithmic trading engine engineered specifically for trading **Bitcoin Multipliers (`cryBTCUSD`)** on Deriv with small-capital accounts ($20 balance profile).

---

## 🌟 Core Features

- **Multi-Timeframe Intelligence Matrix**: Integrates 15m (Macro EMA-200 & Swings), 5m (Structure/ADX/ATR/Liquidity Sweeps), and 1m (Trigger EMA-20 & RSI-14) streams with a **100-Point Probability Matrix** (minimum 75% required for execution).
- **Dynamic ATR Proximity Guard**: Replaces static dollar levels with volatility-adjusted clearance checks (`0.5x 5m ATR`).
- **Step-Ratchet Trailing Engine**: 
  - Server-side hard SL at `-$0.75`.
  - Shift SL floor to `$0.00` (Break-Even) at `+$0.50` PnL.
  - Advance in `+$0.25` steps maintaining a `$0.50` trailing gap once peak PnL > `+$0.75`.
- **Server-Side Native SL Handshake**: Automatically detects native backend contract settlement, preventing zombie loop retries and triggering an immediate 10-minute loss quarantine.
- **Circuit Breakers & Safeguards**:
  - **Stake**: Fixed `$1.00` stake (provides 26 trade attempts on a $20 balance).
  - **Leverage**: Capped `x100` multiplier leverage to resist BTC wicks.
  - **Loss Quarantine**: 600 seconds (10 minutes) cooldown after any losing trade.
  - **Max Consecutive Losses**: 4 consecutive losses circuit breaker.
  - **Daily Drawdown Limit**: `$3.00` max daily drawdown (15% account protection).

---

## 📂 Project Architecture

```
aegisBTC/
├── config.py                 # System parameters, symbol, leverage, and risk limits
├── indicators.py             # TA computation library (EMA, RSI, ADX, ATR, Swing Levels)
├── intelligence.py           # 100-Point Confluence matrix and regime classification
├── strat.py                  # MTF Candle processor, Dynamic ATR proximity guard, liquidity sweeps
├── engine.py                 # Position management, step-ratchet trailing, native SL handshake
├── deriv_client.py           # Async WebSocket client, candle streaming, proposal execution
├── main.py                   # CLI entrypoint (--live, --test, --validate)
├── PROJECT_DESIGN_DOC.md     # In-depth system architecture specification
├── DERIV_API_DOCS.md         # Deriv WebSocket API request/response specifications
└── tests/
    └── test_aegis_btc.py     # Test suite verifying indicator math, matrix scoring, and risk rules
```

---

## 🚀 Getting Started

### 1. Installation

Clone or navigate to the repository directory:
```bash
git clone https://github.com/your-org/aegis-btc.git
cd aegis-btc
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

Edit `.env` and set your Deriv API credentials:
```env
DERIV_APP_ID=1089
DERIV_API_TOKEN=your_deriv_api_token_here
DERIV_SYMBOL=cryBTCUSD
MULTIPLIER_LEVERAGE=100
```

---

## 💻 Operating Modes

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
Run live MTF scanner and automated trade execution on Deriv WebSocket:
```bash
python main.py --live
```

---

## 🧪 Running Unit Tests

Run the full automated test suite using `unittest` or `pytest`:
```bash
python -m unittest tests/test_aegis_btc.py -v
```

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for details.
