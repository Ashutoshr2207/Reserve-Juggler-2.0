"""Adapter to translate AI/ML predictions to backend State and contract schemas."""

from typing import Any, Dict, List, Tuple
import pandas as pd

from reserve_juggler_ml.integration.contract import (
    HORIZON,
    IntegrationError,
    confidence,
    currency_code,
    number,
    timestamp,
    utc_string,
)
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
    currency: str = None,
    training_cutoff: str = None,
) -> ForecastResponse:
    """Validate gross predictions, then format a shadow-only response.

    Marginal-extrema net bounds are an uncalibrated envelope, never a net
    confidence interval or a reserve instruction. Invalid output is rejected,
    not clipped, imputed or relabeled. Currency must always be explicit.
    """
    currency_code(currency)
    confidence(confidence_level)
    origin = timestamp(as_of)
    expected = pd.date_range(origin + pd.DateOffset(hours=1), periods=HORIZON, freq="h")
    for series in (
        deposits_mean,
        deposits_lower,
        deposits_upper,
        withdrawals_mean,
        withdrawals_lower,
        withdrawals_upper,
    ):
        if not isinstance(series, pd.Series) or len(series) != HORIZON:
            raise IntegrationError(
                "INVALID_PREDICTION", "Exactly 72 values per output required."
            )
        if not isinstance(series.index, pd.DatetimeIndex) or series.index.tz is None:
            raise IntegrationError(
                "INVALID_TIMESTAMP", "Timezone-aware prediction index required."
            )
        if not series.index.tz_convert("UTC").equals(expected):
            raise IntegrationError(
                "STALE_CONTEXT", "Predictions must align at as_of +1…+72h."
            )
        for value in series:
            number(value)
    if origin.second or origin.microsecond or origin.nanosecond:
        raise IntegrationError("INVALID_TIMESTAMP", "Zero seconds required at origin.")
    if training_cutoff is not None and timestamp(training_cutoff) > origin:
        raise IntegrationError(
            "FUTURE_TRAINING_DATA", "Training cutoff exceeds origin."
        )
    steps: List[ForecastStep] = []
    for i, dt in enumerate(deposits_mean.index):
        ts_str = utc_string(dt)

        dep_mean = float(deposits_mean.iloc[i])
        dep_low = float(deposits_lower.iloc[i])
        dep_high = float(deposits_upper.iloc[i])

        wdr_mean = float(withdrawals_mean.iloc[i])
        wdr_low = float(withdrawals_lower.iloc[i])
        wdr_high = float(withdrawals_upper.iloc[i])
        if not (dep_low <= dep_mean <= dep_high and wdr_low <= wdr_mean <= wdr_high):
            raise IntegrationError(
                "INVALID_PREDICTION", "Bounds must contain gross means."
            )

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
        training_cutoff=utc_string(training_cutoff) if training_cutoff else None,
        latency_ms=latency_ms,
    )

    return ForecastResponse(
        currency=currency,
        as_of=utc_string(as_of),
        forecast_origin=utc_string(as_of),
        horizon_hours=len(steps),
        confidence_level=confidence_level,
        model_metadata=metadata,
        predictions=steps,
        warnings=["MARGINAL_EXTREMA_ENVELOPE_UNCALIBRATED; SHADOW_ONLY"],
    )


def adapt_to_backend_state(
    response: ForecastResponse,
    profile_withdrawals: List[float] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Convert a validated ForecastResponse into legacy-shaped shadow rows.

    This converter does not install the rows into treasury state or planning.
    """
    # Revalidate even dataclass responses: they can be constructed by callers.
    if (
        not isinstance(response, ForecastResponse)
        or response.contract_version != "1.0.0"
    ):
        raise IntegrationError(
            "UNSUPPORTED_CONTRACT", "Unsupported prediction response."
        )
    if (
        response.horizon_hours != HORIZON
        or len(response.predictions) != HORIZON
        or timestamp(response.forecast_origin) != timestamp(response.as_of)
        or response.liquidity_risk
    ):
        raise IntegrationError(
            "INVALID_PREDICTION", "Complete aligned cashflow response required."
        )
    index = pd.DatetimeIndex([timestamp(s.timestamp) for s in response.predictions])
    series = []
    for target in ("deposits", "withdrawals"):
        for field in ("mean", "lower", "upper"):
            series.append(pd.Series([
                getattr(getattr(s, target), field) for s in response.predictions
            ], index=index))
    validated = format_forecast_response(
        *series, as_of=response.as_of, currency=response.currency,
        confidence_level=response.confidence_level,
        training_cutoff=response.model_metadata.training_cutoff,
    )
    for actual, checked in zip(response.predictions, validated.predictions):
        if type(actual.step) is not int or actual.step != checked.step or any(
            number(getattr(actual.net, field), nonnegative=False)
            != getattr(checked.net, field)
            for field in ("mean", "lower", "upper")
        ):
            raise IntegrationError(
                "INVALID_PREDICTION", "Inconsistent net flow or step index."
            )
    if profile_withdrawals is not None:
        if len(profile_withdrawals) != HORIZON:
            raise IntegrationError(
                "INVALID_PREDICTION", "Complete withdrawal profile required."
            )
        for value in profile_withdrawals:
            number(value)
    net_rows = []
    gross_rows = []

    for i, step in enumerate(response.predictions):
        profile_wdr = (
            profile_withdrawals[i]
            if profile_withdrawals is not None
            else step.withdrawals.mean
        )

        net_rows.append(
            {
                "timestamp": utc_string(step.timestamp),
                "mean": step.net.mean,
                "lower": step.net.lower,
                "upper": step.net.upper,
                "withdrawals": profile_wdr,
            }
        )

        gross_rows.append(
            {
                "timestamp": utc_string(step.timestamp),
                "deposits": step.deposits.mean,
                "deposits_lower": step.deposits.lower,
                "deposits_upper": step.deposits.upper,
                "withdrawals": step.withdrawals.mean,
                "withdrawals_lower": step.withdrawals.lower,
                "withdrawals_upper": step.withdrawals.upper,
            }
        )

    gross_forecast_obj = {
        "model": (
            f"{response.model_metadata.model_name} "
            f"v{response.model_metadata.model_version}"
        ),
        "rows": gross_rows,
        "note": (
            "Shadow only. Net bounds are an uncalibrated marginal-extrema envelope."
        ),
    }

    return net_rows, gross_forecast_obj
