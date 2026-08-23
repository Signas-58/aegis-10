import asyncio
import logging
import sys
import time
import json
import os
import csv
import signal
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd

import config
from websocket_client import DerivWebSocketClient
import engine
import strat

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MainApplication")

class ScalperBotApp:
    def __init__(self):
        self.client = DerivWebSocketClient()
        self.ratchet_engine = engine.TrailingRatchetEngine()
        
        # Multi-Timeframe Buffers
        self.candles_15m: List[Dict[str, Any]] = []
        self.candles_5m: List[Dict[str, Any]] = []
        self.candles_1m: List[Dict[str, Any]] = []

        # State tracking
        self.active_trade: Optional[Dict[str, Any]] = None
        self.consecutive_losses = 0
        self.cumulative_daily_loss = 0.0
        
        self.session_expired = False
        self.shutdown_pending = False
        self.running = True
        self.cooldown_until = 0.0
        self.last_sent_server_sl = config.HARD_STOP_LOSS_USD


    async def run(self):
        """
        Orchestrates application startup, event loops, and shutdown.
        """
        logger.info("Initializing Deriv Multipliers Scalping Bot (Aegis-10)...")
        
        # Load daily circuit breaker metrics from trading_log.csv on startup to persist stats
        self._load_daily_stats_from_csv()
        
        # Immediate circuit breaker check
        if self._check_circuit_breakers():
            return

        # Setup Signal Handlers for Graceful Shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.handle_shutdown_signal()))
            except NotImplementedError:
                # signal handlers not fully supported on some Windows event loops
                pass

        # Connect to WebSocket
        connected = await self.client.connect()
        if not connected:
            logger.error("Could not connect to WebSocket. Terminating.")
            return

        # Authorize connection
        authorized = await self.client.authorize()
        if not authorized:
            logger.error("Could not authorize connection. Terminating.")
            await self.client.disconnect()
            return

        # Register callback subscriptions
        self.client.register_subscription("candles", self._on_candle_stream)
        self.client.register_subscription("ohlc", self._on_candle_stream)
        self.client.register_subscription("proposal_open_contract", self._on_contract_update)

        # Start Safety Session Timer (MAX_RUNTIME_MINUTES)
        asyncio.create_task(self._start_safety_timer())

        # Always fetch historical candles & initiate subscriptions on startup
        success = await self._fetch_historical_candles_all()
        if not success:
            logger.error("Failed to fetch historical candles. Terminating.")
            self.running = False
            return

        # Check for crashed state recovery
        self._load_active_trade_state()
        if self.active_trade:
            contract_id = self.active_trade["contract_id"]
            logger.warning(f"Crash Recovery: Active trade {contract_id} found in active_trade.json. Restoring state...")
            self.ratchet_engine.reset()
            # Subscribe to updates
            subscribed = await self._subscribe_open_contract_api(contract_id)
            if not subscribed:
                logger.error("Could not subscribe to recovered contract. Clearing state to resume normal trading.")
                self._clear_active_trade_state()
                self.active_trade = None

        # Main execution keepalive loop
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            # Cleanup active trade and disconnect cleanly
            if self.active_trade:
                await self.handle_shutdown_signal()
            else:
                await self.client.disconnect()
                logger.info("Bot execution finished.")

    async def handle_shutdown_signal(self):
        """
        Catches termination signals (Ctrl+C) and closes positions cleanly before exiting.
        """
        if not self.running:
            return
        self.running = False
        logger.warning("Shutdown signal received! Initiating cleanup procedure...")
        
        if self.active_trade:
            contract_id = self.active_trade["contract_id"]
            logger.warning(f"Active trade {contract_id} is open. Closing position immediately at market price...")
            await self._close_position_api(contract_id)
            self._clear_active_trade_state()
            
        await self.client.disconnect()
        logger.info("Graceful shutdown completed successfully. Bot stopped.")
        sys.exit(0)

    async def _start_safety_timer(self):
        """
        Limits the session to MAX_RUNTIME_MINUTES (Auto-Shutdown).
        """
        logger.info(f"Session safety timer started. Maximum runtime: {config.MAX_RUNTIME_MINUTES} minutes.")
        await asyncio.sleep(config.MAX_RUNTIME_MINUTES * 60)
        logger.warning("Session safety timer expired!")
        self.session_expired = True
        
        if not self.active_trade:
            logger.info("No active trade open. Initiating immediate graceful shutdown.")
            self.running = False
        else:
            logger.warning("Active trade is currently open. Shutdown pending after trade completes.")
            self.shutdown_pending = True

    async def _fetch_historical_candles_all(self) -> bool:
        """
        Fetches historical candles for 15m, 5m, and 1m horizons, subscribing to their ticks.
        """
        # 1. 15m Horizon (Need min 200 for EMA-200, load 250 for smoothing stability)
        success_15m = await self._fetch_historical_candles_api(config.TF_MACRO, 250, self.candles_15m)
        if not success_15m:
            logger.error("Failed to fetch 15m historical candles.")
            return False

        # 2. 5m Horizon
        success_5m = await self._fetch_historical_candles_api(config.TF_STRUCTURE, 50, self.candles_5m)
        if not success_5m:
            logger.error("Failed to fetch 5m historical candles.")
            return False

        # 3. 1m Horizon
        success_1m = await self._fetch_historical_candles_api(config.TF_TRIGGER, 50, self.candles_1m)
        if not success_1m:
            logger.error("Failed to fetch 1m historical candles.")
            return False


        return True

    async def _fetch_historical_candles_api(self, granularity: int, count: int, buffer: List[Dict[str, Any]]) -> bool:
        """
        Fetches historical candles and subscribes to subsequent ticks.
        """
        logger.info(f"Fetching {count} historical candles (granularity: {granularity}s) for {config.SYMBOL}...")
        payload = {
            "ticks_history": config.SYMBOL,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "style": "candles",
            "granularity": granularity,
            "subscribe": 1
        }
        
        try:
            response = await self.client.send_request(payload)
            if "error" in response:
                logger.error(f"Failed to fetch historical candles for granularity {granularity}: {response['error'].get('message')}")
                return False
            
            history = response.get("candles", [])
            if not history:
                logger.warning(f"No historical candles returned for granularity {granularity}.")
                return False
            
            buffer.clear()
            for candle in history:
                buffer.append({
                    "epoch": int(candle["epoch"]),
                    "open": float(candle["open"]),
                    "high": float(candle["high"]),
                    "low": float(candle["low"]),
                    "close": float(candle["close"])
                })
            
            logger.info(f"Successfully loaded {len(buffer)} historical candles for granularity {granularity}s.")
            return True
        except Exception as e:
            logger.error(f"Error fetching historical candles for granularity {granularity}: {e}")
            return False

    async def _on_candle_stream(self, data: dict):
        """
        Triggered when a candle update is received from the subscription stream.
        Routes ticks to 15m, 5m, or 1m buffers based on granularity.
        """
        if self.session_expired and not self.active_trade:
            self.running = False
            return

        ohlc_data = data.get("ohlc")
        if ohlc_data:
            granularity = int(ohlc_data.get("granularity", 0))
            epoch = int(ohlc_data["open_time"])
            candle_dict = {
                "epoch": epoch,
                "open": float(ohlc_data["open"]),
                "high": float(ohlc_data["high"]),
                "low": float(ohlc_data["low"]),
                "close": float(ohlc_data["close"])
            }
        else:
            echo_req = data.get("echo_req") or {}
            granularity = int(echo_req.get("granularity", 0))
            
            candle_data = data.get("candle") or data.get("candles")
            if isinstance(candle_data, list) or not candle_data:
                return
            epoch = int(candle_data["epoch"])
            candle_dict = {
                "epoch": epoch,
                "open": float(candle_data["open"]),
                "high": float(candle_data["high"]),
                "low": float(candle_data["low"]),
                "close": float(candle_data["close"])
            }

        if granularity not in [config.TF_MACRO, config.TF_STRUCTURE, config.TF_TRIGGER]:
            return

        # Route to appropriate buffer
        if granularity == config.TF_MACRO:
            buffer = self.candles_15m
            limit = 300
            name = "15m"
        elif granularity == config.TF_STRUCTURE:
            buffer = self.candles_5m
            limit = 100
            name = "5m"
        else:
            buffer = self.candles_1m
            limit = 100
            name = "1m"

        # Check if we already have this candle epoch
        new_candle_started = False
        if buffer and buffer[-1]["epoch"] == epoch:
            buffer[-1] = candle_dict
        else:
            if buffer:
                new_candle_started = True
            buffer.append(candle_dict)
            if new_candle_started and name == "1m":
                logger.info(f"New 1m candle started. Epoch: {epoch}, Close: {candle_dict['close']}")

        # Truncate buffer size
        if len(buffer) > limit:
            buffer[:] = buffer[-limit:]

        # Evaluate strategy signal at the close/start of a new completed 1-minute candle
        if (new_candle_started and name == "1m" and not self.active_trade 
                and not self.session_expired and not self.shutdown_pending):
            
            # Check cooldown / quarantine timer
            current_time = time.time()
            if current_time < self.cooldown_until:
                return

            df_15m = self._get_candles_df(self.candles_15m)
            df_5m = self._get_candles_df(self.candles_5m)
            df_1m = self._get_candles_df(self.candles_1m)

            signal, entry_price = strat.check_entry_signal(df_15m, df_5m, df_1m)
            
            if signal:
                logger.info(f"Signal detected: {signal} at {entry_price}. Preparing execution...")
                await self._enter_trade(signal)

    async def _enter_trade(self, contract_type: str):
        """
        Creates order proposal and executes order with native server SL.
        """
        # 1. Request price proposal with native Stop Loss
        logger.info(f"Requesting proposal for {contract_type} (Stake: ${config.STAKE:.2f}, SL: ${config.HARD_STOP_LOSS_USD:.2f})...")
        payload = {
            "proposal": 1,
            "amount": config.STAKE,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": "USD",
            "underlying_symbol": config.SYMBOL,
            "multiplier": config.MULTIPLIER,
            "limit_order": {
                "stop_loss": config.HARD_STOP_LOSS_USD
            }
        }

        try:
            response = await self.client.send_request(payload)
            if "error" in response:
                logger.error(f"Proposal request rejected: {response['error'].get('message')}")
                return
            
            proposal_id = response.get("proposal", {}).get("id")
            if not proposal_id:
                logger.error("Could not retrieve proposal ID.")
                return

            # 2. Place purchase order
            logger.info(f"Executing order for proposal ID {proposal_id}...")
            buy_payload = {
                "buy": proposal_id,
                "price": config.STAKE
            }
            
            buy_response = await self.client.send_request(buy_payload)
            if "error" in buy_response:
                logger.error(f"Order execution rejected: {buy_response['error'].get('message')}")
                return
            
            contract_id = str(buy_response.get("buy", {}).get("contract_id"))
            if not contract_id:
                logger.error("No contract ID returned after purchase.")
                return

            logger.info(f"Order executed successfully! Contract ID: {contract_id}")

            # 3. Persist state locally before subscribing
            entry_time = time.time()
            self.active_trade = {
                "contract_id": contract_id,
                "contract_type": contract_type,
                "stake": config.STAKE,
                "timestamp": entry_time
            }
            self._save_active_trade_state()
            self.ratchet_engine.reset()
            self.last_sent_server_sl = config.HARD_STOP_LOSS_USD


            # 4. Subscribe to position updates
            await self._subscribe_open_contract_api(contract_id)
        except Exception as e:
            logger.error(f"Error during trade entry: {e}")

    async def _on_contract_update(self, data: dict):
        """
        Processes real-time contract PnL and coordinates exits via the ratchet stop-loss engine.
        """
        open_contract = data.get("proposal_open_contract")
        if not open_contract:
            return

        contract_id = str(open_contract.get("contract_id"))
        if not self.active_trade or self.active_trade.get("contract_id") != contract_id:
            return

        current_pnl = float(open_contract.get("profit", 0.0))
        is_sold = open_contract.get("is_sold") == 1
        status = open_contract.get("status")

        # Check if the contract is concluded
        if is_sold or status in ["won", "lost", "sold"]:
            final_pnl = float(open_contract.get("profit", 0.0))
            logger.info(f"Position concluded. Contract: {contract_id}, Result PnL: ${final_pnl:.2f}")
            
            # Update metrics and write to CSV
            self._process_trade_outcome(contract_id, final_pnl)
            
            # Clear active trade state
            self._clear_active_trade_state()
            self.active_trade = None

            # Check circuit breaker halts
            if self._check_circuit_breakers():
                return

            # Graceful session timer check
            if self.shutdown_pending or self.session_expired:
                logger.info("Session maximum runtime reached. Concluding execution now.")
                self.running = False

            return

        # Feed the active trade PnL update to the ratchet stop-loss floor calculator
        current_sl_floor, should_sell = self.ratchet_engine.process_pnl_update(current_pnl)

        logger.info(f"Contract {contract_id} status: PnL: ${current_pnl:.2f} | Peak: ${self.ratchet_engine.peak_pnl:.2f} | SL Floor: ${current_sl_floor:.2f}")

        # Update the server-side Stop-Loss limit dynamically as the floor rises
        # If floor is negative (Phase 1/entry), server risk is -floor.
        # If floor is >= 0, server risk is set to 0.01 (minimum possible break-even risk on server).
        server_sl_usd = round(max(0.01, -current_sl_floor), 2)
        if server_sl_usd != self.last_sent_server_sl:
            success = await self._update_contract_stop_loss_api(contract_id, server_sl_usd)
            if success:
                self.last_sent_server_sl = server_sl_usd


        if should_sell:
            logger.warning(f"SL Floor Hit ({current_pnl:.2f} <= {current_sl_floor:.2f}). Selling contract immediately...")
            closed = await self._close_position_api(contract_id)
            if not closed:
                logger.error(f"Manual market close failed for contract {contract_id}!")

    async def _subscribe_open_contract_api(self, contract_id: str) -> bool:
        """
        Sends subscription payload for proposal_open_contract to the socket.
        """
        payload = {
            "proposal_open_contract": 1,
            "contract_id": int(contract_id),
            "subscribe": 1
        }
        try:
            response = await self.client.send_request(payload)
            if "error" in response:
                logger.error(f"Failed to subscribe to contract updates: {response['error'].get('message')}")
                return False
            logger.info(f"Subscribed to open updates for contract {contract_id}.")
            return True
        except Exception as e:
            logger.error(f"Error subscribing to contract updates: {e}")
            return False

    async def _update_contract_stop_loss_api(self, contract_id: str, stop_loss_usd: float) -> bool:
        """
        Sends contract_update payload to update stop-loss on the server side.
        """
        payload = {
            "contract_update": 1,
            "contract_id": int(contract_id),
            "limit_order": {
                "stop_loss": stop_loss_usd
            }
        }
        try:
            logger.info(f"Sending server-side stop-loss update for contract {contract_id} to ${stop_loss_usd:.2f}...")
            response = await self.client.send_request(payload)
            if "error" in response:
                logger.error(f"Failed to update stop-loss on server: {response['error'].get('message')}")
                return False
            logger.info(f"Server-side stop-loss updated successfully for contract {contract_id}.")
            return True
        except Exception as e:
            logger.error(f"Error updating stop-loss on server: {e}")
            return False

    async def _close_position_api(self, contract_id: str) -> bool:

        """
        Issues market close command for contract.
        """
        payload = {
            "sell": int(contract_id),
            "price": 0
        }
        try:
            response = await self.client.send_request(payload)
            if "error" in response:
                logger.error(f"Failed to close contract {contract_id}: {response['error'].get('message')}")
                return False
            logger.info(f"Contract {contract_id} closed successfully via API.")
            return True
        except Exception as e:
            logger.error(f"Error closing position via API: {e}")
            return False

    def _process_trade_outcome(self, contract_id: str, final_pnl: float):
        """
        Logs trade details and enforces post-trade win/loss quarantine cooldown rules.
        """
        is_win = final_pnl > 0
        
        if is_win:
            self.consecutive_losses = 0
            self.cumulative_daily_loss -= final_pnl  # Subtract net profit from daily loss tracking
            self.cooldown_until = time.time() + config.COOLDOWN_AFTER_WIN_SECONDS
            logger.info(f"Trade won! Win cooldown active for {config.COOLDOWN_AFTER_WIN_SECONDS}s.")
        else:
            self.consecutive_losses += 1
            self.cumulative_daily_loss += abs(final_pnl)  # Add loss amount to tracking
            self.cooldown_until = time.time() + config.COOLDOWN_AFTER_LOSS_SECONDS
            logger.warning(f"Trade lost. Enforcing 10-Minute Loss Quarantine ({config.COOLDOWN_AFTER_LOSS_SECONDS}s cooldown).")

        # Log to CSV
        log_file = "trading_log.csv"
        file_exists = os.path.exists(log_file)
        
        try:
            with open(log_file, "a", newline="") as csvfile:
                fieldnames = ["timestamp", "contract_id", "contract_type", "stake", "pnl", "consecutive_losses", "cumulative_daily_loss"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow({
                    "timestamp": datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S"),
                    "contract_id": contract_id,
                    "contract_type": self.active_trade["contract_type"] if self.active_trade else "UNKNOWN",
                    "stake": self.active_trade["stake"] if self.active_trade else config.STAKE,
                    "pnl": final_pnl,
                    "consecutive_losses": self.consecutive_losses,
                    "cumulative_daily_loss": self.cumulative_daily_loss
                })
        except Exception as e:
            logger.error(f"Error writing to trading_log.csv: {e}")

    def _check_circuit_breakers(self) -> bool:
        """
        Halts trading immediately if daily safety circuit breaker limits are violated.
        """
        if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
            logger.critical(f"[CIRCUIT BREAKER TRIGGERED - SESSION TERMINATED] Consecutive losses ({self.consecutive_losses}) hit maximum limit ({config.MAX_CONSECUTIVE_LOSSES}).")
            self.running = False
            return True

        if self.cumulative_daily_loss >= config.MAX_DAILY_LOSS_USD:
            logger.critical(f"[CIRCUIT BREAKER TRIGGERED - SESSION TERMINATED] Cumulative daily loss (${self.cumulative_daily_loss:.2f}) hit maximum cap (${config.MAX_DAILY_LOSS_USD:.2f}).")
            self.running = False
            return True

        return False

    def _get_candles_df(self, candles_list: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Helper returning candle data formatted as a pandas DataFrame.
        """
        if not candles_list:
            return pd.DataFrame(columns=["epoch", "open", "high", "low", "close"])
        df = pd.DataFrame(candles_list)
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        df["epoch"] = df["epoch"].astype(int)
        return df

    # ==========================================
    # State Management (Local persistence)
    # ==========================================
    def _save_active_trade_state(self):
        state_file = "active_trade.json"
        try:
            with open(state_file, "w") as f:
                json.dump(self.active_trade, f)
            logger.info("Persisted active trade state to active_trade.json.")
        except Exception as e:
            logger.error(f"Failed to save state to active_trade.json: {e}")

    def _load_active_trade_state(self):
        state_file = "active_trade.json"
        if os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    self.active_trade = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load state from active_trade.json: {e}")
                self.active_trade = None

    def _clear_active_trade_state(self):
        state_file = "active_trade.json"
        if os.path.exists(state_file):
            try:
                os.remove(state_file)
                logger.info("Cleared active trade state file.")
            except Exception as e:
                logger.error(f"Failed to delete active_trade.json: {e}")

    def _load_daily_stats_from_csv(self):
        """
        Parses trading_log.csv to populate consecutive_losses and cumulative_daily_loss.
        """
        log_file = "trading_log.csv"
        if not os.path.exists(log_file):
            return

        try:
            with open(log_file, "r") as f:
                reader = list(csv.DictReader(f))
                if not reader:
                    return
                last_row = reader[-1]
                
                # Verify if the trade was within the same day
                timestamp_str = last_row.get("timestamp")
                if timestamp_str:
                    clean_timestamp = timestamp_str.replace("T", " ").split(".")[0]
                    trade_date = datetime.strptime(clean_timestamp, "%Y-%m-%d %H:%M:%S").date()
                    today = datetime.now().date()
                    if trade_date == today:
                        self.consecutive_losses = int(last_row.get("consecutive_losses", 0))
                        self.cumulative_daily_loss = float(last_row.get("cumulative_daily_loss", 0.0))
                        logger.info(f"Restored daily statistics: Consecutive Losses: {self.consecutive_losses}, Cumulative Loss: ${self.cumulative_daily_loss:.2f}")
        except Exception as e:
            logger.error(f"Failed to load daily statistics from csv log: {e}")

if __name__ == "__main__":
    # Check if we should relaunch in a new visible Command Prompt window (Windows only)
    import sys
    import subprocess
    import platform

    if platform.system() == "Windows" and (len(sys.argv) == 1 or sys.argv[1] != "--child"):
        print("Opening dedicated terminal window to display active trade stream...")
        subprocess.Popen(["cmd.exe", "/k", "python", sys.argv[0], "--child"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        sys.exit(0)

    # Slice out the --child flag if present
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        sys.argv.pop(1)

    app = ScalperBotApp()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("Bot terminated manually via KeyboardInterrupt.")
    except Exception as err:
        logger.error(f"Unhandled runtime exception: {err}")
