"""
MetaTrader 5 (Weltrade / MT5) Client Interface for Aegis-BTC.
Handles direct MT5 terminal login, MTF candle extraction (15m, 5m, 1m),
instant market order execution, position tracking, and dynamic trailing stop loss adjustments.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
import config

logger = logging.getLogger("AegisBTC.MT5Client")

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


class MT5Client:
    """
    Direct MetaTrader 5 Engine for Weltrade / MT5 Brokers.
    """
    def __init__(
        self,
        account: int = config.MT5_ACCOUNT,
        password: str = config.MT5_PASSWORD,
        server: str = config.MT5_SERVER,
        symbol: str = config.MT5_SYMBOL,
        volume: float = config.MT5_VOLUME
    ):
        self.account = account
        self.password = password
        self.server = server
        self.symbol = symbol
        self.volume = volume
        self.is_connected = False
        self.is_authorized = False
        self.account_info: Dict[str, Any] = {}
        
        # Ingested MTF candles
        self.candles_15m: List[Dict[str, float]] = []
        self.candles_5m: List[Dict[str, float]] = []
        self.candles_3m: List[Dict[str, float]] = []
        self.candles_1m: List[Dict[str, float]] = []
        
        # Position tracking
        self.active_ticket: Optional[int] = None

    def connect(self) -> bool:
        """
        Initialize MT5 terminal and authenticate account.
        """
        if mt5 is None:
            logger.error("`MetaTrader5` python package is not installed.")
            return False

        logger.info("Initializing MetaTrader 5 Terminal connection...")
        if not mt5.initialize():
            logger.error(f"MT5 initialize failed: {mt5.last_error()}")
            return False

        # Attempt explicit login if credentials are provided
        if self.account and self.password:
            logger.info(f"Logging in to MT5 Account: {self.account} on Server: {self.server}...")
            authorized = mt5.login(self.account, password=self.password, server=self.server)
            if not authorized:
                logger.error(f"MT5 login failed for Account {self.account}: {mt5.last_error()}")
                return False

        # Verify active account info
        acc = mt5.account_info()
        if acc is None:
            logger.error("Failed to retrieve MT5 account info.")
            return False

        self.account_info = {
            "account_id": str(acc.login),
            "balance": str(acc.balance),
            "equity": str(acc.equity),
            "currency": acc.currency,
            "server": acc.server,
            "account_type": "demo" if acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else "real"
        }
        self.is_connected = True
        self.is_authorized = True
        logger.info(
            f"🎉 [MT5 AUTH SUCCESS] Account: {acc.login} | Server: {acc.server} | "
            f"Balance: ${acc.balance:.2f} {acc.currency} | Equity: ${acc.equity:.2f}"
        )

        # Select & enable symbol in MarketWatch
        if not mt5.symbol_select(self.symbol, True):
            logger.warning(f"Symbol '{self.symbol}' not found directly. Searching available symbols...")
            selected = self._resolve_symbol_variant()
            if not selected:
                logger.error(f"Could not enable symbol '{self.symbol}' in MT5 MarketWatch.")
                return False

        return True

    def _resolve_symbol_variant(self) -> bool:
        """
        Auto-detect symbol variants if symbol differs (e.g. BTCUSD, BTCUSD.a, cryBTCUSD).
        """
        symbols = mt5.symbols_get()
        if not symbols:
            return False
        for s in symbols:
            if "BTCUSD" in s.name.upper() or "BITCOIN" in s.name.upper():
                logger.info(f"Matched symbol variant: '{s.name}' for trading.")
                self.symbol = s.name
                return mt5.symbol_select(self.symbol, True)
        return False

    def fetch_mtf_candles(self) -> bool:
        """
        Ingest 15m, 5m, 3m, and 1m OHLC rates directly from MT5 terminal memory.
        """
        if not self.is_connected or mt5 is None:
            return False

        timeframes = [
            (mt5.TIMEFRAME_M15, "15m"),
            (mt5.TIMEFRAME_M5, "5m"),
            (mt5.TIMEFRAME_M3, "3m"),
            (mt5.TIMEFRAME_M1, "1m")
        ]

        for tf, label in timeframes:
            rates = mt5.copy_rates_from_pos(self.symbol, tf, 0, 200)
            if rates is None or len(rates) == 0:
                logger.warning(f"Failed to fetch {label} rates for {self.symbol}.")
                continue
            
            formatted = [
                {
                    "open": float(r['open']),
                    "high": float(r['high']),
                    "low": float(r['low']),
                    "close": float(r['close']),
                    "epoch": int(r['time'])
                }
                for r in rates
            ]

            if tf == mt5.TIMEFRAME_M15:
                self.candles_15m = formatted
            elif tf == mt5.TIMEFRAME_M5:
                self.candles_5m = formatted
            elif tf == mt5.TIMEFRAME_M3:
                self.candles_3m = formatted
            elif tf == mt5.TIMEFRAME_M1:
                self.candles_1m = formatted

        return True

    def get_latest_price(self) -> float:
        """
        Fetch latest bid/ask spot tick for symbol.
        """
        if not self.is_connected or mt5 is None:
            return 0.0
        tick = mt5.symbol_info_tick(self.symbol)
        if tick:
            return float(tick.bid)
        return 0.0

    def send_order(self, signal_type: str, stop_loss_usd: float = config.HARD_STOP_LOSS_USD) -> Optional[Dict[str, Any]]:
        """
        Execute instant market ORDER_TYPE_BUY or ORDER_TYPE_SELL with explicit SL.
        """
        if not self.is_connected or mt5 is None:
            logger.error("Cannot send MT5 order: Not connected.")
            return None

        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            logger.error(f"Cannot fetch tick info for {self.symbol}.")
            return None

        order_type = mt5.ORDER_TYPE_BUY if signal_type in (config.CONTRACT_TYPE_UP, "BUY", "MULTUP") else mt5.ORDER_TYPE_SELL
        sl_distance = (stop_loss_usd / self.volume) if self.volume > 0 else 75.0
        tp_usd = self.volume * getattr(config, "TAKE_PROFIT_LOT_MULT", 100.0)
        tp_distance = (tp_usd / self.volume) if self.volume > 0 else 100.0

        if order_type == mt5.ORDER_TYPE_BUY:
            price = tick.ask
            sl = tick.bid - sl_distance
            tp = price + tp_distance
        else:
            price = tick.bid
            sl = tick.ask + sl_distance
            tp = price - tp_distance

        # Determine supported filling mode (Weltrade requires ORDER_FILLING_FOK)
        sym_info = mt5.symbol_info(self.symbol)
        filling_mode = mt5.ORDER_FILLING_FOK
        if sym_info and hasattr(sym_info, 'filling_mode'):
            # SYMBOL_FILLING_FOK = 1, SYMBOL_FILLING_IOC = 2
            if sym_info.filling_mode & 1:  # SYMBOL_FILLING_FOK flag
                filling_mode = mt5.ORDER_FILLING_FOK
            elif sym_info.filling_mode & 2:  # SYMBOL_FILLING_IOC flag
                filling_mode = mt5.ORDER_FILLING_IOC

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.volume,
            "type": order_type,
            "price": price,
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "deviation": 20,
            "magic": 108920,
            "comment": "Aegis-BTC Engine Trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }

        logger.info(f"Sending MT5 Order: {signal_type} {self.volume} lots {self.symbol} @ ${price:.2f} | SL: ${sl:.2f} | TP: ${tp:.2f} (+${tp_usd:.2f} target)")
        result = mt5.order_send(request)

        if result is None or result.retcode not in (mt5.TRADE_RETCODE_DONE, 10009):
            err = result.comment if result else mt5.last_error()
            logger.error(f"[MT5 ORDER FAILED] Retcode: {result.retcode if result else 'N/A'} | Reason: {err}")
            return None

        self.active_ticket = result.order
        logger.info(f"🎉 [MT5 ORDER EXECUTED] Ticket ID: {result.order} | Price: ${result.price:.2f}")
        return {
            "ticket": result.order,
            "price": result.price,
            "volume": result.volume,
            "symbol": self.symbol
        }

    def get_open_position(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve active MT5 open position for symbol.
        """
        if not self.is_connected or mt5 is None:
            return None

        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None or len(positions) == 0:
            self.active_ticket = None
            return None

        pos = positions[0]
        self.active_ticket = pos.ticket
        return {
            "ticket": pos.ticket,
            "type": "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
            "volume": pos.volume,
            "price_open": pos.price_open,
            "price_current": pos.price_current,
            "profit": pos.profit,
            "sl": pos.sl,
            "tp": pos.tp
        }

    def modify_position_sl(self, ticket: int, sl_floor_usd: float) -> bool:
        """
        Dynamically modify/ratchet server-side Stop Loss price level on MetaTrader 5 terminal.
        """
        if not self.is_connected or mt5 is None:
            return False

        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False

        pos = positions[0]
        entry_price = float(pos.price_open)
        volume = float(pos.volume) if pos.volume > 0 else self.volume

        # Convert USD SL floor into absolute price level based on position direction
        price_offset = sl_floor_usd / volume
        if pos.type == mt5.ORDER_TYPE_BUY:
            new_sl = entry_price + price_offset
        else:
            new_sl = entry_price - price_offset

        # Avoid redundant server calls if SL has not shifted (> $0.10 difference)
        if abs(new_sl - pos.sl) < 0.10:
            return True

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": self.symbol,
            "sl": round(new_sl, 2),
            "tp": pos.tp
        }

        logger.info(f"Modifying MT5 Server SL for Ticket #{pos.ticket}: New SL = ${new_sl:.2f} (Floor: ${sl_floor_usd:+.2f})")
        result = mt5.order_send(request)

        if result and result.retcode in (mt5.TRADE_RETCODE_DONE, 10009):
            logger.info(f"🎉 [MT5 SERVER SL UPDATED] Ticket #{pos.ticket} SL shifted to ${new_sl:.2f}")
            return True
        else:
            err = result.comment if result else mt5.last_error()
            logger.warning(f"Failed to update MT5 Server SL for Ticket #{pos.ticket}: {err}")
            return False

    def close_position(self, ticket: Optional[int] = None) -> bool:
        """
        Close active market deal by ticket ID.
        """
        if not self.is_connected or mt5 is None:
            return False

        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return False

        target = positions[0]
        if ticket:
            for p in positions:
                if p.ticket == ticket:
                    target = p
                    break

        order_type = mt5.ORDER_TYPE_SELL if target.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(self.symbol)
        price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask

        # Determine supported filling mode (Weltrade requires ORDER_FILLING_FOK)
        sym_info = mt5.symbol_info(self.symbol)
        filling_mode = mt5.ORDER_FILLING_FOK
        if sym_info and hasattr(sym_info, 'filling_mode'):
            if sym_info.filling_mode & 1:  # SYMBOL_FILLING_FOK flag
                filling_mode = mt5.ORDER_FILLING_FOK
            elif sym_info.filling_mode & 2:  # SYMBOL_FILLING_IOC flag
                filling_mode = mt5.ORDER_FILLING_IOC

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": target.volume,
            "type": order_type,
            "position": target.ticket,
            "price": price,
            "deviation": 20,
            "magic": 108920,
            "comment": "Aegis-BTC Close Deal",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }

        logger.info(f"Closing MT5 Position Ticket #{target.ticket} @ ${price:.2f}...")
        result = mt5.order_send(request)

        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"🎉 [MT5 POSITION CLOSED] Ticket #{target.ticket} | Profit: ${target.profit:.2f}")
            self.active_ticket = None
            return True

        logger.error(f"Failed to close MT5 Position Ticket #{target.ticket}: {result.comment if result else mt5.last_error()}")
        return False

    def close(self):
        """
        Shutdown MT5 connection.
        """
        if mt5 and self.is_connected:
            mt5.shutdown()
            self.is_connected = False
            logger.info("MT5 Terminal connection shutdown cleanly.")
