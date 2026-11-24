"""
Unit tests for liquidity risk, path-deficit formulations, and scenario simulation.

Verifies:
1. Relative path drawdown proxy calculation (with net_flows or separate dep/wdr).
2. Actual reserve deficit calculations with B_0 and R.
3. Edge cases: negative parameter rejection, empty arrays, zero outflows.
4. Marginal sum envelope vs scenario simulation (Jensen's inequality & envelope conservatism).
5. PairedTrajectoryScenarioCalibrator: fitting, joint simulation, quantile monotonicity, serialization.
6. Temporal isolation: final_test partition guarded by PermissionError.
"""

import numpy as np
import pandas as pd
import pytest

from reserve_juggler_ml.evaluation.splits import PartitionDefinition, generate_rolling_origins
from reserve_juggler_ml.liquidity_risk.path_deficit import (
    compute_actual_path_deficit,
    compute_batch_path_drawdown_proxies,
    compute_cumulative_path_deficit,
    compute_marginal_sum_envelope,
    compute_max_path_deficit,
    compute_relative_path_drawdown_proxy,
    evaluate_horizons_deficit,
)
from reserve_juggler_ml.liquidity_risk.scenarios import (
    PairedTrajectoryScenarioCalibrator,
)


def test_cumulative_path_deficit():
    flows = [10.0, -30.0, 5.0, -10.0]
    cumsum = compute_cumulative_path_deficit(flows)
    assert np.allclose(cumsum, [10.0, -20.0, -15.0, -25.0])


def test_relative_path_drawdown_proxy_calculations():
    # Sequence with maximum cumulative drawdown of 25.0:
    # cumsum: [10, -20, -15, -25, 25] -> lowest is -25.0 -> drawdown is 25.0
    flows = [10.0, -30.0, 5.0, -10.0, 50.0]
    dd_full = compute_relative_path_drawdown_proxy(net_flows=flows, horizon=5)
    assert dd_full == 25.0

    # Truncated at horizon 2: [10.0, -30.0] -> lowest is -20.0 -> drawdown is 20.0
    dd_h2 = compute_relative_path_drawdown_proxy(net_flows=flows, horizon=2)
    assert dd_h2 == 20.0

    # All positive flows -> 0.0 drawdown
    assert compute_relative_path_drawdown_proxy(net_flows=[10.0, 20.0, 30.0]) == 0.0

    # Empty flows -> 0.0 drawdown
    assert compute_relative_path_drawdown_proxy(net_flows=[]) == 0.0

    # Separate deposits and withdrawals
    dep = [100.0, 50.0, 20.0]
    wdr = [80.0, 90.0, 10.0]
    # net = [+20, -40, +10], cumsum = [+20, -20, -10], lowest is -20 -> dd is 20.0
    dd_sep = compute_relative_path_drawdown_proxy(deposits=dep, withdrawals=wdr)
    assert dd_sep == 20.0

    # Rejection of mismatched lengths
    with pytest.raises(ValueError, match="Length mismatch"):
        compute_relative_path_drawdown_proxy(deposits=[1.0, 2.0], withdrawals=[1.0])

    # Rejection of missing arguments
    with pytest.raises(ValueError, match="Must provide either net_flows"):
        compute_relative_path_drawdown_proxy()


def test_actual_path_deficit():
    # Starting cash B_0 = 100, Reserve threshold R = 50
    # Net flows = [-20, -40, +10]
    # Balance path = [100 - 20 = 80, 80 - 40 = 40, 40 + 10 = 50]
    # Deficit path (max(0, 50 - B_h)): [max(0, 50-80)=0, max(0, 50-40)=10, max(0, 50-50)=0]
    # Max deficit = 10.0
    dep = [0.0, 0.0, 20.0]
    wdr = [20.0, 40.0, 10.0]
    b_path, d_path, max_d = compute_actual_path_deficit(
        balance_0=100.0,
        reserve_threshold=50.0,
        deposits=dep,
        withdrawals=wdr,
        horizon=3,
    )
    assert np.allclose(b_path, [80.0, 40.0, 50.0])
    assert np.allclose(d_path, [0.0, 10.0, 0.0])
    assert max_d == 10.0

    # Negative starting balance or threshold rejection
    with pytest.raises(ValueError, match="Opening balance B_0 must be non-negative"):
        compute_actual_path_deficit(-10.0, 50.0, [10.0], [5.0])
    with pytest.raises(ValueError, match="Reserve threshold R must be non-negative"):
        compute_actual_path_deficit(100.0, -5.0, [10.0], [5.0])


