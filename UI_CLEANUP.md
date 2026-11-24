# Workspace UI cleanup — 18 October 2026

The nine operational views now use compact Segoe UI typography, consistent cards,
short page titles and three navigation groups: Workspace, Review and Settings.
The treasury calculations and mutation API contracts were not changed.

- Overview: four primary metrics, one selected-investment card, concise liquidity
  status and a cash timeline. Reserve calculations and assumptions expand on demand.
- Investment options: six comparison columns, product details on demand, separate
  optimized and selected review actions. Planning settings are expandable.
- Payments & events: event form, current reserve/surplus and scheduled events.
  Delay and risk-buffer choices show only the fields relevant to that action.
- Scenario lab: select a preset, compare, optionally adjust assumptions. Historical
  strategy comparison is a separate expandable tool. Duplicate gap measures removed.
- Forecast: chart and current model visible; model methodology and hourly rows
  available in expandable sections. All five horizons and export remain accessible.
- Policy and data: operational controls first; custom-term settings, reset, CSV
  requirements and simulated-balance configuration are expandable.
- History and activity: compact tables, expandable decision explanations, existing
  search/filter/export and maturity records.
- Mobile: closable navigation drawer, local table scrolling, compact assistant
  launcher. Closing investment review restores focus to its trigger.
- Connection errors: plain-language message with technical detail on demand.
- Assistant knowledge updated to the new labels and navigation paths.

Verification:

- `npm run build`: TypeScript and Vite passed.
- Complete Python regression suite: **156 passed in 20.71s**.
- Ruff lint/format checks, legacy JavaScript syntax and `git diff --check`: passed.
- Browser: all nine desktop routes; Overview, investments, events, scenarios,
  policy and data at 390×844; no page overflow observed. Tables scroll locally.
- Investment review/cancel and restored focus, 1h/72h forecast horizons, conditional
  event inputs, and Withdrawals +50% scenario comparison checked against the backend.
- No investment was confirmed and no payment, policy or balance change was saved
  during browser review. The scenario comparison was read-only.

Screenshots: `.runtime/clean-ui-overview.png`, `.runtime/clean-ui-events.png`,
`.runtime/clean-ui-mobile.png`. Rebuild `web` after further frontend changes.
