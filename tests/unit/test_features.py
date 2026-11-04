"""
Unit tests for cryptopilot.features.pipeline.FeaturePipeline.
Covers: Feature engineering, warmup dropping, and zero-lookahead validation.
"""

import numpy as np
import pandas as pd
import pytest

from cryptopilot.features.pipeline import FeaturePipeline
from cryptopilot.indicators.base import InvalidInputError


class TestFeaturePipeline:
    @pytest.fixture
    def sample_ohlcv(self) -> pd.DataFrame:
        n = 100
        np.random.seed(42)
        close = 100.0 + np.cumsum(np.random.randn(n) * 2.0)
        high = close + np.random.uniform(0.5, 3.0, n)
        low = close - np.random.uniform(0.5, 3.0, n)
        open_p = close + np.random.randn(n) * 0.5
        volume = np.random.uniform(100.0, 1000.0, n)

        return pd.DataFrame(
            {
                "open": open_p,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )

    def test_feature_pipeline_standard_transform(self, sample_ohlcv: pd.DataFrame) -> None:
        pipeline = FeaturePipeline()
        features = pipeline.transform(sample_ohlcv, drop_warmup=True)

        # Expected features must be present
        expected_cols = [
            "return_1",
            "return_3",
            "log_return_1",
            "close_to_sma_20",
            "rsi_14",
            "stoch_k_14",
            "stoch_d_3",
            "macd_line",
            "macd_signal",
            "macd_hist",
            "bb_bandwidth_20",
            "bb_percent_b_20",
            "atr_14",
            "adx_14",
            "plus_di_14",
            "minus_di_14",
            "hist_vol_20",
            "vol_to_ma_20",
            "obv",
            "vwap_ratio",
        ]

        for col in expected_cols:
            assert col in features.columns, f"Missing feature: {col}"

        # After dropping warmup, there should be no NaNs in key indicators
        assert not features["rsi_14"].isna().any()
        assert not features["macd_line"].isna().any()
        assert not features["atr_14"].isna().any()

    def test_feature_pipeline_without_warmup_drop(self, sample_ohlcv: pd.DataFrame) -> None:
        pipeline = FeaturePipeline()
        features_full = pipeline.transform(sample_ohlcv, drop_warmup=False)

        assert len(features_full) == len(sample_ohlcv)
        # First row must be NaN for lag returns
        assert np.isnan(features_full["return_1"].iloc[0])

    def test_feature_pipeline_empty(self) -> None:
        pipeline = FeaturePipeline()
        empty_df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        res = pipeline.transform(empty_df)
        assert res.empty

    def test_feature_pipeline_missing_columns(self) -> None:
        pipeline = FeaturePipeline()
        bad_df = pd.DataFrame({"open": [10.0], "close": [12.0]})
        with pytest.raises(InvalidInputError) as exc:
            pipeline.transform(bad_df)
        assert "missing required columns" in str(exc.value)

    def test_zero_lookahead_invariant(self, sample_ohlcv: pd.DataFrame) -> None:
        """
        Critical Quantitative Test:
        Modifying future bars (t > 50) MUST NEVER change any feature at bar t <= 50.
        """
        pipeline = FeaturePipeline()

        # Compute original features
        feat_orig = pipeline.transform(sample_ohlcv, drop_warmup=False)

        # Mutate bar 80 drastically (flash crash)
        mutated_df = sample_ohlcv.copy()
        mutated_df.loc[80, "close"] = 1.0
        mutated_df.loc[80, "high"] = 2.0
        mutated_df.loc[80, "low"] = 0.5
        mutated_df.loc[80, "volume"] = 1000000.0

        feat_mutated = pipeline.transform(mutated_df, drop_warmup=False)

        # Verify bars 0 through 79 are identical
        for col in feat_orig.columns:
            np.testing.assert_allclose(
                feat_orig[col].iloc[:80].to_numpy(),
                feat_mutated[col].iloc[:80].to_numpy(),
                err_msg=f"Lookahead leak detected in feature '{col}' before modified index 80!",
            )

