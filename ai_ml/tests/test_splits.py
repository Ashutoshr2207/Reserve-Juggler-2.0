"""Unit and regression tests for chronological partitioning and rolling-origin evaluation."""

import pytest
import numpy as np
import pandas as pd
from reserve_juggler_ml.evaluation.splits import (
    ChronologicalOrigin,
    PartitionDefinition,
    STANDARD_PARTITIONS,
    generate_rolling_origins,
)


def test_standard_partitions_definitions():
    assert "dev" in STANDARD_PARTITIONS
    assert "validation" in STANDARD_PARTITIONS
    assert "final_test" in STANDARD_PARTITIONS
    assert STANDARD_PARTITIONS["final_test"].is_reserved is True
    assert STANDARD_PARTITIONS["validation"].is_reserved is False


def test_reserved_partition_guard():
    # Attempting to generate origins on final_test without allow_reserved must raise PermissionError
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-11-01", periods=100, freq="h"),
        "deposits": [100.0] * 100,
    })
    with pytest.raises(PermissionError, match="strictly reserved"):
        generate_rolling_origins(df, partition_name="final_test", allow_reserved=False)

    # When allow_reserved is True, it is permitted
    origins, meta = generate_rolling_origins(
        df, partition_name="final_test", min_history_hours=10, horizon_hours=12, allow_reserved=True
    )
    assert meta["partition_name"] == "final_test"


def test_boundary_purging_protects_partition_end():
    # Create a 100-hour series in validation partition
    start_ts = pd.Timestamp("2026-09-01 00:00:00")
    timestamps = pd.date_range(start_ts, periods=100, freq="h")
    df = pd.DataFrame({
        "timestamp": timestamps,
        "deposits": range(100),
    })

    # Custom partition ending at hour 90
    custom_part = {
        "test_part": PartitionDefinition(
            name="test_part",
            start_time=start_ts,
            end_time=start_ts + pd.DateOffset(hours=90),
            is_reserved=False,
        )
    }

    horizon = 20
    # Any origin t where t + 20h > start_ts + 90h must be purged.
    # Therefore, origins at hours > 70 are purged.
    origins, meta = generate_rolling_origins(
        df,
        partition_name="test_part",
        horizon_hours=horizon,
        min_history_hours=10,
        step_hours=5,
        partitions=custom_part,
    )

    assert meta["purged_boundary_origins"] > 0
    for origin in origins:
        # Check that the target end time does not exceed the partition end
        target_end_ts = df["timestamp"].iloc[origin.target_end_idx - 1]
        assert target_end_ts <= custom_part["test_part"].end_time


def test_causal_cutoff_no_lookahead():
    """Verify that history strictly excludes origin_idx and targets start at origin_idx."""
    timestamps = pd.date_range("2026-09-01 00:00:00", periods=200, freq="h")
    df = pd.DataFrame({"timestamp": timestamps, "deposits": range(200)})

    custom_part = {
        "val": PartitionDefinition(
            name="val",
            start_time=timestamps[100],
            end_time=timestamps[199],
            is_reserved=False,
        )
    }

    origins, _ = generate_rolling_origins(
        df,
        partition_name="val",
        horizon_hours=24,
        min_history_hours=50,
        step_hours=10,
        partitions=custom_part,
    )

    assert len(origins) > 0
    for origin in origins:
        # History slice [history_start_idx : history_end_idx] ends at origin_idx (excludes row at origin_idx)
        assert origin.history_end_idx == origin.origin_idx
        # Target start index starts exactly at origin_idx (interval [t, t+1h))
        assert origin.target_start_idx == origin.origin_idx
        # Target end index equals origin_idx + horizon
        assert origin.target_end_idx == origin.origin_idx + origin.horizon_hours
        # History and target indices are strictly disjoint
        assert origin.history_end_idx == origin.target_start_idx


