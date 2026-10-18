# Reserve Juggler: proposed ML integration contract

Status: **historical operational proposal; operational replacement not implemented**.
Audit date: 18 October 2026. A limited, disabled-by-default shadow boundary is now
implemented; [SHADOW_INTEGRATION.md](ai_ml/docs/SHADOW_INTEGRATION.md) is the current
contract for that path and records the architecture, safety gates and validation.
The inventory and line references below describe the earlier audit (including
the older JavaScript frontend); the active frontend is React and authentication
uses MongoDB users with SQLite workspaces. The detailed operational proposal
below is not an implemented activation contract.
Scope: the INR hourly application (`server.py`, `web/`), not the separate daily,
multi-currency application (`app.py`, `main.py`). The README is the requirements
reference; sections 1–4 below describe actual code. Sections 5–10 specify proposed
behavior. No model selection, deployment, data permission, or artifact transfer is
authorized by this document. See [the gap report](BACKEND_FRONTEND_INTEGRATION_GAPS.md).

## 1. Evidence and ownership

Repository references use one-based lines in the audited source. Links identify
the exact implementation; the adjacent line numbers locate it.

| Evidence | Implemented behavior |
| --- | --- |
| [README.md](README.md), lines 7–12, 74–120, 177–231 | Two applications; hourly INR, 72-hour forecast, uncertainty, chronological treasury protection, import and HTTP requirements |
| [server.py](server.py), lines 120–163, 183–260 | Actual HTTP routing, CSV export, request guards and transaction boundaries |
| [treasury.py](liquidity_forecasting/treasury.py), lines 72–219, 252–308 | Observation validation, net and independent gross predictions, state response |
| [planning.py](liquidity_forecasting/planning.py), lines 99–381 | Timed gross profile, net reconciliation, uncertainty heuristic and investment decisions |
| [treasury.py](liquidity_forecasting/treasury.py), lines 361–493, 496–566 | Actual settlement, audit, revision and idempotency behavior |
| [web/app.js](web/app.js), lines 128–199, 414–454, 531–540 | Frontend transport, horizon selection, forecast display and active route selection |
| [web/planning.js](web/planning.js), lines 6–63, 66–149 | Active treasury views, scenario comparison and mutations |

The backend owns cash/vault balances, realized observations, scheduled events,
chronological settlement, reserve floors, treasury policy, product eligibility,
fees, maturity, execution, audit and persistence. ML owns authorized feature
engineering, training/evaluation, approved artifacts and a prediction adapter.
Predictions are estimates and must never authorize or post accounting movements.

## 2. Current HTTP and observation conventions

All GETs below have no body or supported forecast query parameters. Query strings
are discarded for routing. HTTP is loopback-only; the `rj_session` cookie selects
a SQLite workspace. POSTs require a JSON object and `Content-Type:
application/json`, accept at most 1,100,000 request bytes, and reject a supplied
cross-origin `Origin`. A missing Origin is permitted. See `server.py:102–118,
183–215,264–269`.

Every mutation body adds `revision` (current workspace revision) and may add
`request_id` (1–128 characters). Successful mutations return the full State below
and increment revision. An exact request retry returns current State without a
second mutation, even when its original revision is now stale. Reuse with another
action/payload is rejected. Scenario/backtest calls bypass revision/idempotency
handling and do not change an existing workspace. First access can initialize a
workspace. See `treasury.py:496–566`, `server.py:218–254`.

Errors are `{ "error": string }`: 400 for validation and stale revision, 403
host/origin, 404 unknown route, 413 size, 415 media type, 500 unhandled failures.
There are no structured ML error codes, explicit unavailable-forecast response,
or warning arrays. A failed action is not persisted; an accepted simulated
execution failure/timeout is persisted as a decision with unchanged funds.

Current observations (`HistoryRow`):

```text
{ timestamp: string, deposits: number, withdrawals: number }
```

- `deposits` and `withdrawals` are positive-side gross amounts in **INR rupees**,
  not paise, lakhs, crores, USD, net flow, or cumulative balances. Zero is allowed.
  Currency is implicit in CSV and explicit as `State.currency = "INR"`.
- Import requires 168–5,000 rows, those exact three columns in order, finite
  amounts in [0, 1e12], no missing values, no booleans, unique ascending timestamps
  exactly one hour apart. Numeric CSV text is parsed/coerced to floats.
