# Verified Reserve Juggler assistant knowledge

Source review: 18 October 2026. Sources: README.md, ALIGNMENT_REPORT.md,
VERIFICATION.md, BACKEND_FRONTEND_INTEGRATION_GAPS.md, server.py,
liquidity_forecasting/{treasury,planning,model,allocation,balances,fx,evaluation,export}.py,
web/src/components/pages and modals, tests/test_{planning,integrated_treasury,
ml_contract_audit,server}.py. This curated file describes implemented behavior;
it is not a bank policy manual. Current configuration in the supplied context
overrides illustrative defaults. No original standalone Problem Statement file
was found; its scope is recorded in README and ALIGNMENT_REPORT.

## Purpose and boundaries
The Idle Cash Problem is the trade-off between immediately available cash for
withdrawals, payments and settlements, and earning a return on eligible surplus.
The workflow forecasts flows, protects a time-aware reserve, compares eligible
term products, revalidates and simulates execution, records decisions, and releases
principal and contracted interest at maturity. It cannot guarantee every payout.
Hourly INR balances, payment rails, rates, execution and investments are simulated.
There is no bank connection, investment provider, real transfer, production
scheduler, authentication provider or regulatory CRR/SLR calculation. Statutory
balances are outside the operational pool. Imported observations do not establish
live account balances. Gross transaction volume is deposits plus withdrawals,
not spendable cash. Observations describe history; forecasts are estimates.

## Workspace navigation and exact controls (current React frontend)
Sidebar groups are Workspace (Overview, Cashflow forecast, Investment options,
Payments & events), Review (Scenario lab, Decision history, Sweep activity),
and Settings (Reserve policy, Data sources). Values are INR; times are IST.
Advance 1h in the top bar advances one simulated hour. Refresh workspace reloads
state. On mobile use Toggle navigation; Close navigation or the backdrop closes it.

Overview (#overview): four primary figures (Available cash, Required reserve,
Eligible surplus, Projected minimum cash). Selected investment shows suggested
principal, product, lock, annual rate, net return, entry fee and maturity.
Review selected investment opens its confirmation; Compare options opens
Investment options. View reserve calculation expands the floor, added buffer,
lock-window drawdown and eligibility reason. Liquidity position shows modeled
funding gap, locked principal, credited interest and auto-sweep status.
Planning assumptions expands the full method and uncertainty limitations.
Cash availability · next 72 hours shows the timed cash path, before and after the
selected investment. View detailed cash timeline expands all movements.
Upcoming payments & events shows at most five; View all opens Payments & events.
Add a payment or event also opens that page. There is no optimized execution
button on Overview; use Investment options for optimized review.

