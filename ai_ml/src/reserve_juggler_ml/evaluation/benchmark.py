"""Benchmark runner for multi-horizon chronological evaluation."""

from dataclasses import asdict, dataclass
import time
from typing import Any, Callable, Dict, List, Optional
import numpy as np
import pandas as pd

from reserve_juggler_ml.evaluation.metrics import (
    cumulative_total_mae,
    cumulative_total_rmse,
    in_sample_seasonal_scale,
    lead_time_mae,
    lead_time_rmse,
    mean_hourly_mae,
    mean_hourly_rmse,
)
from reserve_juggler_ml.evaluation.splits import ChronologicalOrigin
from reserve_juggler_ml.forecasting.base import BaseForecaster


CUMULATIVE_WINDOWS = [1, 6, 24, 48, 72]
LEAD_TIME_HORIZONS = [1, 6, 24, 48, 72]


@dataclass
class LeadTimeMetric:
    """Error metrics for an exact forecast lead time step h."""
    lead_time_hours: int  # Exact step h (1, 6, 24, 48, 72)
    mae: float            # Lead-time-specific MAE ($ / hr)
    rmse: float           # Lead-time-specific RMSE ($ / hr)
    sample_count: int     # Total origins evaluated


@dataclass
class WindowMetric:
    """
    Error metrics across a cumulative forecast horizon window 1..W.
    Explicitly distinguishes average hourly error rate from cumulative total flow error.
    """
    window_hours: int             # Horizon window W (1, 6, 24, 48, 72)
    mean_hourly_mae: float        # Mean hourly MAE ($ / hr) averaged over lead times 1..W
    mean_hourly_rmse: float       # Mean hourly RMSE ($ / hr) averaged over lead times 1..W
    cumulative_total_mae: float   # Cumulative-total-flow MAE ($ total over W hours): |sum(y) - sum(y_hat)|
    cumulative_total_rmse: float  # Cumulative-total-flow RMSE ($ total over W hours)
    mase: float                   # MASE = mean_hourly_mae / mase_denominator_scale (dimensionless)
    mase_denominator_scale: float # In-sample seasonal naive MAE scale Q ($ / hr)

    @property
    def mae(self) -> float:
        """Backward-compatible alias for mean_hourly_mae ($ / hr)."""
        return self.mean_hourly_mae

    @property
    def rmse(self) -> float:
        """Backward-compatible alias for mean_hourly_rmse ($ / hr)."""
        return self.mean_hourly_rmse


@dataclass
class ModelBenchmarkResult:
    """Complete benchmark results for a single model and target."""
    model_name: str
    target_name: str
    currency: str
    origin_count: int
    total_predictions: int
    partition_name: str
    lead_time_metrics: Dict[int, LeadTimeMetric]  # Keyed by lead_time_hours (1, 6, 24, 48, 72)
    window_metrics: Dict[int, WindowMetric]        # Keyed by window_hours (1, 6, 24, 48, 72)
    elapsed_seconds: float
    model_params: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "target_name": self.target_name,
            "currency": self.currency,
            "origin_count": self.origin_count,
            "total_predictions": self.total_predictions,
            "partition_name": self.partition_name,
            "lead_time_metrics": {
                str(k): asdict(v) for k, v in self.lead_time_metrics.items()
            },
            "window_metrics": {
                str(k): asdict(v) for k, v in self.window_metrics.items()
            },
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "model_params": self.model_params,
        }


