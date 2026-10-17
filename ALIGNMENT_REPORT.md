# Reserve Juggler — verified problem-statement alignment

Updated 18 October 2026. This is an improvement of the existing repository,
not a replacement application. All money movement remains simulated.

> Reserve Juggler predicts when cash will be needed, protects modeled upcoming
> payments, and automatically invests eligible surplus while responding to
> liquidity events.

## Audit and priority gaps

The unchanged baseline test run passed **96 tests in 21.70 seconds**.
Source inspection confirmed the INR hourly simulator, chronological planning,
three term products, fees, scheduled obligations, SQLite sessions, revision
checks, CSV validation, SARIMAX/fallback net forecasts, stress scenarios,
decision history, and the separate daily multi-currency allocation workflow.
No new prediction library or runtime dependency was needed.

The main gaps were integration and execution correctness:

| Gap found in source | Implemented change |
| --- | --- |
| Planner used a deterministic hourly average independently of SARIMAX | Timed planner reconciles gross profiles to the net forecast and includes forecast uncertainty |
| Configured product was the only investment recommendation | Retain manual product selection and compare all three products for highest eligible net return |
| Automatic sweep used a separate product path | Automatic hourly placements use the same optimized, timed planner as investment review |
| Hourly settlement netted aggregate flows and redeemed maturities last | Merge gross outflows, inflows, scheduled events, and maturities on one clock; outflows win ties |
| Revision checking prevented duplicates but did not acknowledge exact retries | Persist request fingerprints; identical retries return current state without another movement; changed payloads and stale new operations are rejected |
| Execution could only succeed | Simulated failure and timeout-before-execution produce audit records without changing balances or creating tranches |
| No treasury A/B/C performance comparison | Rolling chronological replay with common observations, error metrics, fees, funding gaps, idle cash, utilization, failures, and recovery counts |
| Gross forecast values absent | Independent seasonal-naive deposit/withdrawal forecasts with intervals in API and means in forecast table |

## Integrated decision rules

`treasury.forecast` retains the SARIMAX net model and seasonal-naive fallback.
`planning.timeline` reconciles each hourly gross deposit estimate to that net
forecast, splits withdrawals across the existing illustrative payment rails,
reclassifies 8% of deposits as merchant receipts, adds scheduled obligations,
and includes existing principal plus contracted interest only at maturity.
An extreme negative net forecast increases modeled withdrawals rather than
inventing positive receipts. Gross seasonal-naive forecast estimates are
separate display estimates; they need not equal the authoritative net forecast.

Forecast uncertainty uses incremental root-sum-square lower-bound widths:
at hour h the total allowance is sqrt(sum((mean - lower)^2 through h)).
This uses an **uncorrelated-error assumption**. It is an explicitly disclosed
planning heuristic, not a calibrated confidence interval for a cash path.
Serially correlated errors, unseen payment peaks, and wrong forecasts can
invalidate modeled safety; additional configured buffers and scenarios matter.
The legacy net-only reserve utility retains its accumulated lower-bound method
for compatibility and Strategy B. The legacy custom-term sweep is also capped
by the integrated timed path before execution.

For each 6h, 24h, and 48h option, retain operational floor plus additional risk
buffer plus worst cumulative drawdown during its lock. Deduct entry fees
immediately and round eligible principal down to cents. Reject investments
below minimum, with nonpositive net earnings, or with modeled funding gaps.
The full 72-hour baseline is also checked for fee-induced shortfalls after
maturity. Never use vault holdings as current liquid cash. Existing legacy
vault holdings have no assumed redemption date.

The optimizer chooses the greatest net interest **per single placement**,
comparing each option at its actual term. This is not a globally optimal
rolling portfolio or an equal-horizon annualized comparison. Manual selection
remains available. Rates of 4%, 5%, and 5.4% are illustrative configured demo
terms, not available market quotes or guarantees. Early redemption is disabled;
penalties are therefore zero rather than an invented emergency exit mechanism.

Events, policy changes, imports, executions, and maturities recalculate the
recommendation. Risk alerts can set a new additional risk buffer. Settlement
delays move receipts later. Known payouts remain separate from forecast history
until processed. Execution re-evaluates against the current state inside the
server's lock; only a successful placement deducts cash/fee and adds a locked
tranche. Each new tranche stores start, maturity, principal, yield, fee,
expected interest, and redemption restrictions. Revision checks, transactional
state copies, a single SQLite state write, and reconciliation of locked
principal against vault balance protect the local simulation.

