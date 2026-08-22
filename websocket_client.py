import asyncio
import json
import ssl
import logging
import websockets
import urllib.request
import urllib.error
from typing import Dict, Any, Callable, Awaitable

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DerivWebSocketClient")

class DerivWebSocketClient:
    def __init__(self):
        self.ws = None
        self.req_id_counter = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self.subscriptions: Dict[str, Callable[[Dict[str, Any]], Awaitable[None]]] = {}
        self.ping_task = None
        self.read_task = None
        self.is_connected = False
        self.is_authorized = False

    def _get_otp_url_sync(self) -> str:
        """
        Calls the REST endpoint to get an authenticated OTP WebSocket URL.
        """
        logger.info(f"Requesting trading OTP from REST URL: {config.OTP_REST_ENDPOINT}...")
        req = urllib.request.Request(
            config.OTP_REST_ENDPOINT,
            method="POST",
            headers={
                "Authorization": f"Bearer {config.DERIV_TOKEN}",
                "Deriv-App-ID": config.APP_ID,
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, data=b"{}") as response:
            res_data = json.loads(response.read().decode("utf-8"))
            # Handle nested data structure
            url = None
            if "data" in res_data and isinstance(res_data["data"], dict):
                url = res_data["data"].get("url")
            if not url and "url" in res_data:
                url = res_data["url"]
                
            if url:
                return url
            raise ValueError(f"OTP response did not contain 'url': {res_data}")


    async def connect(self):
        """
        Connects to the Deriv WebSocket endpoint.
        """
        is_pat_token = config.DERIV_TOKEN.startswith("pat_")
        is_dot_account = config.DERIV_ACCOUNT_ID.startswith("DOT") or config.DERIV_ACCOUNT_ID.startswith("ROT")
        
        ws_url = config.WS_ENDPOINT
        self.is_authorized = False

        if is_pat_token and is_dot_account:
            logger.info("New Deriv Options Account detected. Requesting OTP authenticated WebSocket URL...")
            try:
                ws_url = await asyncio.to_thread(self._get_otp_url_sync)
                logger.info("Successfully retrieved OTP WebSocket URL.")
                self.is_authorized = True
            except Exception as e:
                logger.error(f"Failed to fetch OTP WebSocket URL: {e}. Falling back to standard WebSocket connection.")

        logger.info(f"Connecting to Deriv WebSocket at {ws_url}...")
        try:
            # Deriv requires SSL and Origin matching the registered App domain
            ssl_context = ssl.create_default_context()
            self.ws = await websockets.connect(
                ws_url, 
                ssl=ssl_context, 
                origin="https://localhost"
            )


            self.is_connected = True
            logger.info("WebSocket connection established.")
            
            # Start background tasks
            self.read_task = asyncio.create_task(self._read_loop())
            self.ping_task = asyncio.create_task(self._ping_loop())
            
            return True
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.is_connected = False
            return False

    async def disconnect(self):
        """
        Disconnects the WebSocket client and cleans up background tasks.
        """
        logger.info("Disconnecting WebSocket client...")
        self.is_connected = False
        self.is_authorized = False
        
        if self.ping_task:
            self.ping_task.cancel()
            self.ping_task = None
            
        if self.ws:
            await self.ws.close()
            self.ws = None
            
        if self.read_task:
            self.read_task.cancel()
            self.read_task = None
            
        logger.info("WebSocket disconnected.")

    async def send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends a request payload, automatically assigns a req_id, 
        and waits for the matching response.
        """
        if not self.is_connected or not self.ws:
            raise ConnectionError("WebSocket is not connected.")

        self.req_id_counter += 1
        req_id = self.req_id_counter
        payload["req_id"] = req_id
        
        future = asyncio.get_running_loop().create_future()
        self.pending_requests[req_id] = future
        
        await self.ws.send(json.dumps(payload))
        
        try:
            # Wait for response with a timeout of 10 seconds
            response = await asyncio.wait_for(future, timeout=10.0)
            return response
        except asyncio.TimeoutError:
            self.pending_requests.pop(req_id, None)
            logger.error(f"Request {req_id} timed out. Payload: {payload}")
            raise TimeoutError(f"Request {req_id} timed out.")
        except Exception as e:
            self.pending_requests.pop(req_id, None)
            logger.error(f"Error in request {req_id}: {e}")
            raise

    async def authorize(self) -> bool:
        """
        Authorizes the connection using the DERIV_TOKEN.
        """
        if self.is_authorized:
            logger.info("Connection is already authorized via OTP WebSocket URL.")
            return True

        if not config.DERIV_TOKEN:
            logger.error("DERIV_TOKEN is empty. Cannot authorize connection.")
            return False

        logger.info("Sending authorization request...")
        payload = {"authorize": config.DERIV_TOKEN}
        try:
            response = await self.send_request(payload)
            if "error" in response:
                logger.error(f"Authorization failed: {response['error'].get('message')}")
                self.is_authorized = False
                return False
            
            logger.info("Authorization successful!")
            self.is_authorized = True
            return True
        except Exception as e:
            logger.error(f"Authorization request error: {e}")
            self.is_authorized = False
            return False

    def register_subscription(self, msg_type: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]):
        """
        Registers a callback to receive incoming stream updates of a specific msg_type.
        """
        self.subscriptions[msg_type] = callback
        logger.info(f"Registered stream handler for type '{msg_type}'.")

    async def _ping_loop(self):
        """
        Background heartbeat task sending ping every PING_INTERVAL seconds.
        """
        try:
            while self.is_connected:
                await asyncio.sleep(config.PING_INTERVAL)
                if self.is_connected and self.ws:
                    # Heartbeat payload
                    await self.ws.send(json.dumps({"ping": 1}))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in ping heartbeat loop: {e}")

    async def _safe_dispatch_callback(self, msg_type: str, data: Dict[str, Any]):
        try:
            await self.subscriptions[msg_type](data)
        except Exception as callback_err:
            logger.error(f"Error in stream callback for '{msg_type}': {callback_err}")

    async def _read_loop(self):
        """
        Background task reading messages from the WebSocket.
        """
        try:
            async for message in self.ws:
                data = json.loads(message)
                req_id = data.get("req_id")
                msg_type = data.get("msg_type")
                
                # 1. Resolve matching request futures
                if req_id in self.pending_requests:
                    future = self.pending_requests.pop(req_id)
                    if not future.done():
                        future.set_result(data)
                        
                # 2. Dispatch to stream subscribers
                if msg_type in self.subscriptions:
                    asyncio.create_task(self._safe_dispatch_callback(msg_type, data))
                        
        except asyncio.CancelledError:
            pass
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket connection closed: {e}")
            self.is_connected = False
            self.is_authorized = False
        except Exception as e:
            logger.error(f"Error in read loop: {e}")
            self.is_connected = False
            self.is_authorized = False

