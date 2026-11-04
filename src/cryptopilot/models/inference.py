"""
CryptoPilot AI - Deterministic Machine Learning Inference Engine.
Translates current-bar market features into calibrated bullish continuation probabilities,
confidence scores, and feature attributions with deterministic safety fallbacks.
"""

from datetime import UTC, datetime

import pandas as pd
from pydantic import BaseModel, Field, field_validator

from cryptopilot.models.pipeline import MLFeatureTransformer
from cryptopilot.models.trainer import XGBoostPredictor


class MLPrediction(BaseModel):
    """Calibrated machine learning prediction for a single market timestamp."""

    symbol: str
    horizon_bars: int = Field(gt=0)
    bullish_probability: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    cost_threshold: float = Field(gt=0.0)
    is_bullish_edge: bool
    top_contributing_features: dict[str, float] = Field(default_factory=dict)
    timestamp: datetime
    model_version: str = "1.0.0"

    @field_validator("timestamp", mode="after")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class MLInferenceEngine:
    """
    Evaluates real-time / closed-bar features and produces calibrated predictions.
    Enforces failsafe defaults (P=0.50, confidence=0.0) whenever features or models are degraded.
    """

    def __init__(
        self,
        transformer: MLFeatureTransformer | None = None,
        predictor: XGBoostPredictor | None = None,
        horizon_bars: int = 4,
        cost_threshold: float = 0.0045,
        decision_threshold_prob: float = 0.55,
        model_version: str = "1.0.0",
    ) -> None:
        self.transformer = transformer
        self.predictor = predictor
        self.horizon_bars = horizon_bars
        self.cost_threshold = cost_threshold
        self.decision_threshold_prob = decision_threshold_prob
        self.model_version = model_version

    def predict_bar(
        self,
        df: pd.DataFrame,
        symbol: str,
        timestamp: datetime | None = None,
    ) -> MLPrediction:
        """
        Infers bullish probability for the latest bar in the DataFrame.
        Returns safe neutral fallback if data or model is incomplete.
        """
        ts = timestamp or datetime.now(UTC)
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)

        # Failsafe default if model or data is missing, or required features missing
        if (
            df is None
            or df.empty
            or self.transformer is None
            or not self.transformer.is_fitted
            or self.predictor is None
            or not self.predictor.is_fitted
            or not any(col in df.columns for col in self.transformer.feature_names)
        ):
            return MLPrediction(
                symbol=symbol,
                horizon_bars=self.horizon_bars,
                bullish_probability=0.50,
                confidence_score=0.0,
                cost_threshold=self.cost_threshold,
                is_bullish_edge=False,
                top_contributing_features={},
                timestamp=ts,
                model_version=self.model_version,
            )

        # Take latest row
        latest_row = df.iloc[-1:]

        try:
            X_scaled = self.transformer.transform(latest_row)
            probs = self.predictor.predict_proba(X_scaled)
            bullish_prob = float(probs[-1, 1])
        except Exception:
            # Deterministic fallback on any transformation error
            return MLPrediction(
                symbol=symbol,
                horizon_bars=self.horizon_bars,
                bullish_probability=0.50,
                confidence_score=0.0,
                cost_threshold=self.cost_threshold,
                is_bullish_edge=False,
                top_contributing_features={},
                timestamp=ts,
                model_version=self.model_version,
            )

        # Confidence: distance from neutral 0.50 scaled to [0, 1]
        confidence = float(min(1.0, abs(bullish_prob - 0.50) * 2.0))
        is_bullish = bullish_prob >= self.decision_threshold_prob

        # Extract top 5 features
        importances = self.predictor.get_feature_importances()
        top_5 = dict(list(importances.items())[:5])

        return MLPrediction(
            symbol=symbol,
            horizon_bars=self.horizon_bars,
            bullish_probability=bullish_prob,
            confidence_score=confidence,
            cost_threshold=self.cost_threshold,
            is_bullish_edge=is_bullish,
            top_contributing_features=top_5,
            timestamp=ts,
            model_version=self.model_version,
        )
