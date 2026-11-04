"""
Unit tests for cryptopilot.models.splitter.PurgedTimeSeriesSplitter.
Covers: Chronological folds, purge window validation, embargo gaps, and zero-leakage assertions.
"""

import numpy as np
import pytest

from cryptopilot.models.splitter import PurgedTimeSeriesSplitter


class TestPurgedTimeSeriesSplitter:
    def test_purged_time_series_splitter_folds(self) -> None:
        splitter = PurgedTimeSeriesSplitter(
            n_splits=3,
            purge_bars=4,
            embargo_bars=10,
            min_train_bars=40,
        )
        assert splitter.get_n_splits() == 3

        # Sample data with 100 observations
        X = np.arange(100).reshape(-1, 1)
        splits = list(splitter.split(X))
        assert len(splits) == 3

        for _fold, (train_idx, test_idx) in enumerate(splits):
            # Invariant 1: Non-empty splits
            assert len(train_idx) > 0
            assert len(test_idx) > 0

            # Invariant 2: Zero index intersection (strict disjoint sets)
            assert len(set(train_idx).intersection(set(test_idx))) == 0

            # Invariant 3: Test is strictly forward in time
            assert test_idx[0] > train_idx[-1]

            # Invariant 4: Embargo gap + purge gap exists between train_end and test_start
            gap = test_idx[0] - train_idx[-1]
            assert gap >= (splitter.embargo_bars + splitter.purge_bars)

    def test_insufficient_samples_raises_value_error(self) -> None:
        splitter = PurgedTimeSeriesSplitter(n_splits=5, min_train_bars=50, embargo_bars=20)
        X_short = np.arange(60).reshape(-1, 1)  # 60 < 50 + 20 + 5
        with pytest.raises(ValueError, match="too small for 5 splits"):
            list(splitter.split(X_short))

    def test_invalid_parameters_raise(self) -> None:
        with pytest.raises(ValueError, match="n_splits must be >= 2"):
            PurgedTimeSeriesSplitter(n_splits=1)

        with pytest.raises(ValueError, match="purge_bars cannot be negative"):
            PurgedTimeSeriesSplitter(purge_bars=-1)

        with pytest.raises(ValueError, match="embargo_bars cannot be negative"):
            PurgedTimeSeriesSplitter(embargo_bars=-1)

        with pytest.raises(ValueError, match="min_train_bars must be positive"):
            PurgedTimeSeriesSplitter(min_train_bars=0)
