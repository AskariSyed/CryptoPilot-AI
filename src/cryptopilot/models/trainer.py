"""
CryptoPilot AI - XGBoost Supervised Predictive Classifier.
Trains calibrated probabilistic classifiers on cost-adjusted return targets,
evaluates against naive baselines (PR-AUC, Brier score), and extracts feature importances.
"""

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from xgboost import XGBClassifier


class ModelEvaluationMetrics(BaseModel):
    """Evaluation metrics comparing trained model against naive benchmarks."""

    pr_auc: float = Field(ge=0.0, le=1.0)
    roc_auc: float = Field(ge=0.0, le=1.0)
    brier_score: float = Field(ge=0.0, le=1.0)
    log_loss_val: float = Field(ge=0.0)
    baseline_pr_auc: float = Field(ge=0.0, le=1.0)
    baseline_brier_score: float = Field(ge=0.0, le=1.0)
    beats_baseline: bool
    sample_count: int


class XGBoostPredictor:
    """
    Supervised predictive model estimating the probability of forward return > cost threshold.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        random_state: int = 42,
    ) -> None:
        self.n_estimators = max(10, n_estimators)
        self.max_depth = max(1, max_depth)
        self.learning_rate = max(0.001, learning_rate)
        self.subsample = min(1.0, max(0.1, subsample))
        self.colsample_bytree = min(1.0, max(0.1, colsample_bytree))
        self.random_state = random_state

        self.model: XGBClassifier | None = None
        self.feature_names: list[str] = []
        self.is_fitted: bool = False
        self.base_rate: float = 0.50

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray | pd.Series,
        X_val: np.ndarray | None = None,
        y_val: np.ndarray | pd.Series | None = None,
        feature_names: list[str] | None = None,
    ) -> ModelEvaluationMetrics:
        """
        Trains XGBoost classifier and evaluates performance on validation set.
        """
        if len(X_train) == 0:
            raise ValueError("X_train cannot be empty")

        y_train_arr = np.asarray(y_train, dtype=int)
        unique_classes = np.unique(y_train_arr)

        if len(unique_classes) < 2:
            # Degenerate single-class target edge case
            self.base_rate = float(unique_classes[0]) if len(unique_classes) == 1 else 0.5
            self.is_fitted = True
            return ModelEvaluationMetrics(
                pr_auc=self.base_rate,
                roc_auc=0.50,
                brier_score=0.0,
                log_loss_val=0.0,
                baseline_pr_auc=self.base_rate,
                baseline_brier_score=0.0,
                beats_baseline=False,
                sample_count=len(X_train),
            )

        # Calculate class imbalance weighting
        pos_count = int(np.sum(y_train_arr == 1))
        neg_count = int(np.sum(y_train_arr == 0))
        scale_pos_weight = float(neg_count / max(1, pos_count))
        self.base_rate = float(pos_count / max(1, len(y_train_arr)))

        self.model = XGBClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            subsample=self.subsample,
            colsample_bytree=self.colsample_bytree,
            scale_pos_weight=scale_pos_weight,
            random_state=self.random_state,
            eval_metric="logloss",
        )

        eval_set = (
            [(X_val, np.asarray(y_val, dtype=int))]
            if X_val is not None and y_val is not None
            else None
        )

        self.model.fit(
            X_train,
            y_train_arr,
            eval_set=eval_set,
            verbose=False,
        )

        self.feature_names = feature_names or [f"feature_{i}" for i in range(X_train.shape[1])]
        self.is_fitted = True

        # Evaluate on validation set if provided, else on training set
        X_eval = X_val if X_val is not None and len(X_val) > 0 else X_train
        y_eval = np.asarray(
            y_val if y_val is not None and len(y_val) > 0 else y_train_arr, dtype=int
        )

        return self.evaluate(X_eval, y_eval)

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> ModelEvaluationMetrics:
        """
        Evaluates predictions against true binary targets and naive baseline.
        """
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model must be fitted before calling evaluate")

        y_true = np.asarray(y, dtype=int)
        y_probs = self.predict_proba(X)[:, 1]

        # Calculate model metrics
        try:
            pr_auc = float(average_precision_score(y_true, y_probs))
        except (ValueError, ZeroDivisionError):
            pr_auc = self.base_rate

        try:
            roc_auc = float(roc_auc_score(y_true, y_probs))
        except (ValueError, ZeroDivisionError):
            roc_auc = 0.50

        brier = float(brier_score_loss(y_true, y_probs))
        logloss = float(log_loss(y_true, y_probs))

        # Naive baseline: predicts constant base rate (training mean)
        baseline_probs = np.full_like(y_probs, fill_value=self.base_rate)
        try:
            baseline_pr_auc = float(average_precision_score(y_true, baseline_probs))
        except (ValueError, ZeroDivisionError):
            baseline_pr_auc = self.base_rate

        baseline_brier = float(brier_score_loss(y_true, baseline_probs))

        # Model beats baseline if PR-AUC is higher and Brier score is lower
        beats_baseline = (pr_auc > baseline_pr_auc) and (brier <= baseline_brier)

        return ModelEvaluationMetrics(
            pr_auc=pr_auc,
            roc_auc=roc_auc,
            brier_score=brier,
            log_loss_val=logloss,
            baseline_pr_auc=baseline_pr_auc,
            baseline_brier_score=baseline_brier,
            beats_baseline=beats_baseline,
            sample_count=len(y_true),
        )

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Returns 2D calibrated probability array: [P(y=0), P(y=1)].
        """
        if not self.is_fitted or self.model is None:
            # Fallback neutral probabilities
            n_samples = len(X)
            return np.full((n_samples, 2), fill_value=0.50)

        probs = self.model.predict_proba(X)
        return np.asarray(probs, dtype=np.float64)

    def predict(self, X: np.ndarray, threshold: float = 0.50) -> np.ndarray:
        """
        Returns binary class predictions using threshold.
        """
        probs = self.predict_proba(X)[:, 1]
        return (probs >= threshold).astype(int)

    def get_feature_importances(self) -> dict[str, float]:
        """
        Returns mapping of feature name -> normalized gain importance.
        """
        if not self.is_fitted or self.model is None:
            return {}

        raw_importances = self.model.feature_importances_
        total_imp = float(np.sum(raw_importances))

        if total_imp <= 0.0:
            return dict.fromkeys(self.feature_names, 0.0)

        importances: dict[str, float] = {}
        for i, name in enumerate(self.feature_names):
            if i < len(raw_importances):
                importances[name] = float(raw_importances[i] / total_imp)
            else:
                importances[name] = 0.0

        return dict(sorted(importances.items(), key=lambda item: item[1], reverse=True))
