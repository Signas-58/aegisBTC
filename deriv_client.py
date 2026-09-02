"""
Deriv WebSocket & REST Client Interface for Aegis-BTC.
Handles async WebSocket connection, MTF candle streaming (15m, 5m, 1m),
REST Bearer authorization against Deriv trading endpoints, and proposal execution.
"""

import asyncio
import json
import logging
import urllib.request
from typing import Dict, Any, Callable, Optional, List
import config

logger = logging.getLogger("AegisBTC.DerivClient")

try:
    import websockets
except ImportError:
    websockets = None


class DerivWSClient:
    """
    WebSocket and REST API Manager for Deriv API.
    """
    def __init__(self, app_id: str = config.APP_ID, api_token: str = config.API_TOKEN):
        self.app_id = app_id
        self.api_token = api_token
        self.ws_url = f"wss://ws.derivws.com/websockets/v3?app_id=1089"
        self.rest_url = "https://api.derivws.com/trading/v1/options/accounts"
        self.ws = None
        self.is_connected = False
        self.is_authorized = False
        self.account_info = {}
        
        # Candles storage per granularity
        self.candles_15m: List[Dict[str, float]] = []
        self.candles_5m: List[Dict[str, float]] = []
        self.candles_1m: List[Dict[str, float]] = []
        
        # Callback subscriptions
        self.on_signal_callback: Optional[Callable] = None
        self.poc_callback: Optional[Callable] = None
        self.sell_error_callback: Optional[Callable] = None
        
        # Req IDs tracking
        self._req_id_counter = 1

    def _get_next_req_id(self) -> int:
        req_id = self._req_id_counter
        self._req_id_counter += 1
        return req_id

    def check_rest_auth(self) -> bool:
        """
        Authenticate via Deriv REST API using Bearer Token & App ID.
        """
        if not self.api_token:
            logger.warning("No DERIV_TOKEN set. Skipping REST authorization check.")
            return False

        headers = {
            "Deriv-App-ID": self.app_id if self.app_id else "32hxfkzWYA2IiQoReM03s",
            "Authorization": f"Bearer {self.api_token}",
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json"
        }
        try:
            req = urllib.request.Request(self.rest_url, headers=headers, method="GET")
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                accounts = data.get("data", [])
                
                # First pass: Look for exact configured account ID (e.g. DOT93113459)
                target_acc = None
                for acc in accounts:
                    if acc.get("account_id") == config.DERIV_ACCOUNT_ID:
                        target_acc = acc
                        break
                
                # Second pass: Fallback to demo account if configured account ID not found
                if not target_acc:
                    for acc in accounts:
                        if acc.get("account_type") == "demo":
                            target_acc = acc
                            break

                if target_acc:
                    self.account_info = target_acc
                    self.is_authorized = True
                    logger.info(
                        f"🎉 [REST AUTH SUCCESS] Connected Account: {target_acc.get('account_id')} | "
                        f"Type: {target_acc.get('account_type')} | Balance: ${float(target_acc.get('balance', 0)):.2f} {target_acc.get('currency')}"
                    )
                    return True
        except Exception as e:
            logger.debug(f"REST Auth check notice: {e}")
        return False

    async def connect(self) -> bool:
        """
        Connect to Deriv WS endpoint and authorize with API Token.
        """
        if websockets is None:
            logger.error("`websockets` package is not installed.")
            return False

        # Perform REST auth verification
        self.check_rest_auth()

        try:
            logger.info(f"Connecting to Deriv WebSocket Stream: {self.ws_url}...")
            self.ws = await websockets.connect(self.ws_url)
            self.is_connected = True
            logger.info("Deriv WebSocket stream connected successfully.")

            # Send WebSocket authorization if token is a classic V3 WS token (not pat_)
            if self.api_token and not self.api_token.startswith("pat_"):
                logger.info("Sending WebSocket authorization request...")
                auth_req = {"authorize": self.api_token, "req_id": self._get_next_req_id()}
                await self.send_json(auth_req)

            return True
        except Exception as e:
            logger.error(f"Failed to connect to Deriv WS: {e}")
            self.is_connected = False
            return False

    async def subscribe_mtf_candles(self, symbol: str = config.SYMBOL):
        """
        Fetch 15m, 5m, and 1m OHLC candles for the specified symbol.
        """
        for granularity, label in [(900, "15m"), (300, "5m"), (60, "1m")]:
            req = {
                "ticks_history": symbol,
                "count": 200,
                "end": "latest",
                "granularity": granularity,
                "style": "candles",
                "req_id": self._get_next_req_id()
            }
            await self.send_json(req)
            logger.debug(f"Ingested {symbol} {label} candles (granularity: {granularity}s).")

    async def send_proposal(self, proposal_payload: Dict[str, Any]) -> int:
        req_id = self._get_next_req_id()
        proposal_payload["req_id"] = req_id
        await self.send_json(proposal_payload)
        return req_id

    async def buy_contract(self, proposal_id: str, price: float = config.STAKE) -> int:
        req_id = self._get_next_req_id()
        payload = {
            "buy": proposal_id,
            "price": price,
            "req_id": req_id
        }
        await self.send_json(payload)
        logger.info(f"Sent BUY request for Proposal ID: {proposal_id} at price ${price:.2f}")
        return req_id

    async def subscribe_poc(self, contract_id: int) -> int:
        req_id = self._get_next_req_id()
        payload = {
            "proposal_open_contract": 1,
            "contract_id": contract_id,
            "subscribe": 1,
            "req_id": req_id
        }
        await self.send_json(payload)
        logger.info(f"Subscribed to Proposal Open Contract tracking for ID: {contract_id}")
        return req_id

    async def manual_sell_contract(self, contract_id: int, price: float = 0.0) -> int:
        req_id = self._get_next_req_id()
        payload = {
            "sell": contract_id,
            "price": price,
            "req_id": req_id
        }
        await self.send_json(payload)
        logger.info(f"Sent MANUAL SELL request for Contract ID: {contract_id}")
        return req_id

    async def send_json(self, payload: Dict[str, Any]):
        if not self.ws or not self.is_connected:
            logger.error("Cannot send WebSocket message: Not connected.")
            return
        await self.ws.send(json.dumps(payload))

    async def listen_loop(self):
        """
        Main message processing loop.
        """
        if not self.ws:
            return
            
        try:
            async for raw_msg in self.ws:
                msg = json.loads(raw_msg)
                msg_type = msg.get("msg_type")

                if "error" in msg:
                    err_details = msg["error"]
                    err_msg = err_details.get("message", "Unknown error")
                    err_code = err_details.get("code", "UNKNOWN")
                    logger.error(f"[DERIV API ERROR] Code: {err_code} | Msg: {err_msg}")
                    if self.sell_error_callback:
                        self.sell_error_callback(err_msg)
                    continue

                if msg_type == "authorize":
                    auth_info = msg.get("authorize", {})
                    acc_id = auth_info.get("loginid")
                    bal = auth_info.get("balance")
                    currency = auth_info.get("currency")
                    self.is_authorized = True
                    logger.info(f"🎉 [WS AUTH SUCCESS] Connected Account: {acc_id} | Balance: ${bal} {currency}")

                elif msg_type in ("candles", "ohlc"):
                    self._process_candle_message(msg)

                elif msg_type == "proposal":
                    proposal = msg.get("proposal", {})
                    prop_id = proposal.get("id")
                    if prop_id:
                        logger.info(f"[PROPOSAL CONFIRMED] ID: {prop_id} | Ask Price: ${proposal.get('ask_price')}")
                        await self.buy_contract(prop_id)

                elif msg_type == "buy":
                    buy_info = msg.get("buy", {})
                    contract_id = buy_info.get("contract_id")
                    if contract_id:
                        logger.info(f"[BUY CONFIRMED] Purchased Contract ID: {contract_id}")
                        await self.subscribe_poc(contract_id)

                elif msg_type == "proposal_open_contract":
                    poc = msg.get("proposal_open_contract", {})
                    if self.poc_callback and poc:
                        self.poc_callback(poc)

        except websockets.exceptions.ConnectionClosed:
            logger.warning("Deriv WebSocket connection closed.")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Error in WebSocket listen loop: {e}")
            self.is_connected = False

    def _process_candle_message(self, msg: Dict[str, Any]):
        echo_req = msg.get("echo_req", {})
        granularity = echo_req.get("granularity") or (msg.get("ohlc", {}).get("granularity"))
        
        if "candles" in msg:
            raw_candles = msg["candles"]
            formatted = [
                {
                    "open": float(c["open"]),
                    "high": float(c["high"]),
                    "low": float(c["low"]),
                    "close": float(c["close"]),
                    "epoch": int(c["epoch"])
                }
                for c in raw_candles
            ]
            if granularity == 900:
                self.candles_15m = formatted
            elif granularity == 300:
                self.candles_5m = formatted
            elif granularity == 60:
                self.candles_1m = formatted

        elif "ohlc" in msg:
            ohlc = msg["ohlc"]
            candle = {
                "open": float(ohlc["open"]),
                "high": float(ohlc["high"]),
                "low": float(ohlc["low"]),
                "close": float(ohlc["close"]),
                "epoch": int(ohlc["open_time"])
            }
            g = int(ohlc.get("granularity", 0))
            if g == 900:
                self._update_single_candle(self.candles_15m, candle)
            elif g == 300:
                self._update_single_candle(self.candles_5m, candle)
            elif g == 60:
                self._update_single_candle(self.candles_1m, candle)

    def _update_single_candle(self, candle_list: List[Dict[str, float]], new_candle: Dict[str, float]):
        if not candle_list:
            candle_list.append(new_candle)
            return
        if candle_list[-1]["epoch"] == new_candle["epoch"]:
            candle_list[-1] = new_candle
        else:
            candle_list.append(new_candle)
            if len(candle_list) > 300:
                candle_list.pop(0)

    async def close(self):
        if self.ws and self.is_connected:
            await self.ws.close()
            self.is_connected = False
            logger.info("Deriv WebSocket connection closed cleanly.")
