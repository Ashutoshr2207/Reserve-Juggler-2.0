"""
Evaluation metrics for time-series forecasting, uncertainty intervals, and liquidity cash flows.

Distinguishes between:
1. Lead-time-specific error at exact forecast horizon h (USD/hr)
2. Mean hourly error rate across horizon window 1..W (USD/hr)
3. Cumulative-total-flow error for horizon window 1..W (USD total volume over W hours)
4. Mean Absolute Scaled Error (MASE) against in-sample seasonal naive scale
"""

from typing import Dict, Optional, Union
import numpy as np


def mean_absolute_error(
    y_true: Union[np.ndarray, list],
    y_pred: Union[np.ndarray, list],
) -> float:
    """Mean Absolute Error (MAE). Units: USD/hr or measurement units."""
    t = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(t - p)))


def root_mean_squared_error(
    y_true: Union[np.ndarray, list],
    y_pred: Union[np.ndarray, list],
) -> float:
    """Root Mean Squared Error (RMSE). Units: USD/hr or measurement units."""
    t = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean((t - p) ** 2)))


def lead_time_mae(
    y_trues: Union[np.ndarray, list],
    y_preds: Union[np.ndarray, list],
    lead_time_hour: int,
) -> float:
    """
    Lead-time-specific MAE evaluated at exact forecast step h (1-indexed).
    Formula: (1 / M) * sum_{m=1}^M |y_{m, h} - y_hat_{m, h}|
    Units: USD / hr.
    """
    t = np.asarray(y_trues, dtype=float)
    p = np.asarray(y_preds, dtype=float)
    idx = lead_time_hour - 1
    if t.ndim == 1:
        return float(np.abs(t[idx] - p[idx]))
    return float(np.mean(np.abs(t[:, idx] - p[:, idx])))


def lead_time_rmse(
    y_trues: Union[np.ndarray, list],
    y_preds: Union[np.ndarray, list],
    lead_time_hour: int,
) -> float:
    """
    Lead-time-specific RMSE evaluated at exact forecast step h (1-indexed).
    Formula: sqrt( (1 / M) * sum_{m=1}^M (y_{m, h} - y_hat_{m, h})^2 )
    Units: USD / hr.
    """
    t = np.asarray(y_trues, dtype=float)
    p = np.asarray(y_preds, dtype=float)
    idx = lead_time_hour - 1
    if t.ndim == 1:
        return float(np.abs(t[idx] - p[idx]))
    return float(np.sqrt(np.mean((t[:, idx] - p[:, idx]) ** 2)))


def mean_hourly_mae(
    y_trues: Union[np.ndarray, list],
    y_preds: Union[np.ndarray, list],
    window_hours: int,
) -> float:
    """
    Mean hourly MAE averaged across forecast lead times 1..W.
    Formula: (1 / (M * W)) * sum_{m=1}^M sum_{h=1}^W |y_{m, h} - y_hat_{m, h}|
    Units: USD / hr.
    """
    t = np.asarray(y_trues, dtype=float)
    p = np.asarray(y_preds, dtype=float)
    if t.ndim == 1:
        return float(np.mean(np.abs(t[:window_hours] - p[:window_hours])))
    return float(np.mean(np.abs(t[:, :window_hours] - p[:, :window_hours])))


def mean_hourly_rmse(
    y_trues: Union[np.ndarray, list],
    y_preds: Union[np.ndarray, list],
    window_hours: int,
) -> float:
    """
    Mean hourly RMSE across forecast lead times 1..W.
    Formula: sqrt( (1 / (M * W)) * sum_{m=1}^M sum_{h=1}^W (y_{m, h} - y_hat_{m, h})^2 )
    Units: USD / hr.
    """
    t = np.asarray(y_trues, dtype=float)
    p = np.asarray(y_preds, dtype=float)
    if t.ndim == 1:
        return float(np.sqrt(np.mean((t[:window_hours] - p[:window_hours]) ** 2)))
    return float(np.sqrt(np.mean((t[:, :window_hours] - p[:, :window_hours]) ** 2)))