`request_id` deduplicates an exact action and payload, including its original
revision, across retries and restarts. A repeated key with different contents
is rejected. A new key with a stale revision is rejected. Omitted keys retain
legacy revision protection. The simulated timeout means **no execution took
place**; an unknown outcome from a real provider would require provider-side
idempotency and reconciliation and is not modeled here.

## Measured results

The complete figures and assumptions are saved in `reports/*.json`.
All observations below are **seed-42 synthetic INR cashflows**, not bank data.
Each strategy starts with ₹100 million cash and no historical investments.
Fixed strategy A uses an explicitly configured ₹85 million buffer. B uses the
original forecast reserve and 24h/5% fee-free simulated product. C uses the
integrated planner with the existing term fees. Thus the comparison measures
the complete policies, not an isolated forecast model improvement.

Every hourly forecast is fitted only to the prefix ending before the observed
hour. All three strategies share that forecast and chronological gross flows.
The CSV replay contains no separately scheduled external obligations; those
are exercised in the scenario and acceptance tests. All three strategies are
reevaluated hourly; this experiment does not isolate the incremental value of
intrahour event updates.

### 72-hour seasonal-naive replay: 15–18 October 2026 UTC

| Strategy | Net accrued interest | Average idle cash | Below-floor observations | Max funding gap |
| --- | ---: | ---: | ---: | ---: |
| A — Fixed buffer | ₹8,827.99 | ₹81,295,896.27 | 0 | ₹0 |
| B — Original forecast reserve | ₹32,534.59 | ₹20,891,175.46 | 34 | ₹5,194,766.73 |
| C — Improved Reserve Juggler | ₹31,669.04 | ₹27,547,962.00 | 0 | ₹0 |

Common one-hour net forecast MAE: ₹229,543.66; RMSE: ₹267,138.54.
C charged ₹1,490 entry fees and credited ₹22,655.18 realized interest; its
₹33,159.04 accrued interest includes still-locked investments. B's higher
net income came with modeled floor breaches. Do not claim C maximizes realized
income across every strategy or every risk assumption.

### 24-hour SARIMAX-pipeline replay: 17–18 October 2026 UTC

| Strategy | Net accrued interest | Below-floor observations | Entry fees |
| --- | ---: | ---: | ---: |
| A | ₹2,657.13 | 0 | ₹0 |
| B | ₹10,562.97 | 0 | ₹0 |
| C | ₹10,164.56 | 0 | ₹610 |

Common one-hour forecast MAE: ₹176,854.48; RMSE: ₹229,795.37. C's realized
interest was ₹246.39; most interest was still accrued on locked positions.
This run does not demonstrate a yield improvement over B. The SARIMAX pipeline
can fall back if fitting fails; the evaluation label identifies the requested
pipeline, not a guarantee that every fitted origin converged.

### Failure injection

In the 72-hour fallback replay with every third eligible attempt failing,
C recorded 11 failed attempts, 11 subsequent recoveries, zero below-floor
observations, and ₹31,615.53 net accrued interest. Recovery means the next
eligible placement succeeded; it does not mean recovery of money lost in a
failed transfer. Failure attempts never moved funds. All data are in
`reports/strategy-failures.json`.

Net income is accrued interest less entry fees and illustrative financing cost.
The financing assumption charges 12% annually for one hour on each peak hourly
floor gap; funds are not silently borrowed into balances. Total shortfall is
the sum of observed below-floor gaps and can count a continuing deficit more
than once. Penalties are zero because early redemption is unavailable.
Utilization is successful principal divided by summed eligible principal at
attempts, not unique capital throughput.

## Verification and acceptance evidence

The original 96 tests were preserved; the final suite passed **116 tests in 13.71 seconds**. Ruff lint, the 36-file format check, and both JavaScript syntax checks passed. New acceptance tests cover forecast
uncertainty, optimized selection, fees, failure and timeout deferral, persisted
exact retries, stale keys, intrahour maturities, same-time obligations before
redemption, reconciliation, explicit timezones, extreme net outflows, gross
forecast alignment, boolean rejection, risk alerts, isolated scenarios, and
training-prefix leakage checks. Existing tests cover CSV constraints,
chronological payout protection, maturity interest, settlement delay, stress,
HTTP isolation, persistence, and the multi-currency/daily engine.

