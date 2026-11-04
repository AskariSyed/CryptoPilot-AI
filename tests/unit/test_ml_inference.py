"""
Unit tests for cryptopilot.models.inference.MLInferenceEngine and MLPrediction.
Covers: Single-bar inference, confidence scoring, bullish edge thresholds, and safety fallbacks.
"""

from datetime import UTC

import numpy as np
import pandas as pd
import pytest

from cryptopilot.models.inference import MLInferenceEngine
from cryptopilot.models.pipeline import MLFeatureTransformer
from cryptopilot.models.trainer import XGBoostPredictor


class TestMLInferenceEngine:
    @pytest.fixture
    def trained_components(self) -> tuple[MLFeatureTransformer, XGBoostPredictor]:
        np.random.seed(42)
        n = 80
        df_train = pd.DataFrame(
            {
                "feat_mom": np.random.randn(n),
                "feat_vol": np.random.randn(n),
            }
        )
        y_train = (df_train["feat_mom"] > 0).astype(int)

        transformer = MLFeatureTransformer(scaler_type="standard")
        X_scaled = transformer.fit_transform(df_train)

        predictor = XGBoostPredictor(n_estimators=15, random_state=42)
        predictor.fit(X_scaled, y_train, feature_names=["feat_mom", "feat_vol"])

        return transformer, predictor

    def test_predict_bar_normal(self, trained_components) -> None:
        transformer, predictor = trained_components
        engine = MLInferenceEngine(
            transformer=transformer,
            predictor=predictor,
            decision_threshold_prob=0.55,
        )

        # Bullish feature row
        df_bar = pd.DataFrame({"feat_mom": [3.5], "feat_vol": [0.1]})
        pred = engine.predict_bar(df_bar, symbol="BTC/USDT")

        assert pred.symbol == "BTC/USDT"
        assert pred.bullish_probability >= 0.0
        assert pred.bullish_probability <= 1.0
        assert pred.confidence_score >= 0.0
        assert pred.confidence_score <= 1.0
        assert pred.timestamp.tzinfo == UTC
        assert len(pred.top_contributing_features) > 0

    def test_predict_bar_failsafe_fallback_on_unfitted_or_missing_model(self) -> None:
        # None components
        engine = MLInferenceEngine(transformer=None, predictor=None)
        pred = engine.predict_bar(pd.DataFrame({"a": [1.0]}), symbol="ETH/USDT")
        assert pred.bullish_probability == 0.50
        assert pred.confidence_score == 0.0
        assert pred.is_bullish_edge is False
        assert pred.top_contributing_features == {}

    def test_predict_bar_failsafe_fallback_on_empty_df(self, trained_components) -> None:
        transformer, predictor = trained_components
        engine = MLInferenceEngine(transformer=transformer, predictor=predictor)
        pred = engine.predict_bar(pd.DataFrame(), symbol="SOL/USDT")
        assert pred.bullish_probability == 0.50
        assert pred.confidence_score == 0.0

    def test_predict_bar_failsafe_fallback_on_data_error(self, trained_components) -> None:
        transformer, predictor = trained_components
        engine = MLInferenceEngine(transformer=transformer, predictor=predictor)
        # Passing wrong schema that causes transform error
        df_corrupt = pd.DataFrame({"completely_different_text_col": ["string_val"]})
        pred = engine.predict_bar(df_corrupt, symbol="BTC/USDT")
        assert pred.bullish_probability == 0.50
        assert pred.confidence_score == 0.0
