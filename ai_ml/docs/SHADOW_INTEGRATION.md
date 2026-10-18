# Implemented shadow integration

18 October 2026. Status: local, disabled-by-default integration for review.
This document describes the implemented boundary. Operational replacement,
probabilistic reserve rules and deployment remain unimplemented proposals in the
older contracts. No production financial performance is claimed.

## Architecture and authority

```text
React api('state') / mutation response
  -> authenticated server.py handlers -> treasury transaction lock
       -> existing net SARIMAX / seasonal-naive fallback
       -> existing independent seasonal-naive gross display
       -> unchanged timed planner, reserves, products and settlement
       -> capture authoritative response and independently owned shadow inputs
       -> persist authoritative mutation, if any
  -> release treasury lock
       -> ml_shadow diagnostic (additive; never used above)
            disabled: no optional ML imports or model/data access
            enabled: currency/availability gates
              -> one process-wide daemon worker, at most 2s wait
              -> reviewed backend-injected ShadowProvider, if present
              -> validate full-history request and model provenance
              -> separate gross ForecastOutput objects
              -> strict existing ML adapter / legacy-shaped shadow rows
              -> discard predictions; return diagnostic only
```

`planning.timeline` still uses historical gross profiles reconciled to the
authoritative legacy net forecast and its existing uncertainty heuristic.
Displayed gross forecasts remain independent seasonal-naive estimates.
ML gross predictions are not silently installed into either path. `advance`,
`apply_action`, settlement, fees, risk buffers, all investment paths, revision
checks and reconciliation do not consult shadow output.

React continues consuming `forecast`, `gross_forecast`, `plan`, `model` and
`intelligence` as before. It does not call ML directly. No `web/` changes or new
HTTP routes were required. Existing CSV headers and State `schema_version: 2`
are preserved. Assistant context does not include the new diagnostic.

GET `/api/state` and successful mutation responses add optional diagnostics only
after releasing the store lock. Mutations build their authoritative response and
commit SQLite state first. The response retains that operation's revision even
if another mutation completes during the shadow wait; it never refetches or
replays the financial action. Existing revision/idempotency checks remain in
force. CSV export, legacy scenarios and assistant context use only the legacy
snapshot and do not invoke a shadow provider.

`capture_inputs()` runs under the treasury lock and copies only full gross
history, currency and selected confidence. The worker sees an independently
owned request/DataFrame, no mutable treasury state or transaction lock. Direct
Python callers of `snapshot(..., shadow_provider=...)` must likewise hold no
treasury lock; HTTP handlers always use the split capture/diagnostic flow.

## Configuration and availability

`RJ_ML_SHADOW_ENABLED=false` is the default, including when unset. Only `true`
enables diagnostics; other values report `INVALID_CONFIGURATION`. Set this in
the backend environment or local ignored `.env`; restart the backend to reload
environment configuration.

The root requirements do not install `reserve_juggler_ml` or all of its optional
tree-model dependencies. With a reviewed provider, use the declared ML package
environment and `PYTHONPATH=.;ai_ml/src` from the repository root (or a separately
installed package). The existing Python 3.12 environment has pandas, NumPy,
SciPy, scikit-learn and XGBoost. No dependency or lockfile was changed. The default
application and INR/USD skip path require no ML package import.

There is intentionally no automatic research-model loader or training call.
`create_server(..., shadow_provider=provider)` is an explicit backend-owned
injection point for a reviewed, already-loaded implementation of `ShadowProvider`.
`treasury.snapshot(..., shadow_provider=provider)` supports the same boundary.
Neither is a client request field. Enabling the environment flag alone cannot
activate or deserialize a research pickle. A compatible provider must be provided
by reviewed backend code; the normal CLI supplies none.

