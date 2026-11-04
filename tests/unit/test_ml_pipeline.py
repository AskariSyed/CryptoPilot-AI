"""
Unit tests for cryptopilot.models.pipeline.MLFeatureTransformer.
Covers: Feature selection, median imputation, chronological scaling, and anti-leakage contracts.
"""

import numpy as np
import pandas as pd
import pytest

from cryptopilot.models.pipeline import MLFeatureTransformer


class TestMLFeatureTransformer:
    def test_feature_selection_ignores_metadata(self) -> None:
        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2026-01-01", periods=10, freq="15min"),
                "symbol": ["BTC/USDT"] * 10,
                "open": [100.0] * 10,
                "high": [105.0] * 10,
                "low": [95.0] * 10,
                "close": [102.0] * 10,
                "volume": [500.0] * 10,
                "target": [1] * 10,
                "forward_return": [0.01] * 10,
                "rsi_14": np.linspace(40, 60, 10),
                "macd_diff": np.linspace(-1, 1, 10),
            }
        )
        transformer = MLFeatureTransformer(scaler_type="robust")
        transformer.fit(df)
        assert transformer.is_fitted is True
        assert transformer.feature_names == ["rsi_14", "macd_diff"]

    def test_imputation_strictly_uses_train_medians(self) -> None:
        df_train = pd.DataFrame(
            {
                "feat_a": [10.0, 20.0, 30.0],  # Median = 20.0
                "feat_b": [1.0, np.nan, 3.0],  # Median = 2.0
            }
        )
        transformer = MLFeatureTransformer(scaler_type="standard")
        transformer.fit(df_train)
        assert transformer.medians["feat_a"] == 20.0
        assert transformer.medians["feat_b"] == 2.0

        # Transform test data containing NaNs
        df_test = pd.DataFrame(
            {
                "feat_a": [np.nan],
                "feat_b": [np.nan],
            }
        )
        X_test = transformer.transform(df_test)
        # Because scaler is standard: (median - mean) / std is finite and not NaN
        assert not np.isnan(X_test).any()

    def test_transform_before_fit_raises_runtime_error(self) -> None:
        transformer = MLFeatureTransformer()
        df = pd.DataFrame({"feat_a": [1.0, 2.0]})
        with pytest.raises(
            RuntimeError, match="must be fitted on training data before calling transform"
        ):
            transformer.transform(df)

    def test_invalid_scaler_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported scaler_type"):
            MLFeatureTransformer(scaler_type="invalid_scaler")

    def test_empty_train_raises_value_error(self) -> None:
        transformer = MLFeatureTransformer()
        with pytest.raises(ValueError, match="cannot be None or empty"):
            transformer.fit(pd.DataFrame())

    def test_no_numeric_features_raises_value_error(self) -> None:
        transformer = MLFeatureTransformer()
        df_text = pd.DataFrame({"symbol": ["BTC"], "side": ["BUY"]})
        with pytest.raises(ValueError, match="No numeric feature columns found"):
            transformer.fit(df_text)

    def test_transform_empty_returns_empty_array(self) -> None:
        df_train = pd.DataFrame({"feat_a": [1.0, 2.0, 3.0]})
        transformer = MLFeatureTransformer()
        transformer.fit(df_train)
        empty_res = transformer.transform(pd.DataFrame())
        assert empty_res.shape == (0, 1)

    def test_fit_transform_convenience(self) -> None:
        df_train = pd.DataFrame({"feat_a": [1.0, 2.0, 3.0, 4.0, 5.0]})
        transformer = MLFeatureTransformer(scaler_type="standard")
        X = transformer.fit_transform(df_train)
        assert X.shape == (5, 1)
        assert transformer.is_fitted is True
