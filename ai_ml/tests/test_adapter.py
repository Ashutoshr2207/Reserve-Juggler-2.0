"""Unit tests for backend integration adapter."""

import pandas as pd
from reserve_juggler_ml.integration.adapter import (
    adapt_to_backend_state,
    format_forecast_response,
)


def test_format_forecast_response_and_backend_adapter():
    index = pd.date_range("2026-10-18 09:00:00", periods=72, freq="h", tz="UTC")

    dep_mean = pd.Series([1000.0] * 72, index=index)
    dep_low = pd.Series([900.0] * 72, index=index)
    dep_high = pd.Series([1100.0] * 72, index=index)

    wdr_mean = pd.Series([800.0] * 72, index=index)
    wdr_low = pd.Series([700.0] * 72, index=index)
    wdr_high = pd.Series([900.0] * 72, index=index)

    resp = format_forecast_response(
        deposits_mean=dep_mean,
        deposits_lower=dep_low,
        deposits_upper=dep_high,
        withdrawals_mean=wdr_mean,
        withdrawals_lower=wdr_low,
        withdrawals_upper=wdr_high,
        as_of="2026-10-18T08:00:00Z",
        confidence_level=0.95,
        model_name="TestBaseline",
        model_version="1.0.0",
        currency="INR",
    )

    assert resp.currency == "INR"
    assert resp.horizon_hours == 72
    assert len(resp.predictions) == 72
    assert resp.predictions[0].net.mean == 200.0  # 1000 - 800

    # Test backend adapter translation
    net_rows, gross_forecast_obj = adapt_to_backend_state(resp)

    # Net rows compatibility check for server.py
    assert len(net_rows) == 72
    assert set(net_rows[0].keys()) == {
        "timestamp",
        "mean",
        "lower",
        "upper",
        "withdrawals",
    }
    assert net_rows[0]["mean"] == 200.0

    # Gross forecast compatibility check for web/app.js
    assert gross_forecast_obj["model"] == "TestBaseline v1.0.0"
    assert len(gross_forecast_obj["rows"]) == 72
    assert set(gross_forecast_obj["rows"][0].keys()) == {
        "timestamp",
        "deposits",
        "deposits_lower",
        "deposits_upper",
        "withdrawals",
        "withdrawals_lower",
        "withdrawals_upper",
    }