def evaluate_model_on_origins(
    df: pd.DataFrame,
    origins: List[ChronologicalOrigin],
    model_factory: Callable[[], BaseForecaster],
    target_col: str,
    currency: str = "USD",
    seasonality_for_mase: int = 24,
    windows: List[int] = CUMULATIVE_WINDOWS,
    lead_times: List[int] = LEAD_TIME_HORIZONS,
) -> ModelBenchmarkResult:
    """
    Evaluate a forecaster model across pre-computed chronological origins.

    Computes:
    1. Lead-time-specific MAE and RMSE at selected horizons (1, 6, 24, 48, 72).
    2. Mean hourly MAE and RMSE across forecast lead times 1-6, 1-24, 1-48, 1-72.
    3. Cumulative-total-flow forecast error for each window (summing hourly flows before comparison).
    4. MASE scaled against in-sample 24-hour seasonal naive difference.

    Strictly prevents lookahead by slicing history up to origin_idx + 1.
    """
    if not origins:
        raise ValueError("Cannot evaluate model with empty origins list.")

    start_time = time.time()
    model_name = "Unknown"
    model_params = {}

    horizon = origins[0].horizon_hours
    n_origins = len(origins)

    # Pre-index datetime series to avoid repeated timestamp parsing
    ts_index = pd.to_datetime(df["timestamp"])
    full_target_series = pd.Series(df[target_col].to_numpy(dtype=float), index=ts_index)
    y_raw = df[target_col].to_numpy(dtype=float)

    all_y_true = np.zeros((n_origins, horizon), dtype=float)
    all_y_pred = np.zeros((n_origins, horizon), dtype=float)
    all_scales = np.zeros(n_origins, dtype=float)

    for i, origin in enumerate(origins):
        # 1. Extract permitted history strictly up to origin
        history_series = full_target_series.iloc[origin.history_start_idx:origin.history_end_idx]

        # 2. Extract true future targets
        y_true = y_raw[origin.target_start_idx:origin.target_end_idx]
        all_y_true[i, :len(y_true)] = y_true

        # 3. Compute in-sample seasonal naive scale
        scale = in_sample_seasonal_scale(history_series.to_numpy(dtype=float), seasonality=seasonality_for_mase)
        all_scales[i] = scale

        # 4. Instantiate and fit forecaster on history
        model = model_factory()
        model.fit(history_series)

        if i == 0:
            model_name = getattr(model, "model_name_", type(model).__name__)
            if hasattr(model, "lookback_hours"):
                model_params["lookback_hours"] = model.lookback_hours
            if hasattr(model, "season_length"):
                model_params["season_length"] = model.season_length
            if hasattr(model, "n_estimators"):
                model_params["n_estimators"] = model.n_estimators
            if hasattr(model, "max_depth"):
                model_params["max_depth"] = model.max_depth
            if hasattr(model, "learning_rate"):
                model_params["learning_rate"] = model.learning_rate
            if hasattr(model, "random_state"):
                model_params["random_state"] = model.random_state

        # 5. Generate 72-hour forecast
        pred_output = model.predict(periods=origin.horizon_hours, frequency="h")
        y_pred = pred_output.mean.to_numpy(dtype=float)
        all_y_pred[i, :len(y_pred)] = y_pred

        if i == 0:
            model_name = pred_output.model_name

    elapsed = time.time() - start_time
    total_preds = n_origins * horizon

    # 6. Calculate lead-time-specific metrics
    lead_time_results: Dict[int, LeadTimeMetric] = {}
    for h in lead_times:
        if h <= horizon:
            lt_mae = lead_time_mae(all_y_true, all_y_pred, lead_time_hour=h)
            lt_rmse = lead_time_rmse(all_y_true, all_y_pred, lead_time_hour=h)
            lead_time_results[h] = LeadTimeMetric(
                lead_time_hours=h,
                mae=lt_mae,
                rmse=lt_rmse,
                sample_count=n_origins,
            )

    # 7. Calculate cumulative window metrics (mean hourly vs cumulative total)
    window_results: Dict[int, WindowMetric] = {}
    mean_scale = float(np.mean(all_scales)) if np.mean(all_scales) > 1e-9 else 1.0

    for w in windows:
        if w <= horizon:
            m_h_mae = mean_hourly_mae(all_y_true, all_y_pred, window_hours=w)
            m_h_rmse = mean_hourly_rmse(all_y_true, all_y_pred, window_hours=w)
            c_t_mae = cumulative_total_mae(all_y_true, all_y_pred, window_hours=w)
            c_t_rmse = cumulative_total_rmse(all_y_true, all_y_pred, window_hours=w)
            mase = float(m_h_mae / mean_scale)

            window_results[w] = WindowMetric(
                window_hours=w,
                mean_hourly_mae=m_h_mae,
                mean_hourly_rmse=m_h_rmse,
                cumulative_total_mae=c_t_mae,
                cumulative_total_rmse=c_t_rmse,
                mase=mase,
                mase_denominator_scale=mean_scale,
            )

    return ModelBenchmarkResult(
        model_name=model_name,
        target_name=target_col,
        currency=currency,
        origin_count=n_origins,
        total_predictions=total_preds,
        partition_name=origins[0].partition_name,
        lead_time_metrics=lead_time_results,
        window_metrics=window_results,
        elapsed_seconds=elapsed,
        model_params=model_params,
    )