def cumulative_total_mae(
    y_trues: Union[np.ndarray, list],
    y_preds: Union[np.ndarray, list],
    window_hours: int,
) -> float:
    """
    Cumulative-total-flow forecast MAE for horizon window W.
    Computes the actual sum of hourly flows before comparing predicted and observed totals.
    Formula: (1 / M) * sum_{m=1}^M | sum_{h=1}^W y_{m, h} - sum_{h=1}^W y_hat_{m, h} |
    Units: USD total cash flow volume over the W-hour window.
    """
    t = np.asarray(y_trues, dtype=float)
    p = np.asarray(y_preds, dtype=float)
    if t.ndim == 1:
        return float(np.abs(np.sum(t[:window_hours]) - np.sum(p[:window_hours])))
    sum_true = np.sum(t[:, :window_hours], axis=1)
    sum_pred = np.sum(p[:, :window_hours], axis=1)
    return float(np.mean(np.abs(sum_true - sum_pred)))


def cumulative_total_rmse(
    y_trues: Union[np.ndarray, list],
    y_preds: Union[np.ndarray, list],
    window_hours: int,
) -> float:
    """
    Cumulative-total-flow forecast RMSE for horizon window W.
    Computes the actual sum of hourly flows before comparing predicted and observed totals.
    Formula: sqrt( (1 / M) * sum_{m=1}^M ( sum_{h=1}^W y_{m, h} - sum_{h=1}^W y_hat_{m, h} )^2 )
    Units: USD total cash flow volume over the W-hour window.
    """
    t = np.asarray(y_trues, dtype=float)
    p = np.asarray(y_preds, dtype=float)
    if t.ndim == 1:
        return float(np.abs(np.sum(t[:window_hours]) - np.sum(p[:window_hours])))
    sum_true = np.sum(t[:, :window_hours], axis=1)
    sum_pred = np.sum(p[:, :window_hours], axis=1)
    return float(np.sqrt(np.mean((sum_true - sum_pred) ** 2)))


def in_sample_seasonal_scale(
    y_train: Union[np.ndarray, list],
    seasonality: int = 24,
) -> float:
    """
    Hyndman & Koehler (2006) in-sample seasonal naive MAE denominator scale:
    Q = (1 / (T - s)) * sum_{t=s+1}^T |y_t - y_{t-s}|
    where s is seasonality (default 24 hours for daily cycle).
    Units: USD / hr.
    """
    train = np.asarray(y_train, dtype=float)
    if len(train) <= seasonality:
        scale_diffs = (
            np.abs(train[1:] - train[:-1]) if len(train) > 1 else np.array([1.0])
        )
    else:
        scale_diffs = np.abs(train[seasonality:] - train[:-seasonality])

    return float(np.mean(scale_diffs))


def mean_absolute_scaled_error(
    y_true: Union[np.ndarray, list],
    y_pred: Union[np.ndarray, list],
    y_train: Optional[Union[np.ndarray, list]] = None,
    seasonality: int = 24,
    scale: Optional[float] = None,
) -> float:
    """
    Mean Absolute Scaled Error (MASE) per Hyndman & Koehler (2006).
    Numerator: Mean hourly MAE across the forecast window.
    Denominator: In-sample seasonal naive MAE scale Q on training series.
    Dimensionless ratio. Values < 1 indicate improvement over seasonal naive baseline.
    """
    t = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    mae_forecast = float(np.mean(np.abs(t - p)))

    if scale is None:
        if y_train is None:
            raise ValueError("Either 'scale' or 'y_train' must be provided.")
        scale = in_sample_seasonal_scale(y_train, seasonality=seasonality)

    if scale <= 1e-9:
        return float(mae_forecast)
    return float(mae_forecast / scale)


def interval_coverage_probability(
    y_true: Union[np.ndarray, list],
    lower: Union[np.ndarray, list],
    upper: Union[np.ndarray, list],
) -> float:
    """Interval Coverage Probability (ICP): fraction of true values within [lower, upper]."""
    t = np.asarray(y_true, dtype=float)
    low = np.asarray(lower, dtype=float)
    high = np.asarray(upper, dtype=float)
    covered = (t >= low) & (t <= high)
    return float(np.mean(covered))


