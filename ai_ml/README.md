# Reserve Juggler AI/ML Module (`reserve_juggler_ml`)

Standalone, clean machine learning package for cash-flow forecasting, calibrated prediction intervals, and liquidity-risk estimation in Reserve Juggler.

---

## 1. Module Purpose & Boundary

This module implements the predictive intelligence layer of Reserve Juggler. It operates under strict architectural separation:

- **AI/ML Scope (Advisory):** Feature engineering, multi-horizon point forecasting, prediction intervals, and liquidity-risk quantiles.
- **Backend Scope (Executive):** Accounting balances, payment execution, statutory reserve policy, term investment sweeps (6h, 24h, 48h), and audit ledgers.

The AI/ML module produces **estimates only**. It does not make financial allocations or execute balance movements.

---

## 2. Directory Layout

```text
ai_ml/
├── README.md                     # Package documentation and quick start
├── AI_ML_PLAN.md                 # 6-phase engineering execution plan
├── pyproject.toml                # Standalone package build and dependency definitions
├── .gitignore                    # OD-02 data protection and artifact exclusions
├── configs/                      # Default experiment & model configuration
├── docs/                         # Architecture, audit, and contract documentation
│   ├── REPOSITORY_AUDIT.md       # Complete 17-section repository analysis
│   ├── REQUIREMENTS_MATRIX.md   # README specifications vs code/test matrix
│   ├── DATA_AUDIT_REPORT.md      # Committee dataset audit and schema verification
│   ├── MODEL_SELECTION_PLAN.md   # Model comparison protocol and promotion criteria
│   └── INTEGRATION_CONTRACT.md   # Canonical request/response API specifications
├── src/
│   └── reserve_juggler_ml/       # Core Python package
│       ├── data/                 # Causal data loaders & validation schemas
│       ├── features/             # Causal feature engineering (no lookahead)
│       ├── forecasting/          # Baseline, seasonal-naïve, and ML models
│       ├── uncertainty/          # Conformal & residual prediction intervals
│       ├── liquidity_risk/       # Quantile path-deficit estimation
│       ├── evaluation/           # Chronological rolling metrics
│       └── integration/          # Backend adapter for server.py / treasury.py
├── tests/                        # Comprehensive unit & contract tests
├── notebooks/                    # Interactive exploration (git-ignored artifacts)
└── scripts/                      # Training & evaluation CLI runners
```

---

## 3. Local Data Configuration (Zero Git Exposure)

Per **OD-02 (Bounded Internal Research Guard)**, private datasets and trained weights must never be committed to Git. The committee dataset is referenced externally without copying it into the repository:

```bash
# Set external dataset location in your local environment
$env:RESERVE_JUGGLER_DATASET_PATH="C:\Users\Office Pc\OneDrive\Documents\AIML refined\treasury_4tier_dataset.csv"
```

If the environment variable is not set, the loader checks the canonical local path:
`C:\Users\Office Pc\OneDrive\Documents\AIML refined\treasury_4tier_dataset.csv`.

---

## 4. Setup & Testing

### Installation (Editable Mode)
```powershell
# From the repository root or ai_ml/ directory:
pip install -e ai_ml
```

### Running Tests
```powershell
python -m pytest ai_ml/tests -v
```
