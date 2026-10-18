"""Unit tests for Random Forest direct multi-horizon forecaster."""

import numpy as np
import pandas as pd
import pytest

from reserve_juggler_ml.features.causal import extract_causal_feature_vector
from reserve_juggler_ml.features.training_dataset import build_supervised_dataset
from reserve_juggler_ml.forecasting.random_forest import RandomForestForecaster


@pytest.fixture
def sample_hourly_series():
    """Create a synthetic 300-hour series with hourly DatetimeIndex."""
    dates = pd.date_range("2026-01-01 00:00:00", periods=300, freq="h")
    # Diurnal wave with noise
    hours = dates.hour
    values = 1000.0 + 500.0 * np.sin(2 * np.pi * hours / 24.0) + np.random.RandomState(42).normal(0, 50, 300)
    return pd.Series(values, index=dates, name="deposits_usd")


def test_random_forest_init():
    rf = RandomForestForecaster(n_estimators=50, max_depth=8, random_state=123)
    assert rf.n_estimators == 50
    assert rf.max_depth == 8
    assert rf.random_state == 123
    assert not rf.is_fitted_


def test_random_forest_rejects_insufficient_history(sample_hourly_series):
    rf = RandomForestForecaster(min_history_hours=168)
    short_series = sample_hourly_series.iloc[:100]
    with pytest.raises(ValueError, match="Insufficient history"):
        rf.fit(short_series)


def test_random_forest_rejects_nan_inputs(sample_hourly_series):
    rf = RandomForestForecaster()
    corrupt_series = sample_hourly_series.copy()
    corrupt_series.iloc[10] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        rf.fit(corrupt_series)


def test_random_forest_predict_before_fit():
    rf = RandomForestForecaster()
    with pytest.raises(RuntimeError, match="Model must be fitted"):
        rf.predict()


def test_random_forest_fit_and_predict_contract(sample_hourly_series):
    rf = RandomForestForecaster(n_estimators=20, max_depth=6, random_state=42)
    rf.fit(sample_hourly_series)

    assert rf.is_fitted_
    output = rf.predict(periods=72)

    # Standardized output contract
    assert output.model_name == "Random Forest"
    assert output.converged is True
    assert len(output.mean) == 72
    assert len(output.lower) == 72
    assert len(output.upper) == 72

    # Non-negative flow constraint
    assert (output.mean >= 0.0).all()
    assert (output.lower >= 0.0).all()

    # Monotonic hourly forecast timestamps starting at t = last_ts + 1h
    expected_start = sample_hourly_series.index[-1] + pd.DateOffset(hours=1)
    assert output.mean.index[0] == expected_start
    assert output.mean.index[-1] == expected_start + pd.DateOffset(hours=71)

    # Latency tracking
    assert "inference_ms" in output.metadata
    assert output.metadata["inference_ms"] > 0.0


def test_random_forest_reproducibility(sample_hourly_series):
    rf1 = RandomForestForecaster(n_estimators=30, max_depth=6, random_state=42)
    rf2 = RandomForestForecaster(n_estimators=30, max_depth=6, random_state=42)

    rf1.fit(sample_hourly_series)
    rf2.fit(sample_hourly_series)

    out1 = rf1.predict(72)
    out2 = rf2.predict(72)

    np.testing.assert_allclose(out1.mean.to_numpy(), out2.mean.to_numpy())


def test_random_forest_fit_supervised_direct():
    n_samples = 50
    n_features = 22
    horizon = 72
    X = np.random.RandomState(42).normal(100, 10, (n_samples, n_features))
    Y = np.random.RandomState(42).uniform(500, 2000, (n_samples, horizon))

    rf = RandomForestForecaster(n_estimators=10, max_depth=5, random_state=42)
    rf.fit_supervised(X, Y)

    assert rf.is_fitted_
    # Verify rejection of empty or mismatched arrays
    with pytest.raises(ValueError, match="cannot be empty"):
        rf.fit_supervised(np.zeros((0, n_features)), np.zeros((0, horizon)))
    with pytest.raises(ValueError, match="Mismatched sample counts"):
        rf.fit_supervised(np.zeros((10, n_features)), np.zeros((20, horizon)))


def test_random_forest_final_test_isolation():
    # Attempting to build supervised dataset for 'final_test' must raise PermissionError
    dates = pd.date_range("2026-11-01 00:00:00", periods=200, freq="h")
    df = pd.DataFrame({
        "timestamp": dates,
        "deposits_usd": np.ones(200) * 1000.0,
    })
    with pytest.raises(PermissionError, match="strictly reserved"):
        build_supervised_dataset(df, target_col="deposits_usd", partition_name="final_test")
