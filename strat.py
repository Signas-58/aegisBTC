"""
Strategy & Proximity Guard Engine for Aegis-BTC.
Evaluates Multi-Timeframe candles, computes dynamic ATR proximity buffers,
detects liquidity sweeps, and produces signal proposals.
"""

from typing import List, Dict, Any, Tuple
import config
from indicators import (
    calculate_ema, calculate_rsi, calculate_tr_and_atr,
    calculate_adx, get_swing_levels
)
from intelligence import (
    classify_market_regime, calculate_intelligence_score,
    REGIME_HIGH_RISK
)


from datetime import datetime, timezone, timedelta

def is_in_silver_bullet_window(dt: datetime = None) -> bool:
    """
    Check if the given datetime falls within active ICT Silver Bullet windows in Central Africa Time (CAT / UTC+2).
    Default dt is current UTC time converted to CAT.
    """
    if dt is None:
        dt = datetime.now(timezone.utc) + timedelta(hours=2)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc) + timedelta(hours=2)
    else:
        dt = dt.astimezone(timezone(timedelta(hours=2)))

    time_str = dt.strftime("%H:%M")
    
    for start_str, end_str in config.SILVER_BULLET_WINDOWS_CAT:
        if start_str <= time_str < end_str:
            return True
            
    return False


def detect_3m_fvg(
    candles_3m: List[Dict[str, float]],
    direction: str,
    atr_3m: float = 0.0
) -> Tuple[bool, float]:
    """
    Detect 3-minute Fair Value Gap (FVG) imbalance formation:
    - Bullish 3m FVG: 3m_Low[i] > 3m_High[i-2] with displacement candle at i-1.
    - Bearish 3m FVG: 3m_High[i] < 3m_Low[i-2] with displacement candle at i-1.
    Returns (has_fvg, gap_size).
    """
    if not candles_3m or len(candles_3m) < 3:
        return False, 0.0

    current_price = candles_3m[-1]['close']
    min_gap_size = atr_3m * config.FVG_MIN_ATR_RATIO if atr_3m > 0 else 0.0

    # Scan recent candles for active / retesting FVG zone
    lookback = min(5, len(candles_3m) - 2)
    
    for idx in range(len(candles_3m) - 1, len(candles_3m) - 1 - lookback, -1):
        if idx < 2:
            break
            
        c_prev2 = candles_3m[idx - 2]
        c_disp = candles_3m[idx - 1]
        c_curr = candles_3m[idx]

        if direction == config.CONTRACT_TYPE_UP:
            if c_curr['low'] > c_prev2['high']:
                gap_size = c_curr['low'] - c_prev2['high']
                if c_disp['close'] > c_disp['open'] and gap_size >= min_gap_size:
                    if current_price >= c_prev2['high']:
                        return True, gap_size

        elif direction == config.CONTRACT_TYPE_DOWN:
            if c_curr['high'] < c_prev2['low']:
                gap_size = c_prev2['low'] - c_curr['high']
                if c_disp['close'] < c_disp['open'] and gap_size >= min_gap_size:
                    if current_price <= c_prev2['low']:
                        return True, gap_size

    return False, 0.0


def check_dynamic_proximity_guard(
    current_price: float,
    htf_resistance: float,
    htf_support: float,
    atr_5m: float,
    direction: str
) -> Tuple[bool, float]:
    """
    BTC Dynamic ATR Proximity Guard:
    proximity_buffer = atr_5m * PROXIMITY_GUARD_ATR_MULT
    - Block MULTUP if (htf_resistance - current_price) < proximity_buffer
    - Block MULTDOWN if (current_price - htf_support) < proximity_buffer
    Returns (is_allowed, clearance_in_atr_units).
    """
    buffer = atr_5m * config.PROXIMITY_GUARD_ATR_MULT
    
    if direction == config.CONTRACT_TYPE_UP:
        distance_to_res = htf_resistance - current_price
        clearance_atr = distance_to_res / atr_5m if atr_5m > 0 else 0.0
        if distance_to_res < buffer:
            return False, clearance_atr
        return True, clearance_atr
        
    elif direction == config.CONTRACT_TYPE_DOWN:
        distance_to_sup = current_price - htf_support
        clearance_atr = distance_to_sup / atr_5m if atr_5m > 0 else 0.0
        if distance_to_sup < buffer:
            return False, clearance_atr
        return True, clearance_atr
        
    return False, 0.0


def detect_liquidity_sweep(
    candles_5m: List[Dict[str, float]],
    htf_resistance: float,
    htf_support: float,
    direction: str
) -> bool:
    """
    Detect 5-minute liquidity sweeps (wicks extending past 15m key levels with rejection closes).
    - For MULTUP: Candle low dipped below htf_support but close is above support (bullish liquidity grab).
    - For MULTDOWN: Candle high spiked above htf_resistance but close is below resistance (bearish liquidity grab).
    """
    if not candles_5m:
        return False
        
    last_candle = candles_5m[-1]
    
    if direction == config.CONTRACT_TYPE_UP:
        if last_candle['low'] <= htf_support and last_candle['close'] > htf_support:
            return True
            
    elif direction == config.CONTRACT_TYPE_DOWN:
        if last_candle['high'] >= htf_resistance and last_candle['close'] < htf_resistance:
            return True
            
    return False


