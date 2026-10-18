# Backend/frontend ML integration gaps

Original audit: 18 October 2026. **Historical audit and proposed operational gaps.**
The subsequent [shadow integration](ai_ml/docs/SHADOW_INTEGRATION.md) adds strict
ML interface validation and an optional `ml_shadow` snapshot diagnostic. It does
not replace any financial forecast, planner or settlement behavior. The matrix
below remains a list of operational deployment gaps, not completed features.
The proposed schemas and the earlier API
inventory are in [ML_INTEGRATION_CONTRACT.md](ML_INTEGRATION_CONTRACT.md).

The application already has an INR 72-hour pipeline, independent gross forecast
display, timed reserves, 6/24/48h investments and combined stress scenarios.
Its planner consumes net SARIMAX/fallback predictions reconciled into a 14-day
gross profile; the displayed gross predictions do not drive decisions. No external
ML service, calibrated path-risk model or versioned acceptance gate exists.

## Gap matrix

BE = backend; FE = frontend. All changes below are proposed, not applied.

| Area | Existing compatible functionality / evidence | Missing fields or mapping; compatibility concern | BE change needed later | FE change needed later | Required contract tests |
| --- | --- | --- | --- | --- | --- |
| INR data | Gross deposits/withdrawals, explicit timezone import, numeric checks (`treasury.py:72–112`) | CSV has implicit INR; no authorized data classification/de-duplication protocol; D07 USD is not an INR source | Enforce INR/unit at ML boundary; supply authorized full history; exclude separately modeled events | Preserve INR labels and source provenance | Reject USD/scaled/missing/boolean inputs; no implicit FX/relabeling; source/event de-duplication |
| 72h forecast/view | 72 next-hour net and gross rows; FE slices 1/6/24/48/72 (`treasury.py:152–219`; `web/app.js:414–450`) | No bucket semantics, interval length, origin freshness or request context in response | Validate exactly 72 bucket ends, +1…+72h and current origin/context; distinguish full history from State's 168-row tail | Join by timestamp; handle empty/degraded rows without chart/index errors | Missing/duplicate/reordered rows, origins, all views, full-history handoff |
| Gross model handoff | Displayed gross seasonal-naïve rows have bounds | Planner still uses historical gross profile plus net correction; `forecast.withdrawals` is a different 14-day mean (`planning.py:108–145`) | Consume adapter gross means directly; derive consistent net mean; apply stress/channel split once | Replace hardcoded SARIMAX/seasonal-naïve explanation; preserve legacy labels in legacy mode | Prove supplied gross drives planning; no duplicate net/deposits/merchant receipts |
| Uncertainty | 90/95/99% selected policy; net and gross bands; RSS planner allowance (`treasury.py:125–149`; `planning.py:135–145`) | No joint gross-to-net interval mapping or calibration metadata; gross bounds not rendered | Approve independent net-uncertainty adapter before use; version method; reject missing selected level | Display gross bands and method/quality; retain pointwise/path distinction | All levels, nesting/ordering, correlation-aware net mapping, no fake path coverage |
| Model metadata/fallback | Name and converged boolean; seasonal fallback on model error/nonconvergence (`model.py:69–155`) | No version, training cutoff, generation/expiry, warning array, fallback reason or model-neutral quality | Validate approved release and complete current context; explicit fallback allowlist and investment gate | Show status/reason/version/freshness; convergence is not a tree-model quality metric | Failure, timeout, incomplete output, nonconvergence, stale response, approved fallback |
| Risk estimates | `Safe/Warning/High Risk`, numerical shortfall and emergency funding are treasury outputs (`planning.py:263–280`) | No probabilistic path-deficit targets/horizon/quantile/model metadata | Add optional separate advisory risk object; define outflow-first target; retain deterministic event checks | Label model risk separately from treasury status; show unsupported horizons | Exact supported horizon×quantile grid, monotonicity, missing risk, no reserve double counting |
| Investment horizons | Products 6/24/48h; custom term 1–72h; full-72h baseline gap and fee check (`planning.py:7–35,232–280`) | Forecast interval metadata absent; risk support must not imply custom-term interpolation | Check full horizon, selected uncertainty and any required risk; enforce gate on all four investment paths | Unavailable reasons and disabled actions for manual/optimized/legacy/auto flows | Every lock period, fees, minimum principal, late funding gaps, absent forecast blocks placement |
| Time and settlement | UTC normalization, IST UI, ties sort outflows first (`planning.py:38–46,226–244`; `treasury.py:425–463`) | Exact-string prediction lookup fails for equivalent noncanonical offsets; no declared hourly bucket edge | Normalize timestamps by instant before mapping; preserve event ordering and maturity processing | Use timestamp joins and explicit IST labels; don't round minute-30 grids | UTC/+05:30 equivalence, intrahour receipt/maturity, hour-17 regression |
| Scenario testing | Combined UPI/all-withdrawal/delay/payout/execution stress; read-only comparison (`server.py:226–249`; `planning.py:284–331`) | Legacy `/scenario` returns uncapped net-only plan; `/planning_scenario` uses timed planner; no forecast-context provenance | Reuse identical validated forecast context for baseline/stress; disclose planner type; stress once | Keep integrated Scenario Lab canonical; expose forecast quality in both columns | Isolation, delay beyond horizon, mixed shocks, underlying gap survives execution failure |
| Accounting/audit | Revision, transactional copies, request fingerprint, lock, tranches, ledger (`server.py:215–254`; `treasury.py:496–566`) | No accepted/rejected prediction provenance; `advance` needs forecast before any settlement | Audit forecast identity/method; separate accounting/maturity continuation from forecast outage without changing settlement authority | Explain blocked new placements while displaying settled balances and ledger | Retry/race, no duplicate funds, maturity despite model outage, audit survives failure |
| Reserve floor | Planner uses minimum_buffer + risk_buffer (`planning.py:301`) | Realized `advance` halts automation on minimum_buffer only (`treasury.py:454–484`); risk-buffer treatment differs | Agree and document whether added risk buffer is a settlement alert threshold; preserve operational floor | Clarify which floor each displayed breach refers to | Distinct tests between operational and additional risk thresholds |
| Export/version | Net CSV includes currency, IST timestamp, policy, recommendation (`server.py:136–155`) | No gross bounds, cutoff/version/warnings/risk; State schema_version 2 has no ML contract version | Add explicit metadata/export version; preserve old CSV intentionally; don't expose artifacts | Opt into richer exports and metadata; retain existing download behavior | Exact CSV headers/units, State aliases, old-client support, unavailable exports |
| Import boundary bug | Validator advertises 168–5,000 records (`treasury.py:72–74`) | MAE calculation requires ≥192 (`treasury.py:186–188`); 168/191 accepted by validation then fail prediction | Later repair baseline metric boundary without inventing accuracy; leave unchanged in this task | Explain unavailable baseline metric if supported later | 168/191/192/336/5,000 rows through import and State |