- Input timestamps require `Z` or an explicit offset such as `+05:30`; seconds
  and microseconds must be zero. The hour grid need not start at minute 00:
  00:00 IST normalizes to 18:30 UTC. Import normalizes to UTC
  `YYYY-MM-DDTHH:MM:SSZ`. There is no explicit historical bucket-start/bucket-end
  flag in the current API. The code uses a row timestamp as the hour's realization
  timestamp and forecasts from the final timestamp +1h.
- The CSV limit is **1,000,000 Python characters**, although the error/UI say
  “1 MB”; the HTTP body has a separate byte limit. Import does not require exactly
  two decimal places. Forecast floats generally retain more precision.
- UI formatting is `en-IN`, INR and `Asia/Kolkata` (`web/app.js:25–54`); backend
  internal event comparison is UTC (`planning.py:38–46`). Most response times are
  UTC `Z`; tranche times may be equivalent `+00:00` strings.

## 3. Current endpoint schemas and frontend consumption

### GET /api/state

Returns `State` (`treasury.py:252–308`):

```text
revision: integer; currency: "INR"; schema_version: 2
cash, vault, earned: number
policy: Policy
source: string; mode: "simulation"
as_of: timestamp; history_count: integer; history: HistoryRow[] (last 168 only)
forecast: NetRow[72]; gross_forecast: GrossForecast
plan: Plan; model: string; converged: boolean; baseline_mae: number
gross_hourly, daily_vault_yield: number
ledger: LedgerRow[]; tranches: Tranche[]; intelligence: Intelligence
scheduled?: Event[]; planning_policy?: PlanningPolicy; decisions?: Decision[]
operations?: {request_id: fingerprint}; migration_note?: string
```

The response spreads saved state, so optional fields depend on prior actions;
it is not a closed, version-validated response schema. It even includes the
persisted operations map. `history_count` counts all saved rows, while `history`
returns at most 168; a remote trainer must not treat that tail as the full history.

```text
Policy = {minimum_buffer, annual_yield, confidence, lock_hours,
          withdrawal_stress: number, auto_sweep: boolean}
NetRow = {timestamp, mean, lower, upper, withdrawals,
          balance, lower_balance, upper_balance}
GrossForecast = {model: string, note: string, rows: GrossRow[72]}
GrossRow = {timestamp, deposits, deposits_lower, deposits_upper,
            withdrawals, withdrawals_lower, withdrawals_upper}
Plan = {required, drawdown, sweep, shortfall, stress_outflow,
        daily_yield, retained: number}
```

All NetRow fields except timestamp are numeric INR amounts. `mean/lower/upper`
describe **net flow**, so negatives are allowed. `NetRow.withdrawals` is the
14-day UTC-hour average gross withdrawal stress basis, not the independent
seasonal-naïve withdrawal forecast in GrossRow. Balances are cash plus accumulated
net bounds/means less policy withdrawal stress; scheduled obligations and
maturities are absent from this chart. `Plan` starts with the legacy lower-bound
reserve and caps its sweep using the timed planner; `drawdown`/`stress_outflow`
remain legacy calculations (`treasury.py:223–281`).

```text
PlanningPolicy = {option: "flex"|"overnight"|"extended", risk_buffer: number,
                  rates?: {flex?, overnight?, extended?: number}}
Intelligence = {policy: PlanningPolicy, floor: number, options: Option[3],
                selected: Option, optimized: Option, projected_minimum: number,
                locked_principal: number, forecast_model: string,
                forecast_converged: boolean, timeline: Point[], events: Event[],
                method: string, note: string}
Option = {id, name, hours, rate, minimum, penalty,
          required, available_cash, protected_floor, projected_minimum,
          minimum_during_lock_after_sweep, emergency_funding, eligible,
          suggested, shortfall, interest, net_return, matures, fee, reason, risk}
Point = {timestamp, kind, flow, label, id?, balance, status}
Event = {id, kind, amount, timestamp, label, status?}
```

`id/name/penalty/matures/reason/risk` are strings; other Option fields numeric.
`risk` and Point/Event `status` are treasury labels `Safe|Warning|High Risk`, not
ML probabilities or calibrated quantiles. `flow` is signed INR. `events` includes
pending saved obligations; its status lookup defaults to Safe if no timeline
point is found, so it is not evidence of safety outside 72h (`planning.py:349–356`).
Products are 6h/24h/48h with default rates 4/5/5.4 annual percent, minimum
₹250,000/₹500,000/₹1,000,000 and fees ₹20/₹50/₹100 (`planning.py:7–35`).

