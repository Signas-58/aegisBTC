"""
MT5 Execution Bridge for Aegis-Weltrade.
Handles connection lifecycle, dynamic filling-mode resolution, multi-timeframe candle extraction,
relative spread validation, market order execution, and server-side SL modification.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
import config

logger = logging.getLogger("AegisBTC.MT5Bridge")

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


class MT5Bridge:
    """
    Direct MetaTrader 5 Bridge for Weltrade & MT5 brokers.
    Encapsulates dynamic filling-mode resolution, spread filters, and order routing.
    """
    def __init__(
        self,
        account: int = config.WELTRADE_LOGIN,
        password: str = config.WELTRADE_PASSWORD,
        server: str = config.WELTRADE_SERVER,
        symbol: str = config.SYMBOL,
        lot_size: float = config.LOT_SIZE
    ):
        self.account = account
        self.password = password
        self.server = server
        self.symbol = symbol
        self.lot_size = lot_size
        self.is_connected = False
        self.is_authorized = False
        self.account_info: Dict[str, Any] = {}
        self.filling_type = None

        # Rolling spread buffer (last 20 checks)
        self.recent_spreads: List[float] = []

    def connect(self) -> bool:
        """Initialize MT5 terminal connection and authenticate account."""
        if mt5 is None:
            logger.error("`MetaTrader5` python library is not installed.")
            return False

        logger.info("Initializing MetaTrader 5 Terminal connection...")
        if not mt5.initialize():
            logger.error(f"MT5 initialize failed: {mt5.last_error()}")
            return False

        if self.account and self.password:
            logger.info(f"Logging in to MT5 Account: {self.account} on Server: {self.server}...")
            authorized = mt5.login(self.account, password=self.password, server=self.server)
            if not authorized:
                logger.error(f"MT5 login failed for Account {self.account}: {mt5.last_error()}")
                return False

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

        if not mt5.symbol_select(self.symbol, True):
            logger.warning(f"Symbol '{self.symbol}' not found directly. Resolving variant...")
            if not self._resolve_symbol_variant():
                logger.error(f"Could not enable symbol '{self.symbol}' in MT5 MarketWatch.")
                return False

        self.resolve_filling_mode()
        return True

    def _resolve_symbol_variant(self) -> bool:
        """Attempt to find broker-specific symbol variants (e.g. EURUSD.pro, EURUSDm)."""
        if mt5 is None:
            return False
        all_symbols = mt5.symbols_get()
        if not all_symbols:
            return False

        clean_target = self.symbol.replace("/", "").replace("_", "").upper()
        for s in all_symbols:
            s_name = s.name.upper()
            if clean_target in s_name:
                logger.info(f"Resolved symbol variant: '{self.symbol}' -> '{s.name}'")
                self.symbol = s.name
                config.SYMBOL = s.name
                mt5.symbol_select(s.name, True)
                return True
        return False

    def resolve_filling_mode(self) -> int:
        """
        Inspect symbol_info.filling_mode bitmask and select an allowed filling type.
        Prevents 10030 (Unsupported filling mode) rejections.
        """
        if mt5 is None:
            return 0
        info = mt5.symbol_info(self.symbol)
        if not info:
            self.filling_type = mt5.ORDER_FILLING_IOC
            return self.filling_type

        modes = info.filling_mode
        # Bitmask check: 1 = FOK, 2 = IOC, 0/None = Return
        if modes & 2:
            self.filling_type = mt5.ORDER_FILLING_IOC
        elif modes & 1:
            self.filling_type = mt5.ORDER_FILLING_FOK
        else:
            self.filling_type = mt5.ORDER_FILLING_RETURN

        logger.info(f"[MT5 FILLING SOLVER] Resolved Filling Mode: {self.filling_type} (Flags: {modes})")
        return self.filling_type

    def get_timeframe_constant(self, seconds: int) -> int:
        """Map timeframe in seconds to official MT5 TIMEFRAME constants."""
        if mt5 is None:
            return 0
        mapping = {
            60: mt5.TIMEFRAME_M1,
            180: mt5.TIMEFRAME_M3,
            300: mt5.TIMEFRAME_M5,
            900: mt5.TIMEFRAME_M15,
            1800: mt5.TIMEFRAME_M30,
            3600: mt5.TIMEFRAME_H1,
            14400: mt5.TIMEFRAME_H4,
            86400: mt5.TIMEFRAME_D1,
        }
        return mapping.get(seconds, mt5.TIMEFRAME_M5)

    def fetch_candles(self, seconds: int, count: int = 100) -> List[Dict[str, float]]:
        """Fetch historical candles for any given timeframe from MT5."""
        if mt5 is None or not self.is_connected:
            return []

        tf_const = self.get_timeframe_constant(seconds)
        rates = mt5.copy_rates_from_pos(self.symbol, tf_const, 0, count)
        if rates is None or len(rates) == 0:
            return []

        candles = []
        for r in rates:
            candles.append({
                "time": float(r['time']),
                "open": float(r['open']),
                "high": float(r['high']),
                "low": float(r['low']),
                "close": float(r['close']),
                "volume": float(r['tick_volume'])
            })
        return candles

    def fetch_profile_candles(self) -> Tuple[List[Dict[str, float]], List[Dict[str, float]], List[Dict[str, float]]]:
        """
        Dynamically fetches macro, structure, and trigger candles as defined by active profile.
        Returns (macro_candles, structure_candles, trigger_candles).
        """
        macro = self.fetch_candles(config.TF_MACRO, count=220)
        structure = self.fetch_candles(config.TF_STRUCTURE, count=100)
        trigger = self.fetch_candles(config.TF_TRIGGER, count=100)
        return macro, structure, trigger

    def get_live_tick(self) -> Optional[Dict[str, float]]:
        """Fetch current bid, ask, and spread in pips with candle rate fallback."""
        if mt5 is None or not self.is_connected:
            return None

        tick = mt5.symbol_info_tick(self.symbol)
        sym_info = mt5.symbol_info(self.symbol)
        point = sym_info.point if sym_info else 0.00001
        pip_unit = 0.0001 if ("EUR" in self.symbol.upper() or "USD" in self.symbol.upper()) else point * 10

        bid = float(tick.bid) if (tick and tick.bid > 0.0) else 0.0
        ask = float(tick.ask) if (tick and tick.ask > 0.0) else 0.0
        last = float(tick.last) if (tick and tick.last > 0.0) else bid
        tick_time = float(tick.time) if (tick and tick.time > 0) else time.time()

        # Fallback to latest M1 bar if live tick stream is idle
        if bid == 0.0 or ask == 0.0:
            rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M1, 0, 1)
            if rates is not None and len(rates) > 0:
                r = rates[0]
                bid = float(r['close'])
                spread_pts = float(r['spread']) if r['spread'] > 0 else 9.0
                ask = round(bid + (spread_pts * point), 5)
                last = bid
                tick_time = float(r['time'])

        spread_pips = (ask - bid) / pip_unit if pip_unit > 0 else 0.0

        # Update rolling spread buffer
        if spread_pips > 0.0:
            self.recent_spreads.append(spread_pips)
            if len(self.recent_spreads) > 20:
                self.recent_spreads.pop(0)

        mean_spread = sum(self.recent_spreads) / len(self.recent_spreads) if self.recent_spreads else spread_pips

        return {
            "bid": float(bid),
            "ask": float(ask),
            "last": float(last),
            "spread_pips": float(spread_pips),
            "mean_spread_pips": float(mean_spread),
            "pip_unit": float(pip_unit),
            "point": float(point),
            "time": float(tick_time)
        }

    def validate_spread(self) -> Tuple[bool, str, float]:
        """
        Validate live bid-ask spread against absolute MAX_ALLOWED_SPREAD_PIPS
        and relative RELATIVE_SPREAD_MULTIPLIER * 20-tick mean spread.
        """
        tick = self.get_live_tick()
        if not tick:
            return False, "Failed to retrieve live tick", 999.0

        spread = tick["spread_pips"]
        mean_spread = tick["mean_spread_pips"]

        # Absolute limit
        if spread > config.MAX_ALLOWED_SPREAD_PIPS:
            return False, f"Spread {spread:.2f} pips exceeds max threshold {config.MAX_ALLOWED_SPREAD_PIPS:.2f} pips", spread

        # Dynamic relative multiplier limit
        if len(self.recent_spreads) >= 10:
            allowed_relative = mean_spread * config.RELATIVE_SPREAD_MULTIPLIER
            if spread > allowed_relative:
                return False, f"Spread {spread:.2f} pips exceeds 1.5x rolling average ({allowed_relative:.2f} pips)", spread

        return True, "Spread OK", spread

    def send_order(
        self,
        direction: str,
        volume: Optional[float] = None,
        sl_pips: Optional[float] = None,
        tp_pips: Optional[float] = None,
        comment: str = ""
    ) -> Optional[int]:
        """
        Dispatch a BUY or SELL market order attaching magic number, SL, and TP.
        """
        if mt5 is None or not self.is_connected:
            logger.error("MT5 not connected. Cannot dispatch order.")
            return None

        # Validate spread before firing
        is_spread_valid, reason, current_spread = self.validate_spread()
        if not is_spread_valid:
            logger.warning(f"🚫 [ORDER REJECTED - SPREAD FILTER] {reason}")
            return None

        vol = volume if volume is not None else self.lot_size
        sl_pips_val = sl_pips if sl_pips is not None else config.HARD_SL_PIPS
        tp_pips_val = tp_pips if tp_pips is not None else config.FIXED_TP_PIPS

        tick = self.get_live_tick()
        if not tick:
            logger.error("Cannot send order: no live tick.")
            return None

        is_buy = direction.upper() in ("BUY", "MULTUP")
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        price = tick["ask"] if is_buy else tick["bid"]
        pip_unit = tick["pip_unit"]

        if is_buy:
            sl_price = round(price - (sl_pips_val * pip_unit), 5)
            tp_price = round(price + (tp_pips_val * pip_unit), 5)
        else:
            sl_price = round(price + (sl_pips_val * pip_unit), 5)
            tp_price = round(price - (tp_pips_val * pip_unit), 5)

        filling = self.filling_type if self.filling_type is not None else mt5.ORDER_FILLING_IOC
        magic = config.MAGIC_NUMBER
        comm = comment or f"Aegis_{config.ACTIVE_MODE}"

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": vol,
            "type": order_type,
            "price": price,
            "sl": sl_price,
            "tp": tp_price,
            "deviation": 20,
            "magic": magic,
            "comment": comm,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

        logger.info(
            f"🚀 [MT5 ORDER DISPATCH] {direction.upper()} {vol} lots {self.symbol} @ {price:.5f} | "
            f"SL: {sl_price:.5f} ({sl_pips_val:.1f}p) | TP: {tp_price:.5f} ({tp_pips_val:.1f}p) | Magic: {magic}"
        )

        result = mt5.order_send(request)
        if result is None:
            logger.error(f"MT5 order_send returned None. Error: {mt5.last_error()}")
            return None

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"❌ [ORDER REJECTED] Retcode: {result.retcode} | Comment: {result.comment}")
            return None

        logger.info(f"✅ [ORDER FILLED] Ticket #{result.order} | Price: {result.price:.5f} | Volume: {result.volume}")
        return result.order

    def get_open_positions(self, magic_number: Optional[int] = None) -> List[Any]:
        """Fetch active open positions filtered by magic number and symbol."""
        if mt5 is None or not self.is_connected:
            return []

        magic = magic_number if magic_number is not None else config.MAGIC_NUMBER
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            return []

        return [p for p in positions if p.magic == magic]

    def modify_position_sl(self, ticket: int, new_sl: float) -> bool:
        """Modify server-side Stop Loss on an active position ticket."""
        if mt5 is None or not self.is_connected:
            return False

        position = None
        for p in mt5.positions_get(symbol=self.symbol) or []:
            if p.ticket == ticket:
                position = p
                break

        if not position:
            logger.warning(f"Position #{ticket} not found for SL modification.")
            return False

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": self.symbol,
            "sl": round(new_sl, 5),
            "tp": position.tp,
            "magic": position.magic
        }

        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"🛡️ [SL MODIFIED SERVER-SIDE] Ticket #{ticket} new SL: {new_sl:.5f}")
            return True
        else:
            retcode = res.retcode if res else "None"
            logger.warning(f"Failed to modify SL on ticket #{ticket}: Retcode {retcode}")
            return False

    def close_position(self, ticket: int) -> bool:
        """Close an active position ticket at current market price."""
        if mt5 is None or not self.is_connected:
            return False

        position = None
        for p in mt5.positions_get(symbol=self.symbol) or []:
            if p.ticket == ticket:
                position = p
                break

        if not position:
            return False

        tick = self.get_live_tick()
        if not tick:
            return False

        is_buy = (position.type == mt5.ORDER_TYPE_BUY)
        close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
        price = tick["bid"] if is_buy else tick["ask"]

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": self.symbol,
            "volume": position.volume,
            "type": close_type,
            "price": price,
            "deviation": 20,
            "magic": position.magic,
            "comment": f"Aegis_Close_{ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self.filling_type if self.filling_type is not None else mt5.ORDER_FILLING_IOC
        }

        res = mt5.order_send(request)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"🚪 [POSITION CLOSED] Ticket #{ticket} closed at {price:.5f}")
            return True
        else:
            retcode = res.retcode if res else "None"
            logger.error(f"Failed to close position #{ticket}: Retcode {retcode}")
            return False
