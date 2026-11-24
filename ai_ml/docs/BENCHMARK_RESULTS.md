# Phase 1.2 Forecasting Benchmark Methodology & Protocol

**Phase:** Phase 1.2 — Forecast-Origin Timing & Causality Audit  
**Status:** Frozen Methodology & Authoritative Protocol  
**Package:** `ai_ml/` (`reserve_juggler_ml`)  
**Data Protection Notice (OD-02):** Per the bounded internal research authorization, exact numerical figures, error arrays, and derived metrics from the proprietary committee dataset (`D07`) are stored strictly under the local, Git-ignored path:
`ai_ml/.local/phase1/` (`benchmark_results.json` and `phase1_summary.md`).
This tracked documentation specifies the methodology, mathematical formulations, chronological partition rules, and local reproduction commands.

---

## 1. Canonical Chronological Partition Definitions

To ensure fair comparison, prevent temporal data leakage, and mirror real-time bank treasury operations, evaluation strictly adheres to authoritative chronological partitions across the 8,760 hours of 2026:

| Partition | Start Timestamp (UTC) | End Timestamp (UTC) | Duration | Status & Purpose |
|---|---|---|---|---|
| **Development (`dev`)** | `2026-01-01 00:00:00` | `2026-08-31 23:00:00` | 243 days (5,832h) | Open for model feature exploration & training |
| **Validation (`validation`)** | `2026-09-01 00:00:00` | `2026-10-31 23:00:00` | 61 days (1,464h) | Canonical benchmark evaluation partition |
| **Final Test (`final_test`)** | `2026-11-01 00:00:00` | `2026-12-31 23:00:00` | 61 days (1,464h) | **RESERVED** (Guarded; raises `PermissionError`) |

### Authoritative Partition Evidence
- `ai_ml/docs/MODEL_SELECTION_PLAN.md` (Section 3): Formulates the 8-month development split (`dev`), 2-month validation split (`validation`), and 2-month frozen test holdout (`final_test`).
- `ai_ml/src/reserve_juggler_ml/evaluation/splits.py`: Enforces `STANDARD_PARTITIONS` with programmatic `is_reserved=True` assertion guards preventing evaluation on `final_test`.
- `ai_ml/docs/REPOSITORY_AUDIT.md` (Section 15): Confirms temporal partitions preventing lookahead bias.

---

## 2. Walk-Forward Evaluation Harness & Origin Timing Contract

### Strict Timing Contract (Phase 1.2 Resolution)
1. **Interval-Start Semantics:** Each hourly record timestamped $t$ in the treasury dataset represents the cash flow accumulating during the interval $[t, t + 1\text{h})$.
2. **Causal History Cutoff (Strict Anti-Leakage):** A treasury decision made at origin $t$ occurs at the *beginning* of the interval $[t, t + 1\text{h})$. At time $t$, this flow has not occurred yet. Therefore, model history strictly excludes the row timestamped $t$ (`df.iloc[0 : origin_idx]`). The most recent completed observation available to the model is timestamped $t - 1\text{h}$.
3. **Forecast Target Window ($H = 72$):** The 72 forecast targets represent the consecutive hourly intervals $[t, t+1\text{h}), [t+1\text{h}, t+2\text{h}), \dots, [t+71\text{h}, t+72\text{h})$, timestamped $t, t+1\text{h}, \dots, t+71\text{h}$ (`df.iloc[origin_idx : origin_idx + 72]`):
   - First target ($h=1$): interval $[t, t+1\text{h})$, timestamped $t$.
   - Last target ($h=72$): interval $[t+71\text{h}, t+72\text{h})$, timestamped $t+71\text{h}$.
4. **Target Boundary Purging:** Any origin where the 72nd target ($t + 71\text{h}$) exceeds `validation.end_time` (`2026-10-31 23:00:00`) is strictly purged to protect the reserved `final_test` holdout partition.
   - The last valid origin is **`2026-10-29 00:00:00`** (whose 72nd target is `2026-10-31 23:00:00`).
   - Origins from `2026-10-29 01:00:00` to `2026-10-31 23:00:00` (exactly **71 hourly origins**) are purged.
