"""XGBoost direct multi-horizon forecaster for hourly liquidity flows."""

import time
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from scipy.stats import norm
import xgboost as xgb

from reserve_juggler_ml.features.causal import (
    CAUSAL_FEATURE_NAMES,
    extract_causal_feature_vector,
)
from reserve_juggler_ml.forecasting.base import BaseForecaster, ForecastOutput


class XGBoostForecaster(BaseForecaster):
    """
    Direct multi-horizon XGBoost forecaster.

    Generates 72-hour separate forecasts for gross deposits and withdrawals using
    XGBoost's multi-output histogram-based gradient boosted trees. Strictly uses
    causal features from completed observations prior to each forecast origin.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 5,
        learning_rate: float = 0.08,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        random_state: int = 42,
        n_jobs: int = -1,
        tree_method: str = "hist",
        min_history_hours: int = 168,
        horizon_hours: int = 72,
        calibrator: Optional[Any] = None,
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.tree_method = tree_method
        self.min_history_hours = min_history_hours
        self.horizon_hours = horizon_hours
        self.calibrator_ = calibrator

        # Model state
        self.model_: Optional[xgb.XGBRegressor] = None
        self.is_fitted_: bool = False
        self.history_: Optional[pd.Series] = None
        self.last_timestamp_: Optional[pd.Timestamp] = None
        self.series_name_: str = "flow"
        self.feature_names_: List[str] = list(CAUSAL_FEATURE_NAMES)
        self.last_inference_ms_: float = 0.0
        self.residual_std_: float = 0.0

    def fit_supervised(
        self,
        X: np.ndarray,
        Y: np.ndarray,
        residual_std: Optional[float] = None,
    ) -> "XGBoostForecaster":
        """
        Fit the underlying multi-output XGBoost regressor on supervised (X, Y) matrices.

        X: shape (n_samples, n_features), features strictly prior to origin.
        Y: shape (n_samples, horizon_hours), target flows over the horizon.
        """
        if len(X) == 0 or len(Y) == 0:
            raise ValueError("Training matrices X and Y cannot be empty.")
        if len(X) != len(Y):
            raise ValueError(f"Mismatched sample counts: X has {len(X)}, Y has {len(Y)}")
        if np.isnan(X).any() or np.isnan(Y).any():
            raise ValueError("Training matrices contain NaN values.")

        self.model_ = xgb.XGBRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            subsample=self.subsample,
            colsample_bytree=self.colsample_bytree,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
            tree_method=self.tree_method,
        )
        self.model_.fit(X, Y)
        self.is_fitted_ = True

        # Compute empirical residual dispersion on training set for heuristic intervals
        if residual_std is not None:
            self.residual_std_ = float(residual_std)
        else:
            in_sample_preds = self.model_.predict(X)
            errors = Y - in_sample_preds
            self.residual_std_ = float(np.std(errors, ddof=1)) if len(errors) > 1 else 0.0

        return self

    def fit(self, series: pd.Series) -> "XGBoostForecaster":
        """
        Fit or attach historical context to the forecaster.

        - If the model is already trained (is_fitted_ is True), validates and records
          series as the causal historical context for upcoming predict() calls.
        - If not yet trained, extracts supervised (X, Y) pairs from series and fits the model.
        """
        if not isinstance(series, pd.Series):
            raise TypeError(f"Expected pd.Series, got {type(series).__name__}")
        if len(series) < self.min_history_hours:
            raise ValueError(
                f"Insufficient history: minimum {self.min_history_hours} hours required, got {len(series)}"
            )
        if series.isnull().any():
            raise ValueError("Input series contains NaN values.")

        self.series_name_ = str(series.name or "flow")
        self.history_ = series.copy()
        self.last_timestamp_ = pd.to_datetime(series.index[-1])

        if not self.is_fitted_:
            # Build rolling supervised samples from series
            vals = series.to_numpy(dtype=float)
            n_total = len(series)
            n_samples = n_total - self.min_history_hours - self.horizon_hours + 1
            if n_samples <= 0:
                raise ValueError(
                    f"Series of length {n_total} is too short to train multi-horizon model "
                    f"requiring {self.min_history_hours} history and {self.horizon_hours} target steps."
                )

            X_list = []
            Y_list = []
            ts_idx = pd.to_datetime(series.index)
            for idx in range(self.min_history_hours, n_total - self.horizon_hours + 1):
                hist_slice = series.iloc[:idx]
                origin_ts = ts_idx[idx]
                feat = extract_causal_feature_vector(hist_slice, origin_ts)
                targets = vals[idx : idx + self.horizon_hours]
                X_list.append(feat)
                Y_list.append(targets)

            self.fit_supervised(np.array(X_list, dtype=float), np.array(Y_list, dtype=float))

        return self

    def set_context(self, history_series: pd.Series) -> "XGBoostForecaster":
        """Set or update the causal historical context without retraining."""
        return self.fit(history_series)

    def set_calibrator(self, calibrator: Any) -> "XGBoostForecaster":
        """Attach or update the empirical residual calibrator."""
        self.calibrator_ = calibrator
        return self

    def predict(
        self,
        periods: int = 72,
        alpha: float = 0.05,
        frequency: str = "h",
    ) -> ForecastOutput:
        """
        Generate 72-hour direct multi-step forecast using causal feature vector at origin.

        Output Contract:
        - Mean forecasts guaranteed non-negative.
        - Strictly causal features from history_ up to origin.
        - Tracks inference latency in milliseconds.
        - Calibrated prediction intervals when calibrator_ is attached.
        - Fallback to in-sample heuristic intervals when uncalibrated.
        - Bounds contract: 0.0 <= lower <= mean <= upper strictly guaranteed.
        """
        if not self.is_fitted_ or self.model_ is None:
            raise RuntimeError("Model must be fitted before predict() is called.")
        if self.history_ is None or self.last_timestamp_ is None:
            raise RuntimeError("Historical context not set. Call fit() or set_context() first.")
        if periods <= 0:
            raise ValueError(f"periods must be positive, got {periods}")
        if periods > self.horizon_hours:
            raise ValueError(
                f"Requested periods ({periods}) exceeds supported horizon ({self.horizon_hours})"
            )

        t_start = time.perf_counter()

        # Origin timestamp t is 1 hour after the last completed observation
        origin_timestamp = self.last_timestamp_ + pd.DateOffset(hours=1)
        future_index = pd.date_range(
            start=origin_timestamp,
            periods=periods,
            freq=frequency,
        )

        # Extract 22-dimensional causal feature vector at origin t
        X_origin = extract_causal_feature_vector(self.history_, origin_timestamp).reshape(1, -1)

        # Multi-output prediction
        raw_pred = self.model_.predict(X_origin)[0][:periods]

        # Non-negative cash-flow floor
        mean_vals = np.maximum(raw_pred, 0.0)
        mean_series = pd.Series(mean_vals, index=future_index, name=self.series_name_)

        t_elapsed_ms = (time.perf_counter() - t_start) * 1000.0
        self.last_inference_ms_ = t_elapsed_ms

        if self.calibrator_ is not None and getattr(self.calibrator_, "is_fitted_", False):
            lower_series, upper_series = self.calibrator_.calibrate_forecast(
                point_forecast=mean_series,
                alpha=alpha,
                clip_nonnegative=True,
            )
            is_calibrated = True
            cal_method = "lead_time_empirical_quantiles"
        else:
            # Fallback to in-sample residual dispersion heuristic
            crit = float(norm.ppf(1.0 - alpha / 2.0))
            half_width = crit * self.residual_std_
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
            model_name="XGBoost",
            converged=True,
            metadata={
                "inference_ms": round(t_elapsed_ms, 3),
                "n_estimators": self.n_estimators,
                "max_depth": self.max_depth,
                "learning_rate": self.learning_rate,
                "confidence_level": round(1.0 - alpha, 3),
                "calibrated": is_calibrated,
                "uncalibrated_heuristic": not is_calibrated,
                "calibration_method": cal_method,
            },
        )
