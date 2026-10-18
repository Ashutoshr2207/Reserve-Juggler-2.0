# Phase 3 — Prediction-Interval Calibration Methodology & Architecture

**Date:** 18 October 2026  
**Scope:** Standalone AI/ML Module (`ai_ml/`)  
**Status:** Complete — Validation Calibration Executed  
**Local Artifact Directory:** `ai_ml/.local/phase3/` (Strictly Git-Ignored)

---

## 1. Objective & Scope

Phase 3 establishes mathematically sound, out-of-sample calibrated prediction intervals for all forecasting models:
1. **Deterministic 14-Day Baseline** (`DeterministicBaseline`)
2. **Seasonal-Naïve (24h Diurnal)** (`SeasonalNaiveForecaster`)
3. **Seasonal-Naïve (168h Weekly)** (`SeasonalNaiveForecaster`)
4. **Random Forest Forecaster** (`RandomForestForecaster`)
5. **XGBoost Forecaster** (`XGBoostForecaster`)

### Core Problem Solved
Initial heuristic prediction intervals used Gaussian standard error scaling ($z_{1-\alpha/2} \cdot \sigma$) based on in-sample residuals. This heuristic failed in two ways:
1. In-sample residual variance severely underestimates out-of-sample forecast errors (especially for flexible gradient-boosted trees), leading to 5% to 7% empirical under-coverage on unseen data.
2. Forecast error distributions are non-Gaussian, fat-tailed, and strongly lead-time dependent (errors at $h=1$ are substantially smaller than errors at $h=72$).

Phase 3 implements **lead-time-specific empirical residual quantile calibration**, replacing Gaussian assumptions with non-parametric empirical quantile offsets computed on a dedicated out-of-sample calibration split.

---

## 2. Chronological Subdivision & Data Governance

To calibrate out-of-sample intervals without leaking information from the validation partition or compromising the reserved final test set, the accepted development period (Months 1–8) was chronologically subdivided:

```text
Full Observation Timeline (8,760 hours / 365 days)
├──────────────────── Development Partition (Months 1–8) ────────────────────┤
├─ Fit Period (M1–7: Jan–Jul) ─┤─ Calibration (M8: Aug) ─┤
[4,681 Supervised Samples]      [673 Calibration Origins]
                                                           ├─ Validation (M9–10: Sep–Oct) ─┤─ Final Test (M11–12) ─┤
                                                           [1,393 Validation Origins]      [Strictly Reserved]
```

### Chronological Roles:
1. **Model Parameter Fitting (Jan 1 – Jul 31, 2026; 5,088 hours):**
   - 4,681 valid origins ($X \in \mathbb{R}^{4681 \times 22}, Y \in \mathbb{R}^{4681 \times 72}$).
   - 71 boundary origins purged at the end of July so forward targets strictly remain $\le$ July 31.
2. **Interval Calibration (Aug 1 – Aug 31, 2026; 744 hours):**
   - Model parameters are completely frozen.
   - Models generate 72-hour point forecasts across all 673 valid August origins using history strictly $< t$.
   - Realized August flows are compared against forecasts to form residual matrices:
     $$e_{t, h} = y_{t+h} - \hat{y}_{t+h}, \quad t \in \text{August Origins}, \; h \in \{1, \dots, 72\}$$
   - Yields 673 out-of-sample calibration residuals per lead time $h$.
   - 71 boundary origins purged at the end of August so targets do not cross into September.
3. **Validation Assessment (Sep 1 – Oct 31, 2026; 1,464 hours):**
   - 1,393 valid hourly origins evaluated using frozen calibrators.
   - Final evaluation of Interval Coverage Probability (ICP) and Mean Interval Width (MIW).
4. **Final Test Holdout (Nov 1 – Dec 31, 2026):**
   - Strictly reserved. No access or evaluation permitted during Phase 3.

---

## 3. Mathematical Formulation

### 3.1 Empirical Quantile Rule
For a designated nominal coverage level $1 - \alpha$ ($\alpha \in \{0.10, 0.05, 0.01\}$ for 90%, 95%, 99% intervals):
- Lower residual quantile: $\tau_{\text{low}} = \frac{\alpha}{2}$
- Upper residual quantile: $\tau_{\text{high}} = 1 - \frac{\alpha}{2}$

For each lead time $h \in \{1, \dots, 72\}$, quantiles are computed from the 673 August residuals $\mathbf{e}_h = [e_{1, h}, e_{2, h}, \dots, e_{N, h}]$:
$$q_{\text{low}}(h, \alpha) = \text{Quantile}(\mathbf{e}_h, \tau_{\text{low}})$$
$$q_{\text{high}}(h, \alpha) = \text{Quantile}(\mathbf{e}_h, \tau_{\text{high}})$$