Current local inventory contains Phase 2 RF/XGBoost deposit and withdrawal USD
pickles, XGBoost JSON models, and Phase 3/4 calibration artifacts under ignored
`ai_ml/.local/`. Research reports identify USD, dataset checksum, features,
library versions and hyperparameters; package version is `0.1.0`. That is not a
complete immutable serving manifest proving training/calibration cutoff,
feature timezone and application bucket-end semantics. No weights or residuals
were loaded during this integration, and no committee dataset was read.

For the actual INR application with no injected provider, enabling shadow mode
returns `skipped / CURRENCY_MISMATCH`, citing the existing USD research inventory.
For a synthetic USD request without a provider, it returns `MODEL_UNAVAILABLE`.
These diagnostics do not assert that an artifact is deployable or that missing
currency metadata implies compatibility. No INR-to-USD conversion is performed.

## One in-process boundary

`integration.contract.ShadowRequest` is built from the full saved history, never
the 168-row display tail. It carries no cash, vault, reserve threshold, scheduled
event, investment or ledger data. Its contract is `shadow-1.0`:

| Field | Required behavior |
| --- | --- |
| currency | Explicit `INR` or `USD`; missing/unknown values rejected. The public application remains INR |
| unit | `major_currency_unit`: rupees for INR, dollars for USD, never paise/crores or rescaled values |
| timestamp_semantics | `completed_hour_bucket_end`; history row t is the completed bucket `(t-1h, t]` |
| flow_scope | `background_gross_only`, excluding separately modeled events, investment principal/interest and hypothetical stress |
| as_of | Explicit timezone, exact final completed observation timestamp |
| history | 168–5,000 rows, exact timestamp/deposits/withdrawals keys, finite nonnegative numeric amounts <= 1e12; booleans/strings rejected |
| time grid | Unique ascending hourly instants; zero seconds/fractions; UTC normalization preserves minute-30 grids originating in IST |
| horizon_hours / frequency | Exactly 72 / `h`; forecast k ends at as_of + k hours, no forecast at as_of |
| confidence_level | One selected fraction 0.90, 0.95 or 0.99, taken from existing percentage policy |

`ModelSpec` requires model ID, immutable version, explicit training currency,
unit, dataset ID and SHA-256, configuration ID, latest fitting **and calibration**
cutoff, interval method, bucket semantics, UTC feature timezone, flow scope,
supported 72h horizon and minimum history. Cutoff must not exceed request origin.
Currency, unit, semantics and model-history compatibility are checked before
calling the provider. Existing interval-start research artifacts cannot acquire
bucket-end compatibility by relabeling them; that alignment needs independent
verification and a reviewed provider.

The provider receives a private UTC DataFrame copy of just the two gross targets.
It returns exactly `deposits` and `withdrawals`, each the existing `ForecastOutput`
type with matching model identity and 72 timezone-aware indexed means/lower/upper
values. All six series must match the exact requested instant grid. Means and
bounds must be finite and nonnegative, and bounds must contain each mean.
Incorrect dimensions, missing targets, NaN/Inf, negative values, reordered or
misaligned timestamps are rejected, not clipped or repaired.

`format_forecast_response` retains the existing `ForecastResponse` version
`1.0.0`, now requires explicit currency, normalizes timestamps correctly, and
uses the supplied actual training cutoff instead of inventing one from `as_of`.
`adapt_to_backend_state` revalidates that response before constructing the
existing NetRow/GrossRow shapes. These converted rows remain local shadow values.

Net mean is deposits minus withdrawals. Bounds formed from opposite marginal
extrema are explicitly labeled **uncalibrated shadow envelopes**. They are not
same-confidence net intervals or calibrated cash-path bands and never feed the
planner. No liquidity-risk quantiles are fabricated or exposed. Replacing the
planner would require separately validated net uncertainty and event handling.

## API diagnostics and errors

Full snapshot responses gain `ml_shadow`; it is not saved in SQLite or the ledger:

```json
{
  "contract_version": "shadow-1.0",
  "enabled": true,
  "status": "skipped",
  "code": "CURRENCY_MISMATCH",
  "message": "Existing research artifacts are USD-trained; no reviewed runtime provider is configured.",
  "authoritative_forecast": "existing_treasury",
  "controls_treasury": false,
  "inference_ran": false,
  "input_currency": "INR",
  "model_currency": "USD",
  "model": null,
  "warnings": []
}
```

Statuses are `disabled`, `skipped`, `failed` or `completed`. A completed result
includes actual model ID/version/interval method and an uncalibrated-envelope
warning. No prediction arrays, private paths, raw records, weights, residuals,
calibration matrices or dataset contents are returned to the browser.

Failures include `UNSUPPORTED_CURRENCY`, `CURRENCY_MISMATCH`,
`ML_PACKAGE_UNAVAILABLE`, `MODEL_UNAVAILABLE`, `INVALID_MODEL_METADATA`,
`UNSUPPORTED_CONTRACT`, `INSUFFICIENT_HISTORY`, `INVALID_HISTORY`,
`INVALID_TIMESTAMP`, `INVALID_NUMBER`, `UNSUPPORTED_CONFIDENCE`, `STALE_CONTEXT`,
`FUTURE_TRAINING_DATA`, `INVALID_PREDICTION`, `TIMEOUT`, `INFERENCE_FAILED` and
`INTEGRATION_FAILED`, `SHADOW_BUSY` and `CIRCUIT_OPEN`. Exceptions never become
successful predictions. Unexpected
integration exceptions are logged and reported with a non-sensitive error code.
`inference_ran` distinguishes provider invocation from pre-inference rejection.

Fallback means retaining the original treasury SARIMAX/seasonal-naive result,
not training or invoking an alternative USD model. Legacy forecast failures
still follow their existing error behavior; shadow output cannot rescue or
replace an invalid legacy forecast. The existing 168–191-row baseline-MAE bug
is unchanged and remains a separate issue.

## Request deadline and worker lifecycle

The previous post-return timeout check has been supplemented by a real caller
deadline. `integration.shadow.ShadowExecutor` admits at most one daemon worker
process-wide, with no queue. The fixed production wait is two seconds, including
request validation, provider metadata access, inference and adapter validation.
Only a completed result timestamped by the deadline is accepted. Waiting on
the worker holds neither the treasury lock nor the executor bookkeeping lock.
Authoritative forecast construction has its existing independent cost; the 2s
bound applies to the optional shadow phase, not the entire HTTP request.

An overlapping request returns `skipped / SHADOW_BUSY` promptly. A deadline
overrun or explicit provider timeout returns `failed / TIMEOUT` and permanently
opens the process-wide circuit. Subsequent attempts, including replacement
provider objects or new server instances in that process, return
`skipped / CIRCUIT_OPEN` without launching or queueing a worker. A result arriving
late is discarded and cannot alter an HTTP response or persisted financial state.

The circuit stays open even if the old worker eventually exits. **Recovery is a
backend process restart** after diagnosing the provider. Toggling the feature
flag, refreshing the page, or creating another provider does not reset it. The
normal application has no circuit-reset API. Tests replace the executor solely
to isolate deliberately timed-out synthetic cases.

This is the bounded daemon-thread fallback, not killable process isolation.
Existing injected providers can contain closures and runtime-loaded objects;
there is no reviewed Windows spawn/provider-loading contract to reuse. A timeout
does **not** cancel a running Python thread. A permanently stalled provider may
retain one daemon worker and its copied input until process exit, but cannot
create additional workers through this boundary or retain the request's store
lock. Runtime code never joins an abandoned worker; it cannot prevent application
shutdown. Providers are trusted code and must not reach treasury globals/locks.
This is not a sandbox for arbitrary code or native code that monopolizes the GIL.
A supported process loader is a separate future isolation improvement.

