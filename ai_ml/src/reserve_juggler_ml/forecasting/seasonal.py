"""Seasonal-naïve benchmark and fallback forecaster."""

import numpy as np
import pandas as pd
from scipy.stats import norm
from typing import Any, Optional

from reserve_juggler_ml.forecasting.base import BaseForecaster, ForecastOutput


class SeasonalNaiveForecaster(BaseForecaster):
    """
    Seasonal-naïve forecaster using a 24-hour cycle.
    Serves as the primary operational fallback when complex models fail.
    """

    def __init__(self, season_length: int = 24, calibrator: Optional[Any] = None):
        self.season_length = season_length
        self.calibrator_ = calibrator
        self.history_: Optional[pd.Series] = None
        self.residual_scale_: float = 0.0
        self.last_timestamp_: Optional[pd.Timestamp] = None
        self.series_name_: str = "flow"

    def set_calibrator(self, calibrator: Any) -> "SeasonalNaiveForecaster":
        """Attach or update the empirical residual calibrator."""
        self.calibrator_ = calibrator
        return self

    def fit(self, series: pd.Series) -> "SeasonalNaiveForecaster":
        if len(series) < self.season_length:
            raise ValueError(
                f"Series length ({len(series)}) must be at least season length ({self.season_length})"
            )

        self.history_ = series.copy()
        self.series_name_ = str(series.name or "flow")
        self.last_timestamp_ = pd.to_datetime(series.index[-1])

        vals = series.to_numpy(dtype=float)
        errors = vals[self.season_length:] - vals[:-self.season_length]
        self.residual_scale_ = float(np.std(errors, ddof=1)) if len(errors) > 1 else 0.0
        return self

    def predict(
        self,
        periods: int = 72,
        alpha: float = 0.05,
        frequency: str = "h",
    ) -> ForecastOutput:
        if self.history_ is None or self.last_timestamp_ is None:
            raise RuntimeError("Model must be fitted before predict() is called.")

        future_index = pd.date_range(
            start=self.last_timestamp_ + pd.DateOffset(hours=1),
            periods=periods,
            freq=frequency,
        )

        last_cycle = self.history_.iloc[-self.season_length:].to_numpy(dtype=float)
        repeats = int(np.ceil(periods / self.season_length))
        tiled = np.tile(last_cycle, repeats)[:periods]
        tiled = np.maximum(tiled, 0.0)

        mean_series = pd.Series(tiled, index=future_index, name=self.series_name_)

        if self.calibrator_ is not None and getattr(self.calibrator_, "is_fitted_", False):
            lower_series, upper_series = self.calibrator_.calibrate_forecast(
                point_forecast=mean_series,
                alpha=alpha,
                clip_nonnegative=True,
            )
            is_calibrated = True
            cal_method = "lead_time_empirical_quantiles"
        else:
            crit = float(norm.ppf(1 - alpha / 2))
            half_width = crit * self.residual_scale_
            lower_vals = np.minimum(tiled, np.maximum(tiled - half_width, 0.0))
            upper_vals = np.maximum(tiled, tiled + half_width)
            lower_series = pd.Series(lower_vals, index=future_index, name=self.series_name_)
            upper_series = pd.Series(upper_vals, index=future_index, name=self.series_name_)
            is_calibrated = False
            cal_method = "in_sample_gaussian_heuristic"

        return ForecastOutput(
            mean=mean_series,
            lower=lower_series,
            upper=upper_series,
            model_name=f"Seasonal Naive ({self.season_length}h)",
            converged=True,
            metadata={
                "residual_scale": round(self.residual_scale_, 2),
                "season_length": self.season_length,
                "confidence_level": round(1.0 - alpha, 3),
                "calibrated": is_calibrated,
                "uncalibrated_heuristic": not is_calibrated,
                "calibration_method": cal_method,
            },
        )
