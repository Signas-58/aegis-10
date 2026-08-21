import logging
from typing import Dict, Any, Optional

import config
from websocket_client import DerivWebSocketClient

logger = logging.getLogger("ExecutionEngine")

class ExecutionEngine:
    def __init__(self, client: DerivWebSocketClient):
        self.client = client

    async def get_proposal(self, contract_type: str, stake: float) -> Optional[str]:
        """
        Requests a contract proposal from Deriv.
        Returns the proposal ID if successful, or None.
        """
        logger.info(f"Requesting {contract_type} proposal for stake ${stake:.2f}...")
        payload = {
            "proposal": 1,
            "amount": stake,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": "USD",
            "multiplier": config.MULTIPLIER,
            "symbol": config.SYMBOL
        }
        
        try:
            response = await self.client.send_request(payload)
            if "error" in response:
                logger.error(f"Proposal request rejected: {response['error'].get('message')}")
                return None
            
            proposal_id = response.get("proposal", {}).get("id")
            if proposal_id:
                logger.info(f"Received proposal ID: {proposal_id}")
            return proposal_id
        except Exception as e:
            logger.error(f"Error requesting proposal: {e}")
            return None

    async def execute_order(self, proposal_id: str, stake: float) -> Optional[str]:
        """
        Executes a buy order for the given proposal ID.
        Returns the contract_id if successful, or None.
        """
        logger.info(f"Executing order for proposal ID {proposal_id}...")
        payload = {
            "buy": proposal_id,
            "price": stake
        }
        
        try:
            response = await self.client.send_request(payload)
            if "error" in response:
                logger.error(f"Order execution rejected: {response['error'].get('message')}")
                return None
            
            contract_id = response.get("buy", {}).get("contract_id")
            if contract_id:
                logger.info(f"Order executed successfully! Contract ID: {contract_id}")
            return str(contract_id)
        except Exception as e:
            logger.error(f"Error executing order: {e}")
            return None

    async def subscribe_open_contract(self, contract_id: str) -> bool:
        """
        Subscribes to updates for a specific contract to track live PnL.
        """
        logger.info(f"Subscribing to updates for contract ID {contract_id}...")
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
            logger.info(f"Subscribed to updates for contract {contract_id}.")
            return True
        except Exception as e:
            logger.error(f"Error subscribing to open contract: {e}")
            return False

    async def close_position(self, contract_id: str) -> bool:
        """
        Manually closes an active position (market exit).
        """
        logger.info(f"Sending request to close contract {contract_id}...")
        payload = {
            "sell": int(contract_id),
            "price": 0  # 0 means market close price
        }
        
        try:
            response = await self.client.send_request(payload)
            if "error" in response:
                logger.error(f"Failed to close contract {contract_id}: {response['error'].get('message')}")
                return False
            
            logger.info(f"Contract {contract_id} closed successfully.")
            return True
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False