```text
LedgerRow = {id, timestamp, type, amount, description, status: "Simulated"}
Tranche = {amount, matures, annual_yield, hours,
           started?, fee?, expected_interest?, redemption?}
Decision = {timestamp, action, cash, reserve, investment, reason,
            before: Option, after: Option}
```

Ledger is newest-first, capped at 1,000; normal decision history is capped at 200.
The failed planning execution branch returns before the decision cap. Legacy
sweeps lack the optional tranche fields. See `treasury.py:311–358,542–557` and
`planning.py:474–537`.

Frontend consumption is concrete, not inferred from README:

| Consumer | Fields read |
| --- | --- |
| Transport (`web/app.js:163–199`) | revision; entire returned State replaces local state; errors read `error` |
| Forecast (`web/app.js:389–415,447–450`) | forecast timestamp/mean/withdrawals/balance/lower_balance/upper_balance; gross rows deposits/withdrawals **by array index**; model, history_count, baseline_mae; policy minimum_buffer/confidence/withdrawal_stress; source/as_of through shell |
| Overview/options (`web/planning.js:6–42`) | cash, as_of, source, policy.minimum_buffer; intelligence policy/floor/selected/optimized/options/projected_minimum/locked_principal/method/note/timeline; decisions[0].reason; option names, terms, fees, returns, risk, maturity and eligibility |
| Events/history (`web/planning.js:44–63`) | intelligence.events id/label/timestamp/amount/status; decisions timestamp/action/cash/before.required/after.required/before.suggested/after.suggested/reason |
| Activity (`web/app.js:485–510,570–584`) | ledger id/timestamp/type/amount/description/status; tranches amount/matures/annual_yield; earned; source/history_count/as_of |
| Policy/forms (`web/app.js:453–471`; `web/planning.js:39–50,126–147,151–153`) | Policy fields, planning policy option/risk_buffer and per-option rates; cash/vault |

Gross bounds, `converged`, `forecast_converged`, gross model/note, schema_version,
operations and migration_note are not rendered by these views. Model name exposes
fallback text, but there is no rendered warning/reason/version/training-cutoff or
forecast freshness indicator. Some legacy page functions remain in JS without an
active route; `#scenarios` maps to `stressPage`, not `scenariosPage`.

### GET /api/template; GET /api/export; POST /api/import

| Endpoint | Current request and response | Frontend |
| --- | --- | --- |
| GET `/api/template` | No body; `text/csv; charset=utf-8`, attachment `reserve-juggler-hourly-sample.csv`; header `timestamp,deposits,withdrawals`; 1,008 fixed seed-42 synthetic rows, 42 days ending `2026-10-18T08:00:00Z`; no currency column or ML metadata | Data page download link (`web/app.js:506–510`) |
| GET `/api/export` | No body; CSV `reserve-juggler-forecast.csv`, 72 rows; exact header order: `timestamp,mean,lower,upper,withdrawals,balance,lower_balance,upper_balance,source,currency,timestamp_ist,model,confidence,minimum_buffer,withdrawal_stress_pct,lock_hours,recommended_sweep` | Download link; no CSV parsing in frontend. This is not a gross forecast export or a ledger export |
| POST `/api/import` | `{revision, request_id?, csv: string}`; returns State; rejects locked new tranches; validates history; replaces it, rebuilds demo scheduled events, preserves simulated balances and disables auto-sweep | File text sent by import handler (`web/app.js:694–708`); returned State consumed normally |

Export repeats policy/model/recommendation metadata per row; `timestamp_ist` is
ISO 8601 with `+05:30`. `confidence` is 90/95/99 **percent**, not 0.90/0.95/0.99.
Export has no model version, warning, origin, training cutoff, interval method or
risk output. It uses the same implicit INR assumptions as State. Browser ledger
export is generated independently from local State (`web/app.js:570–584`).

### Remaining forecast, policy, planning and scenario routes

Each mutating row below uses the common revision/request_id envelope and returns
State. Omitted `execution` defaults to `success`; values are `success|failure|timeout`.

