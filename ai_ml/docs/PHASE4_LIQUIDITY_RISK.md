# Phase 4 — Liquidity-Risk & Path-Deficit Evaluation

**Date:** 18 October 2026  
**Scope:** Standalone AI/ML Module (`ai_ml/`)  
**Status:** Complete — Empirical Path-Risk Evaluation Executed  
**Local Artifact Directory:** `ai_ml/.local/phase4/` (Strictly Git-Ignored)

---

## 1. Executive Summary & Problem Formulation

### 1.1 The Cumulative Path-Risk Challenge
In bank treasury operations, liquidity risk over an investment lock horizon $H \in \{6, 24, 48, 72\}$ hours is inherently a **cumulative path property**, not an isolated hourly property:
- **Phase 2** evaluated point forecast accuracy for individual hourly cash flows ($\hat{y}_{t+h}$).
- **Phase 3** calibrated marginal prediction intervals for individual hourly cash flows ($[\hat{L}_{t+h}, \hat{U}_{t+h}]$).
- **Phase 4** addresses the joint cumulative path of net cash flows over time:
  $$S_{t, h} = \sum_{i=1}^h (\text{deposits}_{t+i} - \text{withdrawals}_{t+i}) = \sum_{i=1}^h \text{net\_flow}_{t+i}$$

### 1.2 Defining "Liquidity Deficit" Under Available Evidence
A rigorous distinction must be maintained between an **actual reserve deficit** and a **relative path-drawdown proxy**:

1. **Actual Reserve Deficit (Requires Authorized $B_0$ and $R$):**
   An actual reserve breach occurs only when the bank's true cash balance falls below a policy reserve threshold $R$:
   $$B_{t, h} = B_0 + \sum_{i=1}^h (\text{deposits}_{t+i} - \text{withdrawals}_{t+i})$$
   $$\text{deficit}_{t, h} = \max(0, R - B_{t, h})$$
   $$\text{maximum\_path\_deficit} = \max_{1 \le h \le H} \text{deficit}_{t, h}$$
   *Evidence Check:* The synthetic 4-tier banking committee dataset provides hourly transaction flows (`deposits_usd`, `withdrawals_usd`, `net_flow_usd`), but **does not contain opening cash balances $B_0$ or statutory reserve thresholds $R$**. Neither $B_0$ nor $R$ can be manufactured or invented.

2. **Relative Cumulative Net-Outflow / Path-Drawdown Proxy (Supported Metric):**
   Without $B_0$ and $R$, the mathematically supported and defensible metric is the maximum relative cumulative net cash outflow from the origin:
   $$D_{t, H} = \max_{1 \le h \le H} \max\left(0, \sum_{i=1}^h (\text{withdrawals}_{t+i} - \text{deposits}_{t+i})\right) = \max_{1 \le h \le H} \max\left(0, -S_{t, h}\right)$$
   **Financial Meaning:** $D_{t, H}$ measures the maximum cumulative cash drain experienced over the horizon starting from an arbitrary reference level of zero. It represents the minimum liquidity buffer required at origin $t$ to prevent cash depletion over horizon $H$ in the absence of external sweeps or borrowing.
   **Crucial Disclaimer:** This is a **relative path-drawdown proxy**, NOT an actual reserve breach, regulatory shortfall, or probability of insolvency.

---

## 2. Methodology: Path Uncertainty & Paired-Trajectory Scenarios

### 2.1 Why Adding Marginal Prediction Intervals Fails (The Envelope Fallacy)
A common planning heuristic (e.g., in `liquidity_forecasting/treasury.py:reserve_plan`) sums pointwise marginal lower bounds:
$$E_{t, H}^{\text{marginal}} = \max_{1 \le h \le H} \max\left(0, \sum_{i=1}^h -\hat{L}_{t+i}^{\text{net}}\right)$$
where $\hat{L}_{t+i}^{\text{net}} = \hat{L}_{t+i}^{\text{dep}} - \hat{U}_{t+i}^{\text{wdr}}$.