Browser verification used the actual backend: overview values, optimized
48-hour review, failed placement with unchanged cash, strategy replay output,
and combined festival/settlement-delay scenario blocking new investment.
Screenshot: `.runtime/alignment-scenario.png`. Final test/check results are
recorded in `VERIFICATION.md`.

## Installation and execution

On the prepared Windows machine:

```powershell
.\start.ps1
# Or run the backend explicitly:
.\.venv-win\Scripts\python.exe server.py --port 8000
```

For a fresh environment, install Python 3.12, create a virtual environment,
and install `requirements.txt` and `requirements-dev.txt`. The existing lock
file records the prepared environment. No new packages were added.

```powershell
python -m venv .venv-win
.\.venv-win\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv-win\Scripts\python.exe -m pytest -q --basetemp=.runtime/pytest-new-run
.\.venv-win\Scripts\python.exe -m ruff check .
node --check web/app.js
node --check web/planning.js
```

Use a fresh `--basetemp` directory if Windows sandbox temporary-directory
permissions prevent pytest from creating its default numbered directory.

Reproduce evaluation:

```powershell
.\.venv-win\Scripts\python.exe -m liquidity_forecasting.strategy_evaluation
.\.venv-win\Scripts\python.exe -m liquidity_forecasting.strategy_evaluation --hours 24 --model sarimax
.\.venv-win\Scripts\python.exe -m liquidity_forecasting.strategy_evaluation --failure-every 3
```

The API exposes `/api/planning_optimize` with revision, optional request_id,
and execution (`success`, `failure`, `timeout`). `/api/backtest` performs a
read-only 24-hour fallback replay of the session's current history.
`/api/planning_scenario` accepts hypothetical withdrawal, UPI, delay, payout,
and execution assumptions. It never saves balances. Existing endpoints remain.

## Demonstration walkthrough

1. Open Overview: inspect liquid cash, locked principal, reserve, projected
   minimum, eligible principal, selected terms, best-return option, and timeline.
2. Open Cashflow forecast: inspect 1h/6h/24h/48h/72h net forecasts and independent
   gross forecasts, model status, intervals, timestamps, and baseline error.
3. Open Investment options: compare minimums, fees, rates, terms, and net return.
   Review optimized sweep, select failure/timeout, and inspect the deferred
   explanation and unchanged balances. Review again and choose success to lock
   a new tranche.
4. Open Payments & events: add a payout, deposit, settlement, or delay. A risk
   alert sets the additional risk buffer. Inspect the before/after decision.
5. Scenario Lab: compare normal, +50% withdrawals, festival spending plus
   delayed settlement, unexpected payout, or execution failure. Funding gaps
   remain visible. Run the chronological strategy comparison.
6. Enable auto-sweep under Reserve policy and advance one hour: eligible
   placements use the optimizer. Continue advancing through maturity and inspect
   Sweep activity and contracted interest credits. A funding gap halts automation.
7. Inspect Decision history, locked tranches, and CSV export. The original
   multi-currency Streamlit application (`app.py`) and batch CLI (`main.py`)
   remain available through their existing documented commands.

## Files changed

- `liquidity_forecasting/planning.py`: forecast-aware timeline, optimization,
  risk alerts, explanations, execution outcomes, tranche terms.
- `liquidity_forecasting/treasury.py`: gross forecasts, integrated legacy cap,
  chronological settlement, automated optimization, retries, reconciliation.
- `liquidity_forecasting/strategy_evaluation.py`: new common-data replay CLI.
- `server.py`: optimize and read-only replay endpoints.
- `web/planning.js`: optimized review, failure controls, stress results,
  timeline, and measured strategy comparison.
- `web/app.js`: request identifiers, gross forecast columns, short horizons,
  failed-sweep ledger filter.
- `tests/test_integrated_treasury.py`, `tests/test_server.py`: acceptance and
  endpoint regression coverage.
- `reports/*.json`: reproducible measured results.
- README, planning, handover, verification, and this report: current behavior,
  evidence, demonstrations, and limits.

## Remaining limits

No bank connection, real provider, external event bus, production scheduler,
provider timeout reconciliation, authentication, regulatory reserve compliance,
or production failover is implemented. This remains a loopback simulation with
one process-wide lock. Failed/rejected computed options explain their reasons;
invalid HTTP requests are rejected without writing a financial decision, while
accepted failures/timeouts are persisted in the ledger. Event-driven simulation
recalculates when API events arrive; it is not a real-time banking feed.
Forecast uncertainty has not been calibrated on real bank data. No universal
payout guarantee or general outperformance claim is justified by these tests.
