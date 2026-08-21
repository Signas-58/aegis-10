import os
import csv
import logging
from datetime import datetime, timedelta

import config

logger = logging.getLogger("RiskManager")

LOG_FILE = "trading_log.csv"

class RiskManager:
    def __init__(self):
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.pause_until = None
        self._load_trading_history()

    def _load_trading_history(self):
        """
        Reads trading_log.csv on startup to calculate daily cumulative PnL 
        and consecutive losses count.
        """
        if not os.path.exists(LOG_FILE):
            return

        try:
            today_str = datetime.utcnow().strftime("%Y-%m-%d")
            total_daily_pnl = 0.0
            consecutive_losses = 0
            recent_trades = []

            with open(LOG_FILE, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    recent_trades.append(row)

            # Process trades in chronological order
            for row in recent_trades:
                pnl = float(row.get("pnl", 0.0))
                timestamp_str = row.get("timestamp", "")
                
                # Check if trade was done today (UTC)
                if timestamp_str.startswith(today_str):
                    total_daily_pnl += pnl
                
                # Track consecutive losses
                if pnl < 0:
                    consecutive_losses += 1
                else:
                    consecutive_losses = 0

            self.daily_pnl = total_daily_pnl
            self.consecutive_losses = consecutive_losses
            
            logger.info(f"Risk state loaded. Daily PnL: ${self.daily_pnl:.2f}, Consecutive Losses: {self.consecutive_losses}")
            
            # Check if consecutive loss limit was hit recently
            if self.consecutive_losses >= config.CONSECUTIVE_LOSS_LIMIT:
                # Get the timestamp of the last trade
                if recent_trades:
                    last_trade_time = datetime.fromisoformat(recent_trades[-1]["timestamp"])
                    time_elapsed = datetime.utcnow() - last_trade_time
                    pause_delta = timedelta(seconds=config.PAUSE_DURATION_SECONDS)
                    if time_elapsed < pause_delta:
                        self.pause_until = last_trade_time + pause_delta
                        logger.warning(f"Consecutive loss cooldown active. Paused until {self.pause_until.isoformat()}")

        except Exception as e:
            logger.error(f"Error loading trading history: {e}")

    def log_trade(self, contract_id: str, contract_type: str, stake: float, pnl: float):
        """
        Appends completed trade details to trading_log.csv and updates risk metrics.
        """
        file_exists = os.path.exists(LOG_FILE)
        timestamp = datetime.utcnow().isoformat()
        
        try:
            with open(LOG_FILE, "a", newline="") as f:
                fieldnames = ["timestamp", "contract_id", "contract_type", "stake", "pnl"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerow({
                    "timestamp": timestamp,
                    "contract_id": contract_id,
                    "contract_type": contract_type,
                    "stake": stake,
                    "pnl": pnl
                })
            
            # Update metrics
            self.daily_pnl += pnl
            if pnl < 0:
                self.consecutive_losses += 1
            else:
                self.consecutive_losses = 0

            logger.info(f"Logged trade {contract_id}. PnL: ${pnl:.2f}. Updated Daily PnL: ${self.daily_pnl:.2f}, Consecutive Losses: {self.consecutive_losses}")

            # Check consecutive loss circuit breaker
            if self.consecutive_losses >= config.CONSECUTIVE_LOSS_LIMIT:
                self.pause_until = datetime.utcnow() + timedelta(seconds=config.PAUSE_DURATION_SECONDS)
                logger.warning(f"Hit {self.consecutive_losses} consecutive losses. Pausing trading until {self.pause_until.isoformat()}")

        except Exception as e:
            logger.error(f"Error logging trade to CSV: {e}")

    def is_trading_halted(self) -> bool:
        """
        Checks if any circuit breakers or pauses are active.
        """
        # 1. Daily drawdown limit check
        if self.daily_pnl <= -abs(config.DAILY_LOSS_LIMIT):
            logger.error(f"Trading halted: Daily loss limit reached (${self.daily_pnl:.2f} <= -${config.DAILY_LOSS_LIMIT:.2f}).")
            return True

        # 2. Consecutive loss pause check
        if self.pause_until and datetime.utcnow() < self.pause_until:
            remaining_seconds = (self.pause_until - datetime.utcnow()).total_seconds()
            logger.warning(f"Trading paused: Cooldown active. {remaining_seconds / 60:.1f} minutes remaining.")
            return True
            
        return False

    def get_stop_loss_floor(self, highest_pnl: float) -> float:
        """
        Calculates the dynamic Stop-Loss threshold (in USD PnL) based on the peak PnL.
        """
        if highest_pnl >= config.STAGE_2_TRIGGER:
            # Stage 3 (Trailing): Trail stop-loss trailing distance behind peak PnL
            # But must not fall below Stage 2 lock profit level
            return max(config.STAGE_2_LOCK_PROFIT, highest_pnl - config.TRAILING_SL_DISTANCE)
        elif highest_pnl >= config.STAGE_1_TRIGGER:
            # Stage 1 (Break-Even): Stop-Loss set at 0.00
            return 0.00
        else:
            # Stage 0 (Entry): Hard Stop-Loss set at INITIAL_STOP_LOSS
            return config.INITIAL_STOP_LOSS

    def check_exit_condition(self, current_pnl: float, highest_pnl: float) -> bool:
        """
        Evaluates whether the active trade has hit its dynamic Stop-Loss floor.
        """
        sl_floor = self.get_stop_loss_floor(highest_pnl)
        if current_pnl <= sl_floor:
            logger.info(f"Exit trigger hit! Current PnL: ${current_pnl:.2f} <= Stop-Loss Floor: ${sl_floor:.2f} (Peak PnL: ${highest_pnl:.2f})")
            return True
        return False
