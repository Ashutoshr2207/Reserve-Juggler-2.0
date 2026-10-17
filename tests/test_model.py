import numpy as np
import pandas as pd

import liquidity_forecasting.model as model_module
from liquidity_forecasting.data import (
    generate_sample_cashflows,
    preprocess_data,
)
from liquidity_forecasting.model import (
    forecast_currency,
    forecast_currency_with_intervals,
)


def test_forecast_currency_produces_expected_horizon_without_nans():
    data = preprocess_data(generate_sample_cashflows())
    horizon = 14

    forecast = forecast_currency(
        data,
        "EUR",
        periods=horizon,
    )

    expected_index = pd.date_range(
        start=data.index.max() + pd.Timedelta(days=1),
        periods=horizon,
        freq="D",
    )

    assert len(forecast) == horizon
    assert isinstance(forecast, (pd.Series, np.ndarray))
    assert pd.Series(forecast).isna().sum() == 0
    assert isinstance(forecast.index, pd.DatetimeIndex)
    assert forecast.index.equals(expected_index)
    assert forecast.name == "EUR"


def test_forecast_result_contains_prediction_intervals():
    data = preprocess_data(generate_sample_cashflows())
    horizon = 7

    result = forecast_currency_with_intervals(
        data,
        "EUR",
        periods=horizon,
    )

    assert len(result.mean) == horizon
    assert len(result.lower) == horizon
    assert len(result.upper) == horizon
    assert result.mean.index.equals(result.lower.index)
    assert result.mean.index.equals(result.upper.index)
    assert (result.lower <= result.upper).all()
    assert isinstance(result.converged, bool)
    assert result.model_name in {
        "SARIMAX",
        "Seasonal Naive (fallback)",
    }


def test_non_converged_model_uses_seasonal_naive_fallback(monkeypatch):
    class NonConvergedResult:
        mle_retvals = {"converged": False}

    class NonConvergedSarimax:
        def __init__(self, *args, **kwargs):
            pass

        def fit(self, disp=False):
            return NonConvergedResult()

    monkeypatch.setattr(
        model_module,
        "SARIMAX",
        NonConvergedSarimax,
    )

    dates = pd.date_range("2025-01-01", periods=14, freq="D")
    data = pd.DataFrame(
        {"EUR": [float(value) for value in range(14)]},
        index=dates,
    )

    result = model_module.forecast_currency_with_intervals(
        data,
        "EUR",
        periods=3,
    )

    assert result.model_name == "Seasonal Naive (fallback)"
    assert result.converged is False
    assert result.mean.tolist() == [7.0, 8.0, 9.0]
    assert len(result.lower) == 3
    assert len(result.upper) == 3