5. **Real Valid Origins:** Exactly **1,393 valid hourly forecast origins** ($1,464 - 71 = 1,393$).
   Each model produces $1,393 \times 72 = \mathbf{100,296}$ out-of-sample predictions per series.
6. **Coarser Evaluation Stride (Optional):** Daily evaluation (`step_hours=24`) yields **59 valid origins** (2 purged: Oct 30 and Oct 31). Hourly evaluation (`step_hours=1`, 1,393 origins) remains the primary benchmark.

---

## 3. Explicit Metric Definitions & Semantics

For both gross targets (`deposits_usd` and `withdrawals_usd`), error metrics are computed and reported with distinct names, mathematical formulas, and explicit units:

### 3.1 Lead-Time-Specific Forecast Error ($h \in \{1, 6, 24, 48, 72\}$)
Evaluates point forecast accuracy at exact lead time step $h$ across all $M = 1,393$ origins:
$$\text{MAE}_{\text{lead}}(h) = \frac{1}{M} \sum_{m=1}^M \left| y^{(m)}_{t_m + (h-1)\text{h}} - \hat{y}^{(m)}_{t_m + (h-1)\text{h}} \right|$$
$$\text{RMSE}_{\text{lead}}(h) = \sqrt{\frac{1}{M} \sum_{m=1}^M \left( y^{(m)}_{t_m + (h-1)\text{h}} - \hat{y}^{(m)}_{t_m + (h-1)\text{h}} \right)^2}$$
- **Units:** USD / hour (rate of error at specific horizon step $h$).

### 3.2 Mean Hourly Forecast Error Rate ($1..W$, $W \in \{1, 6, 24, 48, 72\}$)
The average per-hour prediction error across all lead times up to window $W$:
$$\text{MAE}_{\text{mean\_hourly}}(1..W) = \frac{1}{M \cdot W} \sum_{m=1}^M \sum_{h=1}^W \left| y^{(m)}_{t_m + (h-1)\text{h}} - \hat{y}^{(m)}_{t_m + (h-1)\text{h}} \right|$$
$$\text{RMSE}_{\text{mean\_hourly}}(1..W) = \sqrt{\frac{1}{M \cdot W} \sum_{m=1}^M \sum_{h=1}^W \left( y^{(m)}_{t_m + (h-1)\text{h}} - \hat{y}^{(m)}_{t_m + (h-1)\text{h}} \right)^2}$$
- **Units:** USD / hour (average hourly error rate over window $W$).

### 3.3 Cumulative-Total-Flow Forecast Error ($W \in \{1, 6, 24, 48, 72\}$)
Measures the aggregate cash volume error over the entire lock period. Computes the **actual sum of hourly flows before taking the absolute or squared error**:
$$\text{MAE}_{\text{cum\_total}}(W) = \frac{1}{M} \sum_{m=1}^M \left| \sum_{h=1}^W y^{(m)}_{t_m + h} - \sum_{h=1}^W \hat{y}^{(m)}_{t_m + h} \right|$$
$$\text{RMSE}_{\text{cum\_total}}(W) = \sqrt{\frac{1}{M} \sum_{m=1}^M \left( \sum_{h=1}^W y^{(m)}_{t_m + h} - \sum_{h=1}^W \hat{y}^{(m)}_{t_m + h} \right)^2}$$
- **Units:** USD total cash flow volume over the $W$-hour window.
- **Critical Semantic Distinction:** An average of hourly errors is NOT cumulative-total error. For $W=72$, summing hourly errors ($\approx 72 \times \$1.2\text{M} = \$86.4\text{M}$) overstates the true cumulative liquidity cash deficit ($\approx \$46.5\text{M}$) because intraday forecast fluctuations partially offset.

