"""Unit tests for the benchmark evaluation runner and cumulative window metrics."""

import pandas as pd
import numpy as np
from reserve_juggler_ml.evaluation.benchmark import (
    CUMULATIVE_WINDOWS,
    evaluate_model_on_origins,
)
from reserve_juggler_ml.evaluation.splits import (
    PartitionDefinition,
    generate_rolling_origins,
)
from reserve_juggler_ml.forecasting.baseline import DeterministicBaseline
from reserve_juggler_ml.forecasting.seasonal import SeasonalNaiveForecaster


def test_evaluate_model_on_origins_synthetic():
    # Construct 500 hours of synthetic data
    timestamps = pd.date_range("2026-09-01 00:00:00", periods=500, freq="h")
    # Diurnal cycle with noise
    values = 1000.0 + 300.0 * np.sin(2 * np.pi * timestamps.hour / 24.0) + np.random.normal(0, 5, 500)
    df = pd.DataFrame({
        "timestamp": timestamps,
        "net_flow": values,
    })

    part = {
        "val": PartitionDefinition(
            name="val",
            start_time=timestamps[200],
            end_time=timestamps[450],
            is_reserved=False,
        )
    }

    origins, meta = generate_rolling_origins(
        df,
        partition_name="val",
        horizon_hours=72,
        min_history_hours=168,
        step_hours=24,
        partitions=part,
    )

    assert meta["valid_origins"] > 0

    # Evaluate Baseline A (14-day deterministic profile)
    res_a = evaluate_model_on_origins(
        df=df,
        origins=origins,
        model_factory=lambda: DeterministicBaseline(lookback_hours=168),
        target_col="net_flow",
        currency="USD",
        seasonality_for_mase=24,
        windows=CUMULATIVE_WINDOWS,
    )

    # Evaluate Baseline B (24h seasonal naive)
    res_b24 = evaluate_model_on_origins(
        df=df,
        origins=origins,
        model_factory=lambda: SeasonalNaiveForecaster(season_length=24),
        target_col="net_flow",
        currency="USD",
        seasonality_for_mase=24,
        windows=CUMULATIVE_WINDOWS,
    )

    # Evaluate Baseline B (168h weekly seasonal naive)
    res_b168 = evaluate_model_on_origins(
        df=df,
        origins=origins,
        model_factory=lambda: SeasonalNaiveForecaster(season_length=168),
        target_col="net_flow",
        currency="USD",
        seasonality_for_mase=24,
        windows=CUMULATIVE_WINDOWS,
    )

    # 1. Verify identical origins across all three baseline models
    assert res_a.origin_count == meta["valid_origins"]
    assert res_b24.origin_count == meta["valid_origins"]
    assert res_b168.origin_count == meta["valid_origins"]
    assert res_a.total_predictions == meta["valid_origins"] * 72
    assert res_b24.total_predictions == meta["valid_origins"] * 72
    assert res_b168.total_predictions == meta["valid_origins"] * 72

    # 2. Verify lead-time metrics at specific horizons
    for res in [res_a, res_b24, res_b168]:
        for h in [1, 6, 24, 48, 72]:
            assert h in res.lead_time_metrics
            lt = res.lead_time_metrics[h]
            assert lt.mae >= 0.0
            assert lt.rmse >= 0.0
            assert lt.sample_count == meta["valid_origins"]

    # 3. Verify window metrics (mean hourly vs cumulative total)
    for res in [res_a, res_b24, res_b168]:
        for w in CUMULATIVE_WINDOWS:
            assert w in res.window_metrics
            wm = res.window_metrics[w]
            assert wm.mean_hourly_mae >= 0.0
            assert wm.mean_hourly_rmse >= 0.0
            assert wm.cumulative_total_mae >= 0.0
            assert wm.cumulative_total_rmse >= 0.0
            assert wm.mase >= 0.0
            assert wm.mase_denominator_scale > 0.0

    # 4. Verify serialization to dictionary
    d = res_a.to_dict()
    assert d["origin_count"] == meta["valid_origins"]
    assert "lead_time_metrics" in d
    assert "window_metrics" in d

