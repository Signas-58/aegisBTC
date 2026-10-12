"""
Aegis Profile-Adaptive AI Market Regime Classifier Engine.
Uses a lightweight Random Forest Machine Learning classifier (scikit-learn)
specifically tuned to the active operational profile (SCALP_M1, EXPANSION_M5, SILVER_BULLET_PURE)
to classify live market conditions into:
- Trend / Expansion State (High probability setup -> Trade Approved)
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
    logger.warning("[AI SCANNER NOTICE] scikit-learn or joblib not installed. Running in rule-based fallback mode.")


def get_model_cache_path(mode: Optional[str] = None) -> str:
    """Generate profile-specific model cache filepath."""
    profile_mode = (mode or config.ACTIVE_MODE).upper()
    models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    os.makedirs(models_dir, exist_ok=True)
    return os.path.join(models_dir, f"regime_rf_{profile_mode}.joblib")


class MiniAIScanner:
    """
    Profile-Adaptive Random Forest Machine Learning Market Regime Classifier.
    Adapts features and labeling horizon based on the active profile.
    """

    def __init__(self, mode: Optional[str] = None, cache_file: Optional[str] = None):
        self.mode = (mode or config.ACTIVE_MODE).upper()
        self.cache_file = cache_file if cache_file else get_model_cache_path(self.mode)
        self.is_trained = False
        self.model = None

        if ML_AVAILABLE:
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=5,
                random_state=42,
                n_jobs=-1
            )
            self._load_cached_model()

    def set_mode(self, mode: str):
        """Switch operational profile and load profile-specific cached model."""
        self.mode = mode.upper()
        self.cache_file = get_model_cache_path(self.mode)
        self.is_trained = False
        if ML_AVAILABLE:
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=5,
                random_state=42,
                n_jobs=-1
            )
            self._load_cached_model()

    def _load_cached_model(self) -> bool:
        """Attempt to restore a previously trained model for this profile from disk."""
        if not ML_AVAILABLE or not os.path.exists(self.cache_file):
            return False
        try:
            self.model = joblib.load(self.cache_file)
            self.is_trained = True
            logger.info(f"🧠 [AI SCANNER] Restored cached model for [{self.mode}] from '{os.path.basename(self.cache_file)}'.")
            return True
        except Exception as e:
            logger.warning(f"Could not load cached model '{self.cache_file}': {e}")
            return False

    def _save_cached_model(self) -> bool:
        """Persist trained model weights to disk."""
        if not ML_AVAILABLE or not self.is_trained or self.model is None:
            return False
        try:
            joblib.dump(self.model, self.cache_file)
            logger.info(f"💾 [AI SCANNER] Saved model for [{self.mode}] to '{os.path.basename(self.cache_file)}'.")
            return True
        except Exception as e:
            logger.warning(f"Failed to cache model '{self.cache_file}': {e}")
            return False

    def candles_to_dataframe(self, candles: List[Dict[str, float]]) -> Optional['pd.DataFrame']:
        """Convert a list of candle dicts to a pandas DataFrame."""
        if not ML_AVAILABLE or not candles:
            return None
        try:
            df = pd.DataFrame(candles)
            for col in ['open', 'high', 'low', 'close']:
                if col in df.columns:
                    df[col] = df[col].astype(float)
            if 'volume' in df.columns:
                df['volume'] = df['volume'].astype(float)
            return df
        except Exception as e:
            logger.error(f"Error converting candles to DataFrame: {e}")
            return None

    def extract_features(self, df: 'pd.DataFrame') -> 'pd.DataFrame':
        """
        Extract profile-adaptive predictive features from OHLCV candles:
        1. Normalized Returns & 10-period Rolling Volatility
        2. High-Low Candle Range Ratio relative to Close
        3. Distance spread between Fast and Slow EMAs
        4. Candle Range Expansion Ratio (Current bar vs 10-period rolling average)
        5. Relative Volume (Current volume vs 20-period moving average)
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
        ema_fast = df["close"].ewm(span=getattr(config, "EMA_FAST", 8), adjust=False).mean()
        ema_slow = df["close"].ewm(span=getattr(config, "EMA_SLOW", 21), adjust=False).mean()
        features["ma_spread"] = (ema_fast - ema_slow) / df["close"]

        # Feature 4: Range Expansion Ratio
        rolling_range = candle_range.rolling(window=10).mean()
        features["expansion_ratio"] = candle_range / (rolling_range + 1e-6)

        # Feature 5: Relative Volume
        if "volume" in df.columns:
            vol_mean = df["volume"].rolling(window=20).mean()
            features["rel_volume"] = df["volume"] / (vol_mean + 1e-6)
        else:
            features["rel_volume"] = 1.0

        return features.dropna()

    def train_on_history(self, candles_or_df: Union[List[Dict[str, float]], 'pd.DataFrame']) -> bool:
        """
        Train the AI model on historical candles from MT5 using active profile targets:
        - EXPANSION_M5: >= 15 pips over next 6 candles (30 mins)
        - SCALP_M1: >= 5 pips over next 5 candles (5 mins)
        - SILVER_BULLET_PURE: >= 12 pips over next 5 candles (15 mins)
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

            profile_cfg = config.PROFILES.get(self.mode, config.CONFIG)
            horizon = profile_cfg.get("AI_LABEL_HORIZON", 6)
            pip_target = profile_cfg.get("AI_LABEL_PIPS", 0.0015)

            # If symbol is not standard EUR/USD (e.g. JPY, Gold), scale appropriately
            if "JPY" in config.SYMBOL.upper():
                pip_target = pip_target * 100.0
            elif "XAU" in config.SYMBOL.upper() or "GOLD" in config.SYMBOL.upper():
                pip_target = pip_target * 1000.0

            future_move = (df["close"].shift(-horizon) - df["close"]).loc[features.index]
            labels = (future_move.abs() >= pip_target).astype(int)

            # Fit Random Forest Classifier
            self.model.fit(features, labels)
            self.is_trained = True
            expansion_rate = float(labels.mean() * 100)
            logger.info(
                f"🤖 [AI SCANNER TRAINED - {self.mode}] Fitted on {len(features)} candles | "
                f"Horizon: {horizon} bars | Target: {pip_target:.4f} | Expansion Rate: {expansion_rate:.1f}%"
            )
            self._save_cached_model()
            return True

        except Exception as e:
            logger.error(f"[AI SCANNER TRAINING ERROR] {e}")
            return False

    def predict_regime_confidence(self, candles_or_df: Union[List[Dict[str, float]], 'pd.DataFrame']) -> float:
        """
        Returns a Market Regime Expansion Confidence Score (0.00 to 1.00) for the latest closed candle [-2].
        If confidence >= AI_CONFIDENCE_THRESHOLD, market is in high-probability expansion.
        """
        if not ML_AVAILABLE or not self.is_trained or self.model is None:
            return 1.0  # Fallback to allow trade

        if isinstance(candles_or_df, list):
            df = self.candles_to_dataframe(candles_or_df)
        else:
            df = candles_or_df

        if df is None or len(df) < 25:
            return 1.0

        try:
            features = self.extract_features(df)
            if features.empty:
                return 1.0

            # Evaluate latest completed vector
            latest_vector = features.iloc[[-1]]
            probabilities = self.model.predict_proba(latest_vector)[0]

            confidence = float(probabilities[1]) if len(probabilities) > 1 else float(probabilities[0])
            return round(confidence, 3)

        except Exception as e:
            logger.warning(f"[AI SCANNER PREDICTION ERROR] {e}")
            return 1.0
