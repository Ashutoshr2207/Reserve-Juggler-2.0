"""
Reproducible CLI evaluation runner for Phase 1 forecasting baselines.
Evaluates:
  1. Baseline A: Deterministic 14-day hourly diurnal baseline.
  2. Baseline B (24h): Seasonal-naïve 24-hour daily cycle.
  3. Baseline B (168h): Seasonal-naïve 168-hour weekly cycle.

Evaluated on the external D07 committee dataset (USD-denominated).
Evaluates 1-hour walk-forward origins across the validation partition.
Results are stored locally under `ai_ml/.local/phase1/` (strictly Git-ignored).
"""

import json
from pathlib import Path
import sys
import time

# Ensure ai_ml/src is in pythonpath
SCRIPT_DIR = Path(__file__).resolve().parent
AI_ML_ROOT = SCRIPT_DIR.parent
SRC_DIR = AI_ML_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd

from reserve_juggler_ml.data.loader import (
    audit_committee_dataset,
    load_committee_dataset,
)
from reserve_juggler_ml.evaluation.benchmark import (
    CUMULATIVE_WINDOWS,
    LEAD_TIME_HORIZONS,
    evaluate_model_on_origins,
)
from reserve_juggler_ml.evaluation.splits import (
    STANDARD_PARTITIONS,
    generate_rolling_origins,
)
from reserve_juggler_ml.forecasting.baseline import DeterministicBaseline
from reserve_juggler_ml.forecasting.seasonal import SeasonalNaiveForecaster