## Financial ordering and hour-17 finding

Current code sorts by `(timestamp, flow >= 0)` in both the planner and realized
settlement: outflows precede same-time deposits and maturities. The lock-period
reserve includes obligations at the maturity timestamp before redemption
(`planning.py:226–249`; `treasury.py:374–463`). Vault principal is excluded from
cash until its contractual maturity. Fees reduce liquid cash immediately, and
locked-principal reconciliation remains in `treasury.py:561–565`.

The repository contained no specifically identified original hour-17 failing
fixture or reproduction payload. **The temporal-ordering pattern was not
reproduced in the tested cases; the original report is not declared resolved.**
Four new passing cases in [tests/test_ml_contract_audit.py](tests/test_ml_contract_audit.py)
provide explicit evidence:

- Lines 10–72: hour-17 ₹50m payment, with ₹50m maturity 15 minutes earlier,
  exactly equal, or 15 minutes later. Planning finds a ₹50m protected-floor gap
  for equal/later maturity; realized replay records Shortfall at payment time.
  Earlier maturity funds the payment. Cash accounting includes simulated flows.
- Lines 75–95: hour-17 ₹70m payment cannot use hour-18 ₹40m deposit; with ₹100m
  cash and ₹10m floor, required reserve is ₹80m and suggested principal ₹20m.

Existing passing regressions additionally cover 15/30/45-minute payment/maturity
ordering with identical closing balances (`tests/test_integrated_treasury.py:83–137`),
future receipts and every recommended option's timed floor (`tests/test_planning.py:17–89`),
and explicit IST payment-before-settlement (`tests/test_indian_banking.py:20–41`).
Keep these as integration gates; obtain the original fixture before closing its
specific defect record. No financial code was changed to make these tests pass.

## Verification evidence

Run from repository root with the existing Windows environment:

```powershell
.\.venv-win\Scripts\python.exe -m pytest -q --basetemp=.runtime/pytest-ml-contract-audit-final-20261018
.\.venv-win\Scripts\python.exe -m ruff check tests/test_ml_contract_audit.py
.\.venv-win\Scripts\python.exe -m ruff format --check tests/test_ml_contract_audit.py
```

Results: **120 passed in 51.20s** (116 preexisting cases plus four new cases), Ruff
lint passed, test formatting passed. This run includes actual HTTP workflow,
export/import, revision, retry, scenario and real-model integration tests in
`tests/test_server.py:163–271`. Most other server tests stub snapshot, so their
passing alone is not evidence for a real-model response schema. No browser visual
test or model quality evaluation was performed in this audit.

A separate synthetic-only probe called the actual GET handlers in process with
an in-memory Store. It confirmed:

- State: INR, 1,008 saved observations but only 168 returned; 72 net and 72 gross
  rows; origin `2026-10-18T08:00:00Z`, first `2026-10-18T09:00:00Z`, last
  `2026-10-21T08:00:00Z`; model SARIMAX, converged true in this run.
- First net forecast minus independently predicted gross difference was
  approximately **−₹103,044.28**: the two displays are not interchangeable.
- Template: HTTP handler status 200, 1,008 rows, three advertised columns. Export:
  status 200, 72 rows, exact 18-column header documented in the contract.
- With only the net fitter replaced by existing seasonal-naïve prediction to
  isolate the baseline calculation, validated lengths 168 and 191 raised
  `ValueError: operands could not be broadcast together` with shapes
  `(168,)/(144,)` and `(168,)/(167,)`; 192 and 336 returned 72 rows.

Local reproducible probe and results (ignored runtime files, metadata only):
[script](.runtime/ml_contract_probe.py), [evidence JSON](.runtime/ml-contract-audit-evidence.json).
Run `.\.venv-win\Scripts\python.exe .runtime/ml_contract_probe.py`.
A standalone socket probe was blocked by Windows error 10013; its replacement
uses the real handler without a network socket. This is distinct from the
passing HTTP tests in the complete suite, not a claimed standalone network pass.

No fitted weights, serialized pipelines, restricted observations or D07 contents
were moved, copied or exported. Existing real-model tests and probes fit only
generated demo observations in memory. Only the two Markdown deliverables and
the synthetic regression test are intended source changes.

## Agreement needed before implementation

Adopt the v1 rupee/bucket/timezone schema and gross/net authority mapping; approve
the uncertainty method, deployment fallback allowlist, freshness settings and
supported optional risk pairs; agree event de-duplication and client/export
versioning. These are contract decisions for the teams, not reasons to alter
treasury behavior during this audit. Model choice remains subject to evaluation.
