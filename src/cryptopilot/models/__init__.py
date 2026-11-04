"""
CryptoPilot AI - Machine Learning Prediction Engine.
Provides leak-free feature pipelines, purged time-series splitting, XGBoost prediction,
probability calibration, and deterministic inference.
"""

from cryptopilot.models.inference import MLInferenceEngine, MLPrediction
from cryptopilot.models.persistence import ModelArtifactManager
from cryptopilot.models.pipeline import MLFeatureTransformer
from cryptopilot.models.splitter import PurgedTimeSeriesSplitter
from cryptopilot.models.target import TargetConfig, TargetLabeler
from cryptopilot.models.trainer import ModelEvaluationMetrics, XGBoostPredictor

__all__ = [
    "MLFeatureTransformer",
    "MLInferenceEngine",
    "MLPrediction",
    "ModelArtifactManager",
    "ModelEvaluationMetrics",
    "PurgedTimeSeriesSplitter",
    "TargetConfig",
    "TargetLabeler",
    "XGBoostPredictor",
]

