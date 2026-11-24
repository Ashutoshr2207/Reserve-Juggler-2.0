# Phase 2 — Random Forest and XGBoost Forecasting Comparison

**Date:** 18 October 2026  
**Scope:** Standalone AI/ML Module (`ai_ml/`)  
**Status:** Complete — Validation Benchmark Executed  
**Local Artifact Directory:** `ai_ml/.local/phase2/` (Strictly Git-Ignored)

---

## 1. Executive Summary & Objective

Phase 2 implements, trains, and rigorously benchmarks two advanced machine learning forecasters against the three established Phase 1 baselines:
1. **Candidate A:** Random Forest direct multi-horizon regressor (`RandomForestForecaster`).
2. **Candidate B:** XGBoost direct multi-horizon gradient boosted trees (`XGBoostForecaster`).
3. **Baselines:**
   - Baseline A: 14-day deterministic hourly profile (`DeterministicBaseline`, lookback=336h).
   - Baseline B (24h): 24-hour diurnal seasonal-naïve (`SeasonalNaiveForecaster`, season=24h).
   - Baseline B (168h): 168-hour weekly seasonal-naïve (`SeasonalNaiveForecaster`, season=168h).

Both candidates predict **gross deposits** (`deposits_usd`) and **gross withdrawals** (`withdrawals_usd`) separately across a **72-hour planning horizon** ($H = 72$) with hourly resolution.

---

## 2. Dataset Constraints & Governance

1. **Authorized Scope:** Evaluation is conducted on the verified synthetic committee dataset (`treasury_4tier_dataset.csv`, SHA-256: `2e7c1d2e5b678e9975250211e7e0017022049c510e1dd90cd7f29e931837b0c5`).
2. **Denomination:** The dataset is denominated in USD. All benchmark metrics remain in USD. No arbitrary conversion to INR is performed.
3. **Partition Isolation:**
   - **Development (`dev`):** 2026-01-01 to 2026-08-31 (5,832 hours). All supervised parameter fitting is strictly confined to this partition.
   - **Validation (`validation`):** 2026-09-01 to 2026-10-31 (1,464 hours). Exactly 1,393 valid hourly origins evaluated.
   - **Final Test (`final_test`):** 2026-11-01 to 2026-12-31 (1,464 hours). **Strictly reserved holdout.** Untouched, uninspected, and guarded by runtime `PermissionError`.
4. **Data Protection:** Per repository data governance, detailed numerical results, serialized model weights, and derived arrays are stored exclusively in `ai_ml/.local/phase2/` and are excluded from Git tracking.

---

## 3. Causal Feature Architecture

Both candidates use an identical, strictly causal 22-dimensional feature vector extracted at forecast origin $t$ (`CAUSAL_FEATURE_NAMES` in `reserve_juggler_ml.features.causal`):

| Feature Category | Features | Description & Temporal Guard |
|---|---|---|
| **Cyclical Calendar** | `hour_sin`, `hour_cos`, `dow_sin`, `dow_cos`, `is_weekend` | Deterministic encodings of forecast origin timestamp $t$. |
| **Autoregressive Lags** | `lag_1`, `lag_2`, `lag_3`, `lag_24`, `lag_48`, `lag_72`, `lag_168` | Completed flow observations strictly prior to $t$ ($y_{t-1}, y_{t-2}, \dots, y_{t-168}$). |
| **Trailing 24h Statistics** | `roll_sum_24`, `roll_mean_24`, `roll_std_24`, `roll_min_24`, `roll_max_24` | Summary statistics computed over trailing 24 hours $[t-24, t-1]$. |
| **Trailing 168h Statistics** | `roll_sum_168`, `roll_mean_168`, `roll_std_168`, `roll_min_168`, `roll_max_168` | Summary statistics computed over trailing 7 days $[t-168, t-1]$. |

### Anti-Leakage Protocol:
- **Interval-Start Semantics:** Row timestamped $t$ represents interval $[t, t+1\text{h})$. At origin $t$, this flow is incomplete and strictly excluded from features.
- **Target Windows:** Forward targets are intervals starting at $t, t+1\text{h}, \dots, t+71\text{h}$.
- **Zero Lookahead:** Features are calculated strictly from observations strictly $< t$.

