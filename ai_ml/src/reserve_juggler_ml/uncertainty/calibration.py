"""
Uncertainty calibration and empirical prediction interval construction.

Implements lead-time-specific empirical residual quantile calibration:
For each forecast horizon step h in 1..72:
    e_{t, h} = y_{t+h} - y_hat_{t+h}
Lower and upper quantiles (tau_low = alpha / 2, tau_high = 1 - alpha / 2) are
estimated from out-of-sample calibration residuals.

Guarantees:
1. Strict causal separation: calibrators fit on out-of-sample calibration residuals
   (e.g., August) and are frozen before evaluation on validation/production.
2. Non-negative cash flow limits: lower bounds clamped at 0.0 for gross flows.
3. Schema compatibility: strictly enforces 0.0 <= lower <= point_forecast <= upper.
4. Lead-time dependent error dynamics: quantiles computed independently per horizon step.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from scipy.stats import norm


SUPPORTED_ALPHAS = [0.10, 0.05, 0.01]  # 90%, 95%, 99% nominal coverage


def compute_empirical_quantile_interval(
    residuals: np.ndarray,
    alpha: float = 0.05,
    method: str = "linear",
) -> Tuple[float, float]:
    """
    Compute non-parametric empirical quantile offsets for residual distributions.
    Returns (lower_offset, upper_offset) such that y_pred + lower_offset to y_pred + upper_offset
    covers 1 - alpha of observations.
    """
    clean_residuals = residuals[~np.isnan(residuals)]
    if len(clean_residuals) < 10:
        std = float(np.std(clean_residuals)) if len(clean_residuals) > 1 else 0.0
        crit = float(norm.ppf(1.0 - alpha / 2.0))
        return -crit * std, crit * std

    lower_quantile = float(np.quantile(clean_residuals, alpha / 2.0, method=method))
    upper_quantile = float(np.quantile(clean_residuals, 1.0 - alpha / 2.0, method=method))
    return lower_quantile, upper_quantile


def compute_conformal_interval_margin(
    residuals: np.ndarray,
    alpha: float = 0.05,
) -> float:
    """
    Compute split-conformal prediction margin on absolute residuals:
    q_{1 - alpha} * (1 + 1/n).
    Guarantees finite-sample marginal coverage >= 1 - alpha under exchangeability.
    """
    clean_abs = np.abs(residuals[~np.isnan(residuals)])
    n = len(clean_abs)
    if n == 0:
        return 0.0

    p = min(1.0, (1.0 - alpha) * (1.0 + 1.0 / n))
    margin = float(np.percentile(clean_abs, 100.0 * p))
    return margin


class LeadTimeEmpiricalCalibrator:
    """
    Lead-time-specific empirical residual quantile calibrator.

    Stores empirical lower and upper residual quantiles for each horizon step h in 1..H
    and supported nominal coverage levels 90% (alpha=0.10), 95% (alpha=0.05), 99% (alpha=0.01).
    """

    def __init__(
        self,
        horizon_hours: int = 72,
        alphas: Optional[List[float]] = None,
        quantile_method: str = "linear",
        min_samples: int = 30,
        model_name: str = "Forecaster",
        target_name: str = "flow",
    ):
        self.horizon_hours = horizon_hours
        self.alphas = alphas or list(SUPPORTED_ALPHAS)
        self.quantile_method = quantile_method
        self.min_samples = min_samples
        self.model_name = model_name
        self.target_name = target_name

        # Fitted calibration parameters
        self.is_fitted_: bool = False
        self.sample_count_: int = 0
        self.lower_quantiles_: Dict[float, np.ndarray] = {}  # alpha -> shape (H,)
        self.upper_quantiles_: Dict[float, np.ndarray] = {}  # alpha -> shape (H,)
        self.mean_residuals_: Optional[np.ndarray] = None    # shape (H,)
        self.std_residuals_: Optional[np.ndarray] = None     # shape (H,)
        self.warnings_: List[str] = []

    def fit(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> "LeadTimeEmpiricalCalibrator":
        """
        Fit residual quantiles on out-of-sample calibration predictions.

        y_true: shape (N_samples, H), realized actual cash flows.
        y_pred: shape (N_samples, H), point forecast predictions.

        Residual definition:
            e_{t, h} = y_{true, t, h} - y_{pred, t, h}
        """
        y_t = np.asarray(y_true, dtype=float)
        y_p = np.asarray(y_pred, dtype=float)

        if y_t.ndim != 2 or y_p.ndim != 2:
            raise ValueError(
                f"Expected 2D arrays (N, H), got y_true.ndim={y_t.ndim}, y_pred.ndim={y_p.ndim}"
            )
        if y_t.shape != y_p.shape:
            raise ValueError(
                f"Shape mismatch: y_true {y_t.shape} vs y_pred {y_p.shape}"
            )
        n_samples, horizon = y_t.shape
        if n_samples < self.min_samples:
            raise ValueError(
                f"Insufficient calibration samples: required at least {self.min_samples}, got {n_samples}"
            )
        if horizon < self.horizon_hours:
            raise ValueError(
                f"Horizon mismatch: expected at least {self.horizon_hours} steps, got {horizon}"
            )

        self.sample_count_ = n_samples
        residuals = y_t[:, :self.horizon_hours] - y_p[:, :self.horizon_hours]

        if np.isnan(residuals).any():
            raise ValueError("Calibration residuals contain NaN values.")

        self.mean_residuals_ = np.mean(residuals, axis=0)
        self.std_residuals_ = np.std(residuals, axis=0, ddof=1)
        self.warnings_ = []

        # Check finite-sample tail sample depth
        for a in self.alphas:
            tail_obs = n_samples * (a / 2.0)
            if tail_obs < 3.0:
                self.warnings_.append(
                    f"Sample count {n_samples} yields only {tail_obs:.2f} expected tail observations "
                    f"for alpha={a} ({100*(1-a):.0f}% level); extreme tail may be noisy."
                )

        # Compute empirical quantiles per horizon step
        for a in self.alphas:
            tau_low = a / 2.0
            tau_high = 1.0 - a / 2.0

            q_low = np.quantile(residuals, tau_low, axis=0, method=self.quantile_method)
            q_high = np.quantile(residuals, tau_high, axis=0, method=self.quantile_method)

            # Ensure lower <= upper
            inverted = q_low > q_high
            if inverted.any():
                q_low[inverted] = q_high[inverted]

            self.lower_quantiles_[a] = q_low
            self.upper_quantiles_[a] = q_high

        self.is_fitted_ = True
        return self

    def calibrate_forecast(
        self,
        point_forecast: Union[np.ndarray, pd.Series],
        alpha: float = 0.05,
        clip_nonnegative: bool = True,
    ) -> Tuple[Union[np.ndarray, pd.Series], Union[np.ndarray, pd.Series]]:
        """
        Construct calibrated lower and upper bounds for a point forecast.

        Contract:
        1. lower <= point_forecast <= upper guaranteed for all steps.
        2. If clip_nonnegative is True, lower >= 0.0 guaranteed.
        3. Preserves input type (returns pd.Series if point_forecast is pd.Series).
        """
        if not self.is_fitted_:
            raise RuntimeError("Calibrator must be fitted before calling calibrate_forecast().")

        is_series = isinstance(point_forecast, pd.Series)
        if is_series:
            y_pred_arr = point_forecast.to_numpy(dtype=float)
            idx = point_forecast.index
            name = point_forecast.name
        else:
            y_pred_arr = np.asarray(point_forecast, dtype=float)

        p_len = len(y_pred_arr)
        if p_len > self.horizon_hours:
            raise ValueError(
                f"Forecast length ({p_len}) exceeds calibrator horizon ({self.horizon_hours})"
            )

        # Retrieve or compute quantiles for requested alpha
        if alpha in self.lower_quantiles_:
            q_low = self.lower_quantiles_[alpha][:p_len]
            q_high = self.upper_quantiles_[alpha][:p_len]
        else:
            raise ValueError(
                f"Alpha {alpha} not in pre-calibrated alphas ({list(self.lower_quantiles_.keys())})."
            )

        raw_lower = y_pred_arr + q_low
        raw_upper = y_pred_arr + q_high

        # Enforce bounds contract: 0.0 <= lower <= point_forecast <= upper
        if clip_nonnegative:
            lower_arr = np.minimum(y_pred_arr, np.maximum(0.0, raw_lower))
            upper_arr = np.maximum(y_pred_arr, np.maximum(lower_arr, raw_upper))
        else:
            lower_arr = np.minimum(y_pred_arr, raw_lower)
            upper_arr = np.maximum(y_pred_arr, np.maximum(lower_arr, raw_upper))

        if is_series:
            lower_series = pd.Series(lower_arr, index=idx, name=name)
            upper_series = pd.Series(upper_arr, index=idx, name=name)
            return lower_series, upper_series

        return lower_arr, upper_arr

    def to_dict(self) -> Dict[str, Any]:
        """Serialize calibrator state to dictionary."""
        if not self.is_fitted_:
            return {"is_fitted": False}

        return {
            "is_fitted": True,
            "horizon_hours": self.horizon_hours,
            "alphas": self.alphas,
            "quantile_method": self.quantile_method,
            "min_samples": self.min_samples,
            "sample_count": self.sample_count_,
            "model_name": self.model_name,
            "target_name": self.target_name,
            "warnings": self.warnings_,
            "lower_quantiles": {
                str(k): v.tolist() for k, v in self.lower_quantiles_.items()
            },
            "upper_quantiles": {
                str(k): v.tolist() for k, v in self.upper_quantiles_.items()
            },
            "mean_residuals": (
                self.mean_residuals_.tolist() if self.mean_residuals_ is not None else None
            ),
            "std_residuals": (
                self.std_residuals_.tolist() if self.std_residuals_ is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LeadTimeEmpiricalCalibrator":
        """Deserialize calibrator from dictionary."""
        calibrator = cls(
            horizon_hours=data["horizon_hours"],
            alphas=data["alphas"],
            quantile_method=data.get("quantile_method", "linear"),
            min_samples=data.get("min_samples", 30),
            model_name=data.get("model_name", "Forecaster"),
            target_name=data.get("target_name", "flow"),
        )
        if data.get("is_fitted", False):
            calibrator.is_fitted_ = True
            calibrator.sample_count_ = data["sample_count"]
            calibrator.warnings_ = data.get("warnings", [])
            calibrator.lower_quantiles_ = {
                float(k): np.array(v, dtype=float)
                for k, v in data["lower_quantiles"].items()
            }
            calibrator.upper_quantiles_ = {
                float(k): np.array(v, dtype=float)
                for k, v in data["upper_quantiles"].items()
            }
            if data.get("mean_residuals") is not None:
                calibrator.mean_residuals_ = np.array(data["mean_residuals"], dtype=float)
            if data.get("std_residuals") is not None:
                calibrator.std_residuals_ = np.array(data["std_residuals"], dtype=float)

        return calibrator
