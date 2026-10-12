"""
Strategy & Confluence Scoring Matrix for Aegis Multi-Profile Engine.
Evaluates multi-timeframe candle structure strictly on completed bars (index [-2]):
1. Macro Trend Alignment (25 Pts)
2. Structure & FVG Imbalance (25 Pts)
3. Trigger Chart EMA Alignment/Crossover (25 Pts)
4. Momentum & Acceleration (ADX + Volume) (25 Pts)
Enforces strict session time-gates and AI market regime validation.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple, Optional

import config
from indicators import (
    calculate_ema, calculate_rsi, calculate_tr_and_atr,
    calculate_adx, get_swing_levels
)

logger = logging.getLogger("AegisBTC.Strategy")


def is_in_session_window(dt: Optional[datetime] = None) -> bool:
    """
    Check if the current time falls within active profile's session windows in CAT (UTC+2).
    """
    if dt is None:
        dt = datetime.now(timezone.utc) + timedelta(hours=2)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc) + timedelta(hours=2)
    else:
        dt = dt.astimezone(timezone(timedelta(hours=2)))

    time_str = dt.strftime("%H:%M")
    windows = getattr(config, "SILVER_BULLET_WINDOWS_CAT", [("09:00", "18:00")])

    for start_str, end_str in windows:
        if start_str <= time_str < end_str:
            return True
    return False


def detect_fvg(
    candles_structure: List[Dict[str, float]],
    direction: str,
    atr_val: float = 0.0
) -> Tuple[bool, float]:
    """
    Detect Fair Value Gap (FVG) imbalance formation strictly on closed candles:
    - Bullish FVG: Low[i] > High[i-2] with strong displacement candle at i-1.
    - Bearish FVG: High[i] < Low[i-2] with strong displacement candle at i-1.
    Returns (has_fvg, gap_size).
    """
    if not candles_structure or len(candles_structure) < 4:
        return False, 0.0

    current_price = candles_structure[-1]['close']
    min_gap_size = atr_val * config.FVG_MIN_ATR_RATIO if atr_val > 0 else 0.0

    lookback = min(6, len(candles_structure) - 2)
    for idx in range(len(candles_structure) - 2, len(candles_structure) - 2 - lookback, -1):
        if idx < 2:
            break

        c_prev2 = candles_structure[idx - 2]
        c_disp = candles_structure[idx - 1]
        c_curr = candles_structure[idx]

        is_buy = direction.upper() in ("BUY", "MULTUP")
        if is_buy:
            if c_curr['low'] > c_prev2['high']:
                gap_size = c_curr['low'] - c_prev2['high']
                if c_disp['close'] > c_disp['open'] and gap_size >= min_gap_size:
                    if current_price >= c_prev2['high']:
                        return True, gap_size
        else:
            if c_curr['high'] < c_prev2['low']:
                gap_size = c_prev2['low'] - c_curr['high']
                if c_disp['close'] < c_disp['open'] and gap_size >= min_gap_size:
                    if current_price <= c_prev2['low']:
                        return True, gap_size

    return False, 0.0


def evaluate_confluence_proposal(
    macro_candles: List[Dict[str, float]],
    structure_candles: List[Dict[str, float]],
    trigger_candles: List[Dict[str, float]],
    ai_confidence: float = 1.0
) -> Optional[Dict[str, Any]]:
    """
    Evaluates 100-point confluence scoring matrix on completed bar [-2].
    Requires Total Score >= MIN_CONFIDENCE_SCORE (80) AND AI Confidence >= AI_CONFIDENCE_THRESHOLD.
    """
    # 0. Session Gate Filter
    if not is_in_session_window():
        return None

    if len(macro_candles) < 30 or len(structure_candles) < 20 or len(trigger_candles) < 25:
        return None

    # Evaluate on completed bar [-2]
    c_macro_closed = macro_candles[-2]
    c_struct_closed = structure_candles[-2]
    c_trig_closed = trigger_candles[-2]
    live_trig = trigger_candles[-1]

    # Pre-calculate indicator arrays
    macro_closes = [c['close'] for c in macro_candles]
    struct_closes = [c['close'] for c in structure_candles]
    trig_closes = [c['close'] for c in trigger_candles]

    macro_ema200 = calculate_ema(macro_closes, min(len(macro_closes), config.EMA_MACRO))
    struct_tr, struct_atr = calculate_tr_and_atr(structure_candles, 14)
    atr_struct_val = struct_atr[-2] if len(struct_atr) >= 2 else 0.0005

    trig_ema_fast = calculate_ema(trig_closes, config.EMA_FAST)
    trig_ema_slow = calculate_ema(trig_closes, config.EMA_SLOW)
    trig_adx = calculate_adx(trigger_candles, 14)

    # Check candidates for both BUY and SELL
    for candidate_dir in ["BUY", "SELL"]:
        score = 0
        reasons = []
        is_buy = (candidate_dir == "BUY")

        # 1. Macro Trend Alignment (25 Points)
        macro_ma_val = macro_ema200[-2] if len(macro_ema200) >= 2 else c_macro_closed['close']
        if is_buy and c_macro_closed['close'] > macro_ma_val:
            score += 25
            reasons.append("Macro Trend Bullish (> EMA-200)")
        elif (not is_buy) and c_macro_closed['close'] < macro_ma_val:
            score += 25
            reasons.append("Macro Trend Bearish (< EMA-200)")
        else:
            continue  # Must align with macro trend

        # 2. Structure & FVG Imbalance (25 Points)
        has_fvg, gap_size = detect_fvg(structure_candles, candidate_dir, atr_struct_val)
        if has_fvg:
            score += 25
            reasons.append(f"Structure FVG Imbalance Confirmed ({gap_size:.5f})")
        else:
            # Check swing structure alignment if FVG not active
            swing_high, swing_low = get_swing_levels(structure_candles, 10)
            if is_buy and c_struct_closed['close'] > (swing_high + swing_low) / 2:
                score += 15
                reasons.append("Structure Bullish Half-Range")
            elif (not is_buy) and c_struct_closed['close'] < (swing_high + swing_low) / 2:
                score += 15
                reasons.append("Structure Bearish Half-Range")

        # 3. Trigger Chart EMA Alignment / Crossover (25 Points)
        fast_now = trig_ema_fast[-2]
        slow_now = trig_ema_slow[-2]
        fast_prev = trig_ema_fast[-3] if len(trig_ema_fast) >= 3 else fast_now
        slow_prev = trig_ema_slow[-3] if len(trig_ema_slow) >= 3 else slow_now

        has_cross = (fast_prev <= slow_prev and fast_now > slow_now) if is_buy else (fast_prev >= slow_prev and fast_now < slow_now)
        aligned = (fast_now > slow_now) if is_buy else (fast_now < slow_now)

        if has_cross:
            score += 25
            reasons.append(f"Trigger EMA Fresh Cross ({config.EMA_FAST}/{config.EMA_SLOW})")
        elif aligned:
            score += 20
            reasons.append(f"Trigger EMA Aligned ({config.EMA_FAST}/{config.EMA_SLOW})")

        # 4. Momentum & Acceleration (25 Points)
        if len(trig_adx) >= 4:
            adx_val = trig_adx[-2]
            adx_prev = trig_adx[-3]
            adx_prev2 = trig_adx[-4]
            adx_slope_pos = (adx_val > adx_prev >= adx_prev2)

            if adx_val >= config.ADX_MIN_THRESHOLD and adx_slope_pos:
                score += 25
                reasons.append(f"Momentum ADX Strong & Accelerating ({adx_val:.1f})")
            elif adx_val >= config.ADX_MIN_THRESHOLD:
                score += 15
                reasons.append(f"Momentum ADX Strong ({adx_val:.1f})")

        # 5. Volume Confirmation Check
        if "volume" in c_trig_closed and len(trigger_candles) >= 22:
            vol_history = [c['volume'] for c in trigger_candles[-22:-2]]
            vol_mean = sum(vol_history) / len(vol_history) if vol_history else 0.0
            if c_trig_closed['volume'] > vol_mean * 1.1:
                score += 5
                reasons.append("Volume Above 20-MA")

        # Cap score at 100
        score = min(100, score)

        # 6. Confluence Gate Filter
        if score >= config.MIN_CONFIDENCE_SCORE:
            # AI Regime Gate
            ai_thresh = getattr(config, "AI_CONFIDENCE_THRESHOLD", 0.68)
            if ai_confidence < ai_thresh:
                logger.info(
                    f"⚠️ [TRADE BLOCKED BY AI] Confluence: {score}/100 {candidate_dir} | "
                    f"AI Expansion: {ai_confidence:.2f} < Threshold {ai_thresh:.2f}"
                )
                continue

            entry_price = live_trig['close']
            pip_unit = 0.0001 if ("EUR" in config.SYMBOL.upper() or "USD" in config.SYMBOL.upper()) else 0.01

            sl_pips = config.HARD_SL_PIPS
            tp_pips = config.FIXED_TP_PIPS

            sl_price = entry_price - (sl_pips * pip_unit) if is_buy else entry_price + (sl_pips * pip_unit)
            tp_price = entry_price + (tp_pips * pip_unit) if is_buy else entry_price - (tp_pips * pip_unit)

            return {
                "action": candidate_dir,
                "confidence_score": score,
                "ai_confidence": ai_confidence,
                "entry_price": entry_price,
                "sl_price": round(sl_price, 5),
                "tp_price": round(tp_price, 5),
                "sl_pips": sl_pips,
                "tp_pips": tp_pips,
                "reasons": reasons,
                "profile": config.ACTIVE_MODE
            }

    return None