Unexpected provider/metadata errors are replaced inside the worker with a static
integration error; their raw text and traceback do not reach request logging.

## Validation and remaining gates

All new tests use controlled synthetic data or mocked providers. They cover
explicit currency/metadata, history limits, IST/UTC alignment, cutoff causality,
invalid arrays/amounts/bounds, missing provider/package, inference exceptions and
timeout, default disablement, actual handler schemas/CSV export, and identical
financial state/actions with shadow enabled and disabled. Extreme mock forecasts
prove that ML results are not accidentally routed into the planner.

Timeout regressions cover a normal provider, exceptions, blocked prediction and
metadata, single-worker/busy/open-circuit behavior, latched failure after a late
completion, and completion immediately before/after the deadline using a
deterministic clock. A real-handler/in-memory SQLite test uses the default 2s
deadline, checks that the first mutation is already persisted when inference
starts, completes a second read and mutation while the provider is still blocked,
and verifies that an exact retry creates no duplicate investment. Every blocking
fixture uses bounded waits and releases/joins its test worker during cleanup.

The two existing private-dataset audits in `test_data_loader.py` are now opt-in
via `RJ_ML_PRIVATE_DATA_AUDIT=true`; that setting was **not** enabled. One reads
the full-year committee file, so the integration validation intentionally skips
both. Existing reserved-partition guard tests use synthetic fixtures only; no
reserved committee observations were accessed, tuned against or evaluated.

Final validation used the existing `.venv` environment:

```powershell
$env:PYTHONPATH='.;ai_ml/src'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -B -m pytest tests -q -p no:cacheprovider --tb=short --basetemp=ai_ml/.local/integration-validation-20261018-root-2

$env:PYTHONPATH='ai_ml/src'
# RJ_ML_PRIVATE_DATA_AUDIT is unset, so restricted-data audits remain skipped.
.\.venv\Scripts\python.exe -B -m pytest ai_ml/tests -q -p no:cacheprovider --tb=short

.\web\node_modules\.bin\tsc.cmd --noEmit --project web/tsconfig.json
```

| Check | Result |
| --- | --- |
| Complete backend suite, including MongoDB authentication, real-model HTTP, and shadow availability tests | **198 passed, 0 failed, 82 existing dependency deprecation warnings in 95.03s** |
| Complete ML suite, restricted audits disabled | **133 passed, 0 failed, 2 skipped in 11.87s** |
| Focused backend shadow tests (`tests/test_ml_shadow.py`) | **28 passed, 0 failed, 2 warnings in 8.12s** |
| Focused ML contract and adapter tests (`test_shadow_contract.py` + `test_adapter.py`) | **72 passed, 0 failed in 4.76s** |
| Frontend TypeScript check (`tsc --noEmit`) | Exit code **0** |
| Frontend production build (`npm run build`) | **Vite production bundle built in 1.44s with 0 errors** |
| Diff whitespace check | Passed |

The backend suite required loopback access outside the restricted shell sandbox.
Test scratch files are restricted to ignored `ai_ml/.local/`. The two ML skips
are the private-path existence check and full-year committee audit (`test_private_dataset_path_exists`
and `test_data_loader_full_year_audit` in `ai_ml/tests/test_data_loader.py`), which are opt-in via
`RJ_ML_PRIVATE_DATA_AUDIT=true`. They were intentionally skipped to guarantee zero access to
the private committee dataset and zero evaluation of the reserved November–December 2026 holdout partition.
No model selection or quality evaluation was run. Existing fallback and chronology/maturity/accounting
acceptance tests all passed. The diagnostic path completed end-to-end using controlled fixtures
and real in-memory GET/POST handlers. No experimental artifact inference ran on application INR observations.

### Locking and Timeout Defect Resolution Summary

