import logging
from typing import Tuple

import config

logger = logging.getLogger("TradingEngine")


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

        # Phase 1: Step-Ladder Floor when peak PnL is below $1.00
        if self.peak_pnl < 1.00:
            if self.peak_pnl >= 0.75:
                calculated_floor = 0.25
            elif self.peak_pnl >= 0.50:
                calculated_floor = 0.00
            else:
                calculated_floor = -config.HARD_STOP_LOSS_USD
        else:
            # Phase 2: Continuous Trailing once peak PnL is >= $1.00 (Gap of $0.50)
            calculated_floor = self.peak_pnl - config.TRAILING_GAP_USD

        # One-Way Ratchet Rule: Floor can ONLY increase, never decrease
        if calculated_floor > self.current_sl_floor:
            self.current_sl_floor = calculated_floor
            logger.info(f"[RATC_ENG] SL Floor Shifted Upwards to +${self.current_sl_floor:.2f} (Peak PnL: {self.peak_pnl:.2f})")

        # Stage 3: Execution Trigger Check
        should_sell = current_pnl <= self.current_sl_floor
        return self.current_sl_floor, should_sell

