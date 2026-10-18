"""Chronological partitioning and rolling-origin evaluation harness."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd


@dataclass(frozen=True)
class PartitionDefinition:
    """Definition of a chronological partition with strict temporal boundaries."""
    name: str
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    is_reserved: bool = False
    description: str = ""


# Documented 2026 standard partitions per MODEL_SELECTION_PLAN.md
STANDARD_PARTITIONS: Dict[str, PartitionDefinition] = {
    "dev": PartitionDefinition(
        name="dev",
        start_time=pd.Timestamp("2026-01-01 00:00:00"),
        end_time=pd.Timestamp("2026-08-31 23:00:00"),
        is_reserved=False,
        description="Development and model exploration partition (Months 1–8, 243 days, 5,832 hours)",
    ),
    "validation": PartitionDefinition(
        name="validation",
        start_time=pd.Timestamp("2026-09-01 00:00:00"),
        end_time=pd.Timestamp("2026-10-31 23:00:00"),
        is_reserved=False,
        description="Validation and hyperparameter tuning partition (Months 9–10, 61 days, 1,464 hours)",
    ),
    "final_test": PartitionDefinition(
        name="final_test",
        start_time=pd.Timestamp("2026-11-01 00:00:00"),
        end_time=pd.Timestamp("2026-12-31 23:00:00"),
        is_reserved=True,
        description="Reserved final evaluation holdout partition (Months 11–12, 61 days, 1,464 hours)",
    ),
}


@dataclass(frozen=True)
class ChronologicalOrigin:
    """Represents a validated forecast origin for walk-forward evaluation."""
    origin_idx: int
    origin_timestamp: pd.Timestamp
    history_start_idx: int
    history_end_idx: int  # Slice end (exclusive), history is df.iloc[history_start_idx:history_end_idx]
    target_start_idx: int  # Slice start (inclusive) for targets: df.iloc[target_start_idx:target_end_idx]
    target_end_idx: int
    horizon_hours: int
    partition_name: str


def generate_rolling_origins(
    df: pd.DataFrame,
    partition_name: str = "validation",
    horizon_hours: int = 72,
    min_history_hours: int = 336,  # 14 days default for deterministic baseline
    step_hours: int = 1,           # Primary benchmark is hourly evaluation (1-hour step)
    timestamp_col: str = "timestamp",
    allow_reserved: bool = False,
    partitions: Optional[Dict[str, PartitionDefinition]] = None,
) -> Tuple[List[ChronologicalOrigin], Dict[str, Any]]:
    """
    Generate chronological rolling forecast origins for walk-forward out-of-sample evaluation.

    Strict Timing Contract (Phase 1.2 Audit):
    1. Interval-Start Semantics: Each hourly row timestamped t represents the cash-flow
       interval [t, t + 1h). At decision time t, this interval is just beginning and its
       flow is NOT yet complete.
    2. Causal History Cutoff: History available at origin t includes ONLY completed observations
       strictly earlier than t (df.iloc[0 : curr_idx]). The row at curr_idx (timestamp t) is
       strictly excluded from model history and feature computation.
    3. Forecast Target Window: The 72 forecast targets represent intervals starting at
       t, t+1h, ..., t+71h (df.iloc[curr_idx : curr_idx + horizon_hours]).
       - Target 1 (h=1): interval [t, t+1h), timestamped t.
       - Target 72 (h=72): interval [t+71h, t+72h), timestamped t+71h.
    4. Boundary Purging: Any origin where the 72nd target (t + 71h) exceeds partition_end
       is strictly purged to prevent targets from crossing into the reserved final_test partition.
       - Validation partition (1,464 candidate hours): Last valid origin is 2026-10-29 00:00:00
         (whose 72nd target is 2026-10-31 23:00:00).
       - Origins from 2026-10-29 01:00:00 to 2026-10-31 23:00:00 (71 origins) are purged.
       - Valid hourly origins count: exactly 1,393 (1,464 - 71 = 1,393).
    5. Minimum History: Requires at least min_history_hours strictly prior to curr_idx.
    6. Reserved Partition Guard: Attempting to evaluate on final_test raises PermissionError
       unless allow_reserved=True.
    7. Monotonic Chronological Continuity: Enforces strictly increasing hourly timestamps.
    """
    partition_map = partitions or STANDARD_PARTITIONS
    if partition_name not in partition_map:
        raise ValueError(
            f"Unknown partition '{partition_name}'. Available: {list(partition_map.keys())}"
        )

    partition = partition_map[partition_name]
    if partition.is_reserved and not allow_reserved:
        raise PermissionError(
            f"Partition '{partition_name}' is strictly reserved for final frozen evaluation. "
            "Model development and baseline benchmarking must use 'dev' or 'validation'."
        )

    # Ensure timestamps are pandas DatetimeIndex or Series
    ts = pd.to_datetime(df[timestamp_col])
    if not ts.is_monotonic_increasing:
        raise ValueError("DataFrame timestamps must be strictly monotonic increasing.")

    n_rows = len(df)
    valid_origins: List[ChronologicalOrigin] = []
    purged_boundary_count = 0
    insufficient_history_count = 0
    candidate_count = 0

    # Find integer index bounds for partition
    part_mask = (ts >= partition.start_time) & (ts <= partition.end_time)
    part_indices = df.index[part_mask].tolist()

    if not part_indices:
        return [], {
            "partition": partition_name,
            "error": "No records found within partition boundaries",
            "candidate_count": 0,
            "valid_origins": 0,
        }

    # Step through candidate origins in partition
    start_idx = part_indices[0]
    end_idx = part_indices[-1]

    for curr_idx in range(start_idx, end_idx + 1, step_hours):
        candidate_count += 1
        origin_time = ts.iloc[curr_idx]

        # 1. Check sufficient history available strictly before origin curr_idx
        # History is df.iloc[0 : curr_idx], so available count is curr_idx
        available_history = curr_idx
        if available_history < min_history_hours:
            insufficient_history_count += 1
            continue

        # 2. Check forward target window does not cross end of partition or dataframe
        # Target slice is df.iloc[curr_idx : curr_idx + horizon_hours]
        target_start = curr_idx
        target_end = curr_idx + horizon_hours

        if target_end > n_rows:
            purged_boundary_count += 1
            continue

        # Last target observation (h = horizon_hours) is at target_end - 1 (t + 71h)
        target_end_time = ts.iloc[target_end - 1]
        if target_end_time > partition.end_time:
            purged_boundary_count += 1
            continue

        # Valid origin confirmed: strictly disjoint history and targets
        valid_origins.append(
            ChronologicalOrigin(
                origin_idx=curr_idx,
                origin_timestamp=origin_time,
                history_start_idx=0,
                history_end_idx=curr_idx,          # STRICTLY EXCLUDES row at curr_idx (t)
                target_start_idx=target_start,     # STARTS AT curr_idx (row t, first target)
                target_end_idx=target_end,         # ENDS AT curr_idx + horizon_hours (row t + 72)
                horizon_hours=horizon_hours,
                partition_name=partition_name,
            )
        )

    metadata = {
        "partition_name": partition_name,
        "partition_start": str(partition.start_time),
        "partition_end": str(partition.end_time),
        "horizon_hours": horizon_hours,
        "min_history_hours": min_history_hours,
        "step_hours": step_hours,
        "candidate_origins": candidate_count,
        "insufficient_history_origins": insufficient_history_count,
        "purged_boundary_origins": purged_boundary_count,
        "valid_origins": len(valid_origins),
    }

    return valid_origins, metadata
