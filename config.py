import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==============================================================================
# AEGIS-WELTRADE: EURUSD HIGH-WIN-RATE MASTER ENGINE CONFIGURATION
# ==============================================================================

# Account Credentials & Server
WELTRADE_LOGIN = int(os.getenv("WELTRADE_LOGIN", os.getenv("MT5_ACCOUNT", "0"))) if os.getenv("WELTRADE_LOGIN", os.getenv("MT5_ACCOUNT", "")).isdigit() else 0
WELTRADE_PASSWORD = os.getenv("WELTRADE_PASSWORD", os.getenv("MT5_PASSWORD", ""))
WELTRADE_SERVER = os.getenv("WELTRADE_SERVER", os.getenv("MT5_SERVER", "Weltrade-Live"))

# Backwards-compatibility aliases
MT5_ACCOUNT = WELTRADE_LOGIN
MT5_PASSWORD = WELTRADE_PASSWORD
MT5_SERVER = WELTRADE_SERVER

# Asset & Execution Parameters
SYMBOL = os.getenv("SYMBOL", os.getenv("MT5_SYMBOL", "EURUSD"))
MT5_SYMBOL = SYMBOL
LOT_SIZE = float(os.getenv("LOT_SIZE", os.getenv("MT5_VOLUME", "0.01")))
MT5_VOLUME = LOT_SIZE
MAGIC_NUMBER = int(os.getenv("MAGIC_NUMBER", "800826"))
MAX_ALLOWED_SPREAD_PIPS = float(os.getenv("MAX_ALLOWED_SPREAD_PIPS", "1.2"))  # Reject trades if spread exceeds 1.2 pips

CONTRACT_TYPE_UP = "BUY"
CONTRACT_TYPE_DOWN = "SELL"

# Timeframes
TF_MACRO = 900    # 15-Min Macro Horizon
TF_ENTRY = 180    # 3-Min Structure & FVG Horizon
TF_TRIGGER = 60   # 1-Min Bar-Close Execution Trigger
TF_STRUCTURE = 300 # 5-Min Supporting Structure Horizon

# Strategy Execution Mode
STRATEGY_MODE = os.getenv("STRATEGY_MODE", "EURUSD_MASTER").upper()

# Session Time Gates (Central Africa Time / CAT - UTC+2)
SILVER_BULLET_WINDOWS_CAT = [
    ("09:00", "12:00"),  # London Session Open Window
    ("15:00", "18:00"),  # New York Session Open Window
]
STRICT_SILVER_BULLET_GATE = True  # Strict gate: Only execute during high-volume institutional windows

# Strategy Indicators & Confluence Thresholds
MIN_CONFIDENCE_SCORE = 80  # Minimum 80/100 confluence required to enter
EMA_FAST = 8
EMA_SLOW = 21
EMA_MACRO = 200
ADX_MIN_THRESHOLD = 22.0
FVG_MIN_ATR_RATIO = 0.3
PROXIMITY_GUARD_ATR_MULT = 0.5

# Risk Engine & Micro Ratchet (EURUSD Pip Math: 1 pip = 0.0001; on 0.01 lot, 1 pip = $0.10)
HARD_SL_PIPS = 10.0         # 10.0 pips = $1.00 max risk per 0.01 lot
BE_TRIGGER_PIPS = 6.0       # Move SL to Entry ($0.00 risk) at +6.0 pips (+$0.60 profit)
TRAILING_STEP_PIPS = 4.0    # Ratchet SL forward every +4.0 pips (+$0.40)
TRAILING_GAP_PIPS = 4.0     # 4.0 pips trailing offset behind peak
TP_PIPS = 20.0              # 20.0 pips target ($2.00 target on 0.01 lot)

# Dollar Equivalence for Engine Ratchet
HARD_STOP_LOSS_USD = 1.00   # $1.00 max risk per 0.01 lot (10 pips)
BREAK_EVEN_TRIGGER = 0.60   # Shift SL to Break-Even at +$0.60 PnL (6 pips)
TRAILING_STEP_USD = 0.40    # Ratchet step $0.40 (4 pips)
TRAILING_GAP_USD = 0.40     # Trailing gap $0.40 (4 pips)
TAKE_PROFIT_LOT_MULT = 200.0 # $2.00 TP target for 0.01 lot (20 pips)

# Safety Safeguards, Time-Stops & Cooldowns
TIME_STOP_SECONDS = 1200    # 20-minute exit for stagnant trades if PnL >= 0
COOLDOWN_SECONDS = 60       # Minimum 60-second delay between trades
COOLDOWN_AFTER_WIN_SECONDS = 60
COOLDOWN_AFTER_LOSS_SECONDS = 600  # 10-Minute Loss Quarantine
MAX_CONSECUTIVE_LOSSES = 4
MAX_DAILY_LOSS_USD = 3.00   # Daily kill switch threshold ($3.00 max daily loss)
MAX_RUNTIME_MINUTES = 480   # 8-Hour Session Limit

# Deriv API compatibility fallbacks
APP_ID = os.getenv("DERIV_APP_ID", "1089")
API_TOKEN = os.getenv("DERIV_API_TOKEN", os.getenv("DERIV_TOKEN", ""))
DERIV_ACCOUNT_ID = os.getenv("DERIV_ACCOUNT_ID", "DOT93113459")
STAKE = 1.00
MULTIPLIER_LEVERAGE = 100