def analyze_market_and_generate_signal(
    candles_15m: List[Dict[str, float]],
    candles_5m: List[Dict[str, float]],
    candles_1m: List[Dict[str, float]],
    candles_3m: List[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Main MTF Analysis Entry Point for Aegis-BTC Hybrid.
    Processes 15m (Macro), 5m (Structure/Regime), 3m (FVG/Execution), 1m (Trigger) candles.
    Returns signal dict.
    """
    no_signal_res = {
        "signal": "NO_SIGNAL",
        "confidence_score": 0,
        "reason": "Insufficient candle data",
        "breakdown": {},
        "current_price": 0.0,
        "regime": "UNKNOWN",
        "atr_5m": 0.0,
        "in_silver_bullet": False
    }
    
    if len(candles_15m) < 20 or len(candles_5m) < 20 or len(candles_1m) < 20:
        return no_signal_res

    if candles_3m is None:
        candles_3m = candles_5m

    current_price = candles_1m[-1]['close']
    in_sb = is_in_silver_bullet_window()

    # 1. 15m Macro Stream Analysis
    closes_15m = [c['close'] for c in candles_15m]
    ema_200_15m_list = calculate_ema(closes_15m, 200)
    ema_200_15m = ema_200_15m_list[-1]
    htf_resistance, htf_support = get_swing_levels(candles_15m, 20)

    # 2. 5m Structure & Regime Analysis
    adx_5m_list, pdi_5m, mdi_5m = calculate_adx(candles_5m, 14)
    adx_5m = adx_5m_list[-1]
    adx_slope_5m = adx_5m_list[-1] - adx_5m_list[-2] if len(adx_5m_list) >= 2 else 0.0
    
    _, atr_5m_list = calculate_tr_and_atr(candles_5m, 14)
    atr_5m = atr_5m_list[-1]
    avg_atr_5m = sum(atr_5m_list[-10:]) / 10 if len(atr_5m_list) >= 10 else atr_5m
    atr_ratio_5m = (atr_5m / avg_atr_5m) if avg_atr_5m > 0 else 1.0

    regime = classify_market_regime(adx_5m, adx_slope_5m, atr_ratio_5m)
    
    if regime == REGIME_HIGH_RISK:
        return {
            "signal": "NO_SIGNAL",
            "confidence_score": 0,
            "reason": f"REGIME_HIGH_RISK detected (ATR ratio: {atr_ratio_5m:.2f} > 1.8)",
            "breakdown": {},
            "current_price": current_price,
            "regime": regime,
            "atr_5m": atr_5m,
            "in_silver_bullet": in_sb
        }

    # 3. 3m ATR & FVG Analysis
    _, atr_3m_list = calculate_tr_and_atr(candles_3m, 14)
    atr_3m = atr_3m_list[-1] if atr_3m_list else atr_5m

    # 4. 1m Trigger Analysis
    closes_1m = [c['close'] for c in candles_1m]
    ema_20_1m_list = calculate_ema(closes_1m, 20)
    ema_20_1m = ema_20_1m_list[-1]
    rsi_14_1m_list = calculate_rsi(closes_1m, 14)
    rsi_14_1m = rsi_14_1m_list[-1]
    close_1m = closes_1m[-1]

    # Evaluate potential signals for MULTUP and MULTDOWN
    potential_signals = []
    
    for candidate_dir in [config.CONTRACT_TYPE_UP, config.CONTRACT_TYPE_DOWN]:
        allowed, clearance_atr = check_dynamic_proximity_guard(
            current_price, htf_resistance, htf_support, atr_5m, candidate_dir
        )
        if not allowed:
            continue
            
        has_sweep = detect_liquidity_sweep(candles_5m, htf_resistance, htf_support, candidate_dir)
        has_fvg, gap_size = detect_3m_fvg(candles_3m, candidate_dir, atr_3m)

        score, breakdown = calculate_intelligence_score(
            direction=candidate_dir,
            current_price=current_price,
            ema_200_15m=ema_200_15m,
            regime=regime,
            adx_5m=adx_5m,
            atr_ratio_5m=atr_ratio_5m,
            has_liquidity_sweep=has_sweep,
            has_fvg=has_fvg,
            in_silver_bullet=in_sb,
            key_level_clearance_atr=clearance_atr,
            close_1m=close_1m,
            ema_20_1m=ema_20_1m,
            rsi_14_1m=rsi_14_1m
        )
        
        if score >= config.MIN_CONFIDENCE_SCORE:
            potential_signals.append({
                "signal": candidate_dir,
                "confidence_score": score,
                "breakdown": breakdown,
                "reason": f"MTF Hybrid Score {score}% >= {config.MIN_CONFIDENCE_SCORE}% ({candidate_dir})"
            })

    if not potential_signals:
        return {
            "signal": "NO_SIGNAL",
            "confidence_score": 0,
            "reason": f"No directional setup met confidence threshold ({config.MIN_CONFIDENCE_SCORE}%)",
            "breakdown": {},
            "current_price": current_price,
            "regime": regime,
            "atr_5m": atr_5m,
            "in_silver_bullet": in_sb
        }

    best_signal = max(potential_signals, key=lambda s: s['confidence_score'])
    best_signal["current_price"] = current_price
    best_signal["regime"] = regime
    best_signal["atr_5m"] = atr_5m
    best_signal["in_silver_bullet"] = in_sb

    return best_signal