Cashflow forecast (#forecast): Projected cash balance chart with 1h, 6h, 24h,
48h and 72h buttons; actual model and planning-envelope status below it.
Export 72-hour forecast downloads CSV. Model details & forecast limitations
expands model metadata and baseline MAE. Hourly forecast data expands the table
for the selected horizon. This net-flow chart excludes scheduled obligations
and maturities; use Overview for the integrated timed path.

Investment options (#investments): Available products compares short product
names (Intraday placement, Overnight deposit, 48-hour deposit), term/rate,
minimum/fee, suggested principal, net return and status. Each row's Details
expands the engine reason, eligible principal and maturity. Review optimized
sweep opens the highest-return eligible term. Review selected investment uses
the configured selected product. Investment planning settings is collapsed:
open it before changing Selected investment, Additional risk buffer · INR or
illustrative annual rates, then Save & recalculate.
How products are compared explains the single-placement term comparison.
Review simulated investment is the existing confirmation dialog. Check fee,
maturity and net earnings; choose Simulated execution outcome (Success,
Execution failure, Timeout before execution). Confirm simulation executes only
the simulation; Cancel returns without placing anything. Chat cannot do this.

Payments & events (#events): Add a simulated event. Event type choices:
Withdrawal; Payment / salary payout; Incoming deposit; Settlement receipt;
Delay pending settlements; Set additional risk buffer.
For payments/receipts fill Amount · INR and Due in · hours. For a delay only
Delay duration · hours is shown; it shifts all pending settlement receipts.
For a risk-buffer change only New risk buffer · INR is shown; it replaces the
additional buffer immediately. Select Simulate event & recalculate.
The Current position card shows reserve/surplus and View decision history.
Upcoming payments & events lists the scheduled records. This page no longer
repeats investment execution controls.

Scenario lab (#scenarios): isolated hypothetical baseline/stress comparison.
1. Open Scenario lab.
2. Choose a Scenario preset: Normal operations; Withdrawals +50%;
UPI spike +50%; Merchant settlement delay · 12h; Salary-day NEFT payments;
Festival spending + delay; Investment execution failure.
3. Optionally open Adjust assumptions to change Extra UPI outflows · %,
All-channel outflow increase · %, Merchant availability delay · hours,
Hypothetical investment execution, or Additional payout in 6 hours · INR.
4. Select Compare scenarios. Inspect reserve, funding gap, eligible surplus,
suggested investment, expected net return, projected minimum and risk.
Open Historical strategy comparison then Run comparison for the separate
read-only 24-hour rolling seasonal-naive strategy replay. Evaluation assumptions
expands its methodology. Neither comparison changes saved financial state.
Pending scenario results are not supplied to chat; request displayed details.

Decision history (#decisions): before/after cash, reserve and principal records.
View explanation expands an individual recorded reason.
Sweep activity (#activity): search, filter, sort and export ledger records; View
opens a movement detail. Locked sweep principal lists contractual maturities and
credited interest. About opening vault holdings explains their lack of maturity.

Reserve policy (#policy): Liquidity controls contains Minimum cash buffer · INR,
Forecast confidence (90/95/99), Additional withdrawals · %, and Automatically
sweep eligible surplus after each simulated hour. Save policy applies them.
Custom-term sweep settings expands Vault lock period · hours (1–72) and
Assumed annual yield · %, which belong to the legacy custom-term sweep.
Configured product terms remain in Investment options. How the reserve is
calculated expands explanatory help. Reset workspace expands a destructive
Reset sandbox control with the existing confirmation. Existing investments
retain their contracted terms.

Data sources (#data): Download sample CSV. Choose hourly cashflow CSV under
Import hourly cashflows, then Validate & import. CSV format & requirements
expands the contract. Exact columns: timestamp,deposits,withdrawals, in that
order. Advertised contract: 168–5,000 consecutive hourly rows, max 1 MB,
unique ascending timezone-bearing timestamps, zero seconds/fractions,
finite nonnegative amounts <= 1 trillion, no booleans or silent filling.
Existing baseline MAE bug can reject 168–191 otherwise validated rows; use
at least 192 until repaired. Imports replace observations, preserve balances,
rebuild demo scheduled events and disable auto-sweep. Import controls are
disabled while tranches are locked; wait for maturity. Do not recommend
discarding a workspace merely to import data.
Configure simulated balances expands Liquid funds · ₹, Already invested · ₹
and Save simulated balances. Changes are unavailable while investments are locked.
What is simulated? expands the local simulation/bank-connection disclosure.

## Forecast implementation
Hourly net = deposits minus withdrawals. fit_hourly fits the last 672 hours
(28 days), AR(1) plus 24-hour seasonal AR(1) SARIMAX, and produces 72 hourly
mean/lower/upper estimates. Failure, a convergence warning or nonconvergence
uses seasonal-naive fallback. Use the supplied model and converged status;
fallback is not a successful SARIMAX fit. Independent seasonal-naive gross
deposit/withdrawal estimates with intervals are separate display estimates;
their difference need not equal the net forecast. The planning path reconciles
gross hourly profiles to net forecasts without counting net flow twice.
baseline_mae compares the final seven days of net observations with the same
hours one day earlier. It is not SARIMAX accuracy or a future error guarantee.

## Time-aware reserve, eligibility and return
Use the planner's supplied values; never recalculate an investment from chat.
Protected floor = policy minimum_buffer + planning risk_buffer. Required reserve
adds the worst cumulative drawdown through the product's lock period, including
obligations at the maturity timestamp before redemption. Planning uses a full
72-hour baseline safety check, immediate entry fee, scheduled obligations,
stressed withdrawals, net forecasts and existing contractual maturities.
Eligible principal is cash minus required reserve minus entry fee, floored at
zero and rounded down to cents; funding gaps (including fee-induced gaps) block
eligibility. Suggested principal is zero if below minimum or interest <= fee.
Eligible and suggested can differ. Read the recorded reason for each option.
Uncertainty allowance through hour h = sqrt(sum((mean-lower)^2 through h)).
This root-sum-square planning heuristic assumes uncorrelated errors; it is not
a calibrated confidence bound for the entire cash path. Correlated forecast
errors, unmodeled peaks and shocks can defeat modeled protection. Use additional
risk buffers and stress testing. Risk labels are model outputs, not guarantees.
Cash is liquid; vault holdings and locked principal are not spendable. Opening
legacy vault holdings have no assumed maturity. New tranches release principal
and contracted interest only at their maturity. A later deposit cannot pay an
earlier obligation. At equal timestamps outflows precede receipts and maturities.
Demo rails split withdrawals UPI 45%, IMPS 20%, NEFT 20%, RTGS 10%, ATM 5%; 8% of
deposits are reclassified as merchant receipts. These are illustrative assumptions.
Illustrative product defaults: flex / Intraday treasury placement (demo): 6h,
4% annual, minimum ₹250,000, ₹20 entry; overnight / Overnight treasury deposit
(demo): 24h, 5%, minimum ₹500,000, ₹50 entry; extended / 48-hour treasury deposit
(demo): 48h, 5.4%, minimum ₹1,000,000, ₹100 entry. Current context overrides rates.
No early redemption. Simple expected interest = principal * annual rate / 100 *
hours / (365*24), rounded to cents. Net return deducts the entry fee. Expected
interest on locked principal is not credited interest. earned is already credited.
The optimizer chooses greatest net return for one placement at each term's actual
duration; ties favor shorter terms. It is not a global multi-period portfolio
optimizer and does not compare equal holding horizons. With no eligible product,
the optimized record is only a comparison result, not an actionable investment.
Every execution is revalidated under the process-wide lock. Revisions reject
stale requests; request fingerprints deduplicate exact retries. Simulated failure
or timeout-before-execution logs deferral without moving funds or creating tranches.
An unknown real-provider execution outcome is not implemented.
Advance 1h generates noisy simulated observations, processes due obligations
and maturities in timestamp order, records ledger movements, then reevaluates.
Do not promise an exact future closing balance. Operational floor breaches halt
automation. The realized breach threshold is minimum_buffer; the planner also
reserves risk_buffer (an existing distinction). If enabled and eligible, an
optimized automatic placement is attempted after each simulated hour.
The legacy custom-term reserve accumulates net lower-bound flows, is additionally
capped by the integrated timeline, and differs from the fee-aware term optimizer.
Reserve policy keeps those settings under Custom-term sweep settings; use the
integrated implementation for product decisions and disclose the difference.

## Troubleshooting and separate daily application
Stale revision: refresh the workspace, inspect the new recommendation, retry via
the established controls; don't bypass revision or confirmation. No eligible
investment: inspect actual per-product reasons, floor, risk buffer, fees, minimum,
lock window, obligations and funding gap. Do not call positive eligible principal
investable if suggested is zero. Connection failure: check local Python server,
use Retry connection; first model fitting may take time. Assistant failure does
not invalidate or change dashboard data. Missing provider configuration requires
server-side GROQ_API_KEY; never ask users to paste secrets into chat.
The separate daily application (app.py Streamlit, main.py batch) handles EUR, USD,
JPY, BRL, INR, AUD daily net cashflows, SARIMAX/fallback, projected balances and
shortfalls, EUR normalization at illustrative FX rates, constrained SciPy linear
program funding allocation with costs and priorities, rolling backtests, plots
and Excel reporting. Allocations are analytical recommendations, not executed
bank transfers. Do not mix its funding allocator with hourly term investments.
Historical synthetic replay results are policy comparisons, not proof of live
performance, guaranteed safety or higher income in every case.
