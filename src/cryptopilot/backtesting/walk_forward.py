"""
CryptoPilot AI - Walk-Forward Cross-Validation Partitioner.
Generates chronologically partitioned training, validation, and out-of-sample test splits
with strict purging and embargo to eliminate cross-window data leakage.
"""

from dataclasses import dataclass
from typing import Literal

import pandas as pd


@dataclass(frozen=True)
class WalkForwardPartition:
    """Represents a single cross-validation fold."""

    fold: int
    train_df: pd.DataFrame
    validation_df: pd.DataFrame | None
    test_df: pd.DataFrame
    train_indices: tuple[int, int]  # (start_inclusive, end_exclusive)
    validation_indices: tuple[int, int] | None
    test_indices: tuple[int, int]


class WalkForwardPartitioner:
    """
    Splits chronological market data into walk-forward cross-validation folds.
    Supports both rolling (fixed-length) and expanding (anchored) train windows.
    Enforces purge and embargo gaps to prevent lookahead and autocorrelation leakage.
    """

    def __init__(
        self,
        train_bars: int,
        test_bars: int,
        validation_bars: int = 0,
        step_bars: int | None = None,
        mode: Literal["rolling", "expanding"] = "rolling",
        purge_bars: int = 0,
        embargo_bars: int = 0,
    ) -> None:
        if train_bars <= 0:
            raise ValueError(f"train_bars must be positive, got {train_bars}")
        if test_bars <= 0:
            raise ValueError(f"test_bars must be positive, got {test_bars}")
        if validation_bars < 0:
            raise ValueError(f"validation_bars cannot be negative, got {validation_bars}")
        if purge_bars < 0:
            raise ValueError(f"purge_bars cannot be negative, got {purge_bars}")
        if embargo_bars < 0:
            raise ValueError(f"embargo_bars cannot be negative, got {embargo_bars}")

        self.train_bars = train_bars
        self.test_bars = test_bars
        self.validation_bars = validation_bars
        self.step_bars = step_bars if step_bars is not None and step_bars > 0 else test_bars
        self.mode = mode
        self.purge_bars = purge_bars
        self.embargo_bars = embargo_bars

    def partition(self, df: pd.DataFrame) -> list[WalkForwardPartition]:
        """
        Generates list of WalkForwardPartition folds for the provided DataFrame.
        """
        if df is None or df.empty:
            return []

        n_bars = len(df)
        min_required = self.train_bars + self.validation_bars + self.test_bars
        if n_bars < min_required:
            return []

        partitions: list[WalkForwardPartition] = []
        fold = 1
        current_offset = 0

        while True:
            train_start = 0 if self.mode == "expanding" else current_offset
            train_end_nominal = current_offset + self.train_bars

            # Apply purge: remove last purge_bars from end of train to isolate from validation/test
            train_end = max(train_start + 1, train_end_nominal - self.purge_bars)

            if self.validation_bars > 0:
                val_start = train_end_nominal
                val_end = val_start + self.validation_bars
                test_start = val_end
            else:
                val_start = 0
                val_end = 0
                test_start = train_end_nominal

            test_end = test_start + self.test_bars

            if test_end > n_bars:
                break

            train_slice = df.iloc[train_start:train_end].copy()
            val_slice = df.iloc[val_start:val_end].copy() if self.validation_bars > 0 else None
            test_slice = df.iloc[test_start:test_end].copy()

            val_indices = (val_start, val_end) if self.validation_bars > 0 else None

            partition = WalkForwardPartition(
                fold=fold,
                train_df=train_slice,
                validation_df=val_slice,
                test_df=test_slice,
                train_indices=(train_start, train_end),
                validation_indices=val_indices,
                test_indices=(test_start, test_end),
            )
            partitions.append(partition)

            fold += 1
            # Advance offset by step_bars + embargo_bars
            current_offset += self.step_bars + self.embargo_bars

        return partitions
