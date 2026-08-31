"""
Technical Indicators Engine for Aegis-BTC.
Computes EMA, RSI, ADX, ATR, and Swing High/Low levels on OHLC candle data.
"""

from typing import List, Dict, Tuple, Optional


def calculate_ema(prices: List[float], period: int) -> List[float]:
    """
    Calculate Exponential Moving Average (EMA) for a given price series and period.
    """
    if not prices or len(prices) < period:
        return [sum(prices) / len(prices) if prices else 0.0] * len(prices)
    
    multiplier = 2.0 / (period + 1)
    ema_values = []
    # Seed with SMA
    sma = sum(prices[:period]) / period
    for i in range(period - 1):
        ema_values.append(sma)
    ema_values.append(sma)
    
    for price in prices[period:]:
        sma = (price - sma) * multiplier + sma
        ema_values.append(sma)
        
    return ema_values


def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """
    Calculate Relative Strength Index (RSI) using Wilder's Smoothing.
    """
    if len(prices) <= period:
        return [50.0] * len(prices)
    
    gains = []
    losses = []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i - 1]
        gains.append(max(0.0, change))
        losses.append(max(0.0, -change))
    
    rsi_values = [50.0] * (period)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0:
        rsi_values.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_values.append(100.0 - (100.0 / (1.0 + rs)))
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100.0 - (100.0 / (1.0 + rs)))
            
    return rsi_values


def calculate_tr_and_atr(candles: List[Dict[str, float]], period: int = 14) -> Tuple[List[float], List[float]]:
    """
    Calculate True Range (TR) and Average True Range (ATR) for candle data.
    Each candle is expected to be a dict with 'high', 'low', 'close'.
    """
    if not candles:
        return [], []
    
    tr_list = []
    for i in range(len(candles)):
        high = candles[i]['high']
        low = candles[i]['low']
        if i == 0:
            tr = high - low
        else:
            prev_close = candles[i - 1]['close']
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
        
    if len(tr_list) < period:
        avg_tr = sum(tr_list) / len(tr_list) if tr_list else 0.0
        return tr_list, [avg_tr] * len(tr_list)
    
    # Wilder's Smoothing for ATR
    atr_values = [sum(tr_list[:period]) / period] * period
    curr_atr = sum(tr_list[:period]) / period
    for i in range(period, len(tr_list)):
        curr_atr = (curr_atr * (period - 1) + tr_list[i]) / period
        atr_values.append(curr_atr)
        
    return tr_list, atr_values


def calculate_adx(candles: List[Dict[str, float]], period: int = 14) -> Tuple[List[float], List[float], List[float]]:
    """
    Calculate ADX, +DI, and -DI for a sequence of candles.
    Returns (adx_list, plus_di_list, minus_di_list).
    """
    if len(candles) < period + 1:
        n = len(candles)
        return [0.0] * n, [0.0] * n, [0.0] * n

    tr_list, atr_list = calculate_tr_and_atr(candles, period)
    
    plus_dm_list = []
    minus_dm_list = []
    
    for i in range(1, len(candles)):
        up_move = candles[i]['high'] - candles[i - 1]['high']
        down_move = candles[i - 1]['low'] - candles[i]['low']
        
        if up_move > down_move and up_move > 0:
            plus_dm_list.append(up_move)
        else:
            plus_dm_list.append(0.0)
            
        if down_move > up_move and down_move > 0:
            minus_dm_list.append(down_move)
        else:
            minus_dm_list.append(0.0)

    # Smooth DM using Wilder's technique
    smooth_plus_dm = [sum(plus_dm_list[:period])]
    smooth_minus_dm = [sum(minus_dm_list[:period])]
    
    for i in range(period, len(plus_dm_list)):
        smooth_plus_dm.append(smooth_plus_dm[-1] - (smooth_plus_dm[-1] / period) + plus_dm_list[i])
        smooth_minus_dm.append(smooth_minus_dm[-1] - (smooth_minus_dm[-1] / period) + minus_dm_list[i])

    plus_di = []
    minus_di = []
    dx = []

    for i in range(len(smooth_plus_dm)):
        idx = i + period
        atr = atr_list[idx] if idx < len(atr_list) else atr_list[-1]
        if atr == 0:
            p_di = 0.0
            m_di = 0.0
        else:
            p_di = 100.0 * (smooth_plus_dm[i] / (atr * period))
            m_di = 100.0 * (smooth_minus_dm[i] / (atr * period))
        
        plus_di.append(p_di)
        minus_di.append(m_di)
        
        di_sum = p_di + m_di
        if di_sum == 0:
            dx.append(0.0)
        else:
            dx.append(100.0 * abs(p_di - m_di) / di_sum)

    # ADX smoothing of DX
    if len(dx) < period:
        adx_short = [sum(dx) / len(dx) if dx else 0.0] * len(candles)
        return adx_short, [0.0] * len(candles), [0.0] * len(candles)

    adx_values = [sum(dx[:period]) / period]
    for i in range(period, len(dx)):
        adx_values.append((adx_values[-1] * (period - 1) + dx[i]) / period)

    # Pad prefix to match candles length
    pad_len = len(candles) - len(adx_values)
    padded_adx = [adx_values[0]] * pad_len + adx_values
    padded_pdi = [plus_di[0]] * pad_len + plus_di
    padded_mdi = [minus_di[0]] * pad_len + minus_di

    return padded_adx, padded_pdi, padded_mdi


def get_swing_levels(candles: List[Dict[str, float]], lookback: int = 20) -> Tuple[float, float]:
    """
    Get swing high (resistance) and swing low (support) over recent lookback candles.
    """
    if not candles:
        return 0.0, 0.0
    
    subset = candles[-lookback:] if len(candles) >= lookback else candles
    highs = [c['high'] for c in subset]
    lows = [c['low'] for c in subset]
    
    return max(highs), min(lows)