1. **Original Defect:** In earlier draft integration designs, running or awaiting shadow inference while holding `server.store.lock` meant that any slow provider, stalled inference, or timeout blocked the entire process-wide lock, starving all concurrent `/api/state` reads and financial mutations.
2. **Current Resolution:**
   - In `server.py`, all mutations (`apply_action`), SQLite state persistence (`store.write`), response snapshotting (`snapshot`), and owned gross input copying (`capture_inputs`) occur under `with self.server.store.lock:`.
   - The store lock is released immediately before calling `self.add_shadow_diagnostics()`.
   - `ShadowExecutor` runs inference inside a single daemon thread bounded by a 2.0-second caller deadline (`TIMEOUT_SECONDS = 2.0`).
   - If an overlapping request arrives while a worker is running, it immediately returns `skipped / SHADOW_BUSY` without queueing or blocking.
   - If inference exceeds 2.0s, the caller is released immediately with `failed / TIMEOUT`, and the executor latches into `CIRCUIT_OPEN`. Subsequent requests return `skipped / CIRCUIT_OPEN` without launching a new thread.
   - Authoritative financial state, balances, ledger entries, and exact retries remain completely intact and unaffected by provider timeouts or failures.
3. **Thread Lifecycle and Recovery Limitation:**
   - Python daemon threads cannot be forcibly killed safely. A permanently stalled provider thread remains alive until completion or process shutdown.
   - `CIRCUIT_OPEN` is process-lifetime; recovering from a tripped circuit after a stalled provider requires restarting the backend server process.

## Changed files and reasons

| File | Purpose |
| --- | --- |
| `.env.example` | Disabled-by-default shadow flag |
| `server.py` | Capture/persist under the treasury lock; add diagnostics after releasing it |
| `liquidity_forecasting/treasury.py` | Add diagnostic only when building a snapshot |
| `liquidity_forecasting/ml_shadow.py` | Owned gross-input capture, configuration, compatibility skips and diagnostic failure containment |
| `ai_ml/src/reserve_juggler_ml/integration/contract.py` | Request and model-provenance validation |
| `ai_ml/src/reserve_juggler_ml/integration/shadow.py` | Paired inference, strict validation, bounded single daemon worker and latched circuit |
| `ai_ml/src/reserve_juggler_ml/integration/adapter.py` | Strict output validation, UTC normalization, real cutoff and shadow-only converter |
| `tests/test_ml_shadow.py` | Financial noninterference and real handler contract tests |
| `ai_ml/tests/test_shadow_contract.py` | Synthetic input/output, currency, time, metadata and error tests |
| `ai_ml/tests/test_adapter.py` | Explicit timezone fixture for the strict adapter |
| `ai_ml/tests/test_data_loader.py` | Make private-data audits opt-in to avoid reading the reserved dataset |
| `ML_INTEGRATION_CONTRACT.md` | Identify the historical proposal and link the implemented contract |
| `BACKEND_FRONTEND_INTEGRATION_GAPS.md` | Distinguish shadow implementation from unresolved operational gaps |
| `ai_ml/docs/INTEGRATION_CONTRACT.md` | Retire conflicting draft activation/default assumptions for shadow mode |
| `ai_ml/docs/SHADOW_INTEGRATION.md` | Current architecture, contract, risks, verification and deployment blockers |

No frontend, dependency/lockfile, planner, settlement or allocation algorithm was
changed. `ai_ml/.local/` remains ignored by `ai_ml/.gitignore`; no generated models,
datasets or numerical artifact files were introduced into tracked source. Work
remains local on `AIML`, with no staged changes, commits, pushes or branch changes.

Before any INR model deployment: obtain authorized representative INR data and
classification excluding separately modeled events; verify bucket alignment and
UTC feature conventions; freeze a provenance-checked release including all
calibration cutoffs; independently validate gross/net errors, uncertainty and
liquidity-risk behavior on authorized nonreserved splits; review provider loading
and isolation requirements;
and review a separate operational-acceptance design. Passing shadow tests grants
no authority over financial decisions.