def run_phase1_benchmark(
    partition_name: str = "validation",
    step_hours: int = 1,
    horizon_hours: int = 72,
    min_history_hours: int = 336,
) -> Path:
    print("=" * 75)
    print("RESERVE JUGGLER AI/ML — PHASE 1.2 FORECAST-ORIGIN TIMING & CAUSALITY PROTOCOL")
    print("=" * 75)

    # 1. Audit and verify committee dataset
    print("\n[1/5] Verifying external committee dataset...")
    audit = audit_committee_dataset()
    print(f"  Dataset path: {audit['filepath']}")
    print(f"  SHA-256:      {audit['sha256']}")
    print(f"  Verified:     {audit['sha256_verified']}")
    print(f"  Dimensions:   {audit['row_count']} rows, {audit['column_count']} columns")
    print(f"  Currency:     {audit['currency']} (USD synthetic banking data)")

    if not audit["sha256_verified"]:
        raise ValueError("Dataset SHA-256 verification failed!")

    # 2. Load dataset in read-only mode
    print("\n[2/5] Loading dataset into memory (zero copies/modifications)...")
    df = load_committee_dataset(verify_checksum=True)

    # 3. Generate chronological rolling origins with boundary purging
    stride_label = "hourly (step=1h)" if step_hours == 1 else f"stride={step_hours}h"
    print(f"\n[3/5] Generating chronological rolling origins for partition '{partition_name}' ({stride_label})...")
    origins, origin_meta = generate_rolling_origins(
        df=df,
        partition_name=partition_name,
        horizon_hours=horizon_hours,
        min_history_hours=min_history_hours,
        step_hours=step_hours,
    )
    print(f"  Partition range:      {origin_meta['partition_start']} to {origin_meta['partition_end']}")
    print(f"  Candidate origins:    {origin_meta['candidate_origins']}")
    print(f"  Insufficient history: {origin_meta['insufficient_history_origins']}")
    print(f"  Purged boundaries:    {origin_meta['purged_boundary_origins']} (full {horizon_hours}h target window required)")
    print(f"  Valid origins:        {origin_meta['valid_origins']}")

    if not origins:
        raise RuntimeError("No valid origins found for evaluation!")

    # 4. Define baseline model candidates to evaluate
    models_to_evaluate = [
        ("Baseline A (14d Deterministic)", lambda: DeterministicBaseline(lookback_hours=336)),
        ("Baseline B (24h Seasonal-Naïve)", lambda: SeasonalNaiveForecaster(season_length=24)),
        ("Baseline B (168h Weekly-Naïve)", lambda: SeasonalNaiveForecaster(season_length=168)),
    ]

    targets = [
        ("deposits_usd", "Gross Deposits (USD)"),
        ("withdrawals_usd", "Gross Withdrawals (USD)"),
    ]

    results = []
    print("\n[4/5] Executing walk-forward evaluation across identical origins...")

    for model_label, model_factory in models_to_evaluate:
        print(f"\n--- Evaluating {model_label} ---")
        for target_col, target_label in targets:
            print(f"  Target: {target_label} ...", end=" ", flush=True)
            t_start = time.time()
            res = evaluate_model_on_origins(
                df=df,
                origins=origins,
                model_factory=model_factory,
                target_col=target_col,
                currency="USD",
                seasonality_for_mase=24,
                windows=CUMULATIVE_WINDOWS,
                lead_times=LEAD_TIME_HORIZONS,
            )
            elapsed = time.time() - t_start
            m72 = res.window_metrics[72]
            print(
                f"Done ({elapsed:.2f}s). "
                f"72h Mean Hourly MAE: ${m72.mean_hourly_mae:,.2f}/hr, "
                f"72h Cum Total MAE: ${m72.cumulative_total_mae:,.2f}"
            )
            results.append(res)

    # 5. Save detailed local results
    print("\n[5/5] Saving detailed results to Git-ignored local directory...")
    local_dir = AI_ML_ROOT / ".local" / "phase1"
    local_dir.mkdir(parents=True, exist_ok=True)

    json_path = local_dir / "benchmark_results.json"
    output_payload = {
        "benchmark_phase": "Phase 1.2 Forecast-Origin Timing & Causality Validated Protocol",
        "dataset_audit": audit,
        "origin_metadata": origin_meta,
        "evaluation_partition": partition_name,
        "stride_hours": step_hours,
        "windows_evaluated": CUMULATIVE_WINDOWS,
        "lead_times_evaluated": LEAD_TIME_HORIZONS,
        "results": [r.to_dict() for r in results],
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)
    print(f"  Saved JSON: {json_path}")

    # Generate local summary report
    summary_path = local_dir / "phase1_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# Phase 1.2 Local Benchmark Evaluation Summary\n\n")
        f.write(f"- **Benchmark Protocol:** Hourly Walk-Forward Evaluation (`step_hours={step_hours}`, strict interval-start cutoff)\n")
        f.write(f"- **Dataset:** `{audit['filepath']}`\n")
        f.write(f"- **SHA-256:** `{audit['sha256']}`\n")
        f.write(f"- **Partition:** `{partition_name}` ({origin_meta['partition_start']} to {origin_meta['partition_end']})\n")
        f.write(f"- **Candidate Origins:** {origin_meta['candidate_origins']} hourly origins\n")
        f.write(f"- **Purged Boundary Origins:** {origin_meta['purged_boundary_origins']} (final {horizon_hours} hours purged to protect partition boundary)\n")
        f.write(f"- **Valid Origins Evaluated:** {origin_meta['valid_origins']} identical origins per model\n")
        f.write(f"- **Total Predictions per Series:** {origin_meta['valid_origins'] * horizon_hours:,} predictions\n")
        f.write(f"- **Forecast Horizon:** {horizon_hours} hours\n")
        f.write(f"- **Currency:** USD (D07 Synthetic Treasury Data, unmodified)\n\n")

        f.write("## 1. Mean Hourly Forecast Error Rates (USD / hr)\n\n")
        f.write("Averaged hourly error across forecast lead times 1..W:\n")
        f.write("$$\\text{MAE}_{\\text{mean}} = \\frac{1}{M \\cdot W} \\sum_{m=1}^M \\sum_{h=1}^W |y_{m, h} - \\hat{y}_{m, h}|$$\n\n")
        f.write("| Model | Target | Window | Mean Hourly MAE (USD/hr) | Mean Hourly RMSE (USD/hr) | MASE | In-Sample Scale Q (USD/hr) |\n")
        f.write("|---|---|---|---:|---:|---:|---:|\n")
        for res in results:
            for w in CUMULATIVE_WINDOWS:
                m = res.window_metrics[w]
                f.write(
                    f"| {res.model_name} | {res.target_name} | {w}h | "
                    f"${m.mean_hourly_mae:,.2f} | ${m.mean_hourly_rmse:,.2f} | {m.mase:.4f} | ${m.mase_denominator_scale:,.2f} |\n"
                )

        f.write("\n## 2. Cumulative Total Flow Forecast Errors (USD Total Volume)\n\n")
        f.write("Actual sum of hourly flows before taking forecast error across horizon window W:\n")
        f.write("$$\\text{MAE}_{\\text{cum}} = \\frac{1}{M} \\sum_{m=1}^M \\left| \\sum_{h=1}^W y_{m, h} - \\sum_{h=1}^W \\hat{y}_{m, h} \\right|$$\n\n")
        f.write("| Model | Target | Window | Cum Total MAE (USD) | Cum Total RMSE (USD) |\n")
        f.write("|---|---|---|---:|---:|\n")
        for res in results:
            for w in CUMULATIVE_WINDOWS:
                m = res.window_metrics[w]
                f.write(
                    f"| {res.model_name} | {res.target_name} | {w}h | "
                    f"${m.cumulative_total_mae:,.2f} | ${m.cumulative_total_rmse:,.2f} |\n"
                )

        f.write("\n## 3. Lead-Time-Specific Forecast Errors (USD / hr)\n\n")
        f.write("Point forecast error at exact forecast lead time step h:\n")
        f.write("$$\\text{MAE}_{\\text{lead}}(h) = \\frac{1}{M} \\sum_{m=1}^M |y_{m, h} - \\hat{y}_{m, h}|$$\n\n")
        f.write("| Model | Target | Horizon h | Lead-Time MAE (USD/hr) | Lead-Time RMSE (USD/hr) | Samples |\n")
        f.write("|---|---|---|---:|---:|---:|\n")
        for res in results:
            for h in LEAD_TIME_HORIZONS:
                lt = res.lead_time_metrics[h]
                f.write(
                    f"| {res.model_name} | {res.target_name} | h={h} | "
                    f"${lt.mae:,.2f} | ${lt.rmse:,.2f} | {lt.sample_count} |\n"
                )

    print(f"  Saved Summary: {summary_path}")
    print("\nPhase 1.1 Benchmark Protocol Validation Complete!")
    return summary_path


if __name__ == "__main__":
    run_phase1_benchmark()

