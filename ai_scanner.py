"""
Aegis Profile-Adaptive AI Market Regime Classifier Engine.
Now re-exports DualAIEnsemble for backwards compatibility.
"""

from ai_ensemble import DualAIEnsemble, ML_AVAILABLE, get_ensemble_cache_path

# Alias MiniAIScanner to DualAIEnsemble
class MiniAIScanner(DualAIEnsemble):
    """
    Subclass of DualAIEnsemble providing 100% backwards compatibility
    with existing tests and single-pair code.
    """
    def __init__(self, mode=None, cache_file=None, symbol=None):
        import config
        sym = symbol or getattr(config, "SYMBOL", "EURUSD")
        super().__init__(symbol=sym, mode=mode)
        if cache_file:
            self.cache_file = cache_file

    def train_on_history(self, candles_or_df):
        return self.train_ensemble(candles_or_df)

__all__ = ["MiniAIScanner", "DualAIEnsemble", "ML_AVAILABLE", "get_ensemble_cache_path"]
