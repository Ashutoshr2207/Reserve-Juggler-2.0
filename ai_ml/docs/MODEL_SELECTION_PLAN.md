# Reserve Juggler Model Selection & Evaluation Plan

**Audit Date:** 18 October 2026  
**Scope:** Standalone AI/ML Module (`ai_ml/`)  
**Objective:** Establish a mathematically sound, reproducible evaluation protocol to benchmark, select, and calibrate forecasting and liquidity-risk models for Reserve Juggler.

---

## 1. Forecasting Targets & Multi-Horizon Strategy

### 1.1 Primary Prediction Targets
The primary application requires hourly balance projections across a 72-hour planning horizon ($H = 72$). Models must output separate gross predictions:
1. **Gross Receipts Target:** $y_t^{\text{dep}} = \text{deposits}_{t}$
2. **Gross Disbursements Target:** $y_t^{\text{wdr}} = \text{withdrawals}_{t}$

*Derived Net Flow:*
$$\hat{y}_{t+h}^{\text{net}} = \hat{y}_{t+h}^{\text{dep}} - \hat{y}_{t+h}^{\text{wdr}}, \quad h \in \{1, 2, \dots, 72\}$$

### 1.2 Multi-Horizon Architecture: Direct Multi-Step vs. Recursive
- **Recursive Forecasting:** Prone to rapid error accumulation and compounding bias across 72 steps.
- **Direct Multi-Step Forecasting (Selected Strategy):** A dedicated model (or multi-output tree regressor) predicts each horizon step $h \in \{1, \dots, 72\}$ directly from features known at origin $t$:
  $$\hat{y}_{t+h} = f_h(\mathbf{x}_t)$$
  This avoids feeding uncertain model predictions back into the feature set.

---

## 2. Causal Feature Engineering & Leakage Rules

All features must be computable strictly from information available at or before forecast origin $t$. Any feature computed from $t+1$ onwards constitutes temporal leakage and is strictly prohibited.

### Permitted Feature Set ($\mathbf{x}_t$):
1. **Deterministic Calendar & Cyclical Features:**
   - Hour of day: $\sin(2\pi \cdot \text{hour} / 24)$, $\cos(2\pi \cdot \text{hour} / 24)$
   - Day of week: $\sin(2\pi \cdot \text{dow} / 7)$, $\cos(2\pi \cdot \text{dow} / 7)$
   - Weekend indicator: $I(\text{dow} \ge 5)$
2. **Autoregressive Lags:**
   - Recent hourly observations: $y_t, y_{t-1}, y_{t-2}, y_{t-3}$
   - Daily seasonal lags: $y_{t-24}, y_{t-48}, y_{t-72}, y_{t-168}$
3. **Causal Rolling Statistics:**
   - 24-hour rolling mean, standard deviation, and min/max computed over $[t-23, t]$.
   - 168-hour (7-day) rolling mean and standard deviation computed over $[t-167, t]$.
   - Differences / Momentum: $y_t - y_{t-24}$, $y_t - y_{t-168}$.

---

## 3. Chronological Evaluation Protocol

Random k-fold cross-validation is strictly disallowed because time-series observations are auto-correlated. Evaluation must use **rolling-origin walk-forward evaluation**:

```text
Full Observation Span (8,760 hours / 365 days)
├────────────────────── Train (Months 1–8) ──────────────────────┤
                                     ├─ Val (M9–10) ─┤
                                                     ├─ Test (M11–12) ─┤
```

- **Warm-Up / Initial Training:** Minimum 30 days (720 hours) up to 180 days.
- **Rolling Step:** Advance origin $t$ by 24 hours (simulating daily treasury planning).
- **Out-of-Sample Window:** Exactly 72 consecutive hours evaluated per origin.

---

## 4. Evaluated Model Candidates

| Candidate ID | Model Family | Description | Strengths & Trade-offs |
|---|---|---|---|
| **CAND-01** | **Deterministic 14-Day Baseline** | Hour-of-week profile average from the trailing 336 hours. | Zero training time; benchmark for all learned models. |
| **CAND-02** | **Seasonal-Naïve (Benchmark/Fallback)** | $y_{t+h} = y_{t+h-24k}$ with empirical residual intervals. | Robust; guarantees sensible bounds; primary operational fallback. |
| **CAND-03** | **SARIMAX `(1,0,0)x(1,0,0,24)`** | State-space seasonal autoregressive model. | Established baseline in existing code; requires statsmodels. |
| **CAND-04** | **Random Forest Regressor** | Multi-output direct tree ensemble with causal lag features. | Handles nonlinear interactions; robust to outliers; CPU fast. |
| **CAND-05** | **XGBoost Regressor** | Gradient-boosted decision trees with objective tuning. | High predictive accuracy; natively installed; fast inference. |
| **CAND-06** | **Quantile Gradient Boosting (Liquidity Risk)** | Regressor trained with Pinball Loss at $\tau \in \{0.01, 0.05, 0.10, 0.50, 0.90, 0.95, 0.99\}$. | Directly predicts worst cumulative path deficit over lock horizons. |

---

## 5. Evaluation Metrics & Promotion Gates

### 5.1 Point Forecast Accuracy
- **Mean Absolute Error (MAE):** $\text{MAE} = \frac{1}{H}\sum_{h=1}^H |y_{t+h} - \hat{y}_{t+h}|$
- **Root Mean Squared Error (RMSE):** $\text{RMSE} = \sqrt{\frac{1}{H}\sum_{h=1}^H (y_{t+h} - \hat{y}_{t+h})^2}$
- **Mean Absolute Scaled Error (MASE):** Scaled against 24-hour seasonal-naïve error.

### 5.2 Uncertainty Interval Quality
For nominal confidence levels $\alpha \in \{0.90, 0.95, 0.99\}$:
- **Interval Coverage Probability (ICP):** Percentage of actual observations falling within $[\hat{L}_{t+h}, \hat{U}_{t+h}]$. Target: $\ge \alpha$.
- **Mean Interval Width (MIW):** $\frac{1}{H}\sum_{h=1}^H (\hat{U}_{t+h} - \hat{L}_{t+h})$. Lower width is preferred given valid coverage.

### 5.3 Liquidity Risk Tail Metrics
- **Quantile Pinball Loss:** Measures quantile calibration at extreme risk tails ($\tau = 0.01$ and $\tau = 0.05$).
- **Maximum Cumulative Path Deficit Error:** Difference between predicted and realized worst drawdown during lock periods ($H \in \{6, 24, 48, 72\}$).

### 5.4 Promotion Criteria Gate
To be promoted to production candidate:
1. **Outperform Seasonal-Naïve:** Point forecast MAE must beat Seasonal-Naïve by at least **10%** across the test split.
2. **Interval Validity:** Empirical coverage must be within $\pm 2\%$ of the nominal level (e.g. 95% interval achieves $\ge 93\%$ coverage).
3. **Inference Latency:** 72-hour forecast generation must execute in under **500 ms** on standard CPU.
4. **Deterministic Fallback:** Must cleanly fall back to Seasonal-Naïve if features are incomplete or inference errors occur.