**Diagnostic vs Equivalent Risk Measure (No Capital Savings Claims):**
- Independent marginal intervals assume worst-case errors occur simultaneously in the adverse direction at every single hour. In reality, forecast errors across consecutive hours mean-revert or partially offset.
- As evaluated below, this marginal sum envelope yields 72-hour diagnostic figures of **$460.9M to $682.3M** across models.
- **Critical Policy Distinction:** Because opening cash balance $B_0$ and statutory reserve threshold $R$ are not present in the dataset, this marginal sum envelope is a **conservative diagnostic planning heuristic**, NOT an equivalent risk measure to a path quantile. These values **do not represent actual required liquidity buffers and do not establish quantified capital savings**.

### 2.2 Empirical Paired-Trajectory Scenario Simulation
To model the joint distribution of 72-hour paths without assuming independent errors, Phase 4 implements [`PairedTrajectoryScenarioCalibrator`](file:///c:/Users/Office%20Pc/source/Reserve-Juggler-2.0/ai_ml/src/reserve_juggler_ml/liquidity_risk/scenarios.py):

1. **Residual Trajectory Pairing on August Calibration Partition ($N=673$):**
   Using frozen model weights trained on Jan–Jul, out-of-sample August forecasts generate aligned pairs of 72-hour residual vectors:
   $$\mathbf{e}_{k, \text{dep}} = \mathbf{y}_{k, \text{dep}} - \hat{\mathbf{y}}_{k, \text{dep}} \in \mathbb{R}^{72}$$
   $$\mathbf{e}_{k, \text{wdr}} = \mathbf{y}_{k, \text{wdr}} - \hat{\mathbf{y}}_{k, \text{wdr}} \in \mathbb{R}^{72}$$
   for each origin $k \in \{1, \dots, 673\}$.
   *Key Invariant:* Pairing residual trajectories across all 72 lead times preserves both the **cross-sectional correlation** between deposits and withdrawals and the **multi-step autocorrelation** along the path. Each 72-step trajectory is preserved as a cohesive vector and is NOT independently resampled across steps or targets.

2. **Simulation Under Non-Negative Flow Constraints:**
   Given point forecasts $(\hat{\mathbf{y}}_{\tau, \text{dep}}, \hat{\mathbf{y}}_{\tau, \text{wdr}})$ at validation origin $\tau$:
   $$\tilde{\mathbf{y}}_{\tau, \text{dep}}^{(k)} = \max\left(0.0, \hat{\mathbf{y}}_{\tau, \text{dep}} + \mathbf{e}_{k, \text{dep}}\right)$$
   $$\tilde{\mathbf{y}}_{\tau, \text{wdr}}^{(k)} = \max\left(0.0, \hat{\mathbf{y}}_{\tau, \text{wdr}} + \mathbf{e}_{k, \text{wdr}}\right)$$
   $$\tilde{D}_{\tau, H}^{(k)} = \max_{1 \le h \le H} \max\left(0, \sum_{i=1}^h (\tilde{\mathbf{y}}_{\tau, \text{wdr}, i}^{(k)} - \tilde{\mathbf{y}}_{\tau, \text{dep}, i}^{(k)})\right)$$
   This generates an empirical sample of 673 scenario path-drawdown values from which mean, standard deviation, and quantiles ($\hat{Q}_{50}, \hat{Q}_{90}, \hat{Q}_{95}, \hat{Q}_{99}$) are estimated.

3. **Reconciling Jensen's Inequality vs Empirical Validation Bias:**
   - **Mathematical Comparison of the Three Flow & Drawdown Quantities (XGBoost, 72h):**
     1. *Original point-forecast path drawdown:* $g(\mathbf{x}_{\text{point}}) = \$40,769,798$, where $\mathbf{x}_{\text{point}} = \hat{\mathbf{y}}_{\text{dep}} - \hat{\mathbf{y}}_{\text{wdr}}$.
     2. *Path drawdown of the mean simulated flow trajectory:* $g(\bar{\mathbf{x}}_{\text{sim}}) = \$45,693,897$, where $\bar{\mathbf{x}}_{\text{sim}} = \frac{1}{N}\sum_{k=1}^N \tilde{\mathbf{x}}^{(k)}$ is the empirical mean net cash flow trajectory across scenarios after residual addition and non-negative clipping.
     3. *Mean scenario path drawdown:* $\bar{D}_{\text{scenarios}} = \frac{1}{N}\sum_{k=1}^N g(\tilde{\mathbf{x}}^{(k)}) = \$53,084,378$.
   - **Exact Quantity Supported by Jensen's Inequality:**
     The path drawdown functional $g(\mathbf{x}) = \max_{1 \le h \le H} \max(0, -\sum_{i=1}^h x_i)$ is convex because it is a pointwise maximum of linear functionals and a non-negative threshold. Jensen's inequality guarantees:
     $$\mathbb{E}_{\text{scenario}}[g(\tilde{\mathbf{x}})] \ge g(\mathbb{E}_{\text{scenario}}[\tilde{\mathbf{x}}]) \iff \bar{D}_{\text{scenarios}} \ge g(\bar{\mathbf{x}}_{\text{sim}})$$
     Across all 1,393 validation origins at 72h, this holds identically: minimum difference across origins is **+$16,630**, and mean Jensen gap is **+$7,390,481** (+16.2% over mean flow drawdown).
   - **Point Forecast Separation ($g(\bar{\mathbf{x}}_{\text{sim}}) \ne g(\mathbf{x}_{\text{point}})$):**
     The mean simulated flow trajectory does not equal the point forecast ($g(\bar{\mathbf{x}}_{\text{sim}}) - g(\mathbf{x}_{\text{point}}) = +\$4,924,100$, or +12.1%). This upward shift arises from:
     (a) Non-negative clipping ($\max(0, \hat{y} + e)$) truncating negative tails, and
     (b) Finite-sample August calibration residual sample means ($\bar{e}_{\text{dep}} \approx -\$107\text{k}, \bar{e}_{\text{wdr}} \approx +\$19\text{k}$).
     **Critical Distinction:** Jensen's inequality supports $\bar{D}_{\text{scenarios}} \ge g(\bar{\mathbf{x}}_{\text{sim}})$. It does NOT support $\bar{D}_{\text{scenarios}} \ge g(\mathbf{x}_{\text{point}})$, nor does it imply $\mathbf{x}_{\text{point}} = \bar{\mathbf{x}}_{\text{sim}}$.
   - **Empirical Validation Tracking Error (Point Forecast vs Realized Actuals):**
     On September–October validation data, point forecasts under-predicted realized actual drawdowns by an average of $\text{Bias} = D^{\text{point}} - D^{\text{actual}} = -\$11,470,911$ for XGBoost and $-\$26,385,191$ for Deterministic Baseline. This is an **empirical sample tracking error** on held-out validation data, NOT a mathematical consequence of Jensen's inequality.
   - Crucially, the scenario mean ($\$53,084,378$) closely tracks the actual validation mean ($\$52,240,709$) with only **+$843,669** empirical bias (+1.6% relative difference).

4. **Methodological Limitations & Caveats:**
   - **Unconditioned Trajectory Resampling:** The scenario calibrator resamples August residual trajectories unconditionally, without conditioning on origin features (such as current flow levels, repo sweep window state, or market volatility). Changes in seasonal volatility between August and the autumn validation months represent a plausible contributing factor rather than a proven causal explanation for coverage degradation.
   - **Overlapping Horizons & Temporal Autocorrelation:** Rolling origins advance hourly, producing overlapping 72-hour trajectories with substantial temporal dependence that violates the exchangeability assumptions required by formal conformal prediction.

---

## 3. Chronological Partitions & Governance

All models and scenario calibrators strictly adhere to established data governance partitions:

| Partition | Time Range | Candidate Hours | Warm-up Skipped | Boundary Purged | Valid Origins | Governance Role |
|---|---|---|---|---|---|---|
| **Fit** | 2026-01-01 00:00 – 2026-07-31 23:00 | 5,088 | 336 (14d) | 71 (72h) | **4,681** | Model parameter training |
| **Calibrate** | 2026-08-01 00:00 – 2026-08-31 23:00 | 744 | 0 | 71 (72h) | **673** | Paired residual trajectory calibration |
| **Validation** | 2026-09-01 00:00 – 2026-10-31 23:00 | 1,464 | 0 | 71 (72h) | **1,393** | Out-of-sample path evaluation |
| **Final Test** | 2026-11-01 00:00 – 2026-12-31 23:00 | 1,464 | — | — | — | **Strictly Reserved & Untouched** |

- **Denominator:** Metrics are evaluated across all **1,393 validation origins** for horizons $H \in \{6, 24, 48, 72\}$.
- **Causality:** History strictly strictly prior to origin index $t$ is used; observation row $t$ is not in history.
- **Isolation:** Programmatic access to `final_test` raises `PermissionError` at runtime.

---

## 4. Empirical Validation Results

### 4.1 Realized Validation Path-Drawdown Distribution Quantiles
Across all 1,393 September–October validation origins, the realized empirical distribution of actual path drawdowns ($D_{\tau, H}^{\text{actual}}$) is:

| Horizon | Mean Actual DD ($) | Median ($q_{50}$) ($) | 90th Pct ($q_{90}$) ($) | 95th Pct ($q_{95}$) ($) | 99th Pct ($q_{99}$) ($) | Max Actual DD ($) | Fraction Zero Drawdown |
|---|---|---|---|---|---|---|---|
| **6 Hours** | $6,208,186 | $1,662,588 | $19,919,257 | $29,554,102 | $49,571,316 | $62,218,509 | 34.24% |
| **24 Hours** | $21,542,207 | $4,892,849 | $69,274,582 | $83,642,375 | $114,800,448 | $121,758,976 | 25.34% |
| **48 Hours** | $37,936,850 | $8,430,850 | $102,649,594 | $121,366,631 | $200,240,992 | $215,385,926 | 20.96% |
| **72 Hours** | $52,240,709 | $29,366,197 | $120,391,882 | $139,701,004 | $214,353,545 | $224,368,939 | 16.37% |

*Note:* Because drawdowns cannot be negative, when net deposits exceed net withdrawals throughout the horizon, the drawdown is $0.0$. At $H=6\text{h}$, 34.24% of origins experience zero net drawdown.

---

### 4.2 Executive Summary: Point Forecast Drawdown vs Scenario Risk Quantiles ($H = 72$ Hours)

Evaluated across all 1,393 September–October validation origins:

| Candidate Model | Actual Mean DD ($) | Point Predicted DD ($) | Point Bias ($) | Point MAE ($) | Scenario Mean DD ($) | Scenario q95 DD ($) | q95 Coverage | q95 Error (pp) | Marginal Sum Env 95 ($) | Env Coverage |
|---|---|---|---|---|---|---|---|---|---|---|
| **Deterministic Baseline (14d)** | $52,240,709 | $25,855,518 | -$26,385,191 | $48,484,224 | $46,983,291 | $122,107,606 | 0.8973 | -5.27 pp | $522,397,413 | 1.0000 |
| **Seasonal Naive (24h)** | $52,240,709 | $59,714,106 | +$7,473,398 | $72,319,376 | $82,908,283 | $180,354,001 | 0.8959 | -5.41 pp | $682,319,286 | 1.0000 |
| **Seasonal Naive (168h)** | $52,240,709 | $53,172,602 | +$931,893 | $21,899,615 | $68,199,642 | $118,970,026 | 0.9785 | +2.85 pp | $560,325,952 | 1.0000 |
| **Random Forest** | $52,240,709 | $43,165,896 | -$9,074,813 | $16,506,249 | $51,239,172 | $90,782,188 | 0.9203 | -2.97 pp | $411,731,147 | 1.0000 |
| **XGBoost** | **$52,240,709** | **$40,769,800** | **-$11,470,911** | **$14,931,412** | **$53,084,378** | **$88,696,233** | **0.9282** | **-2.18 pp** | **$460,871,176** | **1.0000** |

*Note on Units:* All monetary values in USD. Coverage error expressed in absolute percentage points (pp).

---

### 4.3 Multi-Horizon Evaluation Breakdown ($H \in \{6, 24, 48, 72\}$ Hours)

All values are verified against [`ai_ml/.local/phase4/path_deficit_results.json`](file:///c:/Users/Office%20Pc/source/Reserve-Juggler-2.0/ai_ml/.local/phase4/path_deficit_results.json):

| Candidate Model | Horizon | Actual Mean DD ($) | Point MAE ($) | Point Bias ($) | Scenario q50 Cov | Scenario q90 Cov | Scenario q95 Cov | Scenario q99 Cov | Mean q95 Bound ($) |
|---|---|---|---|---|---|---|---|---|---|
| **Deterministic Baseline (14d)** | 6h | $6,208,186 | $5,755,376 | -$2,031,229 | 0.6260 | 0.8916 | 0.9182 | 0.9576 | $21,410,537 |
| Deterministic Baseline (14d) | 24h | $21,542,207 | $21,723,329 | -$10,367,592 | 0.6001 | 0.8313 | 0.8679 | 0.9483 | $61,140,788 |
| Deterministic Baseline (14d) | 48h | $37,936,850 | $37,500,220 | -$19,421,784 | 0.5765 | 0.8227 | 0.8550 | 0.9562 | $94,213,291 |
| Deterministic Baseline (14d) | 72h | $52,240,709 | $48,484,224 | -$26,385,191 | 0.5370 | 0.7724 | 0.8973 | 0.9404 | $122,107,606 |
| **Seasonal Naive (24h)** | 6h | $6,208,186 | $6,562,872 | -$3,242 | 0.6116 | 0.9074 | 0.9555 | 0.9777 | $22,689,800 |
| Seasonal Naive (24h) | 24h | $21,542,207 | $22,108,523 | -$16,110 | 0.6612 | 0.8607 | 0.9261 | 0.9505 | $66,484,141 |
| Seasonal Naive (24h) | 48h | $37,936,850 | $46,167,979 | +$2,683,252 | 0.6490 | 0.8615 | 0.8988 | 0.9390 | $135,497,021 |
| Seasonal Naive (24h) | 72h | $52,240,709 | $72,319,376 | +$7,473,398 | 0.6145 | 0.8184 | 0.8959 | 0.9246 | $180,354,001 |
| **Seasonal Naive (168h)** | 6h | $6,208,186 | $4,224,118 | +$115,084 | 0.6748 | 0.9497 | 0.9670 | 0.9950 | $25,707,318 |
| Seasonal Naive (168h) | 24h | $21,542,207 | $12,777,386 | +$394,041 | 0.7186 | 0.9361 | 0.9526 | 0.9907 | $61,132,677 |
| Seasonal Naive (168h) | 48h | $37,936,850 | $19,339,676 | +$618,246 | 0.7854 | 0.9239 | 0.9548 | 0.9792 | $98,300,326 |
| Seasonal Naive (168h) | 72h | $52,240,709 | $21,899,615 | +$931,893 | 0.8019 | 0.9454 | 0.9785 | 0.9792 | $118,970,026 |
| **Random Forest** | 6h | $6,208,186 | $2,355,181 | -$913,984 | 0.5937 | 0.9296 | 0.9620 | 0.9907 | $15,958,781 |
| Random Forest | 24h | $21,542,207 | $8,474,071 | -$4,386,323 | 0.6497 | 0.8866 | 0.9232 | 0.9684 | $47,792,823 |
| Random Forest | 48h | $37,936,850 | $13,501,543 | -$7,121,815 | 0.6712 | 0.8930 | 0.9296 | 0.9584 | $74,548,025 |
| Random Forest | 72h | $52,240,709 | $16,506,249 | -$9,074,813 | 0.6217 | 0.8837 | 0.9203 | 0.9598 | $90,782,188 |
| **XGBoost** | **6h** | **$6,208,186** | **$2,337,060** | **-$1,043,933** | **0.6202** | **0.9433** | **0.9698** | **0.9914** | **$16,513,562** |
| **XGBoost** | **24h** | **$21,542,207** | **$7,287,797** | **-$4,966,144** | **0.6892** | **0.9304** | **0.9490** | **0.9792** | **$46,979,742** |
| **XGBoost** | **48h** | **$37,936,850** | **$11,605,019** | **-$8,743,709** | **0.7114** | **0.9311** | **0.9469** | **0.9569** | **$72,590,620** |
| **XGBoost** | **72h** | **$52,240,709** | **$14,931,412** | **-$11,470,911** | **0.6827** | **0.9124** | **0.9282** | **0.9627** | **$88,696,233** |

---

## 5. Assessment: Empirical Scenario Coverage & Uncertainty Characterization

An essential audit requirement is to evaluate whether path-risk uncertainty can be characterized as calibrated or exploratory:

1. **Empirical Scenario Coverage Varies Materially by Horizon and Nominal Level:**
   Describing all horizons as "well calibrated" is inaccurate because empirical coverage deviates materially across nominal levels and horizon lengths:
   - **6-Hour Horizon (Empirical Overcoverage):** Realized coverage exceeds nominal targets across all levels: 50% nominal $\to$ 62.02% (+12.02 pp); 90% target $\to$ 94.33% (+4.33 pp); 95% target $\to$ 96.98% (+1.98 pp); 99% target $\to$ 99.14% (+0.14 pp).
   - **24-Hour Horizon (Near-Nominal / Upper Undercoverage):** 50% nominal $\to$ 68.92% (+18.92 pp); 90% target $\to$ 93.04% (+3.04 pp); 95% target $\to$ 94.90% (**-0.10 pp** undercoverage); 99% target $\to$ 97.92% (**-1.08 pp** undercoverage).
   - **48-Hour Horizon (Upper Tail Undercoverage):** 50% nominal $\to$ 71.14% (+21.14 pp); 90% target $\to$ 93.11% (+3.11 pp); 95% target $\to$ 94.69% (**-0.31 pp** undercoverage); 99% target $\to$ 95.69% (**-3.31 pp** undercoverage).
   - **72-Hour Horizon (Material Upper Tail Undercoverage):** Coverage deteriorates at the highest nominal levels across all models:
     - **XGBoost:** 95% nominal target $\to$ **92.82%** empirical coverage (**-2.18 percentage points** undercoverage); 99% nominal target $\to$ **96.27%** (**-2.73 percentage points** undercoverage).
     - **Random Forest:** 95% nominal target $\to$ **92.03%** (**-2.97 pp** undercoverage); 99% nominal target $\to$ **95.98%** (**-3.02 pp** undercoverage).
     - **Deterministic Baseline (14d):** 90% nominal target $\to$ **77.24%** (**-12.76 pp** undercoverage); 95% nominal target $\to$ **89.73%** (**-5.27 pp** undercoverage).
     - **Seasonal Naive (24h):** 95% nominal target $\to$ **89.59%** (**-5.41 pp** undercoverage); 99% nominal target $\to$ **92.46%** (**-6.54 pp** undercoverage).
   - **Zero-Drawdown Mass Effect on Median (50%):** Because 16% to 34% of origins experience zero net drawdown, the empirical distribution has a point mass at zero, causing median scenario bounds to systematically overcover (+12 to +21 pp).

2. **Potential Factors Contributing to Coverage Deviations:**
   - **Temporal Autocorrelation & Overlapping Windows:** Rolling origins advance hourly, producing overlapping 72-hour trajectories with substantial serial autocorrelation. Conformal prediction theorems require exchangeability, which does not hold for rolling multi-step paths.
   - **Unconditioned Resampling as a Possible Limitation:** Scenarios resample August trajectories unconditionally, without conditioning on seasonal volatility or macro regime changes in autumn. This is a plausible limitation and contributing factor, though causality is not formally proven.
   - **Status & Scope:** Paired trajectory scenario simulation provides an **empirically grounded, realistic path-risk approximation** that is substantially superior to naive point forecasts or marginal sum envelopes. However, it must be reported as an **empirical scenario proxy and exploratory path distribution**, NOT a formal conformal guarantee.

---

## 6. Runtime & Computational Efficiency

Evaluated on 12-core workstation:
- Feature extraction across 4,681 fit origins: **0.78 seconds**.
- Supervised model training: RF = **2.41s**, XGBoost = **9.81s**.
- August scenario calibrator fitting ($N=673$): **< 0.1s** per candidate.
- Validation inference and 673-scenario simulation across 1,393 origins:
  - Deterministic Baseline: **4.45 ms / origin** (6.20s total).
  - Seasonal Naive (24h): **2.46 ms / origin** (3.43s total).
  - Seasonal Naive (168h): **2.38 ms / origin** (3.32s total).
  - Random Forest: **1.73 ms / origin** (2.41s total).
  - XGBoost: **1.69 ms / origin** (2.35s total).
- Real-time compatibility: Inference latency of **< 2 ms per origin** is well within the 2,000 ms SLA specified in the Integration Contract.

---

## 7. Limitations & Governance Constraints

1. **Synthetic USD Committee Dataset:** All evaluations were conducted exclusively on the synthetic USD banking committee dataset. Results provide **no empirical evidence of performance in INR-denominated or Indian banking liquidity regimes**.
2. **Proxy vs Actual Deficit:** Results represent relative cumulative net-outflow proxies. They do not represent actual regulatory reserve breaches or insolvency probabilities.
3. **Reservation of Final-Test Partition:** The November–December 2026 partition remains strictly reserved and untouched.

