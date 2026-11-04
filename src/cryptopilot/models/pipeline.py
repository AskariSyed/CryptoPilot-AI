"""
CryptoPilot AI - Leak-Free Feature Scaling & Transformation Pipeline.
Guarantees strict chronological fitting: scalers and statistical parameters
are fitted exclusively on training windows and applied out-of-sample without refitting.
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler, StandardScaler


class MLFeatureTransformer:
    """
    Transforms raw feature DataFrames into normalized, leak-free numeric arrays.
    Enforces that preprocessing statistics (mean, variance, medians) are computed
    strictly on training data.
    """

    EXCLUDED_COLUMNS = {
        "timestamp",
        "symbol",
        "target",
        "forward_return",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    def __init__(self, scaler_type: str = "robust") -> None:
        self.scaler_type = scaler_type.lower()
        if self.scaler_type == "robust":
            self.scaler: StandardScaler | RobustScaler = RobustScaler()
        elif self.scaler_type == "standard":
            self.scaler = StandardScaler()
        else:
            raise ValueError(
                f"Unsupported scaler_type '{scaler_type}'. Choose 'robust' or 'standard'"
            )

        self.feature_names: list[str] = []
        self.medians: dict[str, float] = {}
        self.is_fitted: bool = False

    def _select_feature_columns(self, df: pd.DataFrame) -> list[str]:
        """Identifies valid numeric feature columns excluding metadata and targets."""
        feature_cols: list[str] = []
        for col in df.columns:
            if col.lower() in self.EXCLUDED_COLUMNS:
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                feature_cols.append(col)
        return feature_cols

    def fit(self, df_train: pd.DataFrame) -> "MLFeatureTransformer":
        """
        Fits feature transformer statistics strictly on training data.
        """
        if df_train is None or df_train.empty:
            raise ValueError("Training DataFrame cannot be None or empty")

        self.feature_names = self._select_feature_columns(df_train)
        if not self.feature_names:
            raise ValueError("No numeric feature columns found in training DataFrame")

        X_train = df_train[self.feature_names].copy()

        # Compute medians for imputation strictly on train
        self.medians = {}
        for col in self.feature_names:
            med_val = float(X_train[col].median())
            if np.isnan(med_val):
                med_val = 0.0
            self.medians[col] = med_val
            X_train[col] = X_train[col].fillna(med_val)

        # Replace any residual infinities with 0.0
        X_train = X_train.replace([np.inf, -np.inf], 0.0)

        self.scaler.fit(X_train.values)
        self.is_fitted = True
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """
        Transforms input DataFrame using strictly pre-fitted training statistics.
        """
        if not self.is_fitted:
            raise RuntimeError(
                "MLFeatureTransformer must be fitted on training data before calling transform"
            )

        if df is None or df.empty:
            return np.empty((0, len(self.feature_names)), dtype=np.float64)

        X = df.reindex(columns=self.feature_names).copy()

        # Impute using stored training medians
        for col in self.feature_names:
            X[col] = X[col].fillna(self.medians.get(col, 0.0))

        X = X.replace([np.inf, -np.inf], 0.0)
        transformed: np.ndarray = np.asarray(self.scaler.transform(X.values), dtype=np.float64)
        return transformed

    def fit_transform(self, df_train: pd.DataFrame) -> np.ndarray:
        """Fits on training data and returns transformed array."""
        return self.fit(df_train).transform(df_train)