| Method / route | Body beyond common envelope; validation / response |
| --- | --- |
| POST `/api/policy` | `{policy: Policy}`; all six policy keys required, no extras **inside Policy**; minimum_buffer [0,1e10] INR, annual_yield [0,20] annual %, confidence one of 90/95/99, lock_hours integer [1,72], withdrawal_stress [0,100] %, auto_sweep boolean |
| POST `/api/planning_policy` | `{option, risk_buffer, rates?}`; known product, buffer [0,1e10] INR; rates object for flex/overnight/extended, each [0,20] annual %; missing rates preserve prior/default values |
| POST `/api/planning_balance` | `{cash, vault}`; numeric [0,1e10] INR rounded to two decimals; rejects locked tranches; disables auto-sweep |
| POST `/api/planning_event` | `{kind, hours, amount?}`; kind withdrawal/payment/deposit/settlement/delay/risk; hours numeric (0,48], rounded to two decimals; positive amount ≤1e10 INR for financial events; delay moves all pending settlements and ignores amount; risk sets immediate extra buffer [0,1e10] and still requires hours |
| POST `/api/planning_invest` | `{execution?}`; recomputes selected product and simulates execution |
| POST `/api/planning_optimize` | `{execution?}`; recomputes maximum net-return product at its actual term and simulates execution |
| POST `/api/sweep` | No extra fields; legacy custom 1–72h sweep, timed eligibility cap, no product entry fee |
| POST `/api/advance` | No extra fields; realizes one synthetic hour, processes chronological obligations/maturities, then considers optimized auto-sweep |
| POST `/api/reset` | No extra fields; restores initial sandbox; revision still increments |
| POST `/api/planning_scenario` | Read-only `{stress?: {upi?, withdrawals?, delay?, payout?, execution?}}`; percentages [0,100], delay [0,48] hours, payout [0,1e10] INR due in 6h; returns `{baseline: Intelligence, stressed: Intelligence}`; effective withdrawal % is max(saved, scenario), not their sum |
| POST `/api/scenario` | Read-only `{policy: Policy}`; returns `{plan: Plan, forecast: NetRow[72], policy}`; returned plan is **legacy reserve_plan**, although the internally built snapshot uses a timed cap; not equivalent to planning_scenario |
| POST `/api/backtest` | Read-only `{}`; payload fields not used; fixed 24h seasonal-naïve replay; returns Backtest below |
| GET `/api/health` | `{status: "ok", mode: "simulation"}`; not an ML readiness probe |

Sources: `server.py:183–254`, `treasury.py:125–149,326–358,496–566`,
`planning.py:384–537`. Outside Policy these payloads are not closed schemas;
unknown fields are generally ignored. The frontend sends planning scenarios via
`web/planning.js:116–124`, mutations via lines 126–147, and backtest via lines
74–84. It consumes baseline/stressed **selected** required/shortfall/eligible/
suggested/net_return/projected_minimum/emergency_funding/risk/reason. There is no
standalone `/api/forecast`, ML upload, or path-risk endpoint.

```text
Backtest = {mode, source, hours, model, initial_cash, fixed_buffer, borrowing_rate,
            failure_every, test_start, test_end, results: Strategy[], assumptions: string[]}
Strategy = {strategy, realized_interest, accrued_interest, fees, penalties,
            borrowing_cost, net_interest, average_idle_cash, floor_breaches,
            total_shortfall, maximum_shortfall, surplus_utilization,
            successful_sweeps, failed_sweeps, recoveries, forecast_mae, forecast_rmse}
```

Amounts/errors are INR; utilization is a ratio, rates annual percent, counts
integers. Frontend consumes source/hours/model/assumptions and strategy,
net_interest/average_idle_cash/floor_breaches/maximum_shortfall/forecast_mae/
forecast_rmse (`strategy_evaluation.py:175–223`, `web/planning.js:74–84`).

## 4. Current models, uncertainty and README boundaries

- Net: up to 28 days, SARIMAX (1,0,0) × (1,0,0,24), next 72 hourly points;
  one policy confidence level per call. Exceptions listed in `model.py:148` or
  nonconvergence yield seasonal-naïve, 24-hour season, normal-scaled empirical
  seasonal residual bands (`treasury.py:152–189`, `model.py:23–155`).
- Status is just model name (`SARIMAX` or `Seasonal Naive (fallback)`) and boolean
  converged. Warnings are captured internally but not returned. Fallback reason,
  stable model ID/version, training cutoff and forecast generation time are absent.
  `baseline_mae` is prior-day baseline error over the final 168 hours, not fitted
  model validation. The import minimum is 168 rows but that calculation expects
  192: probes at 168/191 raise a broadcasting ValueError at `treasury.py:188`,
  while 192/336 succeed. This can reject an otherwise valid import before saving.
- Gross: independent 24-hour seasonal-naïve means and bands, clipped at zero,
  produced from saved history. This is neither gross SARIMAX nor a learned
  channel forecast; its difference need not equal net SARIMAX mean.
