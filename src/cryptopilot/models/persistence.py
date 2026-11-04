"""
CryptoPilot AI - Model Artifact Persistence & Versioning Manager.
Saves and loads native XGBoost model files, transformer pipelines, and reproducibility metadata.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib

from cryptopilot.models.pipeline import MLFeatureTransformer
from cryptopilot.models.trainer import ModelEvaluationMetrics, XGBoostPredictor


class ModelArtifactManager:
    """
    Manages serialization, versioning, and atomic loading of model artifacts.
    """

    MODEL_FILENAME = "model.json"
    SCALER_FILENAME = "scaler.joblib"
    METADATA_FILENAME = "metadata.json"

    @classmethod
    def save_artifact(
        cls,
        artifact_dir: Path | str,
        transformer: MLFeatureTransformer,
        predictor: XGBoostPredictor,
        metrics: ModelEvaluationMetrics | None = None,
        model_version: str = "1.0.0",
        extra_metadata: dict[str, Any] | None = None,
    ) -> Path:
        """
        Saves model weights, scaler statistics, and metadata to the artifact directory.
        """
        path = Path(artifact_dir)
        path.mkdir(parents=True, exist_ok=True)

        if not predictor.is_fitted or predictor.model is None:
            raise ValueError("Predictor must be fitted before saving artifact")
        if not transformer.is_fitted:
            raise ValueError("Transformer must be fitted before saving artifact")

        # 1. Save native XGBoost model
        model_path = path / cls.MODEL_FILENAME
        predictor.model.save_model(str(model_path))

        # 2. Save Scaler pipeline
        scaler_path = path / cls.SCALER_FILENAME
        joblib.dump(transformer.scaler, str(scaler_path))

        # 3. Save comprehensive metadata
        meta: dict[str, Any] = {
            "model_version": model_version,
            "saved_at": datetime.now(UTC).isoformat(),
            "scaler_type": transformer.scaler_type,
            "feature_names": transformer.feature_names,
            "medians": transformer.medians,
            "base_rate": predictor.base_rate,
            "hyperparameters": {
                "n_estimators": predictor.n_estimators,
                "max_depth": predictor.max_depth,
                "learning_rate": predictor.learning_rate,
                "subsample": predictor.subsample,
                "colsample_bytree": predictor.colsample_bytree,
                "random_state": predictor.random_state,
            },
        }

        if metrics is not None:
            meta["metrics"] = metrics.model_dump()
        if extra_metadata:
            meta["extra"] = extra_metadata

        metadata_path = path / cls.METADATA_FILENAME
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return path

    @classmethod
    def load_artifact(
        cls,
        artifact_dir: Path | str,
    ) -> tuple[MLFeatureTransformer, XGBoostPredictor, dict[str, Any]]:
        """
        Loads saved model, scaler, and metadata from the artifact directory.
        """
        path = Path(artifact_dir)
        metadata_path = path / cls.METADATA_FILENAME
        model_path = path / cls.MODEL_FILENAME
        scaler_path = path / cls.SCALER_FILENAME

        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found at {metadata_path}")
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found at {model_path}")
        if not scaler_path.exists():
            raise FileNotFoundError(f"Scaler file not found at {scaler_path}")

        # 1. Load metadata
        with open(metadata_path, encoding="utf-8") as f:
            metadata: dict[str, Any] = json.load(f)

        # 2. Reconstruct Transformer
        scaler_type = metadata.get("scaler_type", "robust")
        transformer = MLFeatureTransformer(scaler_type=scaler_type)
        transformer.scaler = joblib.load(str(scaler_path))
        transformer.feature_names = metadata.get("feature_names", [])
        transformer.medians = metadata.get("medians", {})
        transformer.is_fitted = True

        # 3. Reconstruct Predictor
        hparams = metadata.get("hyperparameters", {})
        predictor = XGBoostPredictor(
            n_estimators=hparams.get("n_estimators", 100),
            max_depth=hparams.get("max_depth", 4),
            learning_rate=hparams.get("learning_rate", 0.05),
            subsample=hparams.get("subsample", 0.8),
            colsample_bytree=hparams.get("colsample_bytree", 0.8),
            random_state=hparams.get("random_state", 42),
        )

        from xgboost import XGBClassifier

        predictor.model = XGBClassifier()
        predictor.model.load_model(str(model_path))
        predictor.feature_names = transformer.feature_names
        predictor.base_rate = metadata.get("base_rate", 0.5)
        predictor.is_fitted = True

        return transformer, predictor, metadata
