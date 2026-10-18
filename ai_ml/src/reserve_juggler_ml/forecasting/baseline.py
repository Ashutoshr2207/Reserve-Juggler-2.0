"""Deterministic 14-day hourly baseline forecaster."""

import numpy as np
import pandas as pd
from scipy.stats import norm
from typing import Any, Optional

from reserve_juggler_ml.forecasting.base import BaseForecaster, ForecastOutput


class DeterministicBaseline(BaseForecaster):
    """
    Deterministic 14-day hourly baseline model.
    Profiles the 24-hour diurnal cycle across the trailing 14 days (336 hours)
    and projects the average hourly profile across the 72-hour horizon.
    """

    def __init__(self, lookback_hours: int = 336, calibrator: Optional[Any] = None):
        self.lookback_hours = lookback_hours
        self.calibrator_ = calibrator
        self.hourly_profile_: Optional[pd.Series] = None
        self.residual_std_: float = 0.0
        self.last_timestamp_: Optional[pd.Timestamp] = None
        self.series_name_: str = "flow"

    def set_calibrator(self, calibrator: Any) -> "DeterministicBaseline":
        """Attach or update the empirical residual calibrator."""
        self.calibrator_ = calibrator
        return self

    def fit(self, series: pd.Series) -> "DeterministicBaseline":
        if len(series) < 24:
            raise ValueError(f"Series must have at least 24 hours, got {len(series)}")

        self.series_name_ = str(series.name or "flow")
        tail = series.tail(self.lookback_hours)
        dt_index = pd.to_datetime(tail.index)

        # Calculate hour-of-day mean profile
        hours = dt_index.hour
        self.hourly_profile_ = tail.groupby(hours).mean()

        # Compute empirical residuals against the profile
        profile_values = np.array([self.hourly_profile_[h] for h in hours])
        residuals = tail.to_numpy(dtype=float) - profile_values
        self.residual_std_ = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0
        self.last_timestamp_ = pd.to_datetime(series.index[-1])
        return self

    def predict(
        self,
        periods: int = 72,
        alpha: float = 0.05,
        frequency: str = "h",
    ) -> ForecastOutput:
        if self.hourly_profile_ is None or self.last_timestamp_ is None:
            raise RuntimeError("Model must be fitted before predict() is called.")

        future_index = pd.date_range(
            start=self.last_timestamp_ + pd.DateOffset(hours=1),
            periods=periods,
            freq=frequency,
        )

        mean_vals = np.array([self.hourly_profile_[dt.hour] for dt in future_index], dtype=float)
        mean_vals = np.maximum(mean_vals, 0.0)
        mean_series = pd.Series(mean_vals, index=future_index, name=self.series_name_)

        if self.calibrator_ is not None and getattr(self.calibrator_, "is_fitted_", False):
            lower_series, upper_series = self.calibrator_.calibrate_forecast(
                point_forecast=mean_series,
                alpha=alpha,
                clip_nonnegative=True,
            )
            is_calibrated = True
            cal_method = "lead_time_empirical_quantiles"
        else:
            critical_val = float(norm.ppf(1 - alpha / 2))
            half_width = critical_val * self.residual_std_
            lower_vals = np.minimum(mean_vals, np.maximum(mean_vals - half_width, 0.0))
            upper_vals = np.maximum(mean_vals, mean_vals + half_width)
            lower_series = pd.Series(lower_vals, index=future_index, name=self.series_name_)
            upper_series = pd.Series(upper_vals, index=future_index, name=self.series_name_)
            is_calibrated = False
            cal_method = "in_sample_gaussian_heuristic"

        return ForecastOutput(
            mean=mean_series,
            lower=lower_series,
            upper=upper_series,
            model_name="Deterministic 14-Day Baseline",
            converged=True,
            metadata={
                "residual_std": round(self.residual_std_, 2),
                "confidence_level": round(1.0 - alpha, 3),
                "calibrated": is_calibrated,
                "uncalibrated_heuristic": not is_calibrated,
                "calibration_method": cal_method,
            },
        )
