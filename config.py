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

# MetaTrader 5 (Weltrade / MT5) Config
MT5_ACCOUNT = int(os.getenv("MT5_ACCOUNT", "0")) if os.getenv("MT5_ACCOUNT", "").isdigit() else 0
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "Weltrade-Live")
MT5_SYMBOL = os.getenv("MT5_SYMBOL", "BTCUSD")
MT5_VOLUME = float(os.getenv("MT5_VOLUME", "0.01"))

# Multi-Timeframe Ingestion
TF_MACRO = 900  # 15-Minute Candles (Macro Horizon)
TF_STRUCTURE = 300  # 5-Minute Candles (Structure & Liquidity Horizon)
TF_ENTRY = 180  # 3-Minute Candles (Execution & FVG Horizon)
TF_TRIGGER = 60  # 1-Minute Candles (Trigger Horizon)

# Dual Strategy Modes: "AEGIS_CLASSIC" (Option 1) | "HYBRID_SILVER_BULLET" (Option 2)
STRATEGY_MODE = os.getenv("STRATEGY_MODE", "HYBRID_SILVER_BULLET").upper()

# ICT Silver Bullet CAT Session Windows (UTC+2 / Central Africa Time)
SILVER_BULLET_WINDOWS_CAT = [
    ("09:00", "10:00"),  # London Silver Bullet
    ("16:00", "17:00"),  # NY AM Silver Bullet
    ("20:00", "21:00"),  # NY PM Silver Bullet
]
STRICT_SILVER_BULLET_GATE = False  # If True: Block trades outside SB windows. If False: Award 20 scoring points during windows.

# Strategy & Dynamic ATR Scaling Factors
ADX_MIN_THRESHOLD = 20  # Minimum 5m ADX required
MIN_CONFIDENCE_SCORE = 75  # 75% Intelligence Score required for entry
PROXIMITY_GUARD_ATR_MULT = 0.5  # Key level clearance buffer = 0.5x 5m ATR
FVG_MIN_ATR_RATIO = 0.3  # Minimum imbalance size relative to 3m ATR

# Fixed USD Risk Envelope ($20 Balance Protection)
STAKE = 1.00  # Deriv API stake
HARD_STOP_LOSS_USD = 0.75  # Native server-side SL ($0.75 max risk)
TAKE_PROFIT_LOT_MULT = 100.0  # Take Profit target = 100x Lot Size ($1.00 TP for 0.01 lot)
BREAK_EVEN_TRIGGER = 0.50  # Shift SL floor to $0.00 at +$0.50 PnL
TRAILING_STEP_USD = 0.25  # Lock in profits every +$0.25 step after +$0.75 PnL
TRAILING_GAP_USD = 0.50  # Fixed $0.50 trailing offset behind peak PnL

# Safety Cooldowns & Circuit Breakers
COOLDOWN_AFTER_WIN_SECONDS = 30
COOLDOWN_AFTER_LOSS_SECONDS = 600  # 10-Minute Loss Quarantine
MAX_CONSECUTIVE_LOSSES = 4
MAX_DAILY_LOSS_USD = 3.00
MAX_RUNTIME_MINUTES = 480  # 8-Hour Session Limit
