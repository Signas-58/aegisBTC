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
    has_liquidity_sweep: bool,
    key_level_clearance_atr: float,
    close_1m: float,
    ema_20_1m: float,
    rsi_14_1m: float
) -> Tuple[int, Dict[str, Any]]:
    """
    Computes 100-Point Confluence Score for entry validation.
    Returns (total_score, breakdown_dict).
    
    Vectors:
    1. Macro Trend (25 Pts)
    2. Regime Quality (25 Pts)
    3. Liquidity Setup (25 Pts)
    4. Trigger Precision (25 Pts)
    """
    if direction not in (config.CONTRACT_TYPE_UP, config.CONTRACT_TYPE_DOWN):
        return 0, {"error": "Invalid direction"}
        
    score_macro = 0
    score_regime = 0
    score_liquidity = 0
    score_trigger = 0

    # 1. Macro Trend (Max 25 Pts)
    if direction == config.CONTRACT_TYPE_UP and current_price > ema_200_15m:
        score_macro = 25
    elif direction == config.CONTRACT_TYPE_DOWN and current_price < ema_200_15m:
        score_macro = 25

    # 2. Regime Quality (Max 25 Pts)
    if regime == REGIME_TRENDING:
        score_regime = 25
    elif regime == REGIME_CONSOLIDATING and adx_5m >= 18:
        score_regime = 15
    elif regime == REGIME_CONSOLIDATING:
        score_regime = 10

    # 3. Liquidity Setup (Max 25 Pts)
    if has_liquidity_sweep:
        score_liquidity = 25
    elif key_level_clearance_atr >= 1.0:
        score_liquidity = 15
    elif key_level_clearance_atr >= config.PROXIMITY_GUARD_ATR_MULT:
        score_liquidity = 10

    # 4. Trigger Precision (Max 25 Pts)
    if direction == config.CONTRACT_TYPE_UP:
        if close_1m > ema_20_1m and rsi_14_1m > 50.0:
            score_trigger = 25
        elif close_1m > ema_20_1m or rsi_14_1m > 50.0:
            score_trigger = 12
    elif direction == config.CONTRACT_TYPE_DOWN:
        if close_1m < ema_20_1m and rsi_14_1m < 50.0:
            score_trigger = 25
        elif close_1m < ema_20_1m or rsi_14_1m < 50.0:
            score_trigger = 12

    total_score = score_macro + score_regime + score_liquidity + score_trigger
    
    breakdown = {
        "macro_trend": score_macro,
        "regime_quality": score_regime,
        "liquidity_setup": score_liquidity,
        "trigger_precision": score_trigger,
        "total_score": total_score,
        "regime": regime,
        "meets_threshold": total_score >= config.MIN_CONFIDENCE_SCORE
    }
    
    return total_score, breakdown
