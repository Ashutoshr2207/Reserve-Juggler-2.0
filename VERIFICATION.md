# Current alignment verification — 18 October 2026

- Baseline before edits: **96 passed in 21.70 seconds**.
- Final complete suite: **116 passed in 13.71 seconds**.
- Ruff lint: **all checks passed**; format check: **36 files already formatted**.
- `node --check web/app.js` and `node --check web/planning.js`: **passed**.
- Real-model HTTP integration remains in the full suite. New HTTP acceptance
  test covers optimized timeout, persisted idempotent replay, stale rejection,
  read-only strategy comparison, and unchanged saved balances.
- Browser verified: overview/calculated reserves, optimized product review,
  failed placement with unchanged balances, combined stress blocking, read-only
  strategy table, and hypothetical execution-failure deferral.
- Both 72h fallback and 24h SARIMAX-pipeline rolling evaluations executed;
  measured reports are in `reports/`. Failure replay executed with every third
  eligible attempt failing. See ALIGNMENT_REPORT.md for exact figures and
  assumptions, including cases where C earns less net interest than B.
- A sandbox run hit pytest temporary-directory permissions; a fresh workspace
  `--basetemp` resolved that. A later sandbox run passed 108 tests but blocked
  seven loopback HTTP tests with WinError 10013. The complete final suite was
  therefore run outside that sandbox restriction. No failing network check was
  counted as passing.
- Review server: `http://127.0.0.1:8019` (simulation). Browser screenshot:
  `.runtime/alignment-scenario.png`.

This record supersedes earlier implementation counts below. The multi-currency
regressions pass; no live financial integration or unconditional payout safety
has been verified.

---

# Verification record — 18 October 2026

## Latest planning update

**87 tests passed in 9.76 seconds.** Ruff lint passed; 31 files passed the format
check. Both frontend JavaScript modules passed syntax checks. Browser access now
works: overview, combined stress comparison, investment review/cancel, and mobile
navigation were checked. Responsive inspection used 390×844 and 1440×1000.
See PLANNING.md for current methodology and feature demonstrations. The original
browser restriction and 72-test record below apply to the earlier implementation.

Executed on Windows with the prepared Python 3.12 environment.

| Check | Result |
| --- | --- |
| Full pytest suite | **72 passed in 11.58 seconds** |
| Ruff lint | **All checks passed** |
| Ruff format check | **29 files already formatted** |
| `node --check web/app.js` | **Passed**, exit code 0 |
| Local `/api/health` | **HTTP success**, `{"status":"ok","mode":"simulation"}` |
| Real-model HTTP integration | **Passed**: snapshot → stress scenario → sweep → duplicate rejection → advance → export → reset → CSV import |
| Browser visual/interaction QA | **Not completed**; browser security policy blocked access to the connection-error page because its URL protocol was disallowed |

The initial in-sandbox preview could not be reached from the host browser.
The server was restarted outside the sandbox and its health endpoint responded.
The browser tool subsequently rejected inspecting the prior connection-error page;
no alternate browser mechanism was used to bypass that rejection. Responsive
styles, focus states, reduced-motion handling, and form behavior are implemented
but are not claimed as browser-verified.

An initial shortfall test fixture used cashflows smaller than the simulator's
noise scale; it was corrected to represent a deterministic stressed outflow.
Pytest's sandbox temporary-directory restriction was resolved by rerunning with
approval outside the sandbox. The original daily regression tests pass unchanged.

The actual default SARIMAX run converged and returned:

- Required reserve: **$23,140,672.17**.
- Eligible sweep: **$8,859,327.82**.
- Retained cash: **$23,140,672.18** (conservative cent rounding).
- Added estimated daily yield at 5%: **$1,213.61**.
- Sample average hourly gross movement: **$20,032,124.39**.
- Previous-day baseline holdout MAE: **$237,074.73**.

These are calculated demonstration results, not live financial records or a
guarantee of future payouts. Model output may differ slightly across library
versions; the tested dependency versions are recorded in `requirements-lock.txt`.

No bank API, real transfer, production scheduler, authentication provider,
hosted deployment, or intrahour payout guarantee was tested or claimed.