def test_marginal_sum_envelope():
    # Demonstrates conservative planning envelope
    # Lower bounds on net flows: [-10.0, -20.0, -15.0]
    net_lowers = [-10.0, -20.0, -15.0]
    env = compute_marginal_sum_envelope(net_lowers, horizon=3)
    assert env == 45.0  # 10 + 20 + 15


def test_batch_path_drawdown_proxies():
    # Batch of 3 paths, 72 hours
    batch = np.zeros((3, 72))
    # Path 0: all zero -> 0.0
    # Path 1: constant -10.0 net flow
    batch[1, :] = -10.0
    # Path 2: constant +10.0 net flow
    batch[2, :] = 10.0

    results = compute_batch_path_drawdown_proxies(batch, horizons=[6, 24, 72])
    assert results[6][0] == 0.0
    assert results[6][1] == 60.0
    assert results[6][2] == 0.0

    assert results[24][1] == 240.0
    assert results[72][1] == 720.0


def test_paired_trajectory_scenario_calibrator():
    N, H = 100, 72
    np.random.seed(42)

    # Simulated actuals and predictions
    p_dep = np.random.uniform(500, 1500, (N, H))
    p_wdr = np.random.uniform(400, 1400, (N, H))

    t_dep = np.maximum(0.0, p_dep + np.random.normal(0, 100, (N, H)))
    t_wdr = np.maximum(0.0, p_wdr + np.random.normal(0, 120, (N, H)))

    calibrator = PairedTrajectoryScenarioCalibrator(horizon_hours=H, min_samples=30)
    calibrator.fit(t_dep, p_dep, t_wdr, p_wdr)

    assert calibrator.is_fitted_
    assert calibrator.sample_count_ == N

    # Rejection of insufficient samples
    with pytest.raises(ValueError, match="Insufficient calibration samples"):
        PairedTrajectoryScenarioCalibrator(min_samples=200).fit(t_dep, p_dep, t_wdr, p_wdr)

    # Simulate scenarios on a test forecast
    test_dep = np.full(H, 1000.0)
    test_wdr = np.full(H, 1000.0)

    sim_dep, sim_wdr = calibrator.simulate_scenarios(test_dep, test_wdr)
    assert sim_dep.shape == (N, H)
    assert sim_wdr.shape == (N, H)
    # Strict non-negativity guarantee
    assert (sim_dep >= 0.0).all()
    assert (sim_wdr >= 0.0).all()

    # Path risk evaluation across horizons
    risk = calibrator.predict_path_risk(test_dep, test_wdr, horizons=[6, 24, 48, 72])
    for h in [6, 24, 48, 72]:
        assert h in risk
        h_res = risk[h]
        # Quantile monotonicity: q50 <= q90 <= q95 <= q99
        q = h_res["quantiles"]
        assert q[0.50] <= q[0.90] <= q[0.95] <= q[0.99]
        # Jensen's inequality: mean scenario drawdown >= drawdown of mean simulated flow trajectory
        assert h_res["mean_drawdown"] >= h_res["mean_flow_drawdown"] - 1e-9

    # Horizon monotonicity: drawdown at H=6 <= H=24 <= H=72
    assert risk[6]["quantiles"][0.95] <= risk[24]["quantiles"][0.95] <= risk[72]["quantiles"][0.95]

    # Serialization roundtrip
    cal_dict = calibrator.to_dict()
    restored = PairedTrajectoryScenarioCalibrator.from_dict(cal_dict)
    assert restored.is_fitted_
    assert restored.sample_count_ == N

    risk_restored = restored.predict_path_risk(test_dep, test_wdr, horizons=[24])
    assert np.isclose(risk[24]["mean_drawdown"], risk_restored[24]["mean_drawdown"])


def test_final_test_isolation_during_path_risk():
    # Attempting to access or calibrate on final_test must raise PermissionError
    dates = pd.date_range("2026-11-01 00:00:00", periods=200, freq="h")
    df = pd.DataFrame({
        "timestamp": dates,
        "deposits_usd": np.ones(200) * 1000.0,
    })
    final_test_part = PartitionDefinition("final_test", dates[0], dates[-1], is_reserved=True)
    with pytest.raises(PermissionError, match="strictly reserved"):
        generate_rolling_origins(df, partition_name="final_test", partitions={"final_test": final_test_part})