### 3.2 Interval Construction & Non-Negative Cash-Flow Bounds
Given point forecast $\hat{y}_{t+h}$, the raw calibrated interval is:
$$\hat{L}_{t+h}^{\text{raw}} = \hat{y}_{t+h} + q_{\text{low}}(h, \alpha)$$
$$\hat{U}_{t+h}^{\text{raw}} = \hat{y}_{t+h} + q_{\text{high}}(h, \alpha)$$

Because gross receipts and gross disbursements cannot be negative in primary banking applications, post-processing enforces strict bounding contracts:
$$\hat{L}_{t+h} = \min\left(\hat{y}_{t+h}, \max\left(0.0, \hat{L}_{t+h}^{\text{raw}}\right)\right)$$
$$\hat{U}_{t+h} = \max\left(\hat{y}_{t+h}, \hat{L}_{t+h}, \hat{U}_{t+h}^{\text{raw}}\right)$$

This mathematical formulation guarantees:
1. Non-negativity: $\hat{L}_{t+h} \ge 0.0$.
2. Bound order: $0.0 \le \hat{L}_{t+h} \le \hat{y}_{t+h} \le \hat{U}_{t+h}$.
3. Zero coverage loss: Clamping $\hat{L}$ at $0.0$ never excludes a realization $y \ge 0$, while reducing interval width. Empirical delta on validation coverage across all 30 evaluated combinations is exactly $+0.00000$, with interval width reductions of up to $2,265,884.

---

## 4. Empirical Validation Results & Claims Reconciliation

### 4.1 Chronological Evaluation Metrics (Validation Partition: Sep 1 – Oct 31, 2026)

All empirical metrics are evaluated on the held-out validation partition across **1,393 hourly origins**, yielding **100,296 total prediction points** per candidate and target ($1,393 \text{ origins} \times 72 \text{ lead times}$).

