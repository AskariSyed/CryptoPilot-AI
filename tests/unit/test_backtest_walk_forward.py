"""
Unit tests for cryptopilot.backtesting.walk_forward.WalkForwardPartitioner.
Covers: Rolling and expanding walk-forward splits, validation windows, purging, embargo, and errors.
"""

import pandas as pd
import pytest

from cryptopilot.backtesting.walk_forward import WalkForwardPartitioner


class TestWalkForwardPartitioner:
    def test_rolling_partitions_without_validation(self) -> None:
        df = pd.DataFrame({"close": range(100)})
        partitioner = WalkForwardPartitioner(
            train_bars=40,
            test_bars=20,
            step_bars=20,
            mode="rolling",
        )
        partitions = partitioner.partition(df)
        assert len(partitions) == 3

        # Fold 1
        f1 = partitions[0]
        assert f1.fold == 1
        assert len(f1.train_df) == 40
        assert len(f1.test_df) == 20
        assert f1.validation_df is None
        assert f1.train_indices == (0, 40)
        assert f1.test_indices == (40, 60)

        # Fold 2 (rolled forward by 20)
        f2 = partitions[1]
        assert f2.fold == 2
        assert f2.train_indices == (20, 60)
        assert f2.test_indices == (60, 80)

        # Fold 3
        f3 = partitions[2]
        assert f3.fold == 3
        assert f3.train_indices == (40, 80)
        assert f3.test_indices == (80, 100)

    def test_expanding_partitions_with_validation(self) -> None:
        df = pd.DataFrame({"close": range(120)})
        partitioner = WalkForwardPartitioner(
            train_bars=40,
            validation_bars=10,
            test_bars=20,
            step_bars=20,
            mode="expanding",
        )
        partitions = partitioner.partition(df)
        assert len(partitions) >= 2

        f1 = partitions[0]
        assert f1.train_indices == (0, 40)
        assert f1.validation_indices == (40, 50)
        assert f1.test_indices == (50, 70)
        assert f1.validation_df is not None and len(f1.validation_df) == 10

        f2 = partitions[1]
        # Expanding mode anchors train start at 0!
        assert f2.train_indices == (0, 60)
        assert f2.validation_indices == (60, 70)
        assert f2.test_indices == (70, 90)

    def test_purge_and_embargo(self) -> None:
        df = pd.DataFrame({"close": range(100)})
        partitioner = WalkForwardPartitioner(
            train_bars=40,
            test_bars=20,
            step_bars=20,
            purge_bars=5,  # Train ends at 35 instead of 40
            embargo_bars=5,  # Offset advances by 25 instead of 20
        )
        partitions = partitioner.partition(df)
        assert len(partitions) >= 2

        f1 = partitions[0]
        assert f1.train_indices == (0, 35)  # Purged 5 bars from end
        assert len(f1.train_df) == 35
        assert f1.test_indices == (40, 60)

        f2 = partitions[1]
        # Offset advanced by step (20) + embargo (5) = 25
        # Train nominal = 25..65, purged 5 = 25..60
        assert f2.train_indices == (25, 60)
        assert f2.test_indices == (65, 85)

    def test_insufficient_bars_or_empty_df(self) -> None:
        partitioner = WalkForwardPartitioner(train_bars=50, test_bars=20)
        assert partitioner.partition(pd.DataFrame()) == []
        assert partitioner.partition(pd.DataFrame({"close": range(30)})) == []

    def test_invalid_parameters_raise(self) -> None:
        with pytest.raises(ValueError, match="train_bars must be positive"):
            WalkForwardPartitioner(train_bars=0, test_bars=10)

        with pytest.raises(ValueError, match="test_bars must be positive"):
            WalkForwardPartitioner(train_bars=10, test_bars=-5)

        with pytest.raises(ValueError, match="validation_bars cannot be negative"):
            WalkForwardPartitioner(train_bars=10, test_bars=10, validation_bars=-1)

        with pytest.raises(ValueError, match="purge_bars cannot be negative"):
            WalkForwardPartitioner(train_bars=10, test_bars=10, purge_bars=-2)

        with pytest.raises(ValueError, match="embargo_bars cannot be negative"):
            WalkForwardPartitioner(train_bars=10, test_bars=10, embargo_bars=-3)
