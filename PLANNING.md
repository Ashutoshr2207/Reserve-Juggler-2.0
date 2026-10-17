> **18 October 2026 alignment update:** The planner now uses the net forecast and uncertainty, optimized automatic sweeping, chronological intrahour settlement, simulated execution failure/retry handling, and measured strategy replay. See [ALIGNMENT_REPORT.md](ALIGNMENT_REPORT.md) for current methodology, results, demo steps, and limits. Earlier deterministic-only descriptions below are historical.

# Intelligent Treasury & Liquidity Management — current implementation

## Start and architecture

Run `./start.ps1` from the project folder on Windows, then open
http://127.0.0.1:8000/#overview. The launcher reuses a healthy server and otherwise
starts a persistent hidden Python process. Logs and PID live under `.runtime/`.
Use `./start.ps1 -Foreground` for a terminal process, or the Python setup commands
in HANDOVER.md on a fresh machine. No new runtime dependencies were required.

New module `liquidity_forecasting/planning.py` centralizes the deterministic
baseline, transaction timeline, event overlays, vault eligibility, returns, and
explanations. `treasury.py` integrates it into persisted state and account
mutations. `server.py` exposes the planning endpoints and serves
`web/planning.js`. That frontend module renders the overview, investment options,
payments/events, combined stress scenarios, and decision history. `web/app.js`
retains navigation, API handling, imports, original forecasting views, and ledger.
`web/styles.css` adds responsive planning layouts. SQLite stores demo state under
the existing session cookie. No user session was reset for this update.

## Calculation rules

The baseline forecasts separate hourly deposits and withdrawals using their
average for the matching UTC hour in the last 14 days of observations. It is a
transparent deterministic profile, not a claimed trained ML model. The existing
fitted SARIMAX pipeline remains available as a separate analysis view.

Eight percent of profile deposits is **reclassified**, rather than added, as
merchant receipts because the existing input data has no merchant category.
This illustrative split is disclosed in the UI. Explicit scheduled obligations
are additional commitments. The default demo schedules a $7M customer payment
six hours ahead and a $4M confirmed merchant receipt seven hours ahead.

Transactions are processed in timestamp order, with outflows before receipts
when timestamps tie. Pending merchant delays shift receipt availability. Existing
sweep maturities are counted only when contractually due. The initial $68M vault
has no redemption schedule and is excluded from liquid cash.

For each candidate investment:

1. Protected floor = configured minimum cash reserve + additional risk buffer.
2. Accumulate chronological flows through maturity; find the lowest cumulative
   balance, including earlier deficits that later deposits might erase.
3. Required reserve = protected floor + maximum cumulative drawdown during lock.
4. Maximum eligible principal = max(0, liquid cash − required reserve − entry fee).
5. Check the entire 72-hour baseline as well. Reject if it cannot cover the floor,
   including the immediate cash cost of the entry fee. This conservative check
   does not rely on future investment interest to rescue a shortage.
6. Reject a principal below the minimum or whose gross return does not exceed
   the fee. Otherwise suggest the eligible principal.
7. Gross interest = principal × annual rate / 100 × hours / (365 × 24).
   Net earnings = rounded gross interest − entry fee.

Reserve rounding is upward to cents; principal rounding is downward. A new
investment is checked again on the server under the workspace revision lock.
It deducts principal and fee from cash, adds principal to the vault, and creates
a maturity tranche at the original rate. The simulation clock releases principal
and credits contracted interest at maturity. Early redemption is unavailable.
Legacy manual/automatic sweeps are additionally constrained by the timed planner
using their actual configured lock duration, so scheduled events cannot be
bypassed through the old sweep controls.

Available illustrative options:

| Option | Lock | Annual yield | Minimum principal | Entry fee |
| --- | --- | --- | --- | --- |
| Intraday Vault | 6 hours | 4% | $250,000 | $20 |
| Overnight Vault | 24 hours | 5% | $500,000 | $50 |
| 48-hour Vault | 48 hours | 5.4% | $1,000,000 | $100 |

Safe means the configured deterministic baseline is covered. Warning means no
economic/eligible investment or the reserve floor is threatened at a timeline
point. High Risk means an unfunded baseline requirement, or a negative balance
at a timeline point. The overview funding gap checks the full 72-hour horizon;
the required reserve refers to the selected investment's shorter lock window.
Neither the baseline nor the separate SARIMAX forecast guarantees real payouts.

