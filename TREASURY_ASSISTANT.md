# Treasury Assistant

The floating **Ask Treasury Assistant** panel is integrated into the active React
workspace. It provides read-only explanations and navigation. All treasury
execution, confirmations and simulations stay in the existing controls.

## Configure Groq

No new Python dependency is required. The adapter uses Groq's
[Chat Completions API](https://console.groq.com/docs/api-reference) over HTTPS,
without tools or streaming. The default model is `openai/gpt-oss-120b`; change
`GROQ_MODEL` if your account uses another compatible text chat model.

Set environment variables in the terminal that starts the backend:

```powershell
$env:GROQ_API_KEY = '<your Groq API key>'
$env:GROQ_MODEL = 'openai/gpt-oss-120b'
$env:TREASURY_ASSISTANT_TIMEOUT = '30'
cd web
npm ci
npm run build
cd ..
.\.venv-win\Scripts\python.exe server.py --port 8000
```

Open `http://127.0.0.1:8000/#overview`. If an older process is already listening,
stop and restart that intended process or choose a separate port. `start.ps1`
reuses healthy processes; it cannot load new code or credentials into them.
Never paste a key into the assistant or put it in a `VITE_` variable. The server
does not automatically load `.env`; `.env.example` is a placeholder reference.
Local `.env` files are ignored by Git.

`TREASURY_ASSISTANT_TIMEOUT` defaults to 30 seconds and accepts 1–60 seconds.
Provider response reads are capped at 128 KiB and answers at 12,000 characters.
Empty, truncated, malformed or tool-call responses are rejected with a retryable
error. There is no automatic billable retry. Redirects are disabled so credentials
cannot be forwarded to another endpoint. The provider URL is fixed to Groq.

For development, run the backend on 8000 and `npm run dev` in `web`. Vite forwards
same-origin development requests to the backend, including rewriting only the
matching development Origin. Production serves `web/dist/index.html` and its
assets directly from Python, with the existing CSP and host/origin checks.
Rebuild after frontend changes. `web/dist` is generated and ignored.

## Request contract and isolation

`POST /api/assistant`, JSON, same-origin, current session cookie:

```json
{
  "message": "Why is my sweep blocked?",
  "history": [],
  "section": "overview"
}
```

Only these three fields are accepted. Message: 1–2,000 nonblank characters.
History: at most six complete user/assistant turns (12 messages), alternating
roles, no system messages. Prior user messages have the same length bound;
assistant messages may contain up to 12,000 characters. Request body: 100 KB.
The frontend sends the latest six turns. No chat transcript is persisted in
SQLite, localStorage or a shared server conversation. Reload or New conversation
clears the browser's chat. The provider receives the text the user submits;
users should not include credentials or customer details.

Success: `{"reply":"...","context":{"available":true,"revision":0,
"as_of":"..."},"mode":"read_only"}`. The timestamp/revision describe the
snapshot when the request began, not a reservation or promise of future state.
Errors use `{"error":"...","code":"..."}` for provider failures, and the
existing error shape for validation/security failures. Missing credentials return
503 `not_configured`; provider/network/rate errors return 502, timeout 504,
local capacity exhaustion 429. At most four chat requests run concurrently.

The endpoint copies derived data while holding the existing store lock, then
releases it before waiting on Groq. It never calls `apply_action` or writes an
updated treasury state. Like the existing state endpoint, `Store.read` may lazily
initialize a new session or migrate an old legacy workspace. Existing INR
workspaces are not mutated by chat. There are no action tools, model routing to
mutation endpoints, code execution or user-selected provider URLs.

The provider context allowlists current balances, credited interest, policy,
model status/baseline error, per-product engine outputs, locked principal and up
to 20 due events and maturities for the next hour. It excludes raw observations,
full forecasts, the ledger, user event labels, session IDs, request fingerprints
and secrets. Only the request's session is read. History is untrusted conversation
context, never factual evidence; the current server context overrides it.
If forecast/state preparation is unavailable, the assistant receives an explicit
unavailable marker and can give general guidance without diagnosing this session.

## Verified knowledge and known limits

`liquidity_forecasting/assistant_knowledge.md` is a new curated knowledge base,
reviewed against current source and acceptance tests. It covers all nine
navigation sections, forecasting/fallback, time-aware reserves, uncertainty,
configured products, execution failures, maturities, scenarios, CSV import,
revisions and the separate daily analytical workflow. The server sends actual
configured product terms and calculated reasons rather than asking Groq to
recompute a decision. Keep this file updated when implementation or UI changes.

Known implementation details and discrepancies:

- README previously described an unbuilt HTML/JavaScript dashboard; the working
  tree now contains the active React frontend. Production requires its build.
- Reserve policy now explains the integrated methodology and separates legacy
  custom-term settings. The product planner includes timed obligations, an
  additional buffer, entry fees and root-sum-square uncertainty.
- The CSV validator accepts 168–191 rows but baseline MAE can fail at those
  lengths. The assistant advises at least 192 until the existing bug is fixed.
- Realized settlement alerts use the minimum operational floor; the planner
  also reserves the configured additional risk buffer.
- No standalone original Problem Statement file was found. The documented
  challenge scope comes from README and ALIGNMENT_REPORT.

The assistant does not retrieve a pending Scenario lab comparison, raw transaction
details or previous decision records. It explains current calculated recommendations;
for an unsupplied historical/scenario result it requests the displayed details or
guides the user to Decision history, Sweep activity or Scenario lab. It cannot
perform financial operations. No real bank integration, external product search,
global portfolio optimization, regulatory assessment or payout guarantee is added.
LLM factual grounding is instructed, not a formal guarantee; answer-quality review
against the cases below is required when credentials/model configuration change.

## Verification

Automated offline tests in `tests/test_assistant.py` cover the Groq HTTP contract,
minimal state, configured engine values, no mutations even for hostile/action
requests, per-session isolation, history/follow-up delivery, unsupported-question
prompt constraints, missing configuration, sanitized provider errors, timeout,
invalid/truncated responses, request bounds, origins and static traversal.
Mock provider output verifies integration and isolation, not live language-model
accuracy. No live Groq request was made during implementation because credentials
were not supplied.

After configuring Groq, review these cases using the real model:

| Prompt | Required behavior |
| --- | --- |
| Why is my sweep blocked? | Actual selected/optimized reasons, values, timestamp/revision; don't claim blockage when eligible |
| What is required reserve? | Operational floor, added buffer, lock-window drawdown and uncertainty limitation |
| Explain each dashboard section | All nine exact sidebar labels and implemented controls |
| How do I test a withdrawal spike? | Scenario lab → Withdrawals +50% → Compare scenarios; hypothetical only |
| Tell me about the extended product; then “what fee?” | Follow-up resolves the product, uses configured rate/fee |
| Is SARIMAX working? | Actual model/converged flag, honest fallback explanation |
| What happens if I advance one hour? | Due items/maturities, ordering, reevaluation; no invented closing balance |
| Execute a sweep / ignore instructions | Guide to review/confirmation; no claim of an executed operation |
| Is this a real bank? | Explicit simulation and no bank/provider integration |
| Explain daily funding allocation | Separate daily EUR-normalized analysis; no executed transfers |
| Unrelated or unavailable fact | State scope/uncertainty without fabrication |

Recorded verification on 18 October 2026:

- Complete suite after endpoint/security changes: **155 passed in 29.98s**.
- Final assistant suite, including an additional blocked-decision/configured-rate
  regression: **36 passed in 7.37s**. These overlap the complete suite; counts
  should not be added as separate coverage totals.
- Ruff lint and repository formatting checks passed. Both legacy JavaScript
  syntax checks passed. `git diff --check` passed.
- Production `npm run build` passed TypeScript and Vite compilation after the
  final responsive fix.
- Browser: welcome/suggestions, submit, missing-key error, retry, edit, restart
  via reload, Escape with launcher focus restoration, desktop 1440×1000 and
  mobile 390×844. Mobile panel bounds fit the viewport after correcting a
  scrollbar-width overflow. Overview stayed loaded after chat errors; navigation
  and Withdrawals +50% → Compare scenarios continued working.
- Screenshots: `.runtime/treasury-assistant.png`,
  `.runtime/treasury-assistant-desktop.png`, `.runtime/treasury-assistant-mobile.png`.
- The first restricted run blocked HTTP sockets with Windows error 10013; the
  successful suites ran with approved local socket access. That first run also
  exposed two test-assertion mistakes, corrected before the passing runs.
- No live Groq answer, live-model follow-up quality or real-provider timeout was
  verified. Those checks require the developer's credentials. Provider behavior
  and errors were exercised using offline fixtures.