- Planner: 14-day UTC-hour gross profiles, reconciled to the **net** mean; extreme
  negatives increase represented withdrawals. Uncertainty is the incremental
  root-sum-square of `(mean-lower)` allowances. Channel splits and merchant 8%
  reclassification are demonstration assumptions (`planning.py:108–177`).
- README's 72h view, 6/24/48h products, gross display, fallback, timed safeguards
  and scenario lab are implemented. README does not define an external ML
  protocol, marginal-to-net uncertainty mapping, calibrated path-deficit model,
  RF/XGBoost deployment, or guaranteed outcomes. This proposal adds those
  boundaries without treating them as existing features.
- There is no audited D07 loader/dataset or data-use authorization in tracked
  source. USD experimental data must not be relabeled as INR or accessed/exported
  under this contract. The existing USD-workspace migration creates fresh INR
  demo state rather than converting money (`server.py:46–55`).

## 5. Proposed ML boundary and request

Normative terms “must” below apply to the proposed v1 interface only. Implement
as a pure prediction adapter; if separately hosted, use a private backend-to-ML
`POST /v1/forecast`. This URL is proposed, not an existing route. No frontend
direct ML access or changes to the public routes are needed to agree the schema.

```json
{
  "contract_version": "1.0",
  "request_id": "forecast-request-123",
  "context_id": "opaque-backend-history-policy-snapshot-id",
  "currency": "INR",
  "unit": "rupee",
  "timezone": "Asia/Kolkata",
  "forecast_origin": "2026-10-18T13:30:00+05:30",
  "interval_minutes": 60,
  "horizon_hours": 72,
  "confidence_levels": [0.9, 0.95, 0.99],
  "history": [
    {"timestamp": "2026-10-18T13:30:00+05:30", "deposits": 10000000, "withdrawals": 9800000}
  ],
  "risk_request": null
}
```

The history in this example is abbreviated: valid input needs 168–5,000 consecutive
rows, ending exactly at origin, with all observation rules in section 2. The
backend supplies its full authorized history, not GET /state's 168-row display
tail. `context_id` is an opaque backend-issued token binding history, origin,
currency and requested confidence/policy snapshot; response must echo it.
`request_id` is a correlation/idempotency key for prediction, not authority to
execute an investment. These strings must be nonempty and at most 128 characters.

All keys shown are required except risk_request (omitted means null). Reject
unknown keys in v1; negotiate a version for new fields. confidence_levels is a
nonempty unique ascending subset of [0.90,0.95,0.99]. Currency/unit/timezone,
interval_minutes and horizon_hours are fixed values shown above. Numeric booleans
and strings are rejected. Origin is the final **completed** observation bucket
end, not wall-clock “now”. No missing-hour or amount imputation at this boundary.
Model-specific minimum training history must be declared by the approved adapter;
insufficient history returns an explicit failure or a labeled approved fallback.

Forecast target: background gross cash flows, **excluding separately supplied
scheduled obligations, contractual investment principal/interest and hypothetical
stress overlays**. Historical source classification must support this separation;
otherwise adapter deployment is blocked until backend and ML agree de-duplication.
No cash, vault, floor, policy decision, event settlement or portfolio state needs
to enter the cash-flow model. The backend applies events and stress once.

## 6. Proposed forecast response and field rules

```text
ForecastResponse {
  contract_version: "1.0", request_id: string, context_id: string,
  currency: "INR", unit: "rupee", timezone: "Asia/Kolkata",
  forecast_origin: timestamp, generated_at: timestamp, expires_at: timestamp,
  interval_minutes: 60, horizon_hours: 72, confidence_levels: number[],
  model: Model|null, status: "ok"|"fallback"|"degraded"|"unavailable",
  fallback: null | {from_model_id: string, reason_code: string},
  warnings: Warning[], rows: ForecastRow[],
  net_uncertainty: null | NetUncertainty,
  liquidity_risk: null | RiskResponse
}
Model {
  id: string, version: string, training_cutoff: timestamp|null,
  training_cutoff_reason: null|"not_fitted",
  interval_method: string, evaluation_ref: string|null
}
Warning {code: string, severity: "info"|"warning"|"error", message: string}
ForecastRow {
  timestamp: timestamp,
  deposits: Estimate, withdrawals: Estimate
}
Estimate {
  mean: number,
  intervals: [{confidence: number, lower: number, upper: number}]
}
NetUncertainty {
  method: string, evaluation_ref: string,
  rows: [{timestamp: timestamp,
          intervals: [{confidence: number, lower: number, upper: number}]}]
}
```

