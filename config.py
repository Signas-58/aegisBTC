import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==============================================================================
# AEGIS-WELTRADE: AI-ENHANCED MULTI-PROFILE EXECUTION ENGINE CONFIGURATION
# ==============================================================================

# Broker & Account Credentials
WELTRADE_LOGIN = int(os.getenv("WELTRADE_LOGIN", os.getenv("MT5_ACCOUNT", "0"))) if os.getenv("WELTRADE_LOGIN", os.getenv("MT5_ACCOUNT", "")).isdigit() else 0
WELTRADE_PASSWORD = os.getenv("WELTRADE_PASSWORD", os.getenv("MT5_PASSWORD", ""))
WELTRADE_SERVER = os.getenv("WELTRADE_SERVER", os.getenv("MT5_SERVER", "Weltrade-Live"))

# Backwards-compatibility credentials aliases
MT5_ACCOUNT = WELTRADE_LOGIN
MT5_PASSWORD = WELTRADE_PASSWORD
MT5_SERVER = WELTRADE_SERVER

# Target Instrument & Execution Sizing
SYMBOL = os.getenv("SYMBOL", os.getenv("MT5_SYMBOL", "EURUSD"))
MT5_SYMBOL = SYMBOL
LOT_SIZE = float(os.getenv("LOT_SIZE", os.getenv("MT5_VOLUME", "0.01")))
MT5_VOLUME = LOT_SIZE

CONTRACT_TYPE_UP = "BUY"
CONTRACT_TYPE_DOWN = "SELL"

# ------------------------------------------------------------------------------
# MASTER PROFILE SELECTOR
# Options: "SCALP_M1" | "EXPANSION_M5" (Default) | "SILVER_BULLET_PURE"
# ------------------------------------------------------------------------------
ACTIVE_MODE = os.getenv("ACTIVE_MODE", "EXPANSION_M5").upper()
if ACTIVE_MODE not in ("SCALP_M1", "EXPANSION_M5", "SILVER_BULLET_PURE"):
    ACTIVE_MODE = "EXPANSION_M5"

# System Spread & Blackout Settings
MAX_ALLOWED_SPREAD_PIPS = float(os.getenv("MAX_ALLOWED_SPREAD_PIPS", "1.5"))
RELATIVE_SPREAD_MULTIPLIER = float(os.getenv("RELATIVE_SPREAD_MULTIPLIER", "1.5"))  # Max live spread vs 20-MA
ROLLOVER_START = "22:45"       # Central Africa Time (CAT / UTC+2)
ROLLOVER_END = "00:30"         # CAT
FRIDAY_CLOSE_TIME = "21:00"    # CAT Weekend Position Close
FORCE_CLOSE_ROLLOVER = "22:30" # Force close before widening spreads

# Strategy Confluence & Indicators
MIN_CONFIDENCE_SCORE = 80
AI_ENABLED = bool(os.getenv("AI_ENABLED", "True").lower() in ("true", "1", "yes"))
EMA_FAST = 8
EMA_SLOW = 21
EMA_MACRO = 200
ADX_MIN_THRESHOLD = 20.0
FVG_MIN_ATR_RATIO = 0.3
PROXIMITY_GUARD_ATR_MULT = 0.5
MAX_CONSECUTIVE_LOSSES = 4
MAX_RUNTIME_MINUTES = 480

# Telemetry
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ENABLE_TELEGRAM = bool(os.getenv("ENABLE_TELEGRAM", "False").lower() in ("true", "1", "yes"))

