"""
Unit tests for cryptopilot.models.target.TargetLabeler and TargetConfig.
Covers: Cost-adjusted hurdle, forward-return calculation, binary labeling, and purge boundaries.
"""

import pandas as pd
import pytest

from cryptopilot.models.target import TargetConfig, TargetLabeler


class TestTargetLabeler:
    def test_target_config_cost_threshold(self) -> None:
        cfg = TargetConfig(
            horizon_bars=4,
            taker_fee_pct=0.001,
            slippage_pct=0.0005,
            edge_margin_pct=0.0020,
        )
        # 2 * 0.001 + 0.0005 + 0.0020 = 0.0045 (45 bps)
        assert pytest.approx(cfg.cost_threshold) == 0.0045

    def test_compute_forward_returns_and_nan_trailing(self) -> None:
        labeler = TargetLabeler(TargetConfig(horizon_bars=2))
        closes = pd.Series([100.0, 105.0, 110.0, 115.0])
        returns = labeler.compute_forward_returns(closes)

        # Bar 0 -> Bar 2: (110 - 100) / 100 = 0.10
        assert pytest.approx(returns.iloc[0]) == 0.10
        # Bar 1 -> Bar 3: (115 - 105) / 105 ~ 0.0952
        assert pytest.approx(returns.iloc[1]) == (115.0 - 105.0) / 105.0
        # Trailing 2 bars must be NaN
        assert pd.isna(returns.iloc[2])
        assert pd.isna(returns.iloc[3])

    def test_compute_forward_returns_empty(self) -> None:
        labeler = TargetLabeler()
        assert labeler.compute_forward_returns(pd.Series(dtype=float)).empty

    def test_generate_targets_binary_classification(self) -> None:
        # Hurdle is 0.0045
        labeler = TargetLabeler(
            TargetConfig(
                horizon_bars=2, taker_fee_pct=0.001, slippage_pct=0.0005, edge_margin_pct=0.0020
            )
        )
        df = pd.DataFrame(
            {
                "close": [100.0, 100.0, 102.0, 99.0, 105.0],  # 5 bars
                "feature1": [1.0, 2.0, 3.0, 4.0, 5.0],
            }
        )
        df_pruned, targets, forward_returns = labeler.generate_targets(df)

        # 5 bars - 2 trailing horizon = 3 valid bars
        assert len(df_pruned) == 3
        assert len(targets) == 3
        assert len(forward_returns) == 3

        # Bar 0: (102 - 100)/100 = 0.02 > 0.0045 -> Target = 1
        assert targets.iloc[0] == 1
        assert pytest.approx(forward_returns.iloc[0]) == 0.02

        # Bar 1: (99 - 100)/100 = -0.01 <= 0.0045 -> Target = 0
        assert targets.iloc[1] == 0
        assert pytest.approx(forward_returns.iloc[1]) == -0.01

        # Bar 2: (105 - 102)/102 = 0.0294 > 0.0045 -> Target = 1
        assert targets.iloc[2] == 1

    def test_generate_targets_invalid_inputs(self) -> None:
        labeler = TargetLabeler(TargetConfig(horizon_bars=4))

        with pytest.raises(ValueError, match="Input DataFrame cannot be None or empty"):
            labeler.generate_targets(pd.DataFrame())

        with pytest.raises(ValueError, match="DataFrame must contain a 'close' price column"):
            labeler.generate_targets(pd.DataFrame({"open": [100.0] * 10}))

        with pytest.raises(ValueError, match="insufficient for horizon"):
            labeler.generate_targets(
                pd.DataFrame({"close": [100.0, 101.0, 102.0]})
            )  # len 3 <= horizon 4
