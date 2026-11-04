"""
Unit tests for cryptopilot.models.trainer.XGBoostPredictor.
Covers: Model training, probability output, evaluation against baselines, and feature importances.
"""

import numpy as np
import pytest

from cryptopilot.models.trainer import XGBoostPredictor


class TestXGBoostPredictor:
    @pytest.fixture
    def synthetic_classification_data(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        np.random.seed(42)
        n = 100
        # 3 features: feature 0 has strong positive signal for target
        X = np.random.randn(n, 3)
        # Target probability correlated with feature 0
        prob = 1.0 / (1.0 + np.exp(-X[:, 0] * 2.0))
        y = (prob > 0.50).astype(int)

        X_train, y_train = X[:70], y[:70]
        X_val, y_val = X[70:], y[70:]
        return X_train, y_train, X_val, y_val

    def test_fit_and_evaluate_xgboost(self, synthetic_classification_data) -> None:
        X_train, y_train, X_val, y_val = synthetic_classification_data
        predictor = XGBoostPredictor(n_estimators=20, max_depth=3, random_state=42)

        feature_names = ["momentum_lead", "volatility_spread", "noise_col"]
        metrics = predictor.fit(
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            feature_names=feature_names,
        )

        assert predictor.is_fitted is True
        assert metrics.pr_auc > 0.0
        assert metrics.roc_auc > 0.0
        assert metrics.brier_score <= 1.0
        assert metrics.sample_count == len(X_val)

        # Probabilities contract: 2D shape, sum to 1.0, strictly in [0, 1]
        probs = predictor.predict_proba(X_val)
        assert probs.shape == (len(X_val), 2)
        assert np.all((probs >= 0.0) & (probs <= 1.0))
        assert np.allclose(np.sum(probs, axis=1), 1.0)

        # Binary predictions
        preds = predictor.predict(X_val, threshold=0.50)
        assert len(preds) == len(X_val)
        assert set(np.unique(preds)).issubset({0, 1})

    def test_feature_importances_extraction(self, synthetic_classification_data) -> None:
        X_train, y_train, X_val, y_val = synthetic_classification_data
        predictor = XGBoostPredictor(n_estimators=20, random_state=42)
        feature_names = ["lead_signal", "mid_signal", "noise"]
        predictor.fit(X_train, y_train, feature_names=feature_names)

        importances = predictor.get_feature_importances()
        assert len(importances) == 3
        # Sum of normalized importances must equal ~1.0
        assert pytest.approx(sum(importances.values()), abs=1e-4) == 1.0
        # Lead signal was built to correlate strongest
        assert "lead_signal" in importances

    def test_degenerate_single_class_target_edge_case(self) -> None:
        """When training set contains only a single class (e.g. all 0s), predictor handles gracefully."""
        X_train = np.random.randn(20, 2)
        y_all_zero = np.zeros(20, dtype=int)

        predictor = XGBoostPredictor()
        metrics = predictor.fit(X_train, y_all_zero)
        assert predictor.is_fitted is True
        assert metrics.beats_baseline is False

        # Predictions return base rate
        probs = predictor.predict_proba(X_train[:5])
        assert probs.shape == (5, 2)

    def test_unfitted_predictor_fallback(self) -> None:
        predictor = XGBoostPredictor()
        X = np.random.randn(5, 2)
        probs = predictor.predict_proba(X)
        # Fallback returns neutral 0.50
        assert np.allclose(probs, 0.50)
        assert predictor.get_feature_importances() == {}

        with pytest.raises(RuntimeError, match="must be fitted before calling evaluate"):
            predictor.evaluate(X, np.zeros(5))

    def test_empty_X_train_raises_value_error(self) -> None:
        predictor = XGBoostPredictor()
        with pytest.raises(ValueError, match="X_train cannot be empty"):
            predictor.fit(np.empty((0, 2)), np.array([]))
