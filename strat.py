import pandas as pd
import numpy as np
import logging
from typing import Tuple, Optional, Dict, Any

import config

logger = logging.getLogger("StrategyEngine")

# Try importing pandas_ta, fall back if not available
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False
    logger.warning("pandas-ta not found. Falling back to native pandas calculation for indicators.")


def calculate_15m_indicators(df_15m: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates EMA-200, HTF_RESISTANCE, and HTF_SUPPORT on 15m candles.
    """
    if df_15m.empty or len(df_15m) < 200:
        return df_15m

    df = df_15m.copy()

    # EMA-200
    if HAS_PANDAS_TA:
        try:
            df["ema_200"] = df.ta.ema(length=config.EMA_MACRO_PERIOD)
        except Exception as e:
            logger.error(f"Error calculating 15m EMA with pandas_ta: {e}. Falling back to native.")
            df["ema_200"] = df["close"].ewm(span=config.EMA_MACRO_PERIOD, adjust=False).mean()
    else:
        df["ema_200"] = df["close"].ewm(span=config.EMA_MACRO_PERIOD, adjust=False).mean()

    # Support / Resistance: Highest High and Lowest Low of last 20 15m candles.
    # We exclude the active building candle (index -1) when calculating.
    # Rolling window of 20, shifted by 1 to exclude current candle.
    df["htf_resistance"] = df["high"].shift(1).rolling(window=20).max()
    df["htf_support"] = df["low"].shift(1).rolling(window=20).min()

    return df


def calculate_5m_indicators(df_5m: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates 14-period ADX on 5m candles.
    """
    if df_5m.empty or len(df_5m) < 15:
        return df_5m

    df = df_5m.copy()

    if HAS_PANDAS_TA:
        try:
            adx_df = df.ta.adx(length=14)
            # Find the ADX column (name can vary e.g. ADX_14)
            adx_col = [col for col in adx_df.columns if "ADX" in col]
            if adx_col:
                df["adx_14"] = adx_df[adx_col[0]]
                return df
        except Exception as e:
            logger.error(f"Error calculating 5m ADX with pandas_ta: {e}. Falling back to native.")

    # Native fallback ADX-14 calculation (Wilder's Smoothing)
    high = df["high"]
    low = df["low"]
    close = df["close"]
    close_prev = close.shift(1)

    # True Range (TR)
    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Directional Movement (+DM and -DM)
    high_diff = high - high.shift(1)
    low_diff = low.shift(1) - low

    plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0.0)
    minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0.0)

    # Wilder's Smoothing RMA
    alpha = 1 / 14
    tr_smooth = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_dm_smooth = pd.Series(plus_dm).ewm(alpha=alpha, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm).ewm(alpha=alpha, adjust=False).mean()

    plus_di = 100 * (plus_dm_smooth / tr_smooth.replace(0, 1e-9))
    minus_di = 100 * (minus_dm_smooth / tr_smooth.replace(0, 1e-9))

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-9)
    df["adx_14"] = dx.ewm(alpha=alpha, adjust=False).mean()

    return df


