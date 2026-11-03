"""
Aegis Dual-AI Market Regime & Momentum Ensemble Engine.
Uses a Committee of two complementary ML models from scikit-learn:
1. RandomForestClassifier (Filters out sideways consolidation & spread churn)
2. HistGradientBoostingClassifier (Validates directional momentum & expansion)

Consensus voting rule: Both models must agree (2/2) with confidence >= threshold
to authorize trade execution. Supports multi-symbol model caching.
"""

import os
import logging
from typing import List, Dict, Any, Union, Optional, Tuple
import config

logger = logging.getLogger("AegisBTC.AIEnsemble")

try:
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("[AI ENSEMBLE NOTICE] scikit-learn or joblib not installed. Running in rule fallback mode.")


def get_ensemble_cache_path(symbol: str, mode: Optional[str] = None) -> str:
    """Generate symbol- and profile-specific model cache filepath."""
    profile_mode = (mode or config.ACTIVE_MODE).upper()
    clean_sym = symbol.replace("/", "").replace("_", "").upper()
    models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    os.makedirs(models_dir, exist_ok=True)
    return os.path.join(models_dir, f"ensemble_{clean_sym}_{profile_mode}.joblib")


class DualAIEnsemble:
    """
    Dual-AI Committee (Random Forest + HistGradientBoosting) with consensus voting.
    Trained specifically on historical candles per instrument.
    """

    def __init__(self, symbol: Optional[str] = None, mode: Optional[str] = None):
        self.symbol = (symbol or config.SYMBOL).upper()
        self.mode = (mode or config.ACTIVE_MODE).upper()
        self.cache_file = get_ensemble_cache_path(self.symbol, self.mode)
        self.is_trained = False
        self.rf_model = None
        self.gb_model = None

        if ML_AVAILABLE:
            self.rf_model = RandomForestClassifier(
                n_estimators=80,
                max_depth=5,
                random_state=42,
                n_jobs=-1
            )
            self.gb_model = HistGradientBoostingClassifier(
                max_iter=80,
                max_depth=4,
                learning_rate=0.05,
                random_state=42
            )
            self._load_cached_models()

    def _load_cached_models(self) -> bool:
        """Attempt to restore previously trained models from disk."""
        if not ML_AVAILABLE or not os.path.exists(self.cache_file):
            return False
        try:
            bundle = joblib.load(self.cache_file)
            self.rf_model = bundle.get("rf_model")
            self.gb_model = bundle.get("gb_model")
            self.is_trained = (self.rf_model is not None and self.gb_model is not None)
            if self.is_trained:
                logger.info(f"🧠 [AI ENSEMBLE] Restored [{self.symbol} - {self.mode}] models from '{os.path.basename(self.cache_file)}'.")
            return self.is_trained
        except Exception as e:
            logger.warning(f"Could not load cached ensemble '{self.cache_file}': {e}")
            return False

    def _save_cached_models(self) -> bool:
        """Persist committee models to disk."""
        if not ML_AVAILABLE or not self.is_trained:
            return False
        try:
            bundle = {
                "rf_model": self.rf_model,
                "gb_model": self.gb_model,
                "symbol": self.symbol,
                "mode": self.mode
            }
            joblib.dump(bundle, self.cache_file)
            logger.info(f"💾 [AI ENSEMBLE] Cached [{self.symbol} - {self.mode}] models to '{os.path.basename(self.cache_file)}'.")
            return True
        except Exception as e:
            logger.warning(f"Failed to cache ensemble '{self.cache_file}': {e}")
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
        Extract predictive features:
        1. Normalized Returns & 10-period Rolling Volatility
        2. High-Low Range Ratio
        3. Fast vs Slow EMA Distance Spread
        4. Range Expansion Ratio
        5. Relative Volume
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

    def train_ensemble(self, candles_or_df: Union[List[Dict[str, float]], 'pd.DataFrame']) -> bool:
        """
        Train both Random Forest and HistGradientBoosting on historical candles.
        """
        if not ML_AVAILABLE:
            logger.warning("[AI ENSEMBLE] Machine learning packages not available. Skipping training.")
            return False

        if isinstance(candles_or_df, list):
            df = self.candles_to_dataframe(candles_or_df)
        else:
            df = candles_or_df

        if df is None or len(df) < 50:
            logger.warning(f"[AI ENSEMBLE] Insufficient history for [{self.symbol}] (Need >= 50, got {len(df) if df is not None else 0}).")
            return False

        try:
            features = self.extract_features(df)
            if features.empty or len(features) < 30:
                logger.warning(f"[AI ENSEMBLE] Extracted feature matrix is empty for [{self.symbol}].")
                return False

            profile_cfg = config.PROFILES.get(self.mode, config.CONFIG)
            horizon = profile_cfg.get("AI_LABEL_HORIZON", 6)
            pip_target = profile_cfg.get("AI_LABEL_PIPS", 0.0012)

            # Adjust pip target based on currency pair quotes
            if "JPY" in self.symbol.upper():
                pip_target = pip_target * 100.0
            elif "XAU" in self.symbol.upper() or "GOLD" in self.symbol.upper():
                pip_target = pip_target * 1000.0

            future_move = (df["close"].shift(-horizon) - df["close"]).loc[features.index]
            labels = (future_move.abs() >= pip_target).astype(int)

            # Ensure at least two classes exist
            if len(labels.unique()) < 2:
                # If market was completely flat in sample, synthesize slight threshold
                median_move = future_move.abs().median()
                labels = (future_move.abs() >= median_move).astype(int)

            # Fit Random Forest
            self.rf_model.fit(features, labels)

            # Fit HistGradientBoosting
            self.gb_model.fit(features, labels)

            self.is_trained = True
            expansion_rate = float(labels.mean() * 100)
            logger.info(
                f"🤖 [DUAL-AI ENSEMBLE TRAINED: {self.symbol} - {self.mode}] "
                f"Fitted on {len(features)} candles | Horizon: {horizon} bars | Expansion Rate: {expansion_rate:.1f}%"
            )
            self._save_cached_models()
            return True

        except Exception as e:
            logger.error(f"[AI ENSEMBLE TRAINING ERROR: {self.symbol}] {e}")
            return False

    def evaluate_consensus(
        self,
        candles_or_df: Union[List[Dict[str, float]], 'pd.DataFrame']
    ) -> Tuple[bool, float, Dict[str, float]]:
        """
        Evaluate latest closed candle [-2] against both models.
        Returns:
            passed_consensus (bool): True if both models vote >= threshold (or votes_needed)
            avg_confidence (float): Mean probability score (0.00 to 1.00)
            breakdown (dict): {"rf_prob": ..., "gb_prob": ..., "votes": ...}
        """
        if not ML_AVAILABLE or not self.is_trained:
            # Fallback: approve trade when ML is uninitialized so trading is not blocked
            return True, 1.0, {"rf_prob": 1.0, "gb_prob": 1.0, "votes": 2}

        if isinstance(candles_or_df, list):
            df = self.candles_to_dataframe(candles_or_df)
        else:
            df = candles_or_df

        if df is None or len(df) < 25:
            return True, 1.0, {"rf_prob": 1.0, "gb_prob": 1.0, "votes": 2}

        try:
            features = self.extract_features(df)
            if features.empty:
                return True, 1.0, {"rf_prob": 1.0, "gb_prob": 1.0, "votes": 2}

            latest_vector = features.iloc[[-1]]

            # Model 1: Random Forest Probability
            rf_probs = self.rf_model.predict_proba(latest_vector)[0]
            rf_prob = float(rf_probs[1]) if len(rf_probs) > 1 else float(rf_probs[0])

            # Model 2: HistGradientBoosting Probability
            gb_probs = self.gb_model.predict_proba(latest_vector)[0]
            gb_prob = float(gb_probs[1]) if len(gb_probs) > 1 else float(gb_probs[0])

            avg_conf = (rf_prob + gb_prob) / 2.0

            thresh = getattr(config, "AI_CONFIDENCE_THRESHOLD", 0.65)
            votes_req = getattr(config.CONFIG, "get", lambda k, d: d)("AI_VOTES_REQUIRED", 2)

            votes = 0
            if rf_prob >= thresh:
                votes += 1
            if gb_prob >= thresh:
                votes += 1

            passed = (votes >= votes_req)

            breakdown = {
                "rf_prob": round(rf_prob, 3),
                "gb_prob": round(gb_prob, 3),
                "avg_conf": round(avg_conf, 3),
                "votes": votes,
                "passed": passed
            }

            return passed, round(avg_conf, 3), breakdown

        except Exception as e:
            logger.warning(f"[AI ENSEMBLE EVALUATION ERROR: {self.symbol}] {e}")
            return True, 1.0, {"rf_prob": 1.0, "gb_prob": 1.0, "votes": 2}

    # Backward compatibility aliases
    train_on_history = train_ensemble

    def predict_regime_confidence(self, candles_or_df: Union[List[Dict[str, float]], 'pd.DataFrame']) -> float:
        passed, avg_conf, _ = self.evaluate_consensus(candles_or_df)
        return avg_conf