# ------------------------------------------------------------------------------
# MULTI-PROFILE ARCHITECTURE SPECIFICATIONS
# ------------------------------------------------------------------------------
PROFILES = {
    # --------------------------------------------------------------------------
    # PROFILE 1: 1-MINUTE MICRO-SCALPER (High Frequency / Tight Risk)
    # --------------------------------------------------------------------------
    "SCALP_M1": {
        "MAGIC_NUMBER": 800826,
        "TF_MACRO": 900,         # 15-Min Macro Trend
        "TF_STRUCTURE": 180,     # 3-Min Structure & FVG Imbalance
        "TF_TRIGGER": 60,        # 1-Min Bar-Close Precision Trigger
        "SILVER_BULLET_WINDOWS_CAT": [
            ("09:00", "12:00"),  # London Session Open Window
            ("15:00", "18:00"),  # NY Session Open Window
        ],
        "HARD_SL_PIPS": 10.0,
        "FIXED_TP_PIPS": 15.0,
        "BE_TRIGGER_PIPS": 6.0,
        "TRAILING_STEP_PIPS": 4.0,
        "TIME_STOP_SECONDS": 1200,      # 20-Minute Stagnation Exit
        "COOLDOWN_SECONDS": 60,         # 1-Minute Cooldown
        "COOLDOWN_AFTER_LOSS_SECONDS": 600, # 10-Minute Loss Quarantine
        "AI_LOOKBACK_CANDLES": 1000,
        "AI_LABEL_HORIZON": 5,          # 5 candles forward (5 mins)
        "AI_LABEL_PIPS": 0.0005,        # 5.0 pips minimum expansion
        "AI_CONFIDENCE_THRESHOLD": 0.70,
        "MAX_DAILY_LOSS_USD": 3.00,
    },

    # --------------------------------------------------------------------------
    # PROFILE 2: 5-MINUTE INTRADAY MOMENTUM EXPANSION (RECOMMENDED DEFAULT)
    # --------------------------------------------------------------------------
    "EXPANSION_M5": {
        "MAGIC_NUMBER": 800827,
        "TF_MACRO": 3600,        # 1-Hour Macro Trend (EMA-200)
        "TF_STRUCTURE": 900,     # 15-Min Structure & FVG Imbalance
        "TF_TRIGGER": 300,       # 5-Min Bar-Close Precision Trigger
        "SILVER_BULLET_WINDOWS_CAT": [
            ("09:00", "12:30"),  # London Expansion Window
            ("14:30", "18:00"),  # NY Expansion Window
        ],
        "HARD_SL_PIPS": 15.0,
        "FIXED_TP_PIPS": 30.0,   # 1:2 Risk/Reward Ratio
        "BE_TRIGGER_PIPS": 12.0,
        "TRAILING_STEP_PIPS": 6.0,
        "TIME_STOP_SECONDS": 2700,      # 45-Minute Stagnation Exit
        "COOLDOWN_SECONDS": 300,        # 5-Minute Post-Trade Cooldown
        "COOLDOWN_AFTER_LOSS_SECONDS": 600, # 10-Minute Loss Quarantine
        "AI_LOOKBACK_CANDLES": 1500,
        "AI_LABEL_HORIZON": 6,          # 6 candles forward (30 mins)
        "AI_LABEL_PIPS": 0.0015,        # 15.0 pips minimum expansion
        "AI_CONFIDENCE_THRESHOLD": 0.68,
        "MAX_DAILY_LOSS_USD": 4.50,
    },

    # --------------------------------------------------------------------------
    # PROFILE 3: STRICT PURE ICT SILVER BULLET (EXACT 60-MINUTE WINDOWS)
    # --------------------------------------------------------------------------
    "SILVER_BULLET_PURE": {
        "MAGIC_NUMBER": 800828,
        "TF_MACRO": 3600,        # 1-Hour Trend & Liquidity Sweeps
        "TF_STRUCTURE": 180,     # 3-Min Structure & FVG Displacement
        "TF_TRIGGER": 180,       # 3-Min Bar-Close Execution Trigger
        "SILVER_BULLET_WINDOWS_CAT": [
            ("10:00", "11:00"),  # London Silver Bullet Window (Exact 60 Mins CAT)
            ("16:00", "17:00"),  # NY AM Silver Bullet Window (Exact 60 Mins CAT)
        ],
        "HARD_SL_PIPS": 12.0,
        "FIXED_TP_PIPS": 24.0,   # 1:2 Risk/Reward Ratio
        "BE_TRIGGER_PIPS": 10.0,
        "TRAILING_STEP_PIPS": 5.0,
        "TIME_STOP_SECONDS": 1800,      # 30-Minute Stagnation Exit
        "COOLDOWN_SECONDS": 300,        # 5-Minute Cooldown
        "COOLDOWN_AFTER_LOSS_SECONDS": 600, # 10-Minute Loss Quarantine
        "AI_LOOKBACK_CANDLES": 1200,
        "AI_LABEL_HORIZON": 5,          # 5 candles forward (15 mins)
        "AI_LABEL_PIPS": 0.0012,        # 12.0 pips minimum expansion
        "AI_CONFIDENCE_THRESHOLD": 0.72,
        "MAX_DAILY_LOSS_USD": 3.60,
    },
}