def test_path_alignment_and_origin_causality():
    # Verifies that path targets strictly begin at origin index t and do not include t in history
    dates = pd.date_range("2026-01-01 00:00:00", periods=500, freq="h")
    df = pd.DataFrame({
        "timestamp": dates,
        "deposits_usd": np.linspace(100, 500, 500),
        "withdrawals_usd": np.linspace(80, 480, 500),
    })
    fit_part = PartitionDefinition("fit", dates[0], dates[-1], is_reserved=False)
    origins, meta = generate_rolling_origins(df, "fit", horizon_hours=72, min_history_hours=336, step_hours=1, partitions={"fit": fit_part})

    assert len(origins) > 0
    for o in origins[:5]:
        # History strictly excludes row at origin_idx
        assert o.history_end_idx == o.origin_idx
        assert o.target_start_idx == o.origin_idx
        assert o.target_end_idx == o.origin_idx + 72
        # Target slice matches exact forward horizon
        assert (o.target_end_idx - o.target_start_idx) == 72


def test_scenario_pairing_integrity_and_jensen_inequality():
    # Verifies that residual trajectories preserve origin pairing and 72-hour sequence
    N, H = 50, 72
    np.random.seed(123)

    t_dep = np.random.uniform(500, 1500, (N, H))
    p_dep = np.random.uniform(500, 1500, (N, H))
    t_wdr = np.random.uniform(400, 1400, (N, H))
    p_wdr = np.random.uniform(400, 1400, (N, H))

    calibrator = PairedTrajectoryScenarioCalibrator(horizon_hours=H, min_samples=30)
    calibrator.fit(t_dep, p_dep, t_wdr, p_wdr)

    # Confirm residuals are paired across deposits and withdrawals row-by-row
    expected_e_dep = t_dep - p_dep
    expected_e_wdr = t_wdr - p_wdr
    np.testing.assert_allclose(calibrator.dep_residuals_, expected_e_dep)
    np.testing.assert_allclose(calibrator.wdr_residuals_, expected_e_wdr)
    # Test Jensen's inequality:
    # Because path drawdown functional g(x) = max_{1<=h<=H} max(0, -cumsum_h(x)) is convex,
    # Jensen's inequality mathematically supports:
    #     E[g(X)] >= g(E[X])  <=>  mean_drawdown >= mean_flow_drawdown
    # It does NOT guarantee mean_drawdown >= point_drawdown because non-negative clipping
    # and non-zero residual sample means shift the mean simulated flow trajectory away from the point forecast.
    for seed in [1, 2, 3]:
        np.random.seed(seed)
        fc_dep = np.random.uniform(600, 1200, H)
        fc_wdr = np.random.uniform(600, 1200, H)
        risk = calibrator.predict_path_risk(fc_dep, fc_wdr, horizons=[6, 24, 48, 72])
        for h in [6, 24, 48, 72]:
            assert risk[h]["mean_drawdown"] >= risk[h]["mean_flow_drawdown"] - 1e-9

    # Counterexample verifying Jensen's inequality does NOT support mean_drawdown >= point_drawdown:
    # Construct a point forecast with a net deficit (point drawdown > 0)
    fc_dep_def = np.full(H, 100.0)
    fc_wdr_def = np.full(H, 300.0)  # net deficit = -200 per hour
    # Construct calibration data where positive deposit residual shifts simulated scenarios into large surplus
    t_dep_surplus = np.full((35, H), 1000.0)
    p_dep_surplus = np.full((35, H), 100.0)  # e_dep = +900/hr
    t_wdr_surplus = np.full((35, H), 200.0)
    p_wdr_surplus = np.full((35, H), 200.0)  # e_wdr = 0/hr
    cal_surplus = PairedTrajectoryScenarioCalibrator(horizon_hours=H, min_samples=30)
    cal_surplus.fit(t_dep_surplus, p_dep_surplus, t_wdr_surplus, p_wdr_surplus)

    risk_counter = cal_surplus.predict_path_risk(fc_dep_def, fc_wdr_def, horizons=[24])
    # Point drawdown is positive: 200 * 24 = 4800
    assert risk_counter[24]["point_drawdown"] == 4800.0
    # Simulated net flow is (100 + 900) - 300 = +700 (drawdown = 0.0)
    assert risk_counter[24]["mean_drawdown"] == 0.0
    # Demonstrating point_drawdown > mean_drawdown when residual mean shift occurs:
    assert risk_counter[24]["point_drawdown"] > risk_counter[24]["mean_drawdown"]
    # But true Jensen's inequality (mean_drawdown >= mean_flow_drawdown) still holds identically:
    assert risk_counter[24]["mean_drawdown"] >= risk_counter[24]["mean_flow_drawdown"] - 1e-9