def test_non_monotonic_timestamps_rejected():
    df = pd.DataFrame({
        "timestamp": ["2026-09-02", "2026-09-01"],
        "deposits": [10.0, 20.0],
    })
    with pytest.raises(ValueError, match="monotonic increasing"):
        generate_rolling_origins(df, partition_name="validation")


def test_hourly_origin_generation_and_full_purging():
    """
    Test hourly origin generation (step_hours=1 default).
    Verifies that across the standard validation partition (1,464 candidate hours):
    - Exactly 1,464 candidate origins are evaluated.
    - Exactly 71 origins are purged to prevent the 72h target window from crossing into final_test.
      (Oct 29 01:00 to Oct 31 23:00 = 71 purged origins).
    - Exactly 1,393 valid hourly origins are produced.
    - Consecutive origins increment by exactly 1 hour.
    - Last valid origin is 2026-10-29 00:00:00, whose 72nd target is 2026-10-31 23:00:00.
    """
    # Create full year hourly timestamps to simulate full dataset
    ts = pd.date_range("2026-01-01 00:00:00", "2026-12-31 23:00:00", freq="h")
    df = pd.DataFrame({"timestamp": ts, "deposits": range(len(ts))})

    origins, meta = generate_rolling_origins(
        df=df,
        partition_name="validation",
        horizon_hours=72,
        min_history_hours=336,
        # Default step_hours is 1
    )

    assert meta["step_hours"] == 1
    assert meta["candidate_origins"] == 1464  # Sep (720h) + Oct (744h) = 1,464h
    assert meta["insufficient_history_origins"] == 0  # Jan-Aug (5,832h) > 336h
    assert meta["purged_boundary_origins"] == 71      # Oct 29 01:00 to Oct 31 23:00 = 71h
    assert meta["valid_origins"] == 1393
    assert len(origins) == 1393

    # Verify consecutive 1-hour increments
    for i in range(len(origins) - 1):
        diff_hours = (origins[i + 1].origin_timestamp - origins[i].origin_timestamp).total_seconds() / 3600.0
        assert diff_hours == 1.0

    # First origin check: 2026-09-01 00:00:00
    assert origins[0].origin_timestamp == pd.Timestamp("2026-09-01 00:00:00")
    assert origins[0].history_end_idx == origins[0].origin_idx
    assert origins[0].target_start_idx == origins[0].origin_idx
    assert df["timestamp"].iloc[origins[0].history_end_idx - 1] == pd.Timestamp("2026-08-31 23:00:00")
    assert df["timestamp"].iloc[origins[0].target_start_idx] == pd.Timestamp("2026-09-01 00:00:00")

    # Last origin check: 2026-10-29 00:00:00
    assert origins[-1].origin_timestamp == pd.Timestamp("2026-10-29 00:00:00")

    # Verify last origin's 72nd target ends exactly at partition end
    last_target_end_ts = df["timestamp"].iloc[origins[-1].target_end_idx - 1]
    assert last_target_end_ts == pd.Timestamp("2026-10-31 23:00:00")


def test_validation_final_partition_isolation():
    """
    Verify complete isolation between validation and final_test partitions.
    No validation target may ever touch 2026-11-01 00:00:00 or beyond.
    """
    ts = pd.date_range("2026-01-01 00:00:00", "2026-12-31 23:00:00", freq="h")
    df = pd.DataFrame({"timestamp": ts, "deposits": range(len(ts))})

    origins, _ = generate_rolling_origins(
        df=df,
        partition_name="validation",
        horizon_hours=72,
        min_history_hours=336,
        step_hours=1,
    )

    final_test_start = STANDARD_PARTITIONS["final_test"].start_time
    for origin in origins:
        target_timestamps = df["timestamp"].iloc[origin.target_start_idx:origin.target_end_idx]
        assert all(t < final_test_start for t in target_timestamps)


