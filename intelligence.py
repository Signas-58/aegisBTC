"""
Market Regime & Intelligence Scoring Engine for Aegis-BTC.
Evaluates market conditions using a 100-point probability scoring matrix across MTF streams.
"""

from typing import Dict, Any, Tuple
import config

REGIME_TRENDING = "REGIME_TRENDING"
REGIME_CONSOLIDATING = "REGIME_CONSOLIDATING"
REGIME_HIGH_RISK = "REGIME_HIGH_RISK"


def classify_market_regime(adx_5m: float, adx_slope_5m: float, atr_ratio_5m: float) -> str:
    """
    Classify the market regime based on 5m ADX, ADX slope, and ATR volatility ratio.
    - REGIME_HIGH_RISK: ATR ratio > 1.8 (Extreme volatility spikes)
    - REGIME_TRENDING: ADX >= 20 and ADX slope > 0
    - REGIME_CONSOLIDATING: ADX < 20 and ATR ratio <= 1.0 (or fallback)
    """
    if atr_ratio_5m > 1.8:
        return REGIME_HIGH_RISK
    if adx_5m >= config.ADX_MIN_THRESHOLD and adx_slope_5m > 0:
        return REGIME_TRENDING
    return REGIME_CONSOLIDATING


def calculate_intelligence_score(
    direction: str,
    current_price: float,
    ema_200_15m: float,
    regime: str,
    adx_5m: float,
    atr_ratio_5m: float,
    has_liquidity_sweep: bool,
    has_fvg: bool,
    in_silver_bullet: bool,
    key_level_clearance_atr: float,
    close_1m: float,
    ema_20_1m: float,
    rsi_14_1m: float
) -> Tuple[int, Dict[str, Any]]:
    """
    Computes 100-Point Confluence Score for Aegis-BTC Hybrid (ICT Silver Bullet + Dynamic Step Engine).
    Returns (total_score, breakdown_dict).
    
    5 Scoring Vectors (Total 100 Pts):
    1. HTF Macro Bias (20 Pts): Price > 15m EMA-200 (MULTUP) / Price < 15m EMA-200 (MULTDOWN)
    2. Regime Quality (20 Pts): 5m ADX >= 20 and ATR Ratio <= 1.5
    3. Liquidity Sweep + FVG (25 Pts): 5m Sweep + 3m FVG Displacement
    4. Silver Bullet Window (20 Pts): CAT session time window active
    5. 1m Trigger Precision (15 Pts): 1m Close vs EMA-20 & RSI-14 >/< 50
    """
    if direction not in (config.CONTRACT_TYPE_UP, config.CONTRACT_TYPE_DOWN):
        return 0, {"error": "Invalid direction"}

    # Strict Silver Bullet Gate Check
    if config.STRICT_SILVER_BULLET_GATE and not in_silver_bullet:
        return 0, {
            "macro_bias": 0,
            "regime_quality": 0,
            "liquidity_fvg": 0,
            "silver_bullet": 0,
            "trigger_precision": 0,
            "total_score": 0,
            "regime": regime,
            "in_silver_bullet": False,
            "meets_threshold": False,
            "gate_reason": "STRICT_SILVER_BULLET_GATE: Blocked outside Silver Bullet window"
        }

    score_macro = 0
    score_regime = 0
    score_liquidity_fvg = 0
    score_sb = 0
    score_trigger = 0

    # 1. HTF Macro Bias (Max 20 Pts)
    if direction == config.CONTRACT_TYPE_UP and current_price > ema_200_15m:
        score_macro = 20
    elif direction == config.CONTRACT_TYPE_DOWN and current_price < ema_200_15m:
        score_macro = 20

    # 2. Regime Quality (Max 20 Pts)
    if adx_5m >= config.ADX_MIN_THRESHOLD and atr_ratio_5m <= 1.5:
        score_regime = 20
    elif adx_5m >= 18 and atr_ratio_5m <= 1.7:
        score_regime = 10
    elif regime == REGIME_TRENDING:
        score_regime = 12

    # 3. Liquidity Sweep + 3m FVG (Max 25 Pts)
    if has_liquidity_sweep and has_fvg:
        score_liquidity_fvg = 25
    elif has_liquidity_sweep:
        score_liquidity_fvg = 18
    elif has_fvg:
        score_liquidity_fvg = 15
    elif key_level_clearance_atr >= 1.0:
        score_liquidity_fvg = 10

    # 4. Silver Bullet Window (Max 20 Pts)
    if in_silver_bullet:
        score_sb = 20

    # 5. 1m Trigger Precision (Max 15 Pts)
    if direction == config.CONTRACT_TYPE_UP:
        if close_1m > ema_20_1m and rsi_14_1m > 50.0:
            score_trigger = 15
        elif close_1m > ema_20_1m or rsi_14_1m > 50.0:
            score_trigger = 8
    elif direction == config.CONTRACT_TYPE_DOWN:
        if close_1m < ema_20_1m and rsi_14_1m < 50.0:
            score_trigger = 15
        elif close_1m < ema_20_1m or rsi_14_1m < 50.0:
            score_trigger = 8

    total_score = score_macro + score_regime + score_liquidity_fvg + score_sb + score_trigger

    breakdown = {
        "macro_bias": score_macro,
        "regime_quality": score_regime,
        "liquidity_fvg": score_liquidity_fvg,
        "silver_bullet": score_sb,
        "trigger_precision": score_trigger,
        "total_score": total_score,
        "regime": regime,
        "in_silver_bullet": in_silver_bullet,
        "has_liquidity_sweep": has_liquidity_sweep,
        "has_fvg": has_fvg,
        "meets_threshold": total_score >= config.MIN_CONFIDENCE_SCORE
    }

    return total_score, breakdown