### 3.4 Mean Absolute Scaled Error (MASE)
Per Hyndman & Koehler (2006), scaled against the in-sample 24-hour daily seasonal naive difference:
$$\text{MASE}(1..W) = \frac{\text{MAE}_{\text{mean\_hourly}}(1..W)}{Q_{\text{scale}}}$$
where the in-sample scaling denominator on training series $y_{\text{train}}$ of length $T$ available at origin $t$ is:
$$Q_{\text{scale}} = \frac{1}{T - 24} \sum_{i=25}^T \left| y_{\text{train}, i} - y_{\text{train}, i-24} \right|$$
- **Units:** Dimensionless ratio. $\text{MASE} < 1.0$ indicates outperformance relative to the in-sample seasonal persistence baseline.

---

## 4. Evaluated Baseline Models

All baselines are evaluated on identical 1,393 hourly origins with zero modifications:

1. **Baseline A: Deterministic 14-Day Hourly Profile:**
   - 24-hour diurnal profile averaged from trailing 336 hours strictly prior to origin $t$.
   - Projects deterministic hour-of-day mean: $\hat{y}_{t+(j-1)\text{h}} = \bar{y}_{(t+(j-1)\text{h}).\text{hour}}$.
2. **Baseline B (24h Daily Seasonal-Naïve):**
   - Repeats trailing 24 hours: $\hat{y}_{t+(j-1)\text{h}} = y_{t+(j-1)\text{h}-24k}$ where $k = \lceil j / 24 \rceil$.
   - Primary operational fallback.
3. **Baseline B (168h Weekly Seasonal-Naïve):**
   - Repeats trailing 168 hours (7 days): $\hat{y}_{t+(j-1)\text{h}} = y_{t+(j-1)\text{h}-168}$.
   - Preserves both hour-of-day and day-of-week without model training.

---

## 5. Local Reproduction Instructions

To reproduce the benchmark evaluation locally using the verified committee dataset:

```powershell
# 1. Verify external dataset path
$env:RESERVE_JUGGLER_DATASET_PATH="C:\Users\Office Pc\OneDrive\Documents\AIML refined\treasury_4tier_dataset.csv"

# 2. Run the Phase 1.2 evaluation script
$env:PYTHONPATH="ai_ml/src"
python ai_ml/scripts/run_phase1_evaluation.py
```

The script execution will:
1. Verify SHA-256 checksum against `2e7c1d2e5b678e9975250211e7e0017022049c510e1dd90cd7f29e931837b0c5`.
2. Generate the 1,393 identical hourly walk-forward origins across the `validation` partition.
3. Compute lead-time metrics, mean hourly window metrics, and cumulative total flow metrics across all 3 baselines.
4. Save the full JSON artifact to `ai_ml/.local/phase1/benchmark_results.json`.
5. Generate the local summary markdown tables in `ai_ml/.local/phase1/phase1_summary.md`.

---

## 6. Key Empirical Findings (Phase 1.2 Timing & Causality Audit)

1. **Strict Interval-Start Causality Verified:**
   - History strictly excludes the origin row ($t$). A forecast made at $t$ cannot observe the flow of $[t, t+1\text{h})$.
   - Mutating values in the origin row produces zero change in predictions, confirming 100% causal isolation.
2. **Baseline B (24h) Day-of-Week Compounding:**
   - On hourly walk-forward evaluation, the 24h seasonal naïve model suffers severe degradation beyond $h=24$, with $\text{MASE}$ deteriorating from $1.00$ at $24$h to $1.15$ at $72$h. When origins fall on Thursdays and Fridays, repeating the previous 24 hours forces weekday volumes onto weekends and weekend lulls onto Mondays.
3. **Superiority of Weekly Seasonality:**
   - Baseline B (168h weekly naïve) maintains consistent $\text{MASE} \approx 0.77$ across 72 hours, achieving the lowest cumulative cash flow error (\$31.5M for deposits, \$34.1M for withdrawals) by preserving the day-of-week profile.
4. **Implication for Phase 2 Tree Models (Random Forest & XGBoost):**
   - Direct multi-step tree regressors must include both diurnal hour-of-day and weekly calendar features (day-of-week, is_weekend, lag 168) alongside short-term causal lags strictly prior to origin $t$ to exceed the 168h weekly benchmark.

