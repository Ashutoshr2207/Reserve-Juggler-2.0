"""Feature engineering module for Reserve Juggler ML."""

from reserve_juggler_ml.features.causal import (
    CAUSAL_FEATURE_NAMES,
    build_calendar_features,
    build_causal_rolling_features,
    build_lag_features,
    create_feature_matrix,
    extract_causal_feature_vector,
)
from reserve_juggler_ml.features.training_dataset import build_supervised_dataset

__all__ = [
    "CAUSAL_FEATURE_NAMES",
    "build_calendar_features",
    "build_lag_features",
    "build_causal_rolling_features",
    "create_feature_matrix",
    "extract_causal_feature_vector",
    "build_supervised_dataset",
]

