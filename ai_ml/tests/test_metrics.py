"""Unit tests for point and interval forecast metrics."""

import pytest
import numpy as np
from reserve_juggler_ml.evaluation.metrics import (
    cumulative_total_mae,
    cumulative_total_rmse,
    evaluate_forecast_summary,
    in_sample_seasonal_scale,
    interval_coverage_probability,
    lead_time_mae,
    lead_time_rmse,
    mean_absolute_error,
    mean_absolute_scaled_error,
    mean_hourly_mae,
    mean_hourly_rmse,
    mean_interval_width,
    pinball_loss,
    root_mean_squared_error,
)


def test_mae_and_rmse():
    y_true = np.array([10.0, 20.0, 30.0])
    y_pred = np.array([12.0, 18.0, 33.0])

    # Absolute errors: [2, 2, 3] -> mean = 7/3
    assert mean_absolute_error(y_true, y_pred) == pytest.approx(7.0 / 3.0)
    # Squared errors: [4, 4, 9] -> mean = 17/3 -> sqrt(17/3)
    assert root_mean_squared_error(y_true, y_pred) == pytest.approx(np.sqrt(17.0 / 3.0))


def test_mean_hourly_vs_cumulative_total_error_semantics():
    """
    Demonstrate that average hourly error rate (USD/hr) and cumulative-total error (USD total)
    are fundamentally distinct metrics with different units and aggregation semantics.

    Case 1 (Zero-sum fluctuations):
      y_true = [100.0, 100.0]  (Realized total = 200.0)
      y_pred = [110.0, 90.0]   (Predicted total = 200.0)
      Hourly errors: [+10.0, -10.0]
      Mean hourly MAE = (10 + 10) / 2 = 10.0 USD/hr.
      Cumulative total MAE = |200 - 200| = 0.0 USD.
    """
    y_trues = np.array([[100.0, 100.0]])
    y_preds = np.array([[110.0, 90.0]])

    m_h_mae = mean_hourly_mae(y_trues, y_preds, window_hours=2)
    c_t_mae = cumulative_total_mae(y_trues, y_preds, window_hours=2)

    assert m_h_mae == pytest.approx(10.0)  # Average $10/hr error
    assert c_t_mae == pytest.approx(0.0)   # Net cash flow error is $0.0!
    assert m_h_mae != c_t_mae

    """
    Case 2 (Systematic bias):
      y_true = [100.0, 100.0]  (Realized total = 200.0)
      y_pred = [110.0, 110.0]  (Predicted total = 220.0)
      Hourly errors: [+10.0, +10.0]
      Mean hourly MAE = 10.0 USD/hr.
      Cumulative total MAE = |200 - 220| = 20.0 USD total volume.
    """
    y_trues_bias = np.array([[100.0, 100.0]])
    y_preds_bias = np.array([[110.0, 110.0]])

    m_h_mae_b = mean_hourly_mae(y_trues_bias, y_preds_bias, window_hours=2)
    c_t_mae_b = cumulative_total_mae(y_trues_bias, y_preds_bias, window_hours=2)

    assert m_h_mae_b == pytest.approx(10.0)
    assert c_t_mae_b == pytest.approx(20.0)

    # When window=1, mean hourly MAE equals cumulative total MAE
    assert mean_hourly_mae(y_trues_bias, y_preds_bias, window_hours=1) == pytest.approx(10.0)
    assert cumulative_total_mae(y_trues_bias, y_preds_bias, window_hours=1) == pytest.approx(10.0)


def test_lead_time_metrics():
    """Verify lead-time-specific MAE and RMSE at exact step h."""
    # 2 origins, 3 horizon steps
    y_trues = np.array([
        [10.0, 20.0, 30.0],
        [15.0, 25.0, 35.0],
    ])
    y_preds = np.array([
        [12.0, 22.0, 36.0],  # errors: [2, 2, 6]
        [11.0, 29.0, 35.0],  # errors: [4, 4, 0]
    ])

    # Lead time h=1: errors [2, 4] -> MAE = 3.0, RMSE = sqrt((4+16)/2) = sqrt(10)
    assert lead_time_mae(y_trues, y_preds, lead_time_hour=1) == pytest.approx(3.0)
    assert lead_time_rmse(y_trues, y_preds, lead_time_hour=1) == pytest.approx(np.sqrt(10.0))

    # Lead time h=3: errors [6, 0] -> MAE = 3.0, RMSE = sqrt((36+0)/2) = sqrt(18)
    assert lead_time_mae(y_trues, y_preds, lead_time_hour=3) == pytest.approx(3.0)
    assert lead_time_rmse(y_trues, y_preds, lead_time_hour=3) == pytest.approx(np.sqrt(18.0))


def test_mase_and_in_sample_scale():
    """Verify Hyndman MASE scaling series denominator."""
    # Training series with daily cycle of 24h: constant differences of 5.0
    seasonality = 24
    y_train = np.arange(100, dtype=float) * 5.0  # y[t] - y[t-24] = 24 * 5 = 120.0
    expected_scale = 120.0

    scale = in_sample_seasonal_scale(y_train, seasonality=seasonality)
    assert scale == pytest.approx(expected_scale)

    # Forecast with MAE of 60.0 -> MASE should be exactly 60 / 120 = 0.5
    y_true = np.array([100.0, 100.0])
    y_pred = np.array([160.0, 160.0])

    mase = mean_absolute_scaled_error(y_true, y_pred, y_train=y_train, seasonality=seasonality)
    assert mase == pytest.approx(0.5)


def test_icp_and_miw():
    y_true = np.array([10.0, 20.0, 30.0, 40.0])
    lower = np.array([8.0, 15.0, 25.0, 42.0])  # 40 is below lower (42) -> missed
    upper = np.array([12.0, 25.0, 35.0, 50.0])

    # Coverage: 3 out of 4 covered -> 0.75
    assert interval_coverage_probability(y_true, lower, upper) == 0.75
    # Widths: [4, 10, 10, 8] -> mean = 32/4 = 8.0
    assert mean_interval_width(lower, upper) == 8.0


def test_pinball_loss():
    y_true = np.array([100.0])
    # Underprediction: true = 100, pred = 90 -> error = 10 -> loss = tau * 10
    loss_under = pinball_loss(y_true, np.array([90.0]), quantile=0.9)
    assert loss_under == pytest.approx(0.9 * 10.0)

    # Overprediction: true = 100, pred = 110 -> error = -10 -> loss = (tau - 1) * (-10) = (1 - tau) * 10
    loss_over = pinball_loss(y_true, np.array([110.0]), quantile=0.9)
    assert loss_over == pytest.approx(0.1 * 10.0)


def test_evaluate_forecast_summary():
    y_true = np.array([10.0, 20.0])
    y_pred = np.array([10.0, 20.0])
    lower = np.array([8.0, 18.0])
    upper = np.array([12.0, 22.0])

    summary = evaluate_forecast_summary(y_true, y_pred, lower, upper)
    assert summary["mae"] == 0.0
    assert summary["rmse"] == 0.0
    assert summary["icp"] == 1.0
    assert summary["miw"] == 4.0
