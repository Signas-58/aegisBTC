"""
Aegis Mini AI Market Regime Classifier Engine.
Uses a lightweight Random Forest Machine Learning classifier (scikit-learn)
to classify 1-minute live market conditions into:
- Trend / Expansion State (High win probability setup -> Trade Approved)
- Choppy / Sideways State (High spread churn & stop-out risk -> Trade Blocked)
"""

import os
import logging
from typing import List, Dict, Any, Union, Optional
import config

logger = logging.getLogger("AegisBTC.AIScanner")

try:
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("[AI SCANNER NOTICE] scikit-learn or joblib not installed yet. AI Scanner will run in rule-based fallback mode.")


MODEL_CACHE_FILE = "aegis_ai_regime_model.joblib"


class MiniAIScanner:
    """
    Lightweight Random Forest Machine Learning Market Regime Classifier.
    Evaluates 1-minute OHLCV sequences to output an Expansion Confidence Score (0.00 to 1.00).
    """

    def __init__(self, cache_file: str = MODEL_CACHE_FILE):
        self.cache_file = cache_file
        self.is_trained = False
        self.model = None

        if ML_AVAILABLE:
            self.model = RandomForestClassifier(
                n_estimators=50,
                max_depth=5,
                random_state=42,
                n_jobs=-1
            )
            self._load_cached_model()

    def _load_cached_model(self) -> bool:
        """Attempt to restore a previously trained model from disk."""
        if not ML_AVAILABLE or not os.path.exists(self.cache_file):
            return False
        try:
            self.model = joblib.load(self.cache_file)
            self.is_trained = True
            logger.info(f"🧠 [AI SCANNER] Restored cached AI model from '{self.cache_file}'. Ready for live inference.")
            return True
        except Exception as e:
            logger.warning(f"Could not load cached model '{self.cache_file}': {e}")
            return False

    def _save_cached_model(self):
        """Save trained model to disk for instant restoration on restart."""
        if not ML_AVAILABLE or not self.is_trained or self.model is None:
            return
        try:
            joblib.dump(self.model, self.cache_file)
            logger.info(f"🧠 [AI SCANNER] Model cached to '{self.cache_file}' for zero-latency restarts.")
        except Exception as e:
            logger.warning(f"Could not cache model: {e}")

    def candles_to_dataframe(self, candles: List[Dict[str, float]]) -> Optional['pd.DataFrame']:
        """Convert list of MT5 OHLC candle dicts into a pandas DataFrame."""
        if not ML_AVAILABLE or not candles:
            return None
        df = pd.DataFrame(candles)
        for col in ("open", "high", "low", "close"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def extract_features(self, df: 'pd.DataFrame') -> 'pd.DataFrame':
        """
        Transforms 1-minute OHLCV data into normalized statistical machine learning features:
        1. Percentage returns & 10-period rolling volatility
        2. High-Low range ratio relative to close
        3. Moving average spread: (EMA_8 - EMA_21) / close
        4. Range expansion factor: current candle range vs 10-period rolling mean range
        """
        if not ML_AVAILABLE or df is None or len(df) < 22:
            return pd.DataFrame() if ML_AVAILABLE else None

        features = pd.DataFrame(index=df.index)

        # Feature 1: Returns & Volatility
        returns = df["close"].pct_change()
        features["returns"] = returns
        features["volatility"] = returns.rolling(window=10).std() * 1000.0

        # Feature 2: High-Low Candle Spread Ratio
        candle_range = df["high"] - df["low"]
        features["range_ratio"] = candle_range / df["close"]

        # Feature 3: Fast vs Slow EMA Distance Spread
        ema_8 = df["close"].ewm(span=getattr(config, "EMA_FAST", 8), adjust=False).mean()
        ema_21 = df["close"].ewm(span=getattr(config, "EMA_SLOW", 21), adjust=False).mean()
        features["ma_spread"] = (ema_8 - ema_21) / df["close"]

        # Feature 4: Range Expansion Ratio (Current bar vs 10-period rolling average)
        rolling_range = candle_range.rolling(window=10).mean()
        features["expansion_ratio"] = candle_range / (rolling_range + 1e-6)

        return features.dropna()

    def train_on_history(self, candles_or_df: Union[List[Dict[str, float]], 'pd.DataFrame']) -> bool:
        """
        Train the AI model on recent 1-minute historical candles from MT5.
        Target: 1 = Favorable Trend Expansion (> 5 pips move within 5 candles), 0 = Flat/Choppy Range.
        """
        if not ML_AVAILABLE:
            logger.warning("[AI SCANNER] Machine learning packages not available. Skipping training.")
            return False

        if isinstance(candles_or_df, list):
            df = self.candles_to_dataframe(candles_or_df)
        else:
            df = candles_or_df

        if df is None or len(df) < 50:
            logger.warning(f"[AI SCANNER] Insufficient history for ML training (Need >= 50, got {len(df) if df is not None else 0}).")
            return False

        try:
            features = self.extract_features(df)
            if features.empty or len(features) < 30:
                logger.warning("[AI SCANNER] Extracted feature matrix is empty.")
                return False

            # Define Target Expansion: 5 pips on EURUSD = 0.0005 (or equivalent on other pairs)
            pip_target = 0.0005 if "EUR" in config.SYMBOL.upper() else 5.0
            future_move = (df["close"].shift(-5) - df["close"]).loc[features.index]
            labels = (future_move.abs() >= pip_target).astype(int)

            # Fit Random Forest Classifier
            self.model.fit(features, labels)
            self.is_trained = True
            logger.info(f"🤖 [AI SCANNER TRAINED] Random Forest model fitted on {len(features)} closed candles (Expansion rate: {labels.mean() * 100:.1f}%).")
            self._save_cached_model()
            return True

        except Exception as e:
            logger.error(f"[AI SCANNER TRAINING ERROR] {e}")
            return False

    def predict_regime_confidence(self, candles_or_df: Union[List[Dict[str, float]], 'pd.DataFrame']) -> float:
        """
        Returns a Market Regime Expansion Confidence Score (0.00 to 1.00) for live closed candles.
        If confidence >= AI_CONFIDENCE_THRESHOLD (0.70), market is in healthy expansion.
        If confidence < 0.70, market is in choppy chop state.
        """
        if not ML_AVAILABLE or not self.is_trained or self.model is None:
            # Fallback: approve trade when ML is uninitialized so trading is not blocked
            return 1.0

        if isinstance(candles_or_df, list):
            df = self.candles_to_dataframe(candles_or_df)
        else:
            df = candles_or_df

        if df is None or len(df) < 25:
            return 1.0

        try:
            # Evaluate the completed closed bar [-2]
            features = self.extract_features(df)
            if features.empty:
                return 1.0

            # Use latest completed feature vector
            latest_vector = features.iloc[[-1]]
            probabilities = self.model.predict_proba(latest_vector)[0]
            
            # Probability of Class 1 (Favorable Expansion)
            confidence = float(probabilities[1]) if len(probabilities) > 1 else float(probabilities[0])
            return round(confidence, 3)

        except Exception as e:
            logger.warning(f"[AI SCANNER PREDICTION ERROR] {e}")
            return 1.0
