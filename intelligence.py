import pandas as pd
import numpy as np
import logging
from typing import Tuple, Dict, Any

logger = logging.getLogger("IntelligenceEngine")

def calculate_atr_14(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates 14-period Average True Range (ATR) on OHLC candles.
    """
    if df.empty or len(df) < 15:
        return df

    df = df.copy()
    high = df["high"]
    low = df["low"]
    close = df["close"]
    close_prev = close.shift(1)

    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Wilder's Smoothing RMA for ATR
    alpha = 1 / 14
    df["atr_14"] = tr.ewm(alpha=alpha, adjust=False).mean()
    return df

def classify_market_regime(df_5m: pd.DataFrame) -> Tuple[str, float, float]:
    """
    Classifies the 5m market state into:
    - REGIME_HIGH_RISK (ATR ratio > 1.8)
    - REGIME_TRENDING (ADX >= 20 and ADX Slope > 0)
    - REGIME_CONSOLIDATING (ADX < 20 and ATR ratio <= 1.0)
    - REGIME_NORMAL (Default fallback)
    Returns (regime_name, adx_value, atr_ratio).
    """
    if df_5m.empty or len(df_5m) < 55:
        return "REGIME_NORMAL", 18.0, 1.0

    # Calculate ATR-14
    df = calculate_atr_14(df_5m)
    
    # Calculate ATR Ratio: Current ATR / Baseline ATR (SMA-50 of ATR)
    df["atr_baseline"] = df["atr_14"].rolling(window=50).mean()
    
    # Get last completed values (index -2) to prevent repainting
    current_atr = df["atr_14"].values[-2]
    baseline_atr = df["atr_baseline"].values[-2] if not pd.isna(df["atr_baseline"].values[-2]) else 1e-9
    atr_ratio = current_atr / baseline_atr

    # Calculate ADX-14
    # If adx_14 is already calculated by strat.py, use it; otherwise compute it.
    if "adx_14" in df.columns:
        adx_values = df["adx_14"].values
    else:
        # Import local ADX helper
        import strat
        df = strat.calculate_5m_indicators(df)
        adx_values = df["adx_14"].values

    adx_value = adx_values[-2]
    prev_adx = adx_values[-3]
    adx_slope = adx_value - prev_adx

    # 1. High Risk Check (Volatility spikes / Chaotic noise)
    if atr_ratio > 1.8:
        return "REGIME_HIGH_RISK", adx_value, atr_ratio

    # 2. Trending Regime Check
    if adx_value >= 20 and adx_slope > 0:
        return "REGIME_TRENDING", adx_value, atr_ratio

    # 3. Consolidating Regime Check
    if adx_value < 20 and atr_ratio <= 1.0:
        return "REGIME_CONSOLIDATING", adx_value, atr_ratio

    return "REGIME_NORMAL", adx_value, atr_ratio

def calculate_confluence_score(
    direction: str,
    current_price: float,
    macro_ema_200: float,
    current_regime: str,
    adx_value: float,
    active_sweep_detected: bool,
    distance_to_key_level: float,
    trigger_active: bool
) -> int:
    """
    Computes a confluence score from 0 to 100 based on 4 weighted vectors.
    """
    score = 0

    # Vector 1: Macro Trend Alignment (Max 25 Points)
    if direction == "MULTUP" and current_price > macro_ema_200:
        score += 25
    elif direction == "MULTDOWN" and current_price < macro_ema_200:
        score += 25

    # Vector 2: Volatility & Regime Quality (Max 25 Points)
    if current_regime == "REGIME_TRENDING":
        score += 25
    elif current_regime == "REGIME_CONSOLIDATING" and adx_value >= 18:
        score += 15
    elif current_regime == "REGIME_NORMAL":
        score += 10

    # Vector 3: Liquidity & Key Level Setup (Max 25 Points)
    if active_sweep_detected:
        score += 25  # High-grade smart money setup
    elif distance_to_key_level >= 1.00:
        score += 15  # Plenty of room to run
    elif distance_to_key_level >= 0.25:
        score += 5   # Minimal room to run

    # Vector 4: Trigger Momentum Precision (Max 25 Points)
    if trigger_active:
        score += 25

    return score
