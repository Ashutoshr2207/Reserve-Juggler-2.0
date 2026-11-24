"""Data schemas and transfer contracts for Reserve Juggler ML."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class HistoryObservation:
    timestamp: str
    deposits: float
    withdrawals: float

    def __post_init__(self):
        if self.deposits < 0:
            raise ValueError(f"Deposits must be non-negative, got {self.deposits}")
        if self.withdrawals < 0:
            raise ValueError(
                f"Withdrawals must be non-negative, got {self.withdrawals}"
            )


@dataclass(frozen=True)
class ValueWithInterval:
    mean: float
    lower: float
    upper: float

    def __post_init__(self):
        if self.lower > self.upper:
            raise ValueError(
                f"Lower bound ({self.lower}) cannot exceed upper bound ({self.upper})"
            )


@dataclass(frozen=True)
class ForecastStep:
    step: int
    timestamp: str
    deposits: ValueWithInterval
    withdrawals: ValueWithInterval
    net: ValueWithInterval


@dataclass(frozen=True)
class LiquidityRiskHorizon:
    horizon_hours: int
    max_cumulative_deficit_q95: float
    max_cumulative_deficit_q99: float


@dataclass(frozen=True)
class ModelMetadata:
    model_name: str
    model_version: str
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    training_cutoff: Optional[str] = None
    latency_ms: float = 0.0


@dataclass
class ForecastResponse:
    currency: str
    as_of: str
    forecast_origin: str
    horizon_hours: int
    confidence_level: float
    model_metadata: ModelMetadata
    predictions: List[ForecastStep]
    liquidity_risk: List[LiquidityRiskHorizon] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    contract_version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