---

## 4. Candidate Model Architecture & Hyperparameters

### Candidate A — Random Forest (`RandomForestForecaster`)
- **Location:** `ai_ml/src/reserve_juggler_ml/forecasting/random_forest.py`
- **Architecture:** Direct multi-horizon regression using scikit-learn's native multi-output `RandomForestRegressor`.
- **Hyperparameters:**
  - `n_estimators`: 100
  - `max_depth`: 12
  - `min_samples_split`: 5
  - `min_samples_leaf`: 2
  - `random_state`: 42 (fully reproducible)
  - `n_jobs`: -1 (all available CPU cores)
- **Constraint Handling:** Non-negative flow clamping (`np.maximum(y_pred, 0.0)`).
- **Inference Latency:** Recorded per origin (`last_inference_ms_`).

### Candidate B — XGBoost (`XGBoostForecaster`)
- **Location:** `ai_ml/src/reserve_juggler_ml/forecasting/xgboost_forecaster.py`
- **Architecture:** Direct multi-horizon gradient boosted trees using `xgb.XGBRegressor` with histogram-based partitioning.
- **Hyperparameters:**
  - `n_estimators`: 100
  - `max_depth`: 5
  - `learning_rate`: 0.08
  - `subsample`: 0.8
  - `colsample_bytree`: 0.8
  - `tree_method`: `"hist"` (CPU-optimized)
  - `random_state`: 42 (deterministic)
  - `n_jobs`: -1
- **Constraint Handling:** Non-negative flow clamping (`np.maximum(y_pred, 0.0)`).
- **Inference Latency:** Recorded per origin (`last_inference_ms_`).

---

## 5. Evaluation Protocol & Origin Mathematics

- **Partition:** Validation (Months 9–10: 2026-09-01 00:00:00 to 2026-10-31 23:00:00; 1,464 candidate hours).
- **Lookback Requirement:** Minimum 336 hours (14 days).
- **Forward Horizon:** 72 consecutive hours.
- **Purged Boundaries:** 71 boundary origins purged (origins 2026-10-29 01:00 to 2026-10-31 23:00) because their 72-hour window would cross into the reserved `final_test` partition.
- **Valid Hourly Origins:** Exactly **1,393 origins** evaluated per model per target ($100,296$ total predictions per model).
- **Metrics Evaluated:**
  1. **Lead-Time Error:** MAE and RMSE at exact lead times $h \in \{1, 6, 24, 48, 72\}$.
  2. **Mean Hourly Error:** Average hourly MAE and RMSE across cumulative windows $W \in \{1, 6, 24, 48, 72\}$.
  3. **Cumulative Total Flow Error:** Discrepancy in cumulative liquidity volume $|\sum_{h=1}^W y_{t+h} - \sum_{h=1}^W \hat{y}_{t+h}|$.
  4. **MASE:** Scaled against in-sample 24-hour seasonal-naïve scale $Q$.

- **Interpretation Note:** Point-forecast and cumulative comparisons represent observed empirical improvements on the out-of-sample validation partition, not formal hypothesis-tested statistical significance.
- **Path Deficit Distinction:** Cumulative gross-deposit or gross-withdrawal total-flow error ($|\sum y - \sum \hat{y}|$) is distinct from the maximum cumulative liquidity deficit. Maximum path deficit depends on the intra-horizon chronological cash-flow path and investment lock constraints (modeled separately in Phase 4).

---

## 6. How to Reproduce Locally

To reproduce the complete Phase 2 benchmark on a local workstation:

```bash
# 1. Activate your Python environment (Python 3.12+)
# 2. Run the Phase 2 evaluation runner:
python ai_ml/scripts/run_phase2_evaluation.py

# 3. Run the unit test suite:
pytest ai_ml/tests/
```

Outputs will be generated under `ai_ml/.local/phase2/`:
- `benchmark_results.json`: Full numerical metric matrices across all lead times, windows, and models.
- `phase2_summary.md`: Detailed comparison tables and relative percentage improvements.
- `models/`: Trained model binaries for Random Forest and XGBoost.
