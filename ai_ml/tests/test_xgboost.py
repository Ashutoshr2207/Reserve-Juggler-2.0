"""Unit tests for XGBoost direct multi-horizon forecaster."""

import numpy as np
import pandas as pd
import pytest

from reserve_juggler_ml.features.causal import extract_causal_feature_vector
from reserve_juggler_ml.features.training_dataset import build_supervised_dataset
from reserve_juggler_ml.forecasting.xgboost_forecaster import XGBoostForecaster


@pytest.fixture
def sample_hourly_series():
    """Create a synthetic 300-hour series with hourly DatetimeIndex."""
    dates = pd.date_range("2026-01-01 00:00:00", periods=300, freq="h")
    hours = dates.hour
    values = 1200.0 + 400.0 * np.sin(2 * np.pi * hours / 24.0) + np.random.RandomState(42).normal(0, 40, 300)
    return pd.Series(values, index=dates, name="withdrawals_usd")


def test_xgboost_init():
    xgb_f = XGBoostForecaster(n_estimators=60, max_depth=4, learning_rate=0.05, random_state=99)
    assert xgb_f.n_estimators == 60
    assert xgb_f.max_depth == 4
    assert xgb_f.learning_rate == 0.05
    assert xgb_f.random_state == 99
    assert not xgb_f.is_fitted_


def test_xgboost_rejects_insufficient_history(sample_hourly_series):
    xgb_f = XGBoostForecaster(min_history_hours=168)
    short_series = sample_hourly_series.iloc[:100]
    with pytest.raises(ValueError, match="Insufficient history"):
        xgb_f.fit(short_series)


def test_xgboost_rejects_nan_inputs(sample_hourly_series):
    xgb_f = XGBoostForecaster()
    corrupt_series = sample_hourly_series.copy()
    corrupt_series.iloc[15] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        xgb_f.fit(corrupt_series)


def test_xgboost_predict_before_fit():
    xgb_f = XGBoostForecaster()
    with pytest.raises(RuntimeError, match="Model must be fitted"):
        xgb_f.predict()


def test_xgboost_fit_and_predict_contract(sample_hourly_series):
    xgb_f = XGBoostForecaster(n_estimators=20, max_depth=4, random_state=42)
    xgb_f.fit(sample_hourly_series)

    assert xgb_f.is_fitted_
    output = xgb_f.predict(periods=72)

    # Standardized output contract
    assert output.model_name == "XGBoost"
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


def test_xgboost_reproducibility(sample_hourly_series):
    xgb1 = XGBoostForecaster(n_estimators=25, max_depth=4, random_state=42)
    xgb2 = XGBoostForecaster(n_estimators=25, max_depth=4, random_state=42)

    xgb1.fit(sample_hourly_series)
    xgb2.fit(sample_hourly_series)

    out1 = xgb1.predict(72)
    out2 = xgb2.predict(72)

    np.testing.assert_allclose(out1.mean.to_numpy(), out2.mean.to_numpy(), rtol=1e-5)


def test_xgboost_fit_supervised_direct():
    n_samples = 50
    n_features = 22
    horizon = 72
    X = np.random.RandomState(42).normal(100, 10, (n_samples, n_features))
    Y = np.random.RandomState(42).uniform(500, 2000, (n_samples, horizon))

    xgb_f = XGBoostForecaster(n_estimators=10, max_depth=3, random_state=42)
    xgb_f.fit_supervised(X, Y)

    assert xgb_f.is_fitted_
    with pytest.raises(ValueError, match="cannot be empty"):
        xgb_f.fit_supervised(np.zeros((0, n_features)), np.zeros((0, horizon)))
    with pytest.raises(ValueError, match="Mismatched sample counts"):
        xgb_f.fit_supervised(np.zeros((10, n_features)), np.zeros((20, horizon)))


def test_xgboost_final_test_isolation():
    dates = pd.date_range("2026-11-01 00:00:00", periods=200, freq="h")
    df = pd.DataFrame({
        "timestamp": dates,
        "withdrawals_usd": np.ones(200) * 1500.0,
    })
    with pytest.raises(PermissionError, match="strictly reserved"):
        build_supervised_dataset(df, target_col="withdrawals_usd", partition_name="final_test")
