# Reserve Juggler AI/ML Development Plan

**Status:** Active  
**Module:** `ai_ml/` (`reserve_juggler_ml`)  
**Scope:** Standalone implementation, benchmarking, and integration of predictive models for Reserve Juggler.

---

## Overview of Phases

```text
Phase 0 ──▶ Phase 1 ──▶ Phase 2 ──▶ Phase 3 ──▶ Phase 4 ──▶ Phase 5
 Audit &     Baseline    Tree Models   Uncertainty   Liquidity    Backend
 Scaffolding  Pipelines   Comparison    Calibration   Risk Model   Integration
```

---

## Phase 0: Repository Audit, Data Inspection & Module Initialization (COMPLETED)
- [x] Inspect existing Git branch, working tree, and commit history.
- [x] Audit entire codebase: `server.py`, `web/`, `liquidity_forecasting/`, `tests/`.
- [x] Audit external committee dataset (`treasury_4tier_dataset.csv`, SHA-256, schema, continuity).
- [x] Map README requirements vs implementation in `REQUIREMENTS_MATRIX.md`.
- [x] Draft `REPOSITORY_AUDIT.md`, `DATA_AUDIT_REPORT.md`, `MODEL_SELECTION_PLAN.md`, and `INTEGRATION_CONTRACT.md`.
- [x] Create standalone package scaffolding, `.gitignore`, and unit test fixtures.
- [x] Ensure zero training performed and zero data committed to Git.

---

## Phase 1: Baseline Implementation & Verification (COMPLETED)
- [x] Implement causal data loader supporting external CSV loading and verification without file copying (`data.loader`).
- [x] Implement 14-day deterministic baseline (`DeterministicBaseline`) in `forecasting.baseline`.
- [x] Implement 24-hour seasonal-naïve benchmark/fallback and 168-hour weekly variant in `forecasting.seasonal`.
- [x] Implement chronological evaluation split utility with boundary purging and partition guards in `evaluation.splits`.
- [x] Implement multi-horizon benchmark evaluation harness in `evaluation.benchmark`.
- [x] Establish reproducible baseline metrics (MAE, RMSE, MASE) across 1h, 6h, 24h, 48h, 72h windows stored locally in `.local/phase1/`.
- [x] Document methodology and reproduction commands in `docs/BENCHMARK_RESULTS.md`.

---

## Phase 2: Tree-Based Machine Learning Models (COMPLETED)
- [x] Construct causal feature engineering pipeline (hour/day cyclical encodings, autoregressive lags, rolling statistics) with strict anti-leakage guards (`features.causal`, `features.training_dataset`).
- [x] Implement multi-output `RandomForestForecaster` for direct 72-hour deposit and withdrawal prediction (`forecasting.random_forest`).
- [x] Implement direct `XGBoostForecaster` with histogram-based boosting (`forecasting.xgboost_forecaster`).
- [x] Conduct chronological walk-forward evaluation on 1,393 validation origins and benchmark comparative performance against all 3 baselines.
- [x] Document methodology and local reproduction in `docs/PHASE2_MODEL_COMPARISON.md`; store artifacts under `.local/phase2/`.

---

## Phase 3: Uncertainty Estimation & Prediction Intervals (COMPLETED)
- [x] Implement lead-time empirical residual quantile calibrator for nominal confidence levels (90%, 95%, 99%) in `uncertainty.calibration`.
- [x] Integrate calibrator into all forecasters (`RandomForestForecaster`, `XGBoostForecaster`, `DeterministicBaseline`, `SeasonalNaiveForecaster`).
- [x] Establish strict chronological subdivision: Model Fitting (Jan–Jul, 4,681 samples), Out-of-Sample Calibration (August, 673 origins), and Validation Assessment (Sep–Oct, 1,393 origins).
- [x] Evaluate Interval Coverage Probability (ICP), Mean Interval Width (MIW), and non-negative clipping impact across 72 hours.
- [x] Document methodology and local reproduction in `docs/PHASE3_INTERVAL_CALIBRATION.md`; store artifacts under `.local/phase3/`.

---

## Phase 4: Liquidity-Risk Modeling & Path-Deficit Evaluation (NEXT PHASE)
- [ ] Formulate maximum cumulative path deficit target over relevant investment lock horizons ($H \in \{6, 24, 48, 72\}$).
- [ ] Train Quantile Gradient Boosting regressor targeting tail quantiles ($\tau = 0.01, 0.05, 0.10$).
- [ ] Compare quantile risk estimates against the existing root-sum-square (RSS) uncorrelated-error heuristic.
- [ ] Benchmark stress scenario performance under simulated withdrawal spikes and delayed deposits.

---

## Phase 5: Backend Integration & Acceptance Testing
- [ ] Implement `PredictionAdapter` converting internal model outputs to `INTEGRATION_CONTRACT.md` schema.
- [ ] Integrate with `liquidity_forecasting/treasury.py` so that predicted gross flows feed directly into the treasury planner.
- [ ] Implement automatic fallback to Seasonal-Naïve on inference exceptions or latency thresholds.
- [ ] Execute full end-to-end regression suite and update documentation with empirical verification results.
