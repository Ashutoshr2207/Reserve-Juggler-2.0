"""Unit tests for baseline and seasonal-naïve forecasters."""

import pandas as pd
import numpy as np
from reserve_juggler_ml.forecasting.baseline import DeterministicBaseline
from reserve_juggler_ml.forecasting.seasonal import SeasonalNaiveForecaster


def test_deterministic_baseline_fit_and_predict():
    # 14 days of synthetic hourly data (336 rows)
    index = pd.date_range("2026-10-01 00:00:00", periods=336, freq="h")
    # Base diurnal cycle: higher in afternoon, lower at night
    values = 1000.0 + 500.0 * np.sin(2 * np.pi * index.hour / 24.0) + np.random.normal(0, 10, 336)
    series = pd.Series(values, index=index, name="net_flow")

    model = DeterministicBaseline(lookback_hours=336)
    model.fit(series)
    pred = model.predict(periods=72, alpha=0.05)

    assert len(pred.mean) == 72
    assert len(pred.lower) == 72
    assert len(pred.upper) == 72
    assert (pred.lower <= pred.mean).all()
    assert (pred.mean <= pred.upper).all()
    assert pred.model_name == "Deterministic 14-Day Baseline"
    assert pred.converged is True


def test_seasonal_naive_forecaster_fit_and_predict():
    index = pd.date_range("2026-10-01 00:00:00", periods=168, freq="h")
    values = 500.0 + 200.0 * np.sin(2 * np.pi * index.hour / 24.0)
    series = pd.Series(values, index=index, name="withdrawals")

    model = SeasonalNaiveForecaster(season_length=24)
    model.fit(series)
    pred = model.predict(periods=72, alpha=0.05)

    assert len(pred.mean) == 72
    # Check 24-hour repeating periodicity
    assert np.allclose(pred.mean.iloc[:24].values, pred.mean.iloc[24:48].values)
    assert np.allclose(pred.mean.iloc[24:48].values, pred.mean.iloc[48:72].values)
    assert (pred.lower <= pred.mean).all()
    assert (pred.mean <= pred.upper).all()
