import pandas as pd
import logging
from typing import Tuple, Optional, Dict, Any

import config

logger = logging.getLogger("TradingEngine")

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

    # RSI-14 (RMA smoothing)
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    df["rsi_14"] = 100 - (100 / (1 + rs))
    
    return df


def check_entry_signal(df: pd.DataFrame) -> Tuple[Optional[str], Optional[float]]:
    """
    Evaluates entry conditions on completed candles:
    - Bullish Signal (MULTUP): Candle Close > EMA-20 AND RSI-14 crosses above 50.
    - Bearish Signal (MULTDOWN): Candle Close < EMA-20 AND RSI-14 crosses below 50.
    
    Returns (signal_type, entry_price).
    """
    df = calculate_indicators(df)
    if df.empty or len(df) < 22:
        return None, None

    # Evaluate at the close of the last completed candle (index -2) to prevent repainting
    closes = df["close"].values
    emas = df["ema_20"].values
    rsis = df["rsi_14"].values

    last_close = closes[-2]
    last_ema = emas[-2]
    
    # RSI cross above 50: rsis[-3] <= 50 and rsis[-2] > 50
    rsi_cross_above_50 = rsis[-3] <= 50 and rsis[-2] > 50
    
    # RSI cross below 50: rsis[-3] >= 50 and rsis[-2] < 50
    rsi_cross_below_50 = rsis[-3] >= 50 and rsis[-2] < 50

    # Bullish Signal
    if last_close > last_ema and rsi_cross_above_50:
        logger.info(f"Signal detected: MULTUP. Close: {last_close}, EMA: {last_ema:.4f}, RSI crossed above 50 (prev: {rsis[-3]:.2f} -> curr: {rsis[-2]:.2f})")
        return "MULTUP", last_close

    # Bearish Signal
    if last_close < last_ema and rsi_cross_below_50:
        logger.info(f"Signal detected: MULTDOWN. Close: {last_close}, EMA: {last_ema:.4f}, RSI crossed below 50 (prev: {rsis[-3]:.2f} -> curr: {rsis[-2]:.2f})")
        return "MULTDOWN", last_close

    return None, None


class TrailingRatchetEngine:
    """
    Maintains dynamic stop-loss ratchet floors for active positions.
    """
    def __init__(self):
        self.peak_pnl = 0.00
        self.current_sl_floor = -config.HARD_STOP_LOSS_USD  # -$0.75 Initial Floor

    def reset(self):
        self.peak_pnl = 0.00
        self.current_sl_floor = -config.HARD_STOP_LOSS_USD
        logger.info("Ratchet engine reset to initial state.")

    def process_pnl_update(self, current_pnl: float) -> Tuple[float, bool]:
        """
        Updates the trailing engine state on every tick / POC update.
        Returns (current_sl_floor, should_sell).
        """
        # Track Peak Profit Reached During the Trade
        if current_pnl > self.peak_pnl:
            self.peak_pnl = current_pnl

        # Stage 1: Break-Even Lock
        if self.peak_pnl >= config.BREAK_EVEN_TRIGGER and self.current_sl_floor < 0.00:
            self.current_sl_floor = 0.00
            logger.info(f"[RATC_ENG] Peak PnL reached {self.peak_pnl:.2f}. SL Floor Shifted to Break-Even ($0.00)")

        # Stage 2: Dynamic Continuous Trailing (Uncapped Profit Engine)
        if self.peak_pnl >= config.DYNAMIC_TRAIL_START:
            calculated_floor = self.peak_pnl - config.TRAILING_OFFSET_USD
            # One-Way Ratchet Rule: Floor can ONLY increase, never decrease
            if calculated_floor > self.current_sl_floor:
                self.current_sl_floor = calculated_floor
                logger.info(f"[RATC_ENG] SL Floor Shifted Upwards to +${self.current_sl_floor:.2f} (Peak PnL: {self.peak_pnl:.2f})")

        # Stage 3: Execution Trigger Check
        should_sell = current_pnl <= self.current_sl_floor
        return self.current_sl_floor, should_sell
