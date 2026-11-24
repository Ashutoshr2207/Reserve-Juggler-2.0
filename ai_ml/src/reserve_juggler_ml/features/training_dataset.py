"""Supervised training dataset construction for direct multi-horizon forecasters."""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from reserve_juggler_ml.evaluation.splits import generate_rolling_origins
from reserve_juggler_ml.features.causal import (
    CAUSAL_FEATURE_NAMES,
    extract_causal_feature_vector,
)


def build_supervised_dataset(
    df: pd.DataFrame,
    target_col: str,
    partition_name: str = "dev",
    horizon_hours: int = 72,
    min_history_hours: int = 336,
    step_hours: int = 1,
    timestamp_col: str = "timestamp",
) -> Tuple[np.ndarray, np.ndarray, List[str], Dict[str, Any]]:
    """
    Construct strictly causal supervised training matrices (X, Y) from a designated partition.

    Strict Anti-Leakage Contract:
    1. Origin Generation: Uses generate_rolling_origins() enforcing interval-start semantics.
    2. Partition Isolation: Fits MUST only occur on 'dev'. If 'final_test' is requested, raises PermissionError.
    3. Input Features X: For each origin t, computed strictly from observations prior to t (index 0 to t-1).
       Row timestamped exactly t is strictly excluded.
    4. Targets Y: The 72 hourly forward target flows starting at t through t+71.
    5. Forward Boundary Purging: Origins whose forward 72-hour window exceeds the partition boundary are purged.
    """
    if target_col not in df.columns:
        raise KeyError(f"Target column '{target_col}' not found in DataFrame.")

    origins, meta = generate_rolling_origins(
        df=df,
        partition_name=partition_name,
        horizon_hours=horizon_hours,
        min_history_hours=min_history_hours,
        step_hours=step_hours,
        timestamp_col=timestamp_col,
        allow_reserved=False,  # Rejects final_test strictly
    )

    if not origins:
        raise ValueError(
            f"No valid chronological origins generated for partition '{partition_name}'."
        )

    ts_series = pd.to_datetime(df[timestamp_col])
    target_vals = df[target_col].to_numpy(dtype=float)
    full_history_series = pd.Series(target_vals, index=ts_series)

    n_samples = len(origins)
    n_features = len(CAUSAL_FEATURE_NAMES)

    X = np.zeros((n_samples, n_features), dtype=float)
    Y = np.zeros((n_samples, horizon_hours), dtype=float)

    for i, origin in enumerate(origins):
        # 1. Causal historical series strictly before origin_idx (t)
        hist = full_history_series.iloc[origin.history_start_idx:origin.history_end_idx]
        X[i] = extract_causal_feature_vector(hist, origin.origin_timestamp)

        # 2. Forward target flow window: intervals [t, t+1h) through [t+71h, t+72h)
        targets = target_vals[origin.target_start_idx:origin.target_end_idx]
        Y[i] = targets

    metadata = {
        "partition_name": partition_name,
        "target_col": target_col,
        "sample_count": n_samples,
        "feature_count": n_features,
        "horizon_hours": horizon_hours,
        "min_history_hours": min_history_hours,
        "step_hours": step_hours,
        "origin_generation_metadata": meta,
        "first_origin_timestamp": str(origins[0].origin_timestamp),
        "last_origin_timestamp": str(origins[-1].origin_timestamp),
    }

    return X, Y, list(CAUSAL_FEATURE_NAMES), metadata