| Output / type | Unit, validation and missing-value semantics |
| --- | --- |
| All envelope identity/constants | Required, exactly echo request; no implicit FX or scale conversion. Unknown major version, mismatched context/origin or currency rejects entire result |
| All timestamps | RFC 3339 ISO strings emitted with seconds and **explicit `+05:30`**, e.g. `2026-10-18T14:30:00+05:30`; metadata may include fractional seconds. Rows/origin require zero seconds/fractions. Compare parsed instants, never strings; backend may normalize to UTC internally. Do not round a UTC grid to IST whole hours |
| forecast_origin | Exact completed history bucket end; no row at origin. Row k ends at origin+k hours, for k=1…72. A row covers `(timestamp-1h, timestamp]`, an hourly total, not an instantaneous rate or cumulative forecast |
| generated_at / expires_at | Generation and wall-clock service expiry; generated_at ≤ expires_at. Backend policy configures maximum age and allowable clock skew, and rejects expired responses. Independently require origin/context match current sandbox state: wall-clock age alone cannot validate simulated time |
| model / model.id / version | Model required except unavailable may use null when none ran. IDs/versions are nonempty stable identifiers, ≤128 chars each; actual model used, including fallback; version identifies an approved immutable release/configuration. Not a filesystem path, artifact download URL, or serialized weights |
| model.training_cutoff | Latest observation used for fitted parameters/calibration, ≤origin; must be supplied for fitted models. Nonfitted baselines use null plus reason `not_fitted`; otherwise reason must be null. No future data in fitting, preprocessing or interval calibration |
| model.interval_method | Required nonempty documented algorithm/config ID; no assumption that every candidate supplies calibrated intervals |
| model.evaluation_ref | Approved evaluation report identifier or null with `EVALUATION_UNAVAILABLE` warning; no restricted report contents or artifact bytes |
| status / fallback | `ok`: complete approved primary result; `fallback`: complete approved alternate, fallback object and `MODEL_FALLBACK` warning required; `degraded`: complete means but missing requested intervals/evaluation, advisory display only; `unavailable`: rows empty, error warning required. Fallback is null except for fallback status |
| warnings | Required array, empty if none; nonempty code/message (code ≤64, message ≤500 chars); no credentials, raw dataset records or paths; severity error blocks treasury use |
| rows | Exactly 72, unique, ascending and exactly hourly for ok/fallback/degraded. No null rows, duplicates, gaps, reordering, missing amounts or extra rows. For unavailable, exactly []; never fill absent values with zero or previous output |
| deposits/withdrawals.mean | Finite JSON numbers, [0,1e12] INR **rupees per bucket**, max two decimals; no booleans, numeric strings, NaN/Infinity or null; zero means predicted zero, never missing. No saturation/clipping of invalid incoming output |
| Estimate.intervals | One per requested confidence for ok/fallback; unique ascending confidence fractions, not percentages. Finite nonnegative INR lower/upper ≤1e12 and lower ≤ upper. Wider bands must contain narrower bands. This proposal requires the displayed mean within each band; skewed models must construct compatible bands or return degraded, not mislabel quantiles. Bounds outward-rounded to paise. Degraded may have an empty or requested-level subset, with `INTERVAL_UNAVAILABLE` naming target/level; no null bound |
| net_uncertainty | Null when not available; otherwise all 72 matching timestamps with all requested confidence intervals. Signed INR bounds in [-1e12,1e12], lower ≤ deposits.mean−withdrawals.mean ≤ upper, nested bands, lower ≤ upper, outward rounding, documented joint/calibrated method and nonempty evaluation_ref. No partial object |
| liquidity_risk | Null if not requested; otherwise explicit RiskResponse, including an unsupported/unavailable status if necessary, per section 7 |

All fields in the response types are required; optional availability is represented
only by the documented null/empty/status combinations. Version 1 rejects unknown
keys and all malformed values before applying any result. No amount clipping,
forward filling, currency relabeling, or partial-prefix acceptance by the backend.

Means define net point forecast `deposits.mean - withdrawals.mean`. Marginal
deposit/withdrawal intervals do **not** define a net interval at the same nominal
confidence; correlation matters. `net_uncertainty` is a separately evaluated joint
net-flow estimate. Without it, gross forecasts remain useful for display but are
not eligible for the existing net-uncertainty planner under this proposal.
Do not subtract corresponding marginal endpoints, assume independent errors, or
call accumulated pointwise bounds a calibrated 72h path band. A separate backend
approved conservative uncertainty adapter could be agreed later with its own
method/version/evaluation; it is not silently supplied by v1.

