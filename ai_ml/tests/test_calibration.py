"""
Unit tests for prediction-interval calibration and uncertainty quantification.
Verifies:
1. Residual-quantile calculation for 90%, 95%, 99% coverage levels.
2. Bounds contract: 0.0 <= lower <= mean <= upper strictly guaranteed.
3. Non-negative clipping behavior on lower bounds.
4. Lead-time dependent quantile offsets across 72 horizons.
5. Insufficient calibration data rejection (N < min_samples).
6. Calibrator serialization reproducibility (to_dict / from_dict).
7. Partition and temporal isolation: final_test partition strictly guarded.
"""

import numpy as np
import pandas as pd
import pytest

from reserve_juggler_ml.evaluation.metrics import (
    interval_coverage_probability,
    lead_time_coverage,
    lead_time_width,
    mean_interval_width,
    window_coverage,
    window_width,
)
from reserve_juggler_ml.evaluation.splits import PartitionDefinition, generate_rolling_origins
from reserve_juggler_ml.uncertainty.calibration import (
    LeadTimeEmpiricalCalibrator,
    compute_conformal_interval_margin,
    compute_empirical_quantile_interval,
)


def test_empirical_quantile_interval_calculation():
    # Test on synthetic normal residuals
    np.random.seed(42)
    res = np.random.normal(0, 100, 1000)
    low_95, high_95 = compute_empirical_quantile_interval(res, alpha=0.05)
    low_90, high_90 = compute_empirical_quantile_interval(res, alpha=0.10)

    assert low_95 < 0.0 < high_95
    assert low_90 < 0.0 < high_90
    # 95% interval should be wider than 90% interval
    assert (high_95 - low_95) > (high_90 - low_90)


def test_conformal_interval_margin_finite_sample():
    np.random.seed(42)
    res = np.random.normal(0, 50, 100)
    m95 = compute_conformal_interval_margin(res, alpha=0.05)
    m90 = compute_conformal_interval_margin(res, alpha=0.10)
    assert m95 > m90 > 0.0


def test_lead_time_empirical_calibrator_fit_and_calibrate():
    N, H = 200, 72
    np.random.seed(42)

    # Simulate predictions and actuals with increasing variance over lead times
    y_pred = np.random.uniform(500, 2000, (N, H))
    lead_stds = np.linspace(50, 300, H)
    errors = np.random.normal(0, lead_stds, (N, H))
    y_true = np.maximum(y_pred + errors, 0.0)

    calibrator = LeadTimeEmpiricalCalibrator(horizon_hours=H, alphas=[0.10, 0.05, 0.01])
    calibrator.fit(y_true, y_pred)

    assert calibrator.is_fitted_
    assert calibrator.sample_count_ == N

    # Calibrate a single test forecast
    test_mean = pd.Series(
        np.full(H, 1000.0),
        index=pd.date_range("2026-09-01 00:00:00", periods=H, freq="h"),
        name="deposits_usd",
    )

    for alpha in [0.10, 0.05, 0.01]:
        lower, upper = calibrator.calibrate_forecast(test_mean, alpha=alpha, clip_nonnegative=True)

        # Strict bounds contracts
        assert isinstance(lower, pd.Series)
        assert isinstance(upper, pd.Series)
        assert len(lower) == H
        assert len(upper) == H

        # 0.0 <= lower <= mean <= upper
        assert (lower >= 0.0).all()
        assert (lower <= test_mean).all()
        assert (test_mean <= upper).all()
        assert (lower <= upper).all()

    # Check lead-time width expansion (interval width expands from h=1 to h=72)
    low_95, high_95 = calibrator.calibrate_forecast(test_mean, alpha=0.05)
    width_h1 = high_95.iloc[0] - low_95.iloc[0]
    width_h72 = high_95.iloc[-1] - low_95.iloc[-1]
    assert width_h72 > width_h1


def test_calibrator_rejects_insufficient_samples():
    calibrator = LeadTimeEmpiricalCalibrator(min_samples=50)
    y_true = np.zeros((20, 72))
    y_pred = np.zeros((20, 72))
    with pytest.raises(ValueError, match="Insufficient calibration samples"):
        calibrator.fit(y_true, y_pred)


def test_calibrator_rejects_mismatched_shapes():
    calibrator = LeadTimeEmpiricalCalibrator(min_samples=10)
    with pytest.raises(ValueError, match="Shape mismatch"):
        calibrator.fit(np.zeros((50, 72)), np.zeros((50, 36)))


def test_calibrator_rejects_unsupported_alpha():
    calibrator = LeadTimeEmpiricalCalibrator(alphas=[0.10, 0.05])
    calibrator.fit(np.zeros((50, 72)), np.zeros((50, 72)))
    with pytest.raises(ValueError, match="Alpha 0.5 not in pre-calibrated alphas"):
        calibrator.calibrate_forecast(np.full(72, 100.0), alpha=0.5)


def test_calibrator_serialization_roundtrip():
    N, H = 100, 72
    np.random.seed(42)
    y_pred = np.random.uniform(500, 1500, (N, H))
    y_true = y_pred + np.random.normal(0, 100, (N, H))

    calibrator = LeadTimeEmpiricalCalibrator(horizon_hours=H, model_name="TestModel", target_name="test_target")
    calibrator.fit(y_true, y_pred)

    cal_dict = calibrator.to_dict()
    restored = LeadTimeEmpiricalCalibrator.from_dict(cal_dict)

    assert restored.is_fitted_
    assert restored.sample_count_ == N
    assert restored.model_name == "TestModel"

    test_pred = np.full(H, 1000.0)
    low1, high1 = calibrator.calibrate_forecast(test_pred, alpha=0.05)
    low2, high2 = restored.calibrate_forecast(test_pred, alpha=0.05)

    np.testing.assert_allclose(low1, low2)
    np.testing.assert_allclose(high1, high2)


def test_interval_metrics_functions():
    y_true = np.array([[100.0, 200.0], [150.0, 250.0]])
    lower = np.array([[90.0, 190.0], [140.0, 240.0]])
    upper = np.array([[110.0, 210.0], [160.0, 260.0]])

    icp = interval_coverage_probability(y_true, lower, upper)
    assert icp == 1.0

    # Lead-time coverage & width
    assert lead_time_coverage(y_true, lower, upper, lead_time_hour=1) == 1.0
    assert lead_time_width(lower, upper, lead_time_hour=1) == 20.0

    # Window coverage & width
    assert window_coverage(y_true, lower, upper, window_hours=2) == 1.0
    assert window_width(lower, upper, window_hours=2) == 20.0


def test_final_test_isolation_during_calibration():
    # Attempting to generate origins or calibrate on final_test must raise PermissionError
    dates = pd.date_range("2026-11-01 00:00:00", periods=200, freq="h")
    df = pd.DataFrame({
        "timestamp": dates,
        "deposits_usd": np.ones(200) * 1000.0,
    })
    final_test_part = PartitionDefinition("final_test", dates[0], dates[-1], is_reserved=True)
    with pytest.raises(PermissionError, match="strictly reserved"):
        generate_rolling_origins(df, partition_name="final_test", partitions={"final_test": final_test_part})
