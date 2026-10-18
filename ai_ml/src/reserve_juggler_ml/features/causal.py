"""Causal feature engineering with strict anti-leakage temporal guards."""

import numpy as np
import pandas as pd
from typing import List, Optional


def build_calendar_features(timestamps: pd.Series) -> pd.DataFrame:
    """
    Build cyclical deterministic calendar features from timestamps.
    Known deterministically at any future horizon step.
    """
    dt = pd.to_datetime(timestamps)
    hour = dt.dt.hour
    dayofweek = dt.dt.dayofweek

    features = pd.DataFrame(index=dt.index)
    features["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    features["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    features["dow_sin"] = np.sin(2 * np.pi * dayofweek / 7.0)
    features["dow_cos"] = np.cos(2 * np.pi * dayofweek / 7.0)
    features["is_weekend"] = (dayofweek >= 5).astype(float)
    return features


def build_lag_features(
    series: pd.Series,
    lags: List[int] = [1, 2, 3, 24, 48, 72, 168],
    prefix: str = "lag",
) -> pd.DataFrame:
    """
    Build strictly causal autoregressive lag features.
    Lag k is y_{t-k}, available at forecast origin t.
    """
    features = pd.DataFrame(index=series.index)
    for lag in lags:
        features[f"{prefix}_{lag}"] = series.shift(lag)
    return features


def build_causal_rolling_features(
    series: pd.Series,
    windows: List[int] = [24, 168],
    prefix: str = "roll",
) -> pd.DataFrame:
    """
    Build causal rolling summary statistics (totals, averages, dispersion, extremes).
    Uses .shift(1) before rolling to guarantee strictly zero lookahead to the current period.
    """
    shifted = series.shift(1)
    features = pd.DataFrame(index=series.index)
    for window in windows:
        roll = shifted.rolling(window=window, min_periods=max(1, window // 4))
        features[f"{prefix}_sum_{window}"] = roll.sum()
        features[f"{prefix}_mean_{window}"] = roll.mean()
        features[f"{prefix}_std_{window}"] = roll.std().fillna(0.0)
        features[f"{prefix}_min_{window}"] = roll.min()
        features[f"{prefix}_max_{window}"] = roll.max()
    return features


CAUSAL_FEATURE_NAMES: List[str] = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend",
    "lag_1", "lag_2", "lag_3", "lag_24", "lag_48", "lag_72", "lag_168",
    "roll_sum_24", "roll_mean_24", "roll_std_24", "roll_min_24", "roll_max_24",
    "roll_sum_168", "roll_mean_168", "roll_std_168", "roll_min_168", "roll_max_168",
]


def extract_causal_feature_vector(
    history_series: pd.Series,
    origin_timestamp: Optional[pd.Timestamp] = None,
) -> np.ndarray:
    """
    Extract the canonical 22-dimensional causal feature vector strictly prior to origin_timestamp.

    Guarantees:
    - History must contain only observations completed strictly before origin_timestamp.
    - If origin_timestamp is not provided, it is inferred as history_series.index[-1] + 1 hour.
    - Requires at least 168 hours (7 days) of trailing history.
    - Absolutely no lookahead or target leakage.
    """
    if len(history_series) < 168:
        raise ValueError(
            f"Insufficient history for feature extraction: minimum 168 hours required, got {len(history_series)}"
        )
    if history_series.isnull().any():
        raise ValueError("History series contains null/NaN values; cannot extract features safely.")

    if origin_timestamp is None:
        last_dt = pd.to_datetime(history_series.index[-1])
        origin_timestamp = last_dt + pd.DateOffset(hours=1)
    else:
        origin_timestamp = pd.to_datetime(origin_timestamp)

    vals = history_series.to_numpy(dtype=float)
    hour = origin_timestamp.hour
    dow = origin_timestamp.dayofweek

    # 1. Cyclical calendar of forecast origin t
    h_sin = np.sin(2.0 * np.pi * hour / 24.0)
    h_cos = np.cos(2.0 * np.pi * hour / 24.0)
    d_sin = np.sin(2.0 * np.pi * dow / 7.0)
    d_cos = np.cos(2.0 * np.pi * dow / 7.0)
    is_wknd = 1.0 if dow >= 5 else 0.0

    # 2. Autoregressive lags at t: y_{t-1}, y_{t-2}, y_{t-3}, y_{t-24}, y_{t-48}, y_{t-72}, y_{t-168}
    l1 = vals[-1]
    l2 = vals[-2]
    l3 = vals[-3]
    l24 = vals[-24]
    l48 = vals[-48]
    l72 = vals[-72]
    l168 = vals[-168]

    # 3. Rolling 24h stats over [t-24, t-1]
    t24 = vals[-24:]
    s24 = float(np.sum(t24))
    m24 = float(np.mean(t24))
    sd24 = float(np.std(t24, ddof=1)) if len(t24) > 1 else 0.0
    mn24 = float(np.min(t24))
    mx24 = float(np.max(t24))

    # 4. Rolling 168h stats over [t-168, t-1]
    t168 = vals[-168:]
    s168 = float(np.sum(t168))
    m168 = float(np.mean(t168))
    sd168 = float(np.std(t168, ddof=1)) if len(t168) > 1 else 0.0
    mn168 = float(np.min(t168))
    mx168 = float(np.max(t168))

    return np.array([
        h_sin, h_cos, d_sin, d_cos, is_wknd,
        l1, l2, l3, l24, l48, l72, l168,
        s24, m24, sd24, mn24, mx24,
        s168, m168, sd168, mn168, mx168,
    ], dtype=float)


def create_feature_matrix(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    target_cols: List[str] = ["deposits", "withdrawals"],
    lags: List[int] = [1, 2, 3, 24, 48, 72, 168],
    windows: List[int] = [24, 168],
) -> pd.DataFrame:
    """
    Assemble the complete causal feature matrix.
    Rows with NaN from initial lags should be dropped or trimmed.
    """
    feature_dfs = []
    if timestamp_col in df.columns:
        feature_dfs.append(build_calendar_features(df[timestamp_col]))

    for col in target_cols:
        if col in df.columns:
            feature_dfs.append(build_lag_features(df[col], lags=lags, prefix=f"{col}_lag"))
            feature_dfs.append(build_causal_rolling_features(df[col], windows=windows, prefix=f"{col}_roll"))

    return pd.concat(feature_dfs, axis=1)

