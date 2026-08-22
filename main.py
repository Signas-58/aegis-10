import asyncio
import logging
import sys
import time
from datetime import datetime

import config
import state_manager
from websocket_client import DerivWebSocketClient
from data_processor import DataProcessor
from risk_manager import RiskManager
from execution import ExecutionEngine
import strategy

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
        self.data_processor = DataProcessor()
        self.risk_manager = RiskManager()
        self.execution = ExecutionEngine(self.client)
        
        # State tracking
        self.active_trade = {}
        self.highest_pnl = 0.0
        self.session_expired = False
        self.shutdown_pending = False
        self.running = True

    async def run(self):
        """
        Orchestrates application startup, event loops, and shutdown.
        """
        logger.info("Initializing Deriv Multipliers Scalping Bot...")
        
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

        # Register callbacks
        self.client.register_subscription("candles", self._on_candle_update)
        self.client.register_subscription("ohlc", self._on_candle_update)
        self.client.register_subscription("proposal_open_contract", self._on_contract_update)


        # Start 10-Minute Safety Timer
        asyncio.create_task(self._start_safety_timer())

        # Check for crashed state recovery
        recovered_trade = state_manager.load_active_trade()
        if recovered_trade:
            logger.warning(f"Crash recovery: Found unclosed trade {recovered_trade['contract_id']} from active_trade.json.")
            self.active_trade = recovered_trade
            self.highest_pnl = 0.0  # Reset peak tracking for recovery
            
            # Subscribe to updates for this contract
            subscribed = await self.execution.subscribe_open_contract(recovered_trade["contract_id"])
            if not subscribed:
                logger.error("Could not subscribe to recovered contract. Clearing state to resume normal trading.")
                state_manager.clear_active_trade()
                self.active_trade = {}
        else:
            # Normal boot: fetch historical candles
            success = await self.data_processor.fetch_historical_candles(self.client)
            if not success:
                logger.error("Failed to fetch historical candles. Terminating.")
                self.running = False

        # Keep running until shutdown is triggered
        while self.running:
            await asyncio.sleep(1)

        # Disconnect cleanly
        await self.client.disconnect()
        logger.info("Bot execution finished.")

    async def _start_safety_timer(self):
        """
        Safety timer that flags session expiration after MAX_RUNTIME_MINUTES.
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

    async def _on_candle_update(self, data: dict):
        """
        Triggered when a new candle update is received from the subscription stream.
        """
        if self.session_expired and not self.active_trade:
            self.running = False
            return

        # Process the candle stream
        await self.data_processor.handle_candle_stream(data)
        
        # We only evaluate new entry signals if:
        # 1. No trade is currently open.
        # 2. The 10-minute session has not expired.
        # 3. We are not pending shutdown.
        # 4. Trading is not halted due to circuit breakers (loss caps / cooldowns).
        if not self.active_trade and not self.session_expired and not self.shutdown_pending:
            if self.risk_manager.is_trading_halted():
                return
            
            df = self.data_processor.get_candles_df()
            signal, entry_price = strategy.check_entry_signal(df)
            
            if signal:
                logger.info(f"Signal detected: {signal} at {entry_price}. Preparing execution...")
                await self._enter_trade(signal)

    async def _enter_trade(self, contract_type: str):
        """
        Performs proposal requests, order placement, and initializes position tracking.
        """
        stake = config.DEFAULT_STAKE
        
        # 1. Get proposal ID
        proposal_id = await self.execution.get_proposal(contract_type, stake)
        if not proposal_id:
            logger.error("Could not obtain proposal. Entry aborted.")
            return

        # 2. Place Order
        contract_id = await self.execution.execute_order(proposal_id, stake)
        if not contract_id:
            logger.error("Could not execute purchase order. Entry aborted.")
            return

        # 3. Persist state to active_trade.json BEFORE subscribing
        entry_time = time.time()
        self.active_trade = {
            "contract_id": contract_id,
            "entry_price": 0.0,  # Will be updated on first contract tick update
            "stake": stake,
            "contract_type": contract_type,
            "timestamp": entry_time
        }
        state_manager.save_active_trade(contract_id, 0.0, stake, contract_type, entry_time)
        self.highest_pnl = 0.0
        
        # 4. Subscribe to position updates
        subscribed = await self.execution.subscribe_open_contract(contract_id)
        if not subscribed:
            logger.error("Failed to subscribe to open contract updates! Position state may be stale.")

    async def _on_contract_update(self, data: dict):
        """
        Triggered when open contract state updates are received from the subscription stream.
        """
        open_contract = data.get("proposal_open_contract")
        if not open_contract:
            return

        contract_id = str(open_contract.get("contract_id"))
        
        # Verify this corresponds to our active trade
        if not self.active_trade or self.active_trade.get("contract_id") != contract_id:
            return

        # Extract values
        current_pnl = float(open_contract.get("profit", 0.0))
        entry_price = float(open_contract.get("entry_spot", 0.0))
        
        # Update entry spot price in state if it wasn't recorded
        if self.active_trade.get("entry_price") == 0.0 and entry_price > 0.0:
            self.active_trade["entry_price"] = entry_price
            state_manager.save_active_trade(
                contract_id,
                entry_price,
                self.active_trade["stake"],
                self.active_trade["contract_type"],
                self.active_trade["timestamp"]
            )

        # Check if the contract is closed (sold)
        is_sold = open_contract.get("is_sold") == 1
        status = open_contract.get("status") # "open", "won", "lost", "sold"
        
        if is_sold or status in ["won", "lost", "sold"]:
            # Position concluded
            final_pnl = float(open_contract.get("profit", 0.0))
            logger.info(f"Position concluded. Contract: {contract_id}, Result PnL: ${final_pnl:.2f}")
            
            # Update history and log to CSV
            self.risk_manager.log_trade(
                contract_id,
                self.active_trade["contract_type"],
                self.active_trade["stake"],
                final_pnl
            )
            
            # Clear local state persistence
            state_manager.clear_active_trade()
            self.active_trade = {}
            
            # If shutdown is pending (from safety timer), terminate now
            if self.shutdown_pending or self.session_expired:
                logger.info("Session limit reached. Concluding execution now.")
                self.running = False
                
            return

        # If trade is still open, update highest PnL and evaluate stop-loss thresholds
        self.highest_pnl = max(self.highest_pnl, current_pnl)
        
        # Print status updates periodically (rate-limited via standard update stream)
        logger.info(f"Contract {contract_id} status: PnL: ${current_pnl:.2f} | Peak: ${self.highest_pnl:.2f}")
        
        # Check dynamic stop-loss triggers
        if self.risk_manager.check_exit_condition(current_pnl, self.highest_pnl):
            logger.warning(f"Dynamic stop-loss exit triggered for contract {contract_id}!")
            closed = await self.execution.close_position(contract_id)
            if not closed:
                logger.error(f"Failed to execute manual market close for contract {contract_id}!")

if __name__ == "__main__":
    app = ScalperBotApp()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("Bot terminated manually via KeyboardInterrupt.")
    except Exception as err:
        logger.error(f"Unhandled runtime exception: {err}")
