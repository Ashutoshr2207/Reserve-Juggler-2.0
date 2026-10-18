"""Abstract base class and return structures for forecasters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd


@dataclass
class ForecastOutput:
    mean: pd.Series
    lower: pd.Series
    upper: pd.Series
    model_name: str
    converged: bool = True
    metadata: Optional[Dict] = None


class BaseForecaster(ABC):
    """Abstract interface for all Reserve Juggler forecasting models."""

    @abstractmethod
    def fit(self, series: pd.Series) -> "BaseForecaster":
        """Fit model on historical series."""
        pass

    @abstractmethod
    def predict(
        self,
        periods: int = 72,
        alpha: float = 0.05,
        frequency: str = "h",
    ) -> ForecastOutput:
        """Generate multi-step forecasts with prediction intervals."""
        pass
