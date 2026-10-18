"""Unit tests for Reserve Juggler ML schemas."""

import pytest
from reserve_juggler_ml.data.schemas import (
    ForecastResponse,
    ForecastStep,
    HistoryObservation,
    LiquidityRiskHorizon,
    ModelMetadata,
    ValueWithInterval,
)


def test_history_observation_valid():
    obs = HistoryObservation(
        timestamp="2026-10-18T00:00:00Z",
        deposits=1000.0,
        withdrawals=500.0,
    )
    assert obs.deposits == 1000.0
    assert obs.withdrawals == 500.0


def test_history_observation_rejects_negative():
    with pytest.raises(ValueError, match="Deposits must be non-negative"):
        HistoryObservation("2026-10-18T00:00:00Z", -10.0, 100.0)

    with pytest.raises(ValueError, match="Withdrawals must be non-negative"):
        HistoryObservation("2026-10-18T00:00:00Z", 100.0, -50.0)


def test_value_with_interval_validation():
    val = ValueWithInterval(mean=100.0, lower=80.0, upper=120.0)
    assert val.mean == 100.0

    with pytest.raises(ValueError, match="Lower bound .* cannot exceed upper bound"):
        ValueWithInterval(mean=100.0, lower=130.0, upper=120.0)


def test_forecast_response_to_dict():
    step = ForecastStep(
        step=1,
        timestamp="2026-10-18T01:00:00Z",
        deposits=ValueWithInterval(100.0, 90.0, 110.0),
        withdrawals=ValueWithInterval(80.0, 70.0, 90.0),
        net=ValueWithInterval(20.0, 0.0, 40.0),
    )
    meta = ModelMetadata(model_name="TestModel", model_version="1.0")
    resp = ForecastResponse(
        currency="INR",
        as_of="2026-10-18T00:00:00Z",
        forecast_origin="2026-10-18T00:00:00Z",
        horizon_hours=1,
        confidence_level=0.95,
        model_metadata=meta,
        predictions=[step],
        liquidity_risk=[LiquidityRiskHorizon(6, 50.0, 100.0)],
    )

    data = resp.to_dict()
    assert data["currency"] == "INR"
    assert len(data["predictions"]) == 1
    assert data["predictions"][0]["deposits"]["mean"] == 100.0
    assert data["liquidity_risk"][0]["horizon_hours"] == 6