Candidate families may include deterministic 14-day hourly averages,
seasonal-naïve, SARIMAX, Random Forest, XGBoost or compatible boosting. Compare
rolling origins, no leakage, gross/net errors, interval coverage/width and stress
behavior before approving any release. No existing model is required to survive.
Model quality is distinct from optimizer risk labels and numerical convergence.

## 7. Optional path-deficit risk contract

Cash-flow and risk models are separate. Request risk only when an adapter declares
support for the exact targets. Proposed request replaces null with:

```json
{"horizons_hours": [6, 24, 48, 72], "quantiles": [0.9, 0.95, 0.99], "definition": "background_outflow_first_drawdown_v1"}
```

This is an explicitly proposed target set, not existing model capability. Any
nonempty ascending unique subset of horizons [1,6,24,48,72] and quantiles
[0.90,0.95,0.99] can be requested. No interpolation/extrapolation to unsupported
terms or claim that 95% central interval equals 95th percentile deficit.

```text
RiskResponse {
  definition: "background_outflow_first_drawdown_v1",
  status: "ok"|"unavailable"|"unsupported",
  model: Model|null, forecast_origin: timestamp, context_id: string,
  supported_horizons_hours: integer[], supported_quantiles: number[],
  warnings: Warning[],
  estimates: [{horizon_hours: integer, quantile: number, deficit: number}]
}
```

For stochastic gross paths with Dk deposits and Wk withdrawals, define
S0=0, Sk=Σj≤k(Dj−Wj), and drawdown at horizon h:

```text
Lh = max(0, -min(0, {S(k-1) - Wk, Sk for k=1…h}))
deficit(h,q) = q-quantile of Lh
```

This measures background path drawdown with withdrawals before deposits in each
bucket. It excludes opening cash, reserve floors, separately scheduled events,
investment cash flows and stress overlays. It is **not** a probability of payment
failure, a reserve instruction, eligible investment, terminal net loss, VaR of
the portfolio, or statutory CRR/SLR calculation. Actual intrahour peaks beyond
the stated convention remain unmodeled.

All RiskResponse fields are required. Origin/context must match the envelope;
supported lists enumerate approved capabilities, not requested guesses. For ok,
model is required with the same metadata rules as section 6, no error warnings,
and estimates contain exactly the requested Cartesian product. Deficit is finite,
nonnegative, at most 72×1e12 INR, max two decimals, nondecreasing in horizon and
quantile. Backend risk use additionally requires approved evaluation_ref and
model release. Unsupported or unavailable returns estimates [], explanatory
warning and model null if no applicable model; lists may be empty, never null.
Reject partial grids and unsupported pairs instead of fabricating zero risk.

Optional risk failure does not invalidate an otherwise complete cash-flow
forecast. If backend policy requires risk for investment, its absence blocks new
placements. Risk numbers must not replace the event-by-event reserve check or
be added to a separate uncertainty reserve without an agreed method preventing
double counting. Backend decides any use; advisory display can precede that.

## 8. Errors, fallback and treasury acceptance

Adapter validation failures must return a typed failure without usable rows:

```text
{contract_version: "1.0", request_id: string, context_id: string,
 error: {code: string, message: string, retryable: boolean}, warnings: Warning[]}
```

Use codes `INVALID_REQUEST`, `UNSUPPORTED_CONTRACT`, `CURRENCY_MISMATCH`,
`INSUFFICIENT_HISTORY`, `MODEL_UNAVAILABLE`, `TIMEOUT`, `INVALID_PREDICTION`,
`STALE_CONTEXT`, `UNSUPPORTED_CONFIDENCE`. If HTTP is chosen: 400 for invalid
request, 422 for unsupported semantics/history, 503 for unavailable model and
504 for timeout. A 200 status can carry complete fallback/degraded or explicitly
unavailable ForecastResponse; transport success alone never authorizes use.
Malformed model output is rejected locally even when its HTTP status is 200.

Proposed backend acceptance gate, enforced on reads and again before execution:

1. Validate schema, all 72 rows, identity, origin, timestamps, currency, units,
   interval levels, numerical ranges and approved release; validate age separately.
2. Accept for treasury only ok/fallback with no error warnings, full selected
   confidence bounds, approved net uncertainty and any policy-required risk.
   Fallback also needs an explicit backend allowlist and evaluated limitations.
3. On invalid/stale/unavailable/timeout output, optionally request one approved
   deterministic/seasonal fallback with the **same current context**. Validate it
   identically. Never silently retain another origin's forecast or assume zero flow.
