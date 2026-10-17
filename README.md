# Reserve Juggler

**Predict cash needs, protect upcoming payments, and invest eligible surplus.**

Reserve Juggler addresses **PS 1: The Idle Cash Problem — Automated Treasury Management and Yield Optimization**. It connects financial observations, cash-flow forecasting, liquidity-risk assessment, reserve calculations, investment selection, simulated sweeps, and balance checks in one workflow.

The repository contains two applications:

| Application | Purpose | Entry point |
| --- | --- | --- |
| INR hourly treasury dashboard | Time-aware cash protection, maturity-aware investments, event simulation, and explainable decisions | `server.py` and `web/` |
| Multi-currency daily engine | Daily forecasting, balance projection, EUR-normalized funding allocation, backtesting, and Excel reporting | `app.py` or `main.py` |

**All balances, investments, transfers, and execution outcomes in the hourly dashboard are simulated.** Importing observations does not connect a bank or establish live account balances. The default example uses INR; it is an adaptation of the problem statement, not a currency conversion of its dollar amounts.

## Contents

- [Quick start](#quick-start)
- [Treasury workflow](#treasury-workflow)
- [Forecasting and reserve calculations](#forecasting-and-reserve-calculations)
- [Investment options and execution](#investment-options-and-execution)
- [Dashboard and demonstration](#dashboard-and-demonstration)
- [Data contracts](#data-contracts)
- [API reference](#api-reference)
- [Measured strategy comparisons](#measured-strategy-comparisons)
- [Testing and verification](#testing-and-verification)
- [Multi-currency daily workflow](#multi-currency-daily-workflow)
- [Repository structure](#repository-structure)
- [Limitations and troubleshooting](#limitations-and-troubleshooting)

## Quick start

Use Python 3.12 for the verified environment. Node.js is needed only for the JavaScript syntax checks; the dashboard has no frontend build step.

### Windows

From the repository root, create an environment if one is not already prepared:

```powershell
python -m venv .venv-win
.\.venv-win\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\start.ps1
```

Open [the dashboard](http://127.0.0.1:8000/#overview). The launcher starts a hidden background process or reuses a healthy server on the requested port. Its logs and PID are saved under `.runtime/`.

For foreground execution or another port:

```powershell
.\start.ps1 -Foreground
.\start.ps1 -Port 8019
# Direct execution:
.\.venv-win\Scripts\python.exe server.py --port 8000
```

After backend source changes, restart the server: reusing a healthy process does not reload Python modules. Stop a foreground process with Ctrl+C. The review instance used for the latest verification was on port **8019**; the default remains **8000**.

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
python server.py --port 8000
```

The recorded verification was performed on Windows. `requirements-lock.txt` records the prepared dependency versions. No new runtime dependencies were added for the integrated treasury workflow.

## Treasury workflow

```text
Historical hourly observations + scheduled events
                      ↓
        SARIMAX / seasonal-naive forecast
                      ↓
   Chronological cash path + uncertainty + stress
                      ↓
     Required reserve and eligible principal
                      ↓
       Compare 6h / 24h / 48h investments
                      ↓
   Revalidate → simulate execution → verify balances
                      ↓
       Decision ledger → maturity → recalculate
```

A deposit arriving later cannot fund an earlier payment. Payments, deposits, merchant receipts, and contractual maturities are evaluated in timestamp order, with outflows before receipts at identical timestamps.

For example, a ₹7 million payout at 14:00 must be protected before a ₹4 million settlement arriving at 15:00 is considered. Tests cover this sequencing and intrahour maturities: identical end-of-hour balances can conceal an earlier funding gap.

New events immediately recalculate recommendations. Supported events include withdrawals, payments, deposits, merchant settlements, settlement delays, and risk alerts that change the additional risk buffer. Advancing the sandbox clock realizes a simulated hour, processes due events and maturities, and reevaluates automatic sweeping. This is event-driven simulation, not live payment processing.

## Forecasting and reserve calculations

### Forecasts

- The existing net-flow pipeline fits SARIMAX to up to 28 days of hourly observations and forecasts the next 72 hours using a 24-hour seasonal cycle.
- Fitting failure or nonconvergence uses the existing seasonal-naive fallback and labels the model accordingly.
- Independent seasonal-naive forecasts estimate deposits and withdrawals separately. Their means are displayed in the forecast table; their intervals are returned by the API.
- The authoritative net forecast is reconciled into the planner's gross hourly profile. Independent gross estimates can differ from the net forecast and are not presented as separate SARIMAX predictions.
- The dashboard offers 1h, 6h, 24h, 48h, and 72h views, timestamps in IST, model status, uncertainty, and a previous-day baseline MAE. That baseline MAE is not an accuracy score for the currently fitted SARIMAX forecast.

The illustrative gross profile divides withdrawals into UPI 45%, IMPS 20%, NEFT 20%, RTGS 10%, and ATM 5%. It reclassifies 8% of deposits as merchant settlements rather than adding extra receipts. These proportions are demo assumptions, not classifications inferred from bank transaction data.

### Protected reserve

For each proposed investment, the engine checks every relevant cash-flow point during its lock period:

```text
Protected floor = minimum operational cash + additional risk buffer
Required reserve = protected floor + worst projected lock-period drawdown
Eligible principal = max(0, liquid cash − required reserve − entry fee)
Interest = principal × annual rate / 100 × locked hours / (365 × 24)
Net return = interest − entry fee
```

Principal is rounded down to cents. Minimum investment sizes, fees, net returns, timed obligations, delayed settlements, and existing maturities constrain eligibility. Locked principal is excluded from current liquid cash; it enters the future cash path only at contractual maturity. A full 72-hour baseline check also blocks investments when modeled later funding gaps or fees make the path unsafe.

The integrated planner accumulates uncertainty using a root-sum-square allowance:

```text
Allowance through hour h = sqrt(sum((forecast mean − lower bound)² through h))
```

This is a planning heuristic under an **uncorrelated-error assumption**, not a calibrated confidence interval for an entire cash path. Correlated errors and unmodeled peaks can invalidate the modeled protection. Buffers, stress scenarios, and explicitly reported funding gaps remain necessary; there is no unconditional payout guarantee.

The original net-only reserve utility retains its accumulated lower-bound calculation for compatibility and the historical Strategy B benchmark. The legacy custom-term sweep is additionally capped by the integrated timed cash path before execution. The forecast chart shows net-flow balances; the Overview timeline includes scheduled obligations and maturities.

## Investment options and execution

| Demo product | Lock | Illustrative annual rate | Minimum principal | Entry fee |
| --- | ---: | ---: | ---: | ---: |
| Intraday placement | 6 hours | 4.0% | ₹250,000 | ₹20 |
| Overnight deposit | 24 hours | 5.0% | ₹500,000 | ₹50 |
| Extended deposit | 48 hours | 5.4% | ₹1,000,000 | ₹100 |

Rates are configurable illustrations, not market quotes or guaranteed returns. Early redemption is unavailable. Each new product placement records principal, contracted yield, start, maturity, fee, expected interest, and redemption restrictions.

Manual product selection remains available. The optimizer compares eligible options and chooses the greatest net interest **for a single placement at its actual term**. It is not a global multi-period portfolio optimizer or an equal-horizon comparison. Automatic sweeps use this optimizer after each simulated hour when enabled and eligible.

Execution safeguards include:

- Recalculation against current state before a transfer, under the server's process-wide lock.
- Revision checks to reject stale updates and transactional state copies to prevent partial mutations.
- Optional persisted `request_id` fingerprints: an exact retry returns current state without another investment; reuse with a different action or payload is rejected.
- Simulated success, failure, or timeout-before-execution. Failures and timeouts create audit records without moving money or creating tranches.
- Reconciliation that rejects locked principal exceeding the vault balance.
- Contracted principal and interest release at maturity; funding gaps halt automatic sweeping.

The timeout simulation means that no execution occurred. An unknown outcome from a real provider would need provider-side idempotency and reconciliation, which are outside this application.

## Dashboard and demonstration

| View | What to inspect |
| --- | --- |
| Overview | Liquid cash, required reserve, eligible surplus, locked principal, projected minimum, expected return, and risk status |
| Cashflow forecast | Net and independent gross forecasts, short and long horizons, model status, intervals, and baseline error |
| Investment options | Term constraints, fees, returns, manually selected option, and best-return option |
| Payments & events | Add obligations or receipts, delay settlements, or set a new risk buffer |
| Scenario Lab | Compare normal operations, withdrawal spikes, payday payouts, festival surges, settlement delays, and execution failures |
| Decision history | Recorded before/after reserve and investment calculations with explanations |
| Sweep activity | Movements, failures, locked tranches, maturity schedule, and credited interest |
| Reserve policy / Data sources | Automation settings, minimum buffer, forecast policy, and validated CSV import |

A short demonstration:

1. Open Overview and compare the cash timeline before and after a proposed sweep. Inspect the protected floor and proposed lock period.
2. Review the optimized sweep. Select execution failure or timeout and verify unchanged balances and a deferred decision. A successful simulation locks the principal and charges its fee.
3. Add a large payout or delay a settlement. Inspect the updated reserve, reduced or blocked investment, and decision history.
4. Run a combined Scenario Lab stress. Compare reserve, minimum cash, surplus, net return, funding need, and risk status. Hypothetical scenarios do not save financial changes.
5. Run the read-only chronological strategy comparison from Scenario Lab.
6. Enable auto-sweep under Reserve policy and advance the clock. Follow the resulting investment through maturity and inspect contracted interest.

## Data contracts

### Hourly INR CSV

```csv
timestamp,deposits,withdrawals
2026-10-01T00:00:00Z,10000000,9800000
2026-10-01T01:00:00Z,10200000,9900000
```

The two example rows illustrate the format; imports require **168–5,000 consecutive hourly records**, at most 1 MB. Columns must appear in that order. Timestamps must be valid, unique, ascending, exactly one hour apart, and include `Z` or an explicit offset such as `+05:30`. Seconds and fractional seconds must be zero. Amounts must be finite, nonnegative, at most ₹1 trillion, and cannot be booleans. Invalid or missing values are rejected rather than silently filled.

Use Data sources to download a complete sample CSV. Import replaces the observation history, preserves simulated balances, rebuilds demo scheduled events, and disables automatic sweeping. Import is blocked while new investment tranches are locked. Labels distinguish synthetic observations, imported observations, and subsequently simulated hours.

### Daily multi-currency data

The daily workflow uses a dated numeric net-cashflow column per currency, with a `DatetimeIndex` internally. Its Streamlit CSV loader reads the first column as dates. The default currencies are EUR, USD, JPY, BRL, INR, and AUD. Unlike the hourly contract, net values can be negative. See `validation.py`, `data.py`, and the Streamlit upload controls for the daily preprocessing and validation behavior.

## API reference

The HTTP server binds to loopback only. It serves the dashboard and uses an HttpOnly, SameSite session cookie to separate SQLite-backed workspaces. It applies loopback host checks, same-origin checks, JSON request validation, and a content-security policy. These local safeguards are not production authentication.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Health and simulation mode |
| GET | `/api/state` | Balances, forecasts, integrated intelligence, events, and ledger |
| GET | `/api/template` | Complete hourly sample CSV |
| GET | `/api/export` | Net forecast CSV with policy and recommendation fields |
| POST | `/api/planning_optimize` | Revalidate and simulate the best-return eligible product |
| POST | `/api/planning_invest` | Revalidate and simulate the manually selected product |
| POST | `/api/planning_policy` | Selected product, additional risk buffer, and illustrative rates |
| POST | `/api/planning_event` | Add a payment, withdrawal, deposit, settlement, delay, or risk alert |
| POST | `/api/planning_balance` | Configure simulated balances when no new tranches are locked |
| POST | `/api/planning_scenario` | Read-only timed baseline/stress comparison |
| POST | `/api/backtest` | Read-only 24-hour fallback strategy replay of the current history |
| POST | `/api/policy` | Forecast, floor, custom-term, stress, and automation policy |
| POST | `/api/sweep` | Legacy custom-term sweep with the integrated timed liquidity cap |
| POST | `/api/advance` | Advance one simulated hour and settle due events |
| POST | `/api/import` | Validate and import hourly CSV text |
| POST | `/api/scenario` | Legacy net-only forecast/policy scenario |
| POST | `/api/reset` | Reset the session's sandbox |

Mutation requests require the current `revision`. For an optimized execution:

```json
{
  "revision": 0,
  "request_id": "placement-demo-1",
  "execution": "success"
}
```

Send JSON with `Content-Type: application/json` and retain the session cookie. For an exact retry, reuse the entire original payload, including its revision. `execution` can also be `failure` or `timeout`. Read-only scenario and backtest requests do not increment the revision. Invalid requests are rejected without writing a financial decision; accepted execution failures are recorded.

## Measured strategy comparisons

The saved reports use **seed-42 synthetic INR observations**. Every forecast sees only its historical training prefix; all strategies share the same observations and forecast origins.

- **A — Fixed cash buffer:** retain a configured ₹85 million buffer and invest excess.
- **B — Existing forecast reserve:** original net-only reserve with a 24h, 5%, fee-free demo product.
- **C — Improved Reserve Juggler:** timed, uncertainty-aware reserves and optimized term products with their entry fees.

These compare complete policies, not the isolated impact of one model. Each starts with ₹100 million cash and no existing investments. The historical CSV replay contains no separately scheduled external obligations; scenarios and acceptance tests exercise those. All strategies recalculate hourly, so the replay does not isolate intrahour event-update benefits.

### 72-hour seasonal-naive replay

Evaluation window: 15–18 October 2026 UTC.

| Strategy | Net accrued interest | Average idle cash | Below-floor observations | Maximum funding gap |
| --- | ---: | ---: | ---: | ---: |
| A | ₹8,827.99 | ₹81,295,896.27 | 0 | ₹0 |
| B | ₹32,534.59 | ₹20,891,175.46 | 34 | ₹5,194,766.73 |
| C | ₹31,669.04 | ₹27,547,962.00 | 0 | ₹0 |

Common one-hour net-flow MAE: **₹229,543.66**; RMSE: **₹267,138.54**. C charged ₹1,490 in fees. B earned more net income with modeled floor breaches; C did not outperform every strategy on income.

### 24-hour SARIMAX-pipeline replay

Evaluation window: 17–18 October 2026 UTC.

| Strategy | Net accrued interest | Below-floor observations | Entry fees |
| --- | ---: | ---: | ---: |
| A | ₹2,657.13 | 0 | ₹0 |
| B | ₹10,562.97 | 0 | ₹0 |
| C | ₹10,164.56 | 0 | ₹610 |

Common one-hour MAE: **₹176,854.48**; RMSE: **₹229,795.37**. This run does not demonstrate a net-income improvement over B. The SARIMAX pipeline can fall back at individual origins.

With every third eligible attempt failing in the 72-hour fallback replay, C recorded **11 failures, 11 subsequent recoveries, zero below-floor observations, and ₹31,615.53 net accrued interest**. Recovery means a later eligible placement succeeded, not that money was lost and recovered.

Net interest is accrued interest less entry fees and modeled borrowing costs; accrued returns include still-locked positions and differ from credited interest. Financing cost is an illustrative 12% annual rate charged for one hour on each peak hourly floor gap, without injecting borrowed funds into balances. Below-floor observations are not distinct failed payments; total shortfall can count continuing deficits repeatedly. Early-redemption penalties are zero because early exit is disabled.

Full results: [fallback replay](reports/strategy-comparison.json), [SARIMAX-pipeline replay](reports/strategy-comparison-sarimax.json), and [failure replay](reports/strategy-failures.json).

Reproduce from the repository root:

```powershell
.\.venv-win\Scripts\python.exe -m liquidity_forecasting.strategy_evaluation
.\.venv-win\Scripts\python.exe -m liquidity_forecasting.strategy_evaluation --hours 24 --model sarimax
.\.venv-win\Scripts\python.exe -m liquidity_forecasting.strategy_evaluation --failure-every 3
```

Use `--output path/to/report.json` to keep separate runs; the default output is `.runtime/strategy-comparison.json`.

## Testing and verification

Latest recorded verification, **18 October 2026**:

| Check | Result |
| --- | --- |
| Baseline suite before alignment changes | 96 passed |
| Final complete suite | **116 passed in 13.71 seconds** |
| Ruff lint | Passed |
| Ruff formatting | 36 files passed |
| Both frontend JavaScript syntax checks | Passed |
| Real-model HTTP integration | Passed in the suite |
| Browser checks | Overview, optimized review, failure with unchanged balances, stress blocking, strategy table, and timeline inspected |

Coverage includes chronological payout protection, same-time outflow priority, forecast uncertainty, fees, product constraints, maturity interest, locked-principal exclusion, settlement delays, funding gaps, failure/timeout deferral, exact retries, stale revisions, reconciliation, isolated scenarios, training-prefix leakage checks, and the original daily multi-currency functionality.

```powershell
.\.venv-win\Scripts\python.exe -m pytest -q
.\.venv-win\Scripts\python.exe -m ruff check .
.\.venv-win\Scripts\python.exe -m ruff format --check .
node --check web/app.js
node --check web/planning.js
```

Some Windows sandbox runs blocked pytest temporary directories or loopback sockets. The final complete suite ran outside those restrictions. If temporary-directory creation fails, use a fresh workspace path such as `--basetemp=.runtime/pytest-new-run`. A loopback permission failure is an environment restriction, not a passed integration check.

See [VERIFICATION.md](VERIFICATION.md) for the verification record and [ALIGNMENT_REPORT.md](ALIGNMENT_REPORT.md) for the audit, acceptance evidence, detailed assumptions, and implementation changes. The test suite was not rerun for this documentation-only README update.

## Multi-currency daily workflow

The original daily engine remains separate from hourly investment execution. It supports:

- SARIMAX forecasts with seasonal-naive fallback and prediction intervals.
- Opening balances, minimum buffers, projected balances, and liquidity shortfalls.
- EUR base-currency normalization with configurable illustrative FX rates.
- SciPy linear-programming allocation under funding, transfer-cost, and priority constraints.
- Rolling chronological forecast evaluation, plotting, and Excel export.

Run its Streamlit dashboard or batch demonstration:

```powershell
.\.venv-win\Scripts\python.exe -m streamlit run app.py
.\.venv-win\Scripts\python.exe main.py
```

The batch script generates sample daily cashflows, forecasts and allocation recommendations, writes an Excel report, and displays forecast plots. These analytical allocations are not executed bank transfers. The hourly dashboard's term-product optimizer and daily engine's funding-allocation optimizer serve different purposes.

## Repository structure

```text
LiquidityForecasting-main/
├── server.py                     # Loopback API, static files, SQLite session storage
├── start.ps1                     # Windows background/foreground launcher
├── app.py                        # Daily multi-currency Streamlit application
├── main.py                       # Daily batch demonstration
├── liquidity_forecasting/
│   ├── treasury.py               # Forecasts, simulated settlement, state mutations
│   ├── planning.py               # Timed cash path, reserves, products, explanations
│   ├── strategy_evaluation.py    # Common-data A/B/C chronological replay
│   ├── model.py                  # SARIMAX and seasonal-naive fallback
│   ├── evaluation.py             # Daily rolling forecast evaluation
│   ├── data.py / validation.py   # Daily data generation and validation
│   ├── balances.py / fx.py       # Daily projections and FX normalization
│   ├── allocation.py             # Constrained daily funding allocation
│   └── export.py / plotting.py   # Excel reports and plots
├── web/                          # Dashboard HTML, CSS, and JavaScript modules
├── tests/                        # Unit, acceptance, and HTTP integration tests
├── reports/                      # Saved measured synthetic replay results
├── requirements*.txt            # Runtime, development, and locked dependencies
├── ALIGNMENT_REPORT.md           # Current audit, methodology, results, and demo
├── VERIFICATION.md               # Recorded checks and test evidence
├── PLANNING.md / HANDOVER.md      # Earlier design details with update notices
└── .runtime/                     # Local SQLite state, logs, and generated artifacts
```

## Limitations and troubleshooting

- **No real financial execution:** no bank integration, investment provider, live market rates, or provider-side timeout reconciliation is configured.
- **Local architecture:** the server uses a process-wide lock and local SQLite sessions. Production authentication, external event streaming, scheduling, failover, and multi-process execution controls are not implemented.
- **Modeled liquidity protection:** uncertainty and payment-channel assumptions need calibration on real data. Neither test results nor demo risk labels guarantee future payouts.
- **Operational reserve only:** RBI CRR/SLR balances and regulatory compliance are not calculated. Such balances are outside the demo's investable pool.
- **Legacy vault holdings:** opening invested balances have no contractual redemption schedule and are never treated as immediately spendable. New tranches have explicit maturities.
- **Stale revision:** refresh the workspace and review the new recommendation. Exact operation retries require the original request ID and payload.
- **No eligible investment:** inspect the minimum principal, fees, risk buffer, upcoming obligations, forecast uncertainty, and modeled funding gap.
- **Import blocked by locked tranches:** wait for simulated maturities or use the explicitly destructive sandbox reset if you intend to discard that session's simulation.
- **Model appears to pause on first load:** the first request fits the model; subsequent identical history/policy forecasts use the cache.
- **Port already in use:** reuse the intended server or choose another port. Restart an old backend process after Python changes.

Licensed under the [MIT License](LICENSE).
