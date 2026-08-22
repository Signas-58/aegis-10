import pandas as pd
import logging
from typing import List, Dict, Any

import config
from websocket_client import DerivWebSocketClient

logger = logging.getLogger("DataProcessor")

class DataProcessor:
    def __init__(self):
        # We store candles as a list of dicts: [{'epoch': int, 'open': float, 'high': float, 'low': float, 'close': float}, ...]
        self.candles: List[Dict[str, Any]] = []

    async def fetch_historical_candles(self, client: DerivWebSocketClient) -> bool:
        """
        Fetches the initial cold-start historical candles (50 bars) on startup.
        """
        logger.info(f"Fetching {config.COLD_START_CANDLES} historical candles for {config.SYMBOL}...")
        payload = {
            "ticks_history": config.SYMBOL,
            "adjust_start_time": 1,
            "count": config.COLD_START_CANDLES,
            "end": "latest",
            "style": "candles",
            "granularity": config.GRANULARITY,
            "subscribe": 1, # This fetches history AND subscribes to subsequent candles
            "req_id": 999  # Temporary ID, client will replace
        }
        
        try:
            response = await client.send_request(payload)
            if "error" in response:
                logger.error(f"Failed to fetch history: {response['error'].get('message')}")
                return False
            
            history = response.get("candles", [])
            if not history:
                logger.warning("No historical candles returned from API.")
                return False
            
            # Populate our candles list
            self.candles = []
            for candle in history:
                self.candles.append({
                    "epoch": int(candle["epoch"]),
                    "open": float(candle["open"]),
                    "high": float(candle["high"]),
                    "low": float(candle["low"]),
                    "close": float(candle["close"])
                })
            
            logger.info(f"Successfully loaded {len(self.candles)} historical candles.")
            return True
        except Exception as e:
            logger.error(f"Error fetching historical candles: {e}")
            return False

    async def handle_candle_stream(self, data: Dict[str, Any]):
        """
        Processes live candle updates (ohlc) or historic candles.
        If the epoch already exists, overwrites it with the latest data.
        Otherwise, appends it.
        """
        ohlc_data = data.get("ohlc")
        if ohlc_data:
            # Live stream update
            epoch = int(ohlc_data["open_time"])
            candle_dict = {
                "epoch": epoch,
                "open": float(ohlc_data["open"]),
                "high": float(ohlc_data["high"]),
                "low": float(ohlc_data["low"]),
                "close": float(ohlc_data["close"])
            }
        else:
            # Fallback to legacy candle structure
            candle_data = data.get("candle")
            if not candle_data:
                candle_data = data.get("candles")
                if isinstance(candle_data, list):
                    return
                if not candle_data:
                    return
            epoch = int(candle_data["epoch"])
            candle_dict = {
                "epoch": epoch,
                "open": float(candle_data["open"]),
                "high": float(candle_data["high"]),
                "low": float(candle_data["low"]),
                "close": float(candle_data["close"])
            }

        
        # Check if we already have this candle epoch
        if self.candles and self.candles[-1]["epoch"] == epoch:
            # Overwrite the latest candle (it is still building)
            self.candles[-1] = candle_dict
        elif self.candles and any(c["epoch"] == epoch for c in self.candles):
            # If it's a past candle, find and update it
            for i, c in enumerate(self.candles):
                if c["epoch"] == epoch:
                    self.candles[i] = candle_dict
                    break
        else:
            # New candle epoch started, append it
            self.candles.append(candle_dict)
            logger.info(f"New 1-Minute candle started. Epoch: {epoch}, Close: {candle_dict['close']}")
            
        # Keep list size reasonable (e.g. limit to last 100 candles)
        if len(self.candles) > 100:
            self.candles = self.candles[-100:]

    def get_candles_df(self) -> pd.DataFrame:
        """
        Converts the list of candles into a pandas DataFrame.
        """
        if not self.candles:
            return pd.DataFrame(columns=["epoch", "open", "high", "low", "close"])
        
        df = pd.DataFrame(self.candles)
        # Ensure values are float
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["epoch"] = df["epoch"].astype(int)
        return df
