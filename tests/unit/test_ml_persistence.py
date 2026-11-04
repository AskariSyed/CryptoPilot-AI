"""
Unit tests for cryptopilot.models.persistence.ModelArtifactManager.
Covers: Atomic artifact saving, loading, versioning verification, and integrity checks.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cryptopilot.models.persistence import ModelArtifactManager
from cryptopilot.models.pipeline import MLFeatureTransformer
from cryptopilot.models.trainer import XGBoostPredictor


class TestModelArtifactManager:
    @pytest.fixture
    def trained_components(self) -> tuple[MLFeatureTransformer, XGBoostPredictor]:
        np.random.seed(42)
        n = 50
        df = pd.DataFrame({"f1": np.random.randn(n), "f2": np.random.randn(n)})
        y = (df["f1"] > 0).astype(int)

        transformer = MLFeatureTransformer(scaler_type="robust")
        X_scaled = transformer.fit_transform(df)

        predictor = XGBoostPredictor(n_estimators=10, random_state=42)
        predictor.fit(X_scaled, y, feature_names=["f1", "f2"])

        return transformer, predictor

    def test_save_and_load_artifact(self, tmp_path: Path, trained_components) -> None:
        transformer, predictor = trained_components
        artifact_dir = tmp_path / "model_v1"

        saved_path = ModelArtifactManager.save_artifact(
            artifact_dir=artifact_dir,
            transformer=transformer,
            predictor=predictor,
            model_version="1.0.0",
            extra_metadata={"symbol": "BTC/USDT"},
        )
        assert saved_path.exists()
        assert (artifact_dir / "model.json").exists()
        assert (artifact_dir / "scaler.joblib").exists()
        assert (artifact_dir / "metadata.json").exists()

        # Load back
        loaded_transformer, loaded_predictor, metadata = ModelArtifactManager.load_artifact(
            artifact_dir
        )
        assert loaded_transformer.is_fitted is True
        assert loaded_predictor.is_fitted is True
        assert metadata["model_version"] == "1.0.0"
        assert metadata["extra"]["symbol"] == "BTC/USDT"
        assert loaded_transformer.feature_names == ["f1", "f2"]
        assert loaded_predictor.feature_names == ["f1", "f2"]

        # Predictions from original and loaded model must match exactly
        test_df = pd.DataFrame({"f1": [0.5, -0.2], "f2": [1.1, -0.8]})
        X_orig = transformer.transform(test_df)
        X_loaded = loaded_transformer.transform(test_df)
        assert np.allclose(X_orig, X_loaded)

        p_orig = predictor.predict_proba(X_orig)
        p_loaded = loaded_predictor.predict_proba(X_loaded)
        assert np.allclose(p_orig, p_loaded)

    def test_save_unfitted_raises_value_error(self, tmp_path: Path) -> None:
        transformer = MLFeatureTransformer()
        predictor = XGBoostPredictor()
        with pytest.raises(ValueError, match="Predictor must be fitted"):
            ModelArtifactManager.save_artifact(tmp_path / "bad", transformer, predictor)

    def test_load_nonexistent_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            ModelArtifactManager.load_artifact(tmp_path / "does_not_exist")