def calculate_1m_indicators(df_1m: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates EMA-20 and RSI-14 on 1m candles.
    """
    if df_1m.empty or len(df_1m) < 20:
        return df_1m

    df = df_1m.copy()

    if HAS_PANDAS_TA:
        try:
            df["ema_20"] = df.ta.ema(length=20)
            df["rsi_14"] = df.ta.rsi(length=14)
            return df
        except Exception as e:
            logger.error(f"Error calculating 1m indicators with pandas_ta: {e}. Falling back to native.")

    # Native EMA-20
    df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()

    # Native RSI-14
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    df["rsi_14"] = 100 - (100 / (1 + rs))

    return df


def check_entry_signal(
    df_15m: pd.DataFrame, df_5m: pd.DataFrame, df_1m: pd.DataFrame
) -> Tuple[Optional[str], Optional[float]]:
    """
    Evaluates the 5-layer Multi-Timeframe entry logic.
    Returns (signal_type, current_close_price).
    """
    df_15m_calc = calculate_15m_indicators(df_15m)
    df_5m_calc = calculate_5m_indicators(df_5m)
    df_1m_calc = calculate_1m_indicators(df_1m)

    if (
        df_15m_calc.empty or len(df_15m_calc) < 202
        or df_5m_calc.empty or len(df_5m_calc) < 16
        or df_1m_calc.empty or len(df_1m_calc) < 22
    ):
        return None, None

    # Get values at last completed candle (index -2) to prevent repainting
    
    # 1. 15m Macro Trend Gate
    close_15m = df_15m_calc["close"].values[-2]
    ema_15m = df_15m_calc["ema_200"].values[-2]
    htf_resistance = df_15m_calc["htf_resistance"].values[-2]
    htf_support = df_15m_calc["htf_support"].values[-2]

    macro_bullish = close_15m > ema_15m
    macro_bearish = close_15m < ema_15m

    # 2. 5m ADX Trend Strength Filter
    adx_5m = df_5m_calc["adx_14"].values[-2]
    if adx_5m < config.ADX_MIN_THRESHOLD:
        return None, None

    # 3. 15m Support/Resistance Proximity Guard
    # Use the last completed 1m close price as current execution spot price
    current_price = df_1m_calc["close"].values[-2]

    long_guard_permitted = (htf_resistance - current_price) >= config.PROXIMITY_GUARD_USD
    short_guard_permitted = (current_price - htf_support) >= config.PROXIMITY_GUARD_USD

    # 4. 5m Liquidity Sweep Detection
    # Determine sweeps on the last 3 completed 5m candles (indices -4, -3, -2)
    # We pass the htf support/resistance calculated on the 15m level
    highs_5m = df_5m_calc["high"].values
    lows_5m = df_5m_calc["low"].values
    opens_5m = df_5m_calc["open"].values
    closes_5m = df_5m_calc["close"].values

    bullish_sweeps = []
    bearish_sweeps = []

    for i in [-4, -3, -2]:
        o = opens_5m[i]
        c = closes_5m[i]
        h = highs_5m[i]
        l = lows_5m[i]

        # Bullish: Low dips below HTF support, but body closes above it
        bull_sweep = l < htf_support and min(o, c) > htf_support
        bullish_sweeps.append(bull_sweep)

        # Bearish: High spikes above HTF resistance, but body closes below it
        bear_sweep = h > htf_resistance and max(o, c) < htf_resistance
        bearish_sweeps.append(bear_sweep)

    bullish_sweep_occurred = any(bullish_sweeps)
    bearish_sweep_occurred = any(bearish_sweeps)

    # 5. 1m Trigger Confluence
    close_1m = df_1m_calc["close"].values[-2]
    ema_1m = df_1m_calc["ema_20"].values[-2]
    rsi_1m = df_1m_calc["rsi_14"].values[-2]

    trigger_bullish = close_1m > ema_1m and rsi_1m > 50
    trigger_bearish = close_1m < ema_1m and rsi_1m < 50

    # BULLISH SIGNAL CONFLUENCE
    if (
        macro_bullish
        and long_guard_permitted
        and (trigger_bullish or bullish_sweep_occurred)
    ):
        logger.info(
            f"[SIGNAL] MULTUP. Price: {current_price:.2f}, ADX: {adx_5m:.2f}, "
            f"15m Res: {htf_resistance:.2f} (Dist: {htf_resistance - current_price:.2f}), "
            f"Sweep: {bullish_sweep_occurred}, Trigger: {trigger_bullish}"
        )
        return "MULTUP", current_price

    # BEARISH SIGNAL CONFLUENCE
    if (
        macro_bearish
        and short_guard_permitted
        and (trigger_bearish or bearish_sweep_occurred)
    ):
        logger.info(
            f"[SIGNAL] MULTDOWN. Price: {current_price:.2f}, ADX: {adx_5m:.2f}, "
            f"15m Supp: {htf_support:.2f} (Dist: {current_price - htf_support:.2f}), "
            f"Sweep: {bearish_sweep_occurred}, Trigger: {trigger_bearish}"
        )
        return "MULTDOWN", current_price


    return None, None
