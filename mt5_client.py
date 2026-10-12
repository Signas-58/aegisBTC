"""
Backward-compatibility wrapper for MT5Client mapping to MT5Bridge.
"""
from mt5_bridge import MT5Bridge

class MT5Client(MT5Bridge):
    """
    Subclass of MT5Bridge providing backwards compatibility.
    """
    def fetch_historical_m1_candles(self, count: int = 1000):
        import config
        return self.fetch_candles(config.TF_TRIGGER, count=count)

    def fetch_mtf_candles(self):
        macro, structure, trigger = self.fetch_profile_candles()
        self.candles_15m = macro
        self.candles_5m = structure
        self.candles_3m = structure
        self.candles_1m = trigger
        return bool(macro and structure and trigger)

__all__ = ["MT5Client", "MT5Bridge"]
