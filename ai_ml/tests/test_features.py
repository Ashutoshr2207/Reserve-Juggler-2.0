"""Unit tests for causal feature engineering and anti-leakage checks."""

import pandas as pd
import numpy as np
from reserve_juggler_ml.features.causal import (
    build_calendar_features,
    build_lag_features,
    build_causal_rolling_features,
    create_feature_matrix,
)


def test_calendar_features_shape_and_range():
    timestamps = pd.date_range("2026-10-01", periods=48, freq="h")
    cal = build_calendar_features(pd.Series(timestamps))
    assert len(cal) == 48
    assert "hour_sin" in cal.columns
    assert "hour_cos" in cal.columns
    assert "dow_sin" in cal.columns
    assert "dow_cos" in cal.columns
    assert "is_weekend" in cal.columns
    assert cal["hour_sin"].between(-1.0, 1.0).all()
    assert cal["hour_cos"].between(-1.0, 1.0).all()


def test_lag_features_are_strictly_causal():
    series = pd.Series(range(10), name="values")
    lags = build_lag_features(series, lags=[1, 2], prefix="lag")

    # Row 0: lags should be NaN
    assert np.isnan(lags["lag_1"].iloc[0])
    assert np.isnan(lags["lag_2"].iloc[0])

    # Row 1: lag_1 is 0, lag_2 is NaN
    assert lags["lag_1"].iloc[1] == 0
    assert np.isnan(lags["lag_2"].iloc[1])

    # Row 2: lag_1 is 1, lag_2 is 0
    assert lags["lag_1"].iloc[2] == 1
    assert lags["lag_2"].iloc[2] == 0


def test_rolling_features_have_no_lookahead():
    # Construct a series with a sudden spike at index 5
    vals = [10.0] * 5 + [1000.0] + [10.0] * 5
    series = pd.Series(vals)
    rolling = build_causal_rolling_features(series, windows=[3], prefix="roll")

    # At index 5 (where the spike happens), the rolling mean MUST NOT include 1000.0
    # because it shifts by 1 period before rolling
    assert rolling["roll_mean_3"].iloc[5] == 10.0

    # At index 6, the spike at index 5 should now be reflected in the trailing window
    assert rolling["roll_mean_3"].iloc[6] > 10.0