| Target | Candidate Model | Nominal Level | Realized ICP | Target ICP | Coverage Error (pp) | Relative Error (%) | Mean Interval Width ($) | Uncalibrated Heuristic ICP |
|---|---|---|---|---|---|---|---|---|
| deposits_usd | Deterministic Baseline (14d) | 90% | 0.8666 | 0.90 | -3.34 pp | -3.71% | $4,128,429 | 0.9685 |
| deposits_usd | Deterministic Baseline (14d) | 95% | 0.9319 | 0.95 | -1.81 pp | -1.91% | $5,364,649 | 0.9800 |
| deposits_usd | Deterministic Baseline (14d) | 99% | 0.9689 | 0.99 | -2.11 pp | -2.13% | $11,383,705 | 0.9842 |
| deposits_usd | Seasonal Naive (24h) | 90% | 0.8947 | 0.90 | -0.53 pp | -0.59% | $6,658,587 | 0.9467 |
| deposits_usd | Seasonal Naive (24h) | 95% | 0.9354 | 0.95 | -1.46 pp | -1.54% | $8,504,799 | 0.9605 |
| deposits_usd | Seasonal Naive (24h) | 99% | 0.9709 | 0.99 | -1.91 pp | -1.93% | $16,509,834 | 0.9639 |
| deposits_usd | Seasonal Naive (168h) | 90% | 0.9011 | 0.90 | +0.11 pp | +0.12% | $4,131,858 | 0.9641 |
| deposits_usd | Seasonal Naive (168h) | 95% | 0.9424 | 0.95 | -0.76 pp | -0.80% | $5,702,007 | 0.9641 |
| deposits_usd | Seasonal Naive (168h) | 99% | 0.9799 | 0.99 | -1.01 pp | -1.02% | $18,972,634 | 0.9641 |
| deposits_usd | Random Forest | 90% | 0.8766 | 0.90 | -2.34 pp | -2.60% | $3,034,399 | 0.9118 |
| deposits_usd | Random Forest | 95% | 0.9342 | 0.95 | -1.58 pp | -1.66% | $4,110,461 | 0.9411 |
| deposits_usd | Random Forest | 99% | 0.9825 | 0.99 | -0.75 pp | -0.76% | $13,320,648 | 0.9677 |
| deposits_usd | **XGBoost** | 90% | **0.8935** | 0.90 | **-0.65 pp** | -0.72% | **$3,491,358** | 0.8478 |
| deposits_usd | **XGBoost** | 95% | **0.9474** | 0.95 | **-0.26 pp** | -0.27% | **$4,872,367** | 0.8897 |
| deposits_usd | **XGBoost** | 99% | **0.9863** | 0.99 | **-0.37 pp** | -0.37% | **$13,922,086** | 0.9383 |
| withdrawals_usd | Deterministic Baseline (14d) | 90% | 0.8691 | 0.90 | -3.09 pp | -3.43% | $5,573,440 | 0.9235 |
| withdrawals_usd | Deterministic Baseline (14d) | 95% | 0.9270 | 0.95 | -2.30 pp | -2.42% | $7,427,612 | 0.9532 |
| withdrawals_usd | Deterministic Baseline (14d) | 99% | 0.9786 | 0.99 | -1.14 pp | -1.15% | $12,437,672 | 0.9735 |
| withdrawals_usd | Seasonal Naive (24h) | 90% | 0.8740 | 0.90 | -2.60 pp | -2.89% | $8,039,781 | 0.8951 |
| withdrawals_usd | Seasonal Naive (24h) | 95% | 0.9174 | 0.95 | -3.26 pp | -3.43% | $10,171,137 | 0.9244 |
| withdrawals_usd | Seasonal Naive (24h) | 99% | 0.9701 | 0.99 | -1.99 pp | -2.01% | $15,003,195 | 0.9590 |
| withdrawals_usd | Seasonal Naive (168h) | 90% | 0.8995 | 0.90 | -0.05 pp | -0.06% | $6,288,560 | 0.9204 |
| withdrawals_usd | Seasonal Naive (168h) | 95% | 0.9398 | 0.95 | -1.02 pp | -1.07% | $9,110,042 | 0.9377 |
| withdrawals_usd | Seasonal Naive (168h) | 99% | 0.9874 | 0.99 | -0.26 pp | -0.26% | $16,867,769 | 0.9579 |
| withdrawals_usd | Random Forest | 90% | 0.9023 | 0.90 | +0.23 pp | +0.26% | $4,334,381 | 0.8726 |
| withdrawals_usd | Random Forest | 95% | 0.9417 | 0.95 | -0.83 pp | -0.87% | $5,972,060 | 0.9052 |
| withdrawals_usd | Random Forest | 99% | 0.9890 | 0.99 | -0.10 pp | -0.10% | $11,949,554 | 0.9404 |
| withdrawals_usd | **XGBoost** | 90% | **0.8984** | 0.90 | **-0.16 pp** | -0.18% | **$4,356,494** | 0.8320 |
| withdrawals_usd | **XGBoost** | 95% | **0.9452** | 0.95 | **-0.48 pp** | -0.51% | **$5,958,765** | 0.8746 |
| withdrawals_usd | **XGBoost** | 99% | **0.9915** | 0.99 | **+0.15 pp** | +0.15% | **$11,818,999** | 0.9273 |

### 4.2 Reconciliation of Coverage Claims

#### Discrepancy Analysis
An earlier draft summarized the Phase 3 outcome with the broad statement that *"calibration maintains coverage within ±0.8% of nominal across candidates."* **This claim was an overgeneralization and is factually incorrect when applied across all five models.**

As evidenced in the table above:
1. **Deterministic Baseline (14d)** exhibits significant under-coverage:
   - Deposits 90% nominal: realized coverage is **86.66%** (error: **-3.34 percentage points** / -3.71% relative).
   - Withdrawals 95% nominal: realized coverage is **92.70%** (error: **-2.30 percentage points** / -2.42% relative).
2. **Seasonal Naïve (24h)** exhibits under-coverage up to **-3.26 percentage points**:
   - Withdrawals 95% nominal: realized coverage is **91.74%** (error: **-3.26 percentage points** / -3.43% relative).
3. **Random Forest** exhibits under-coverage on deposits:
   - Deposits 90% nominal: realized coverage is **87.66%** (error: **-2.34 percentage points** / -2.60% relative).

#### Model-Specific Fact: XGBoost Validity
The claim of tight calibration within $\pm 0.8$ percentage points **is strictly true only for XGBoost**. 
Across all six target and coverage combinations:
- Deposits 90%: 89.35% ($-0.65$ pp)
- Deposits 95%: 94.74% ($-0.26$ pp)
- Deposits 99%: 98.63% ($-0.37$ pp)
- Withdrawals 90%: 89.84% ($-0.16$ pp)
- Withdrawals 95%: 94.52% ($-0.48$ pp)
- Withdrawals 99%: 99.15% ($+0.15$ pp)

**Maximum absolute coverage error for XGBoost across all settings is 0.65 percentage points** (well within $\pm 0.8$ pp).

