> **18 October 2026 alignment update:** The planner now uses the net forecast and uncertainty, optimized automatic sweeping, chronological intrahour settlement, simulated execution failure/retry handling, and measured strategy replay. See [ALIGNMENT_REPORT.md](ALIGNMENT_REPORT.md) for current methodology, results, demo steps, and limits. Earlier deterministic-only descriptions below are historical.

# Reserve Juggler — implementation handover

For the current time-aware deterministic dashboard, investment comparison,
event simulation and combined stress testing, see [PLANNING.md](PLANNING.md).
The sections below document the preserved original SARIMAX and daily workflows.

## Product understanding

The platform must keep enough immediately available cash to meet withdrawals
while allocating surplus to an overnight yield account. Those objectives compete:
cash is available but earns nothing; a vault earns interest but locks principal.
Reserve Juggler gives a treasury operator an explainable reserve, a proposed sweep,
and a stress scenario before acting.

The supplied $20M hourly movement and 5% annual yield are problem assumptions,
not verified bank statistics or current market quotes. Default synthetic gross
flows average approximately $20M per hour. All balances and transfers are
simulated. Imported cashflows become model inputs, not account balances.

No finite statistical forecast can guarantee all payouts under arbitrary shocks.
This implementation explicitly shows funding gaps and stops automatic sweeping
after simulated cash becomes negative. It does not invent emergency funding or
claim that unpaid obligations were successfully settled.

## Supplied material and reference analysis

Inputs inspected: the pasted master prompt, all Python source modules and tests,
README, dependencies, project configuration, CI workflow, and license. No separate
CVP/ideation Markdown, production bank API, authentication service, or trained
model artifact was supplied. The repository README serves as the discovery
reference; the supplied code fits statistical models from observations.

| Source idea | Existing implementation | New implementation / boundary |
| --- | --- | --- |
| Anticipate cash shortages | Daily SARIMAX with fallback and prediction intervals | Hourly USD forecasting using the same pipeline and a 24-hour seasonal cycle |
| Keep operating buffers | Daily opening-balance and shortfall projections | Reserve covers the largest planned drawdown over the new sweep lock period |
| Make allocations explainable | EUR-normalized multi-currency funding optimization | Cash-to-vault surplus recommendation, with the retained reserve and yield shown |
| Assess reliability | Rolling backtest utilities | Existing tests retained; web UI shows actual model/fallback and a clearly identified seasonal-naive holdout MAE |
| Govern decisions | Configuration in Streamlit | Server-validated policy, revision checks, atomic persistence, simulated ledger |
| Import and report | Daily CSV/XLSX and Excel reporting | Strict hourly CSV import and forecast/activity CSV export; original XLSX workflow preserved |
| Live ingestion and scheduled transfers | Proposed in README | Not connected; explicit continuous simulation available while the browser is open |

The core value proposition is a clearer, auditable trade-off between payout
liquidity and idle cash. Treasury operators benefit from seeing what is happening,
the forecast evidence, the risk of a withdrawal surge, and the next eligible action
in one workflow. The principal improvement over a mean-only allocation is
planning for the maximum drawdown within the lock window, not only its final hour.

## Design and pages

The interface is white-dominant with navy typography and blue forecast/action
accents. Green, amber, and red carry status meanings. A system font stack keeps
the application independent of remote font services. Fluid headline sizes and
asymmetric layouts distinguish the landing page from the dense workspace.

The landing scene uses original CSS perspective cards for the cash buffer and
yield vault. Subtle vertical motion explains the two destinations; no image
licensing or WebGL dependency is involved. A static fallback and reduced-motion
styles are included. Charts are generated as SVG from API results, with keyboard
focusable points, visible tooltips, an accessible description, and a companion
table. Forms use native labels, bounds, validation, and feedback. Navigation
collapses at narrow widths; tables scroll within their container.