4. If none passes, block **new** manual, legacy, optimized and automatic
   investments (`suggested` and executable principal zero), expose reasons and
   an unavailable recommendation state, and retain cash. Do not invent a numeric
   “safe reserve” from absent predictions or suppress previously known gaps.
5. Continue accounting, due obligations, contractual maturity and audit processing
   independently of model availability. A model outage must not strand maturity
   processing. This requires a later change: current `advance` first calls forecast.

Fresh model output is not guaranteed realized cash. Backend reserve-floor, fees,
minimum sizes, lock restrictions, full 72h funding checks, current revision,
execution locking/idempotency and reconciliation remain mandatory. Record
accepted/rejected forecast ID, context, model/version, status, selected confidence,
warnings, uncertainty method and fallback reason alongside treasury decisions.
Do not put serialized models or restricted data into State, CSV or the ledger.

## 9. Proposed mapping and backward compatibility

Deploy behind an explicit backend adapter setting, with shadow comparison before
treasury activation. Do not swap the existing `forecast()` function and assume
the gross result will reach planning.

| Proposed value | Current target / required later change |
| --- | --- |
| row.timestamp | Parse +05:30 and normalize to canonical UTC Z; join by instant. `planning.timeline` currently looks up exact UTC string keys |
| deposits.mean, withdrawals.mean and selected bands | Flatten into existing `gross_forecast.rows` fields; preserve 72-row ordering for old clients while new clients join by timestamp |
| deposits.mean−withdrawals.mean | `forecast.mean`; new net authority must be labeled and shared by chart and planner |
| net_uncertainty selected bounds | `forecast.lower/upper`; derive legacy balance envelopes in backend and label their limitations |
| withdrawals.mean | `forecast.withdrawals` stress basis only after intentionally changing from 14-day average; same basis in timeline and simulation. This semantic change needs versioned rollout |
| Gross means | Pass directly to a revised timed planner; remove old reconciliation/14-day profile substitution for this mode. Keep single channel decomposition/merchant reclassification and apply stress once |
| model/status/warnings/origin/quality | Add a dedicated versioned forecast metadata object; retain model/converged aliases for legacy mode. For trees/baselines convergence is not applicable: new UI must use status, not fake a convergence value |
| RiskResponse | New separate advisory risk object; never overload `intelligence.selected.risk` or `shortfall` |

Keep `schema_version:2` current behavior intact for this documentation task.
Activation should explicitly version the changed semantics (and define a legacy
client path) before rollout. An unavailable forecast needs frontend support for
empty rows/null chart data and disabled actions; simply returning [] would crash
the current chart. Add exports deliberately rather than silently repurposing CSV
columns. Both scenario endpoints must disclose which planner and forecast context
they use; the integrated scenario should be the UI's canonical treasury comparison.

## 10. Required contract verification before activation

These are future integration tests, not claims of existing implementation:

- Validate 72 aligned means and all requested 90/95/99% bands; malformed currency,
  unit, version, booleans, strings, NaN, negative gross, crossed/nonnested bands,
  missing/null rows, off-grid times, stale context, incomplete risk grids and expiry.
- Round-trip +05:30 and UTC including minute-30 grids; compare instants, preserve
  bucket ends; no double timezone conversion or host timezone dependence.
- Test 168/191/192/336/5,000 history boundaries, feature/calibration cutoff leakage,
  insufficient history, model failure/nonconvergence and explicit approved fallback.
- Prove planner uses the supplied gross means, net mean identity and approved
  joint net intervals once; no added net correction or duplicated merchant/events.
- Verify absent net uncertainty/required risk blocks all investment paths, manual
  and auto; accounting/maturities continue during timeout and malformed responses.
- Preserve outflow-first tests at hours 1,17,72, same-time and intrahour maturity,
  due-before-receipt, entry fees, full-horizon gaps, locked cash and audit integrity.
- Verify read-only scenario isolation, combined stress and execution failure,
  freshness/revision race rejection, request retries, HTTP/CSV compatibility,
  timestamp-based frontend joins and unavailable/degraded warning display.
- Evaluate point forecast errors, empirical interval coverage/width, and risk
  quantile coverage at rolling origins using authorized INR data; compare candidates
  without committing a winner. Passing schema tests alone does not establish quality.

Current verification results, synthetic hour-17 regressions and unresolved limits
are recorded in [BACKEND_FRONTEND_INTEGRATION_GAPS.md](BACKEND_FRONTEND_INTEGRATION_GAPS.md).
