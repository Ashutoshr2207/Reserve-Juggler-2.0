"""Evaluation module for Reserve Juggler ML."""

from reserve_juggler_ml.evaluation.metrics import (
    evaluate_forecast_summary,
    interval_coverage_probability,
    lead_time_coverage,
    lead_time_width,
    mean_absolute_error,
    mean_absolute_scaled_error,
    mean_interval_width,
    pinball_loss,
    root_mean_squared_error,
    window_coverage,
    window_width,
)

from reserve_juggler_ml.evaluation.splits import (
    ChronologicalOrigin,
    PartitionDefinition,
    STANDARD_PARTITIONS,
    generate_rolling_origins,
)

from reserve_juggler_ml.evaluation.benchmark import (
    CUMULATIVE_WINDOWS,
    ModelBenchmarkResult,
    WindowMetric,
    evaluate_model_on_origins,
)

__all__ = [
    "mean_absolute_error",
    "root_mean_squared_error",
    "mean_absolute_scaled_error",
    "interval_coverage_probability",
    "mean_interval_width",
    "lead_time_coverage",
    "lead_time_width",
    "window_coverage",
    "window_width",
    "pinball_loss",
    "evaluate_forecast_summary",
    "PartitionDefinition",
    "STANDARD_PARTITIONS",
    "ChronologicalOrigin",
    "generate_rolling_origins",
    "CUMULATIVE_WINDOWS",
    "ModelBenchmarkResult",
    "WindowMetric",
    "evaluate_model_on_origins",
]