def set_active_mode(mode: str):
    """Dynamically switch active mode and export parameters."""
    global ACTIVE_MODE, CONFIG
    global MAGIC_NUMBER, TF_MACRO, TF_STRUCTURE, TF_TRIGGER, TF_ENTRY
    global SILVER_BULLET_WINDOWS_CAT, HARD_SL_PIPS, FIXED_TP_PIPS, TP_PIPS
    global BE_TRIGGER_PIPS, TRAILING_STEP_PIPS, TIME_STOP_SECONDS, COOLDOWN_SECONDS
    global COOLDOWN_AFTER_WIN_SECONDS, COOLDOWN_AFTER_LOSS_SECONDS
    global AI_LOOKBACK_CANDLES, AI_LABEL_HORIZON, AI_LABEL_PIPS, AI_CONFIDENCE_THRESHOLD
    global MAX_DAILY_LOSS_USD, HARD_STOP_LOSS_USD, BREAK_EVEN_TRIGGER, TRAILING_STEP_USD
    global TRAILING_GAP_USD, TAKE_PROFIT_LOT_MULT

    mode_upper = mode.upper()
    if mode_upper in PROFILES:
        ACTIVE_MODE = mode_upper
    CONFIG = PROFILES[ACTIVE_MODE]

    # Export dynamic profile variables
    MAGIC_NUMBER = CONFIG["MAGIC_NUMBER"]
    TF_MACRO = CONFIG["TF_MACRO"]
    TF_STRUCTURE = CONFIG["TF_STRUCTURE"]
    TF_TRIGGER = CONFIG["TF_TRIGGER"]
    TF_ENTRY = CONFIG["TF_STRUCTURE"]
    SILVER_BULLET_WINDOWS_CAT = CONFIG["SILVER_BULLET_WINDOWS_CAT"]
    HARD_SL_PIPS = CONFIG["HARD_SL_PIPS"]
    FIXED_TP_PIPS = CONFIG["FIXED_TP_PIPS"]
    TP_PIPS = FIXED_TP_PIPS
    BE_TRIGGER_PIPS = CONFIG["BE_TRIGGER_PIPS"]
    TRAILING_STEP_PIPS = CONFIG["TRAILING_STEP_PIPS"]
    TIME_STOP_SECONDS = CONFIG["TIME_STOP_SECONDS"]
    COOLDOWN_SECONDS = CONFIG["COOLDOWN_SECONDS"]
    COOLDOWN_AFTER_WIN_SECONDS = COOLDOWN_SECONDS
    COOLDOWN_AFTER_LOSS_SECONDS = CONFIG.get("COOLDOWN_AFTER_LOSS_SECONDS", 600)
    AI_LOOKBACK_CANDLES = CONFIG["AI_LOOKBACK_CANDLES"]
    AI_LABEL_HORIZON = CONFIG["AI_LABEL_HORIZON"]
    AI_LABEL_PIPS = CONFIG["AI_LABEL_PIPS"]
    AI_CONFIDENCE_THRESHOLD = CONFIG["AI_CONFIDENCE_THRESHOLD"]
    MAX_DAILY_LOSS_USD = CONFIG["MAX_DAILY_LOSS_USD"]

    # Dollar Equivalents (1 pip on 0.01 lot EURUSD = $0.10)
    HARD_STOP_LOSS_USD = HARD_SL_PIPS * LOT_SIZE * 10.0
    BREAK_EVEN_TRIGGER = BE_TRIGGER_PIPS * LOT_SIZE * 10.0
    TRAILING_STEP_USD = TRAILING_STEP_PIPS * LOT_SIZE * 10.0
    TRAILING_GAP_USD = TRAILING_STEP_USD
    TAKE_PROFIT_LOT_MULT = FIXED_TP_PIPS * 10.0

# Initialize with selected ACTIVE_MODE
set_active_mode(ACTIVE_MODE)
STRICT_SILVER_BULLET_GATE = True
STRATEGY_MODE = ACTIVE_MODE

# Deriv API compatibility fallbacks
APP_ID = os.getenv("DERIV_APP_ID", "1089")
API_TOKEN = os.getenv("DERIV_API_TOKEN", os.getenv("DERIV_TOKEN", ""))
DERIV_ACCOUNT_ID = os.getenv("DERIV_ACCOUNT_ID", "DOT93113459")
STAKE = 1.00
MULTIPLIER_LEVERAGE = 100