def mean_interval_width(
    lower: Union[np.ndarray, list],
    upper: Union[np.ndarray, list],
) -> float:
    """Mean Interval Width (MIW): average width of prediction intervals (USD)."""
    low = np.asarray(lower, dtype=float)
    high = np.asarray(upper, dtype=float)
    return float(np.mean(high - low))


def lead_time_coverage(
    y_true: Union[np.ndarray, list],
    lower: Union[np.ndarray, list],
    upper: Union[np.ndarray, list],
    lead_time_hour: int,
) -> float:
    """ICP evaluated at exact forecast step h (1-indexed)."""
    t = np.asarray(y_true, dtype=float)
    low = np.asarray(lower, dtype=float)
    high = np.asarray(upper, dtype=float)
    idx = lead_time_hour - 1
    if t.ndim == 1:
        return float(1.0 if (t[idx] >= low[idx] and t[idx] <= high[idx]) else 0.0)
    covered = (t[:, idx] >= low[:, idx]) & (t[:, idx] <= high[:, idx])
    return float(np.mean(covered))


def lead_time_width(
    lower: Union[np.ndarray, list],
    upper: Union[np.ndarray, list],
    lead_time_hour: int,
) -> float:
    """MIW evaluated at exact forecast step h (1-indexed)."""
    low = np.asarray(lower, dtype=float)
    high = np.asarray(upper, dtype=float)
    idx = lead_time_hour - 1
    if low.ndim == 1:
        return float(high[idx] - low[idx])
    return float(np.mean(high[:, idx] - low[:, idx]))


def window_coverage(
    y_true: Union[np.ndarray, list],
    lower: Union[np.ndarray, list],
    upper: Union[np.ndarray, list],
    window_hours: int,
) -> float:
    """ICP evaluated across horizon window 1..W."""
    t = np.asarray(y_true, dtype=float)
    low = np.asarray(lower, dtype=float)
    high = np.asarray(upper, dtype=float)
    if t.ndim == 1:
        covered = (t[:window_hours] >= low[:window_hours]) & (t[:window_hours] <= high[:window_hours])
        return float(np.mean(covered))
    covered = (t[:, :window_hours] >= low[:, :window_hours]) & (t[:, :window_hours] <= high[:, :window_hours])
    return float(np.mean(covered))


def window_width(
    lower: Union[np.ndarray, list],
    upper: Union[np.ndarray, list],
    window_hours: int,
) -> float:
    """MIW evaluated across horizon window 1..W."""
    low = np.asarray(lower, dtype=float)
    high = np.asarray(upper, dtype=float)
    if low.ndim == 1:
        return float(np.mean(high[:window_hours] - low[:window_hours]))
    return float(np.mean(high[:, :window_hours] - low[:, :window_hours]))



def pinball_loss(
    y_true: Union[np.ndarray, list],
    y_pred: Union[np.ndarray, list],
    quantile: float = 0.5,
) -> float:
    """Quantile pinball loss for evaluating quantile forecasts."""
    if not 0.0 < quantile < 1.0:
        raise ValueError(f"Quantile must be in (0, 1), got {quantile}")

    t = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    error = t - p
    loss = np.maximum(quantile * error, (quantile - 1.0) * error)
    return float(np.mean(loss))


def evaluate_forecast_summary(
    y_true: Union[np.ndarray, list],
    y_pred: Union[np.ndarray, list],
    lower: Union[np.ndarray, list],
    upper: Union[np.ndarray, list],
    y_train: Optional[Union[np.ndarray, list]] = None,
    seasonality: int = 24,
) -> Dict[str, float]:
    """Calculate comprehensive evaluation summary for a single origin."""
    res = {
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": root_mean_squared_error(y_true, y_pred),
        "icp": interval_coverage_probability(y_true, lower, upper),
        "miw": mean_interval_width(lower, upper),
    }
    if y_train is not None and len(y_train) > 0:
        res["mase"] = mean_absolute_scaled_error(
            y_true, y_pred, y_train=y_train, seasonality=seasonality
        )
    return res

