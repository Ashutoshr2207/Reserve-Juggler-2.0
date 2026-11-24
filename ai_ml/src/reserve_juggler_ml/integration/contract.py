"""Validated shadow boundary; never grants authority to the treasury engine."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from numbers import Real

import pandas as pd

HORIZON = 72
UNIT = "major_currency_unit"
SEMANTICS = "completed_hour_bucket_end"
FLOW_SCOPE = "background_gross_only"
CONFIDENCES = (0.90, 0.95, 0.99)


class IntegrationError(ValueError):
    def __init__(self, code, message, *, inference_ran=False):
        super().__init__(message)
        self.code = code
        self.inference_ran = inference_ran


def timestamp(value):
    """Compare instants in UTC, including IST grids with minute-30 UTC ends."""
    if not isinstance(value, (str, datetime, pd.Timestamp)):
        raise IntegrationError("INVALID_TIMESTAMP", "Explicit timezone required.")
    try:
        result = pd.Timestamp(value)
        if pd.isna(result) or result.tzinfo is None:
            raise ValueError
        return result.tz_convert("UTC")
    except (ValueError, TypeError, OverflowError) as exc:
        raise IntegrationError(
            "INVALID_TIMESTAMP", "Valid timestamp with explicit timezone required."
        ) from exc


def utc_string(value):
    return timestamp(value).isoformat().replace("+00:00", "Z")


def number(value, *, nonnegative=True):
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
        or abs(value) > 1e12
        or not math.isfinite(value)
        or (nonnegative and value < 0)
    ):
        raise IntegrationError(
            "INVALID_NUMBER", "Finite numeric major-unit amounts required."
        )
    return float(value)


def currency_code(value):
    if value not in ("INR", "USD"):
        raise IntegrationError(
            "UNSUPPORTED_CURRENCY", "Explicit supported currency INR or USD required."
        )
    return value


def confidence(value):
    if isinstance(value, bool) or value not in CONFIDENCES:
        raise IntegrationError(
            "UNSUPPORTED_CONFIDENCE", "Confidence must be 0.90, 0.95 or 0.99."
        )
    return float(value)


@dataclass(frozen=True)
class ShadowRequest:
    """All history is completed at as_of; prediction k ends at as_of + k hours."""

    currency: str
    as_of: str
    history: list
    confidence_level: float
    unit: str = UNIT
    timestamp_semantics: str = SEMANTICS
    flow_scope: str = FLOW_SCOPE
    horizon_hours: int = HORIZON
    frequency: str = "h"
    contract_version: str = "shadow-1.0"

    def validate(self):
        currency_code(self.currency)
        confidence(self.confidence_level)
        if (
            self.contract_version != "shadow-1.0"
            or self.unit != UNIT
            or self.timestamp_semantics != SEMANTICS
            or self.flow_scope != FLOW_SCOPE
            or type(self.horizon_hours) is not int
            or self.horizon_hours != HORIZON
            or self.frequency != "h"
        ):
            raise IntegrationError(
                "UNSUPPORTED_CONTRACT", "Unsupported request semantics."
            )
        if not isinstance(self.history, list) or not 168 <= len(self.history) <= 5000:
            raise IntegrationError(
                "INSUFFICIENT_HISTORY", "Supply 168–5,000 completed hourly records."
            )
        previous = None
        rows = []
        for row in self.history:
            if not isinstance(row, dict) or set(row) != {
                "timestamp",
                "deposits",
                "withdrawals",
            }:
                raise IntegrationError(
                    "INVALID_HISTORY", "Exact history schema required."
                )
            when = timestamp(row["timestamp"])
            if when.second or when.microsecond or when.nanosecond:
                raise IntegrationError("INVALID_TIMESTAMP", "Zero seconds required.")
            if previous is not None and when - previous != timedelta(hours=1):
                raise IntegrationError(
                    "INVALID_HISTORY", "Consecutive hourly history required."
                )
            rows.append(
                {
                    "timestamp": when,
                    "deposits": number(row["deposits"]),
                    "withdrawals": number(row["withdrawals"]),
                }
            )
            previous = when
        if previous != timestamp(self.as_of):
            raise IntegrationError(
                "STALE_CONTEXT", "History must end exactly at as_of."
            )
        return pd.DataFrame(rows).set_index("timestamp")


@dataclass(frozen=True)
class ModelSpec:
    """Required provenance supplied by a reviewed, already-loaded provider.

    Dataset/configuration IDs identify immutable research inputs; no paths,
    weights or datasets are carried in a request or returned to the frontend.
    trained_through includes the latest fitting AND calibration observations.
    """

    model_id: str
    version: str
    training_currency: str
    unit: str
    dataset_id: str
    dataset_sha256: str
    configuration_id: str
    trained_through: str
    interval_method: str
    timestamp_semantics: str
    feature_timezone: str
    min_history_hours: int = 168
    horizon_hours: int = HORIZON
    flow_scope: str = FLOW_SCOPE

    def validate_for(self, request):
        currency_code(self.training_currency)
        if self.training_currency != request.currency:
            raise IntegrationError(
                "CURRENCY_MISMATCH",
                "Input and training currencies differ; inference skipped.",
            )
        for field in (
            "model_id", "version", "dataset_id", "configuration_id", "interval_method"
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip() or len(value) > 128:
                raise IntegrationError(
                    "INVALID_MODEL_METADATA", "Complete model identity required."
                )
        if (
            not isinstance(self.dataset_sha256, str)
            or len(self.dataset_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.dataset_sha256)
        ):
            raise IntegrationError(
                "INVALID_MODEL_METADATA", "Dataset SHA-256 required."
            )
        if (
            self.unit != request.unit
            or self.timestamp_semantics != request.timestamp_semantics
            or self.flow_scope != request.flow_scope
            or self.feature_timezone != "UTC"
            or type(self.horizon_hours) is not int
            or self.horizon_hours != HORIZON
        ):
            raise IntegrationError(
                "UNSUPPORTED_CONTRACT", "Model semantics differ from request."
            )
        if (
            type(self.min_history_hours) is not int
            or not 168 <= self.min_history_hours <= 5000
        ):
            raise IntegrationError(
                "INVALID_MODEL_METADATA", "Invalid minimum history."
            )
        if len(request.history) < self.min_history_hours:
            raise IntegrationError(
                "INSUFFICIENT_HISTORY", "Model requires more completed history."
            )
        if timestamp(self.trained_through) > timestamp(request.as_of):
            raise IntegrationError(
                "FUTURE_TRAINING_DATA", "Fitting/calibration cutoff exceeds as_of."
            )