#### Technical Rationale for Baseline / Random Forest Divergence
The baseline models and Random Forest exhibit greater coverage decay from August to Sep–Oct because their point forecasts have higher variance and bias drift when transitioning across seasonal regimes. In contrast, XGBoost's point forecast errors remain stationary and zero-centered between August and the autumn validation months, allowing empirical residual quantiles to transfer with high fidelity.

---

## 5. Implementation & Methodological Verification

### 5.1 Partition Origin Verification
The chronological rolling origin generation was verified against `reserve_juggler_ml.evaluation.splits`:
- **Fit Partition (Jan 1 – Jul 31, 2026; 212 days = 5,088 hours):**
  - Lookback warm-up requirement: $T_{\text{lookback}} = 336\text{ hours}$ (14 days). First 336 origins (indices 0 to 335) are skipped due to insufficient history ($336$ skipped).
  - Horizon boundary purging: 72-hour forward targets must not cross July 31 23:00. Candidate origins where $t + 71 > 5,087$ (indices 5,017 to 5,087) are purged ($71$ purged).
  - **Valid Fit Origins:** $5,088 - 336 - 71 = \mathbf{4,681}$ origins.
- **Calibration Partition (Aug 1 – Aug 31, 2026; 31 days = 744 hours):**
  - Warm-up: Available history $\ge 5,088 \gg 336$ hours ($0$ skipped).
  - Boundary purging: Forward targets must not cross Aug 31 23:00 ($71$ purged).
  - **Valid Calibration Origins:** $744 - 0 - 71 = \mathbf{673}$ origins.
- **Validation Partition (Sep 1 – Oct 31, 2026; 61 days = 1,464 hours):**
  - Warm-up: Available history $\ge 5,832 \gg 336$ hours ($0$ skipped).
  - Boundary purging: Forward targets must not cross Oct 31 23:00 ($71$ purged).
  - **Valid Validation Origins:** $1,464 - 0 - 71 = \mathbf{1,393}$ origins.
- **Evaluation Denominator:**
  - Total pooled predictions per model and target: $1,393 \times 72 = \mathbf{100,296}$ predictions.
  - Across 5 models $\times$ 2 targets: $1,002,960$ predictions scored across 3 nominal levels.
  - Lead-time specific metrics ($h=1, 6, 24, 48, 72$) use denominator $N = 1,393$.
  - Window metrics ($w=6, 24, 48, 72$) use denominator $N = 1,393 \times w$.

### 5.2 Finite-Sample Tail Quantile Convention
- Empirical quantiles are computed using standard linear interpolation (`numpy.quantile(..., method='linear')`).
- For August sample size $N = 673$ and $\alpha = 0.01$ (99% nominal coverage), the tail probability $\tau_{\text{low}} = 0.005$ corresponds to $673 \times 0.005 = 3.365$ expected tail observations.
- While sufficient for an empirical approximation, extreme tails (99%) are subject to finite-sample volatility. The system issues an explicit logging notification whenever tail sample count is $< 5$.

### 5.3 Governance & Environmental Limitations
1. **Temporal Dependence:** Forecast errors across overlapping 72-hour forecast horizons are autocorrelated. Theoretical exchangeability assumptions required for exact finite-sample conformal prediction guarantees do not strictly hold for rolling time series. Metrics reported here are empirical validation results on out-of-sample data.
2. **Synthetic USD Dataset Limitation:** All evaluations are conducted on the synthetic USD 4-tier banking committee dataset. These results are **not production-ready** and provide **no empirical evidence of performance in INR-denominated or Indian banking liquidity regimes**.
3. **Reservation of Final Test Partition:** The November–December 2026 partition remains strictly reserved and untouched. Access attempts are halted at runtime by `PermissionError`.

---

## 6. Reproduction Instructions

To reproduce the complete Phase 3 calibration and evaluation on a local workstation:

```bash
# 1. Activate Python 3.12+ environment
# 2. Execute the Phase 3 calibration runner:
$env:PYTHONPATH='ai_ml/src'; python ai_ml/scripts/run_phase3_evaluation.py

# 3. Execute the full test suite (58 tests):
$env:PYTHONPATH='ai_ml/src'; python -m pytest ai_ml/tests
```

Outputs are stored in `ai_ml/.local/phase3/`:
- `calibration_results.json`: Full numerical metric matrices across all models, targets, lead times, and alphas.
- `phase3_summary.md`: Detailed comparison tables and clipping analysis.
- `calibrators/`: Serialized calibrator JSON definitions.

