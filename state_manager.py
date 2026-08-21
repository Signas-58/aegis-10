import os
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("StateManager")

STATE_FILE = "active_trade.json"

def load_active_trade() -> dict:
    """
    Loads active trade state from the local JSON file.
    Returns an empty dict if the file doesn't exist or is invalid.
    """
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            if not isinstance(state, dict):
                logger.warning(f"Malformed state file. Expected dict, got {type(state)}. Resetting.")
                return {}
            return state
    except json.JSONDecodeError:
        logger.error("Failed to parse state file (JSON decode error). Returning empty state.")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading active trade: {e}")
        return {}

def save_active_trade(contract_id: str, entry_price: float, stake: float, contract_type: str, timestamp: float) -> bool:
    """
    Saves the active trade details to a local JSON file for crash recovery.
    """
    state = {
        "contract_id": contract_id,
        "entry_price": entry_price,
        "stake": stake,
        "contract_type": contract_type,
        "timestamp": timestamp
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=4)
        logger.info(f"Persisted active trade state for contract {contract_id}.")
        return True
    except Exception as e:
        logger.error(f"Failed to save active trade state: {e}")
        return False

def clear_active_trade() -> bool:
    """
    Clears the active trade state file (deletes the file).
    """
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
            logger.info("Cleared active trade state file.")
            return True
        except Exception as e:
            logger.error(f"Failed to clear active trade state file: {e}")
            return False
    return True