def test_origin_row_mutation_does_not_affect_forecast():
    """
    Targeted test: demonstrate that changing deposit/withdrawal values in the origin row
    cannot change a forecast made at the start of that interval.
    """
    from reserve_juggler_ml.forecasting.baseline import DeterministicBaseline
    from reserve_juggler_ml.forecasting.seasonal import SeasonalNaiveForecaster

    ts = pd.date_range("2026-08-01 00:00:00", periods=1000, freq="h")
    # Sine wave flow
    flows = 10000.0 + 2000.0 * np.sin(2 * np.pi * ts.hour / 24.0)
    df = pd.DataFrame({"timestamp": ts, "deposits": flows.copy()})

    custom_part = {
        "val": PartitionDefinition(
            name="val",
            start_time=ts[500],
            end_time=ts[800],
            is_reserved=False,
        )
    }

    origins, _ = generate_rolling_origins(
        df,
        partition_name="val",
        horizon_hours=72,
        min_history_hours=336,
        step_hours=1,
        partitions=custom_part,
    )

    origin = origins[10]
    origin_idx = origin.origin_idx

    # Baseline models fitted on clean data
    h_series_clean = pd.Series(
        df["deposits"].iloc[origin.history_start_idx:origin.history_end_idx].values,
        index=pd.to_datetime(df["timestamp"].iloc[origin.history_start_idx:origin.history_end_idx]),
    )
    pred_det_clean = DeterministicBaseline(lookback_hours=336).fit(h_series_clean).predict(72)
    pred_sn24_clean = SeasonalNaiveForecaster(season_length=24).fit(h_series_clean).predict(72)
    pred_sn168_clean = SeasonalNaiveForecaster(season_length=168).fit(h_series_clean).predict(72)

    # Now wildly corrupt the origin row at timestamp t
    df_corrupted = df.copy()
    df_corrupted.loc[origin_idx, "deposits"] = 999_999_999_999.0

    # Extract history using origin indices
    h_series_corrupted = pd.Series(
        df_corrupted["deposits"].iloc[origin.history_start_idx:origin.history_end_idx].values,
        index=pd.to_datetime(df_corrupted["timestamp"].iloc[origin.history_start_idx:origin.history_end_idx]),
    )

    pred_det_corrupted = DeterministicBaseline(lookback_hours=336).fit(h_series_corrupted).predict(72)
    pred_sn24_corrupted = SeasonalNaiveForecaster(season_length=24).fit(h_series_corrupted).predict(72)
    pred_sn168_corrupted = SeasonalNaiveForecaster(season_length=168).fit(h_series_corrupted).predict(72)

    # Forecasts MUST BE 100% IDENTICAL because origin row is strictly excluded from history
    np.testing.assert_array_equal(pred_det_clean.mean.values, pred_det_corrupted.mean.values)
    np.testing.assert_array_equal(pred_sn24_clean.mean.values, pred_sn24_corrupted.mean.values)
    np.testing.assert_array_equal(pred_sn168_clean.mean.values, pred_sn168_corrupted.mean.values)


def test_origin_row_strictly_excluded_from_history():
    """Verify that origin row is strictly excluded from history for all origins."""
    ts = pd.date_range("2026-08-01 00:00:00", periods=500, freq="h")
    df = pd.DataFrame({"timestamp": ts, "deposits": range(500)})

    custom_part = {
        "val": PartitionDefinition(
            name="val",
            start_time=ts[350],
            end_time=ts[450],
            is_reserved=False,
        )
    }

    origins, _ = generate_rolling_origins(
        df,
        partition_name="val",
        horizon_hours=24,
        min_history_hours=336,
        step_hours=1,
        partitions=custom_part,
    )

    for origin in origins:
        # History ends strictly before origin_idx
        assert origin.history_end_idx == origin.origin_idx
        # History slice does not contain origin_timestamp
        history_ts = df["timestamp"].iloc[origin.history_start_idx:origin.history_end_idx]
        assert origin.origin_timestamp not in history_ts.values
        # Target starts exactly at origin_timestamp
        assert df["timestamp"].iloc[origin.target_start_idx] == origin.origin_timestamp


