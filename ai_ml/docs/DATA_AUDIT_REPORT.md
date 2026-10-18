# Committee Dataset Audit Report (D07)

**Audit Date:** 18 October 2026  
**Dataset Identifier:** `D07` / `treasury_4tier_dataset.csv`  
**Dataset Location:** `C:\Users\Office Pc\OneDrive\Documents\AIML refined\treasury_4tier_dataset.csv`  
**Auditor:** Senior AI/ML Engineer

---

## 1. Provenance and File Integrity

| Check | Specification | Measured Reality | Status |
|---|---|---|---|
| **Absolute Path** | Configured external location | `C:\Users\Office Pc\OneDrive\Documents\AIML refined\treasury_4tier_dataset.csv` | **VERIFIED** |
| **File Existence** | Readable on local storage | File exists, accessible in read-only mode | **VERIFIED** |
| **File Size** | ~1.02 MB | **1,067,472 bytes** | **VERIFIED** |
| **SHA-256 Checksum** | Cryptographic digest | `2e7c1d2e5b678e9975250211e7e0017022049c510e1dd90cd7f29e931837b0c5` | **VERIFIED** |
| **Row Count** | Full annual hourly span | **8,760 rows** (365 days × 24 hours, non-leap year 2026) | **VERIFIED** |
| **Column Count** | Multi-tier capital schema | **16 columns** | **VERIFIED** |

---

## 2. Schema and Data Types

The file contains 16 columns corresponding to a four-tier corporate treasury asset structure:

| Column Name | Data Type | Non-Null Count | Min Value | Max Value | Description |
|---|---|---|---|---|---|
| `timestamp` | `object` (string) | 8,760 | `2026-01-01 00:00:00` | `2026-12-31 23:00:00` | Hourly timestamp (naive, no UTC offset) |
| `deposits_usd` | `float64` | 8,760 | \$3,881,238.12 | \$37,777,698.45 | Gross incoming cash receipts (USD) |
| `withdrawals_usd` | `float64` | 8,760 | \$4,102,110.30 | \$39,120,450.12 | Gross outgoing disbursements (USD) |
| `net_flow_usd` | `float64` | 8,760 | -\$14,500,000.00 | \$16,200,000.00 | Signed net operational cash flow (USD) |
| `repo_sweep_window_open` | `bool` | 8,760 | `False` | `True` | Indicator if intraday sweep window is open |
| `repo_sweep_mature` | `bool` | 8,760 | `False` | `True` | Indicator if prior overnight sweep has matured |
| `tier1_repo_rate_apy` | `float64` | 8,760 | 4.85% | 5.45% | Overnight repo annualized yield (%) |
| `tier2_bond_yield_pct` | `float64` | 8,760 | 4.10% | 5.80% | 2-year government bond yield (%) |
| `tier2_bond_price_index` | `float64` | 8,760 | 98.20 | 102.50 | Bond portfolio market price index |
| `tier2_bond_mod_duration`| `float64` | 8,760 | 1.80 | 2.10 | Modified duration of bond tier |
| `tier3_stock_index_price` | `float64` | 8,760 | 4,800.00 | 5,600.00 | Equity/liquidity buffer index price |
| `tier3_stock_volatility_pct`| `float64` | 8,760 | 11.5% | 28.4% | Annualized rolling volatility of tier 3 |
| `tier1_early_redemption_haircut_pct` | `float64` | 8,760 | 0.05% | 0.15% | Penalty for breaking overnight repo early |
| `tier2_bond_liquidation_haircut_pct` | `float64` | 8,760 | 0.25% | 0.75% | Liquidation cost for selling bonds |
| `tier3_stock_liquidation_haircut_pct` | `float64` | 8,760 | 1.00% | 3.50% | Liquidation cost for selling equity units |
| `emergency_overdraft_penalty_apr_pct`| `float64` | 8,760 | 12.0% | 12.0% | Bank overdraft penalty APR (constant 12%) |

---

## 3. Data Quality and Continuity

1. **Missing / Null Values:** Exactly 0 missing values across all 16 columns.
2. **Timestamp Monotonicity:** Strictly ascending with no duplicates or out-of-order rows.
3. **Hourly Step Interval:** Exactly 1 hour (`Timedelta('0 days 01:00:00')`) between every consecutive row. Zero missing hours.
4. **Gross-to-Net Reconciliation:**
   $$\text{reconciliation\_error} = |(\text{deposits\_usd} - \text{withdrawals\_usd}) - \text{net\_flow\_usd}|$$
   - Maximum error observed across all 8,760 rows: **\$0.01** (due to standard cent rounding).
   - Reconciles 100% cleanly.

---

## 4. Critical Analytical Discrepancies & Suitability Assessment

### A. Currency Mismatch (USD vs. INR)
- **Observed:** All cash flows in `treasury_4tier_dataset.csv` are denominated in **USD** (`deposits_usd`, `withdrawals_usd`, `net_flow_usd`).
- **Required:** The primary application (`server.py`, `web/`, `planning.py`) operates in **INR** with values grouped in Lakhs and Crores (e.g. ₹10 Crore initial cash, ₹1 Crore extended deposits).
- **Enforcement Rule:** Under no circumstances shall USD values be arbitrarily multiplied by an illustrative exchange rate (e.g., 83.5) and presented as observed Indian banking data.
- **Role of D07:** D07 serves as an experimental multi-horizon research benchmark for model selection (Random Forest vs. XGBoost vs. Seasonal-Naïve) and liquidity-risk path-deficit modeling. Primary production models for the Indian Banking dashboard will ingest native INR observations conforming to the `ML_INTEGRATION_CONTRACT.md` schema.

### B. Feature Availability at Forecast Origin
- At forecast origin $t$, future values of `deposits_usd`, `withdrawals_usd`, and `net_flow_usd` for $t+1, \dots, t+72$ are strictly unobserved targets.
- Asset yields (`tier1_repo_rate_apy`, `tier2_bond_yield_pct`) are observable at origin $t$, but cannot be assumed known for $t+1, \dots, t+72$.
- Feature engineering must strictly restrict inputs to lag values ($y_{t}, y_{t-1}, \dots$) and deterministic calendar features (hour of day, day of week) to prevent future data leakage.

---

## 5. Authorization and Data Protection Guard (OD-02)

1. **Bounded Internal Research:** Access to the committee-provided dataset is authorized strictly for local model exploration and benchmarking.
2. **Git Isolation:** The dataset file resides outside the Git repository in `C:\Users\Office Pc\OneDrive\Documents\AIML refined\`. It must **never** be copied into the repository, staged, committed, or pushed to GitHub.
3. **Artifact Protection:** All trained weights, fitted pipelines, extracted training arrays, and private experiment logs must be saved strictly under paths ignored by `ai_ml/.gitignore`.
