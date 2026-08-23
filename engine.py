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
