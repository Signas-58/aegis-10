import pandas as pd
import logging
from typing import Tuple, Optional

logger = logging.getLogger("Strategy")

# Try importing pandas_ta, fall back if not available
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False
    logger.warning("pandas-ta not found. Falling back to native pandas calculation for EMA and RSI.")

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates EMA-20 and RSI-14.
    Supports pandas_ta if installed; otherwise, falls back to native pandas calculations.
    """
    if df.empty or len(df) < 20:
        return df

    df = df.copy()

    if HAS_PANDAS_TA:
        try:
            df.ta.ema(length=20, append=True)
            df.ta.rsi(length=14, append=True)
            # Rename columns to standard names for consistency
            ema_col = [col for col in df.columns if "EMA" in col]
            rsi_col = [col for col in df.columns if "RSI" in col]
            if ema_col:
                df.rename(columns={ema_col[0]: "ema_20"}, inplace=True)
            if rsi_col:
                df.rename(columns={rsi_col[0]: "rsi_14"}, inplace=True)
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators with pandas_ta: {e}. Falling back to native.")

    # Native fallback calculation
    # EMA-20
    df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()

    # RSI-14 (Wilder's smoothing RMA)
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    
    # Avoid division by zero
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    df["rsi_14"] = 100 - (100 / (1 + rs))
    
    return df

def check_entry_signal(df: pd.DataFrame) -> Tuple[Optional[str], Optional[float]]:
    """
    Checks the latest candle data for entry signals.
    Returns (signal_type, current_close_price). 
    signal_type is either 'MULTUP', 'MULTDOWN', or None.
    """
    df = calculate_indicators(df)
    if df.empty or len(df) < 22:
        return None, None

    # We evaluate signals at the close of the last completed candle (index -2) 
    # to avoid entry signal fluctuation (repainting) during the live candle (index -1)
    
    # Let's inspect values
    closes = df["close"].values
    emas = df["ema_20"].values
    rsis = df["rsi_14"].values
    
    # Index -2 is the last completed candle, Index -1 is the active live candle
    # Let's check Close Price relative to EMA
    last_close = closes[-2]
    last_ema = emas[-2]
    
    # Check crossovers of RSI:
    # "RSI crosses above 30 from oversold in the last 2 candles"
    # This means RSI was <= 30, and is now > 30.
    # We check:
    # 1. Cross at index -2: rsis[-3] <= 30 and rsis[-2] > 30
    # 2. Cross at index -3: rsis[-4] <= 30 and rsis[-3] > 30
    
    long_cross_1 = rsis[-3] <= 30 and rsis[-2] > 30
    long_cross_2 = rsis[-4] <= 30 and rsis[-3] > 30
    rsi_long_signal = long_cross_1 or long_cross_2
    
    # "RSI crosses below 70 from overbought in the last 2 candles"
    # We check:
    # 1. Cross at index -2: rsis[-3] >= 70 and rsis[-2] < 70
    # 2. Cross at index -3: rsis[-4] >= 70 and rsis[-3] < 70
    
    short_cross_1 = rsis[-3] >= 70 and rsis[-2] < 70
    short_cross_2 = rsis[-4] >= 70 and rsis[-3] < 70
    rsi_short_signal = short_cross_1 or short_cross_2

    # LONG Entry Condition
    if last_close > last_ema and rsi_long_signal:
        logger.info(f"Generated LONG signal (MULTUP). Close: {last_close}, EMA: {last_ema:.4f}, RSI: {rsis[-2]:.2f}")
        return "MULTUP", last_close

    # SHORT Entry Condition
    if last_close < last_ema and rsi_short_signal:
        logger.info(f"Generated SHORT signal (MULTDOWN). Close: {last_close}, EMA: {last_ema:.4f}, RSI: {rsis[-2]:.2f}")
        return "MULTDOWN", last_close

    return None, None