## Demonstrating the five features

1. **Time-aware protection:** Overview → inspect the chronological chart and
   expand its cashflow table. The scheduled payout precedes the confirmed
   receipt. A unit test exercises exactly $10M liquid, $7M due at 14:00, and $4M
   arriving at 15:00: with a $1M floor, required reserve is $8M and investment is
   capped at $2M. The later deposit cannot increase that cap.
2. **Maturity-aware sweeping:** Investment options → compare each minimum,
   maturity, fee, net return, and assessment. Select a vault and additional risk
   buffer, save, then review Simulate Investment. Cancel is supported. Confirm
   simulates account movements only; inspect locked principal in Sweep activity.
3. **Event-driven recalculation:** Payments & events → choose unexpected
   withdrawal, merchant delay, customer payout, or incoming deposit. Set the
   amount and timing/delay. Submit to recalculate every dependent planning value.
   Events are scheduled future changes, so they do not inflate current cash.
   Advance 1 hour on Overview to process due events in the simulation.
4. **Stress scenarios:** Scenario lab → choose +50% withdrawals, 12h merchant
   delay, payday, or a shopping spike combined with delay. Inputs can be combined
   manually. Compare the baseline and stressed reserve, gap, surplus, suggested
   investment, earnings and risk. Stress runs do not modify saved cash or events.
5. **Explainability:** Decision history → inspect timestamp, cash position,
   reserve/investment before and after, trigger and reason. Investment changes,
   saved events, policy changes, imports, and simulated advances are recorded.
   Overview also shows the latest decision explanation alongside its current
   reserve breakdown. A reset intentionally clears the demo history.

## Added API contracts

Existing same-origin JSON/session protections apply. Mutations require the latest
`revision`; failed actions save nothing. GET `/api/state` adds `intelligence`
(policy, protected floor, option assessments, selected recommendation, timeline,
scheduled events and method), plus persisted `scheduled`, `planning_policy` and
`decisions` where present. Existing daily/SARIMAX contracts remain available.

| POST endpoint | JSON fields | Result |
| --- | --- | --- |
| `/api/planning_policy` | `revision`, `option` (flex/overnight/extended), `risk_buffer` (0–10B USD) | Updated snapshot |
| `/api/planning_event` | `revision`, `kind` (withdrawal/payment/deposit/delay), `amount`, `hours` (>0–48) | Updated snapshot and decision history |
| `/api/planning_invest` | `revision` | Updated snapshot; principal, terms and fee computed server-side |
| `/api/planning_scenario` | `stress: {withdrawals:0..100, delay:0..48, payout:0..10B}` | `{baseline, stressed}`; no persistent changes |

`hours` means time from the current simulation clock, except for delay events,
where it shifts all pending explicit merchant receipts. Delay events ignore the
amount. Scenario delays also shift the forecast merchant receipt profile.
Scenario extra payouts occur six hours ahead. Currency is USD; all times are UTC.

## Verification and limitations

The full automated suite passes **87 tests**, including the exact $10M example,
timing-dependent eligibility, full-horizon fee protection, real-duration return
math, minimum investment rejection, principal/fee conservation, no merchant
double counting, maturity tranches, combined stress, event explanations, failed
investment requests, stale revisions, and all original model/API tests.

Ruff lint and formatting pass; both frontend modules pass Node syntax checks.
Browser verification now succeeds: the updated overview and its six metrics
loaded; the shopping-spike-plus-delay scenario produced a side-by-side funding
gap and zero suggested investment; the investment review/cancel workflow worked.
Mobile navigation and dashboard were inspected at 390×844 with no horizontal
page overflow; desktop review was checked at 1440×1000. The browser viewport was
restored afterward. Existing user cash was not changed by these browser checks.

All account balances, vault rates, fees and events are demonstrations. Historical
CSV imports have only aggregate deposits/withdrawals; the merchant split is an
explicit assumption. The deterministic baseline does not predict unobserved
shocks. Advancing an hour uses the existing seeded cashflow simulator and can
therefore realize a different flow from the baseline. Contracts/events are then
reconciled and the plan recalculated. Production bank connectivity, identity,
payment execution, and a durable scheduler remain outside this demo.

For reproduction: `python -m pytest -q`, `python -m ruff check .`,
`python -m ruff format --check .`, `node --check web/app.js`, and
`node --check web/planning.js` using the prepared environment.
