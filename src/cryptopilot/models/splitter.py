"""
CryptoPilot AI - Purged & Embargoed Time-Series Cross-Validation Splitter.
Guarantees chronological separation between training and evaluation windows,
purging forward-labeling overlaps and applying embargo buffers to eliminate
autocorrelation leakage.
"""

from collections.abc import Generator
from typing import Any

import numpy as np
import pandas as pd


class PurgedTimeSeriesSplitter:
    """
    Time-series cross-validation splitter with strict purging and embargoing.
    Implements the standard scikit-learn CV splitter interface (split, get_n_splits).
    """

    def __init__(
        self,
        n_splits: int = 5,
        purge_bars: int = 4,  # Equal to label forward horizon H
        embargo_bars: int = 24,  # Buffer between train and test
        min_train_bars: int = 50,
    ) -> None:
        if n_splits < 2:
            raise ValueError(f"n_splits must be >= 2, got {n_splits}")
        if purge_bars < 0:
            raise ValueError(f"purge_bars cannot be negative, got {purge_bars}")
        if embargo_bars < 0:
            raise ValueError(f"embargo_bars cannot be negative, got {embargo_bars}")
        if min_train_bars <= 0:
            raise ValueError(f"min_train_bars must be positive, got {min_train_bars}")

        self.n_splits = n_splits
        self.purge_bars = purge_bars
        self.embargo_bars = embargo_bars
        self.min_train_bars = min_train_bars

    def get_n_splits(self, X: Any = None, y: Any = None, groups: Any = None) -> int:
        return self.n_splits

    def split(
        self,
        X: pd.DataFrame | np.ndarray,
        y: Any = None,
        groups: Any = None,
    ) -> Generator[tuple[np.ndarray, np.ndarray], None, None]:
        """
        Yields (train_indices, test_indices) for each walk-forward fold.
        Guarantees:
        1. test_indices are strictly forward in time compared to train_indices.
        2. train_indices are purged of the last purge_bars prior to test.
        3. train_indices and test_indices have zero intersection.
        """
        n_samples = len(X)
        if n_samples < (self.min_train_bars + self.embargo_bars + self.n_splits):
            raise ValueError(
                f"Sample size {n_samples} is too small for {self.n_splits} splits with "
                f"min_train={self.min_train_bars} and embargo={self.embargo_bars}"
            )

        # Allocate test segment size
        available_test_samples = n_samples - self.min_train_bars - self.embargo_bars
        test_size = max(1, available_test_samples // self.n_splits)

        for fold in range(self.n_splits):
            # Test window starts after min_train + fold * test_size + embargo
            test_start = self.min_train_bars + (fold * test_size) + self.embargo_bars
            test_end = min(n_samples, test_start + test_size)

            if test_start >= n_samples or test_end <= test_start:
                break

            # Nominal train window before embargo gap
            nominal_train_end = test_start - self.embargo_bars
            # Apply purge: remove last purge_bars from end of train
            effective_train_end = max(1, nominal_train_end - self.purge_bars)

            train_indices = np.arange(0, effective_train_end, dtype=int)
            test_indices = np.arange(test_start, test_end, dtype=int)

            if len(train_indices) == 0 or len(test_indices) == 0:
                continue

            # Anti-leakage invariant: zero overlap
            assert len(set(train_indices).intersection(set(test_indices))) == 0

            yield train_indices, test_indices