| Page | Primary user / purpose | Working interactions | API |
| --- | --- | --- | --- |
| Home | New operator; understand the liquidity/yield trade-off | Workspace CTA, explanation anchor, scenarios link | None |
| Overview | Treasury operator; review available cash and the next allocation | 24/48/72h chart, sweep review dialog, one-hour simulation, export | GET state/export; POST sweep/advance |
| Cashflow forecast | Analyst; inspect the evidence | Horizon selector, keyboard/hover points, numerical table, model explanation | GET state/export |
| Scenario lab | Risk operator; compare hypothetical stress | Normal/payday/shopping presets, editable assumptions, calculated results; simulation start/pause | POST scenario/advance |
| Sweep activity | Treasury reviewer; audit movements | Search, type filter, newest/oldest sorting, pagination, record details, CSV export, maturity table | GET state; filtered ledger export in browser |
| Reserve policy | Treasury operator; govern allocation | Cash floor, interval confidence, lock period, stress, yield, automatic sweeps, reset confirmation | POST policy/reset |
| Data sources | Analyst; validate input provenance | Sample download, CSV import with validation, source details | GET template; POST import |

## Architecture and changed files

```text
LiquidityForecasting-main/
├── web/
│   ├── index.html                 semantic document and app mount
│   ├── app.js                     route renderer, components, charts, API client
│   ├── styles.css                 responsive design system and dimensional scene
│   └── favicon.svg                original brand mark
├── server.py                      loopback HTTP API and SQLite session store
├── start.ps1                      Windows launcher
├── liquidity_forecasting/
│   ├── treasury.py                hourly data, policy, reserve, simulation ledger
│   ├── model.py                   existing SARIMAX with optional frequency
│   ├── evaluation.py              existing baseline with optional frequency
│   └── ...                        original daily analysis modules preserved
├── tests/
│   ├── test_treasury.py            accounting, policy, import and actual model tests
│   ├── test_server.py              sessions, security, persistence, real API workflow
│   └── ...                        original tests preserved
├── .runtime/                      ignored local SQLite data (never packaged)
├── .venv-win/                     prepared Windows environment (never packaged)
├── app.py                         original Streamlit dashboard, unchanged
├── main.py                        original daily CLI, unchanged
├── requirements.txt               original runtime dependencies
├── requirements-dev.txt           original test/development dependencies
├── requirements-lock.txt          exact installed versions used for verification
├── pyproject.toml                 excludes local runtime and Windows environment
├── README.md                      entry point to both applications
└── HANDOVER.md                     this document
```

The frontend presents server-returned amounts and sends intentions rather than
calculating an authoritative sweep. The server validates inputs, serializes
mutations, checks revisions, and persists a complete result only after successful
calculation. The model layer owns fitting, inference, intervals, and fallback.

`model.py` and `evaluation.py` add an optional `frequency` argument, defaulting
to `D`, so original callers keep daily semantics. Both SARIMAX and fallback
paths now advance the selected frequency; hourly results never receive daily
timestamps accidentally. `treasury.py` and `server.py` were needed because the
original project had neither hourly planning nor HTTP endpoints. No existing
Streamlit workflow, funding optimizer, or Excel exporter was replaced.

## Forecast and reserve contract

Input is a consecutive hourly USD series with separate nonnegative deposits and
withdrawals. The model fits `deposits - withdrawals` using at most the latest 672
hours (28 days), SARIMAX order `(1,0,0)` and seasonal order `(1,0,0,24)`.
It produces 72 hourly means, lower bounds, and upper bounds at the selected
90%, 95%, or 99% pointwise confidence. Failed/nonconverged fitting uses the existing
seasonal-naive fallback with a 24-hour cycle and labels it in the UI.

The gross withdrawal stress profile averages each hour of day over the latest
14 days. This is an explicit seasonal profile, not a separately claimed ML model.
The displayed MAE measures a previous-day seasonal-naive prediction on the final
168 hours. It is not a backtested accuracy measure of the current SARIMAX fit.

For each hour `h` until the new sweep matures:

```text
stressed_lower_flow[h] = lower_bound[h] - withdrawal_profile[h] * stress_pct / 100
drawdown = max(0, -min(cumulative_sum(stressed_lower_flow)))
required_reserve = minimum_buffer + drawdown
sweep = max(0, available_cash - required_reserve)
```

The reserve rounds up to cents and sweeps round down. Immediate minimum cash is
also protected even if all projected flows are positive. Existing locked funds
are excluded from spendable cash. Accumulated pointwise bounds are conservative
planning envelopes, **not** calibrated joint path intervals. Risk within an hour,
unexpected shocks, and bank/settlement failures remain outside the guarantee.

Starting balances are $32M cash and $68M vault. The existing $68M is a simulated
holding with no redemption schedule and is never released automatically. New
sweeps create individually locked tranches. A simulated clock step generates a
new observation, applies net flow, releases tranches reaching maturity, credits
simple interest at their original rate, and optionally sweeps fresh surplus.
There is no early withdrawal action. Daily-yield metrics are estimates, while
earned interest is credited only on maturity of new tranches.

Continuous simulation advances an hour every 60 seconds while the tab is open
and visible. The timer is not a production background scheduler. Operations pause
while an action or dialog is pending or a form is focused; refreshing/closing
the browser page stops the timer. The workspace refresh button only reloads data.

## Run locally

Tested with Python 3.12 on Windows. The supplied `.venv` contains Unix binaries,
so a separate `.venv-win` was created without modifying it.

For this prepared checkout:

```powershell
./start.ps1
# Or:
.\.venv-win\Scripts\python.exe server.py --port 8000
```

Open http://127.0.0.1:8000. The Windows launcher starts a hidden background
server and checks readiness. Running it again reuses the healthy server.
Logs and the server PID are stored under `.runtime/`. To stop that background
server, run `Stop-Process -Id (Get-Content .runtime/server.pid)` from this folder.
Use `./start.ps1 -Foreground` for a terminal server that stops with `Ctrl+C`.

For a fresh Windows machine with Python 3.12:

```powershell
py -3.12 -m venv .venv-win
.\.venv-win\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv-win\Scripts\python.exe server.py --port 8000
```

On macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python server.py --port 8000
```

To reproduce the exact tested dependency versions on Python 3.12, install
`requirements-lock.txt` instead. No Node installation, frontend build, credentials,
API keys, or environment variables are required. The database is created under
`.runtime/treasury.sqlite3`. Each browser cookie identifies its own persisted
workspace. Retain that cookie and database to resume the same simulation.

The original daily applications still run with `streamlit run app.py` and
`python main.py`. They accept their original daily multi-currency format, which
is deliberately different from the new hourly CSV contract.

## HTTP API

All endpoints are same-origin under the local server. `GET /api/state` establishes
an opaque `HttpOnly; SameSite=Strict` session cookie. It is local session isolation,
not enterprise identity/authentication. The server binds only to `127.0.0.1`, checks
Host and Origin, has no CORS allowance, uses parameterized SQL, bounds request
sizes, and sends CSP/nosniff headers. Do not expose this development HTTP server to
the public internet. HTTP cookies intentionally do not use `Secure` on localhost.

| Method / path | Request | Success response |
| --- | --- | --- |
| GET `/api/health` | None | `{status:"ok", mode:"simulation"}` |
| GET `/api/state` | Session cookie if resuming | Snapshot described below |
| GET `/api/template` | None | CSV of 1,008 synthetic hourly observations |
| GET `/api/export` | Session cookie | 72-row forecast CSV including policy, model, source, and recommended sweep |
| POST `/api/policy` | `{revision, policy}` | Updated snapshot |
| POST `/api/scenario` | `{policy}` | `{plan, forecast, policy}`; no saved state changes |
| POST `/api/sweep` | `{revision}` | Updated snapshot; amount recomputed by server |
| POST `/api/advance` | `{revision}` | Updated snapshot after one simulated hour |
| POST `/api/import` | `{revision, csv:"..."}` | Updated snapshot; auto-sweep disabled |
| POST `/api/reset` | `{revision}` | Starting snapshot with incremented revision |

All POST requests require `Content-Type: application/json`. A policy object must
have exactly these fields:

```json
{
  "minimum_buffer": 6000000,
  "annual_yield": 5,
  "confidence": 95,
  "lock_hours": 24,
  "withdrawal_stress": 0,
  "auto_sweep": false
}
```

Bounds: buffer 0–10 billion USD; annual yield 0–20%; confidence 90/95/99; integer
lock hours 1–72; withdrawal stress 0–100%; automatic sweeping boolean. All numbers
must be finite. Each successful mutation increments `revision`; stale revisions
are rejected so repeat submissions cannot execute the same proposal twice.

Snapshot fields:

- `revision`, `mode`, `source`, `as_of`, `history_count`, `policy`.
- `cash`, `vault`, `earned`, `gross_hourly`, `daily_vault_yield` in USD.
- `model`, `converged`, `baseline_mae` explaining the calculation.
- `plan`: `required`, `drawdown`, `sweep`, `shortfall`, `stress_outflow`,
  `daily_yield`, `retained`.
- `forecast`: 72 rows of `timestamp`, `mean`, `lower`, `upper`, `withdrawals`,
  `balance`, `lower_balance`, `upper_balance`.
- `history`: latest 168 observed rows; the complete dataset is held server-side.
- `ledger`: newest-first, up to 1,000 entries with reference, time, type, amount,
  description, and simulated status.
- `tranches`: amount, maturity, original rate, and original lock period.

Errors are JSON `{error:"message"}` with 400 for invalid/stale input, 403 for
host/origin rejection, 404 for unknown resources, 413 for oversized bodies, 415
for non-JSON mutations, and 500 for internal failures. Failed mutations do not
save partial state. Detailed internal errors stay in the server log.

Hourly CSV format (minimum 168, maximum 5,000 rows; maximum 1 MB):

```csv
timestamp,deposits,withdrawals
2026-10-01T00:00:00Z,10000000,9800000
2026-10-01T01:00:00Z,10200000,9900000
```

Columns must appear in that order. Timestamps must be unique, increasing, on the
hour, and one hour apart. Explicit offsets normalize to UTC; naive timestamps are
treated as UTC. Missing, negative, infinite, or above-trillion cashflows are
rejected. Import while new sweep tranches are locked is blocked; reset first.

## Verification

Automated suite covers the original daily forecasting/optimization/export
features plus hourly timestamp handling, finite model output, buffer protection
at every step, stress funding gaps, money conservation, duplicate revisions,
locked funds, original-rate maturity interest, automatic sweeps, unfunded
shortfalls, strict imports, local session isolation, persistence, HTTP protections,
and a complete HTTP flow with the real fitted model.

Commands:

```powershell
.\.venv-win\Scripts\python.exe -m pytest -q
.\.venv-win\Scripts\python.exe -m ruff check .
.\.venv-win\Scripts\python.exe -m ruff format --check .
node --check web/app.js
```

Final execution counts and browser verification limits are recorded in
`VERIFICATION.md`. Initial fixture and sandbox temporary-directory failures were
fixed/retested. The loopback server returned a successful health response.

## Production boundary and next integrations

This deliverable is a complete local demonstration workflow, not a deployed bank
treasury service. Sites design guidance was used, but its Worker hosting cannot
run this Python/statsmodels backend directly. The working Python application is
delivered locally rather than publishing a disconnected static replica.

Production requires authenticated users and roles, governed bank balances,
transaction/settlement feeds, timezone/cutoff calendars, API transfer idempotency,
bank confirmation reconciliation, durable job scheduling, operating limits,
liquidity facilities, maturity-aware funding, policy approvals, alert delivery,
validated intrahour forecasting, coverage/backtesting, and operational monitoring.
Those are explicitly unconnected integrations, not hidden mock capabilities.

The source archive excludes environments, private runtime/session data, caches,
logs, generated reports, and archive files. It includes source, tests, docs,
license, original workflow files, and the tested dependency lock.
