"""
CryptoPilot AI - Machine Learning Target Formulation & Labeling.
Generates cost-adjusted forward-return classification targets with strict
purging of unobservable future boundary bars.
"""

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


class TargetConfig(BaseModel):
    """Configuration schema for ML target generation."""

    horizon_bars: int = Field(default=4, gt=0, description="Forward observation horizon in bars")
    taker_fee_pct: float = Field(
        default=0.001, ge=0.0, description="Round-trip maker/taker fee rate"
    )
    slippage_pct: float = Field(
        default=0.0005, ge=0.0, description="Estimated execution slippage rate"
    )
    edge_margin_pct: float = Field(
        default=0.0020, ge=0.0, description="Minimum excess alpha margin"
    )

    @property
    def cost_threshold(self) -> float:
        """Total required forward return hurdle to cover fees and alpha edge."""
        return (2.0 * self.taker_fee_pct) + self.slippage_pct + self.edge_margin_pct


class TargetLabeler:
    """
    Computes forward asset returns and binary classification labels:
    y = 1 if ForwardReturn(t -> t + H) > CostThreshold else 0.
    Prunes trailing unobservable horizon bars to eliminate NaN lookahead.
    """

    def __init__(self, config: TargetConfig | None = None) -> None:
        self.config = config or TargetConfig()

    def compute_forward_returns(self, close_series: pd.Series) -> pd.Series:
        """
        Calculates forward percentage return: (Close[t + H] - Close[t]) / Close[t].
        The last H bars will be NaN.
        """
        if close_series is None or close_series.empty:
            return pd.Series(dtype=np.float64)

        close = close_series.astype(np.float64)
        forward_close = close.shift(-self.config.horizon_bars)
        close_arr = np.asarray(close.values, dtype=np.float64)
        safe_close = np.maximum(close_arr, 1e-8)
        forward_arr = np.asarray(forward_close.values, dtype=np.float64)
        returns_arr = (forward_arr - close_arr) / safe_close
        returns = pd.Series(
            returns_arr, index=close.index, name=f"forward_return_{self.config.horizon_bars}"
        )
        return returns

    def generate_targets(
        self,
        df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
        """
        Generates aligned features, binary targets, and raw forward returns.
        Drops the trailing H rows where future data is unobservable.

        Returns:
            (df_pruned, target_series, forward_returns_series)
        """
        if df is None or df.empty:
            raise ValueError("Input DataFrame cannot be None or empty")

        if "close" not in df.columns:
            raise ValueError("DataFrame must contain a 'close' price column")

        if len(df) <= self.config.horizon_bars:
            raise ValueError(
                f"DataFrame has {len(df)} bars, which is insufficient for horizon {self.config.horizon_bars}"
            )

        forward_returns = self.compute_forward_returns(df["close"])
        threshold = self.config.cost_threshold

        # Binary label: 1 if forward return exceeds hurdle, else 0
        binary_targets = (forward_returns > threshold).astype(int)
        binary_targets.name = "target"

        # Purge the trailing H bars where future return is unknown
        valid_mask = forward_returns.notna()
        df_pruned = df.loc[valid_mask].copy()
        targets_pruned = binary_targets.loc[valid_mask].copy()
        returns_pruned = forward_returns.loc[valid_mask].copy()

        return df_pruned, targets_pruned, returns_pruned
