"""Adapter to translate AI/ML predictions to backend State and contract schemas."""

from typing import Any, Dict, List, Tuple
import pandas as pd

from reserve_juggler_ml.data.schemas import (
    ForecastResponse,
    ForecastStep,
    ModelMetadata,
    ValueWithInterval,
)


def format_forecast_response(
    deposits_mean: pd.Series,
    deposits_lower: pd.Series,
    deposits_upper: pd.Series,
    withdrawals_mean: pd.Series,
    withdrawals_lower: pd.Series,
    withdrawals_upper: pd.Series,
    as_of: str,
    confidence_level: float = 0.95,
    model_name: str = "DeterministicBaseline",
    model_version: str = "0.1.0",
    fallback_used: bool = False,
    fallback_reason: str = None,
    latency_ms: float = 0.0,
    currency: str = "INR",
) -> ForecastResponse:
    """Format forecaster outputs into a canonical ForecastResponse."""
    steps: List[ForecastStep] = []
    for i, dt in enumerate(deposits_mean.index):
        ts_str = pd.to_datetime(dt).strftime("%Y-%m-%dT%H:%M:%SZ")

        dep_mean = max(0.0, float(deposits_mean.iloc[i]))
        dep_low = max(0.0, float(deposits_lower.iloc[i]))
        dep_high = max(0.0, float(deposits_upper.iloc[i]))

        wdr_mean = max(0.0, float(withdrawals_mean.iloc[i]))
        wdr_low = max(0.0, float(withdrawals_lower.iloc[i]))
        wdr_high = max(0.0, float(withdrawals_upper.iloc[i]))

        net_mean = dep_mean - wdr_mean
        net_low = dep_low - wdr_high
        net_high = dep_high - wdr_low

        step = ForecastStep(
            step=i + 1,
            timestamp=ts_str,
            deposits=ValueWithInterval(mean=dep_mean, lower=dep_low, upper=dep_high),
            withdrawals=ValueWithInterval(mean=wdr_mean, lower=wdr_low, upper=wdr_high),
            net=ValueWithInterval(mean=net_mean, lower=net_low, upper=net_high),
        )
        steps.append(step)

    metadata = ModelMetadata(
        model_name=model_name,
        model_version=model_version,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        training_cutoff=as_of,
        latency_ms=latency_ms,
    )

    return ForecastResponse(
        currency=currency,
        as_of=as_of,
        forecast_origin=as_of,
        horizon_hours=len(steps),
        confidence_level=confidence_level,
        model_metadata=metadata,
        predictions=steps,
    )


def adapt_to_backend_state(
    response: ForecastResponse,
    profile_withdrawals: List[float] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Convert a ForecastResponse into the legacy `forecast` (NetRow array)
    and `gross_forecast` objects required by `server.py` and `treasury.py`.
    """
    net_rows = []
    gross_rows = []

    for i, step in enumerate(response.predictions):
        profile_wdr = (
            profile_withdrawals[i]
            if profile_withdrawals and i < len(profile_withdrawals)
            else step.withdrawals.mean
        )

        net_rows.append(
            {
                "timestamp": step.timestamp,
                "mean": step.net.mean,
                "lower": step.net.lower,
                "upper": step.net.upper,
                "withdrawals": profile_wdr,
            }
        )

        gross_rows.append(
            {
                "timestamp": step.timestamp,
                "deposits": step.deposits.mean,
                "deposits_lower": step.deposits.lower,
                "deposits_upper": step.deposits.upper,
                "withdrawals": step.withdrawals.mean,
                "withdrawals_lower": step.withdrawals.lower,
                "withdrawals_upper": step.withdrawals.upper,
            }
        )

    gross_forecast_obj = {
        "model": f"{response.model_metadata.model_name} v{response.model_metadata.model_version}",
        "rows": gross_rows,
        "note": "Reconciled ML gross and net cash-flow predictions.",
    }

    return net_rows, gross_forecast_obj
