import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# API Connection & Symbol Specs
APP_ID = os.getenv("DERIV_APP_ID", "1089")
API_TOKEN = os.getenv("DERIV_API_TOKEN", os.getenv("DERIV_TOKEN", ""))
DERIV_ACCOUNT_ID = os.getenv("DERIV_ACCOUNT_ID", "DOT93113459")
SYMBOL = os.getenv("DERIV_SYMBOL", "cryBTCUSD")  # Deriv Crypto Multipliers Symbol
CONTRACT_TYPE_UP = "MULTUP"
CONTRACT_TYPE_DOWN = "MULTDOWN"
MULTIPLIER_LEVERAGE = int(os.getenv("MULTIPLIER_LEVERAGE", "100"))  # Capped leverage (x100) to protect $20 account from wicks

# Multi-Timeframe Ingestion
TF_MACRO = 900  # 15-Minute Candles (Macro Horizon)
TF_STRUCTURE = 300  # 5-Minute Candles (Structure & Liquidity Horizon)
TF_TRIGGER = 60  # 1-Minute Candles (Trigger Horizon)

# Strategy & Dynamic ATR Scaling Factors
ADX_MIN_THRESHOLD = 20  # Minimum 5m ADX required
MIN_CONFIDENCE_SCORE = 75  # 75% Intelligence Score required for entry
PROXIMITY_GUARD_ATR_MULT = 0.5  # Key level clearance buffer = 0.5x 5m ATR

# Fixed USD Risk Envelope ($20 Balance Protection)
STAKE = 1.00  # Deriv API stake
HARD_STOP_LOSS_USD = 0.75  # Native server-side SL ($0.75 max risk)
BREAK_EVEN_TRIGGER = 0.50  # Shift SL floor to $0.00 at +$0.50 PnL
TRAILING_STEP_USD = 0.25  # Lock in profits every +$0.25 step after +$0.75 PnL
TRAILING_GAP_USD = 0.50  # Fixed $0.50 trailing offset behind peak PnL

# Safety Cooldowns & Circuit Breakers
COOLDOWN_AFTER_WIN_SECONDS = 30
COOLDOWN_AFTER_LOSS_SECONDS = 600  # 10-Minute Loss Quarantine
MAX_CONSECUTIVE_LOSSES = 4
MAX_DAILY_LOSS_USD = 3.00
MAX_RUNTIME_MINUTES = 480  # 8-Hour Session Limit
