import {
  planningOverview,
  investmentPage,
  eventPage,
  stressPage,
  decisionPage,
  bindPlanning,
  demoSettings
} from '/planning.js';
const $ = (selector, root = document) => root.querySelector(selector);
const app = $('#app');
const dialog = $('#dialog');
let state = null,
  loading = false,
  loadError = '',
  horizon = 24,
  ledgerPage = 1;
let ledgerQuery = '',
  ledgerType = 'All',
  ledgerOrder = 'newest',
  scenario = null,
  busy = false,
  timer = null;
let toastTimeout, lastFocus;
const money = (value, digits = 0) => new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: digits,
  minimumFractionDigits: digits
}).format(value);
const compact = value => {
  const absolute = Math.abs(value),
    sign = value < 0 ? '−' : '';
  if (absolute >= 1e7) return `${sign}₹${new Intl.NumberFormat('en-IN',{maximumFractionDigits:2}).format(absolute/1e7)} crore`;
  if (absolute >= 1e5) return `${sign}₹${new Intl.NumberFormat('en-IN',{maximumFractionDigits:2}).format(absolute/1e5)} lakh`;
  return money(value);
};
const number = value => new Intl.NumberFormat('en-IN').format(value);
const date = (value, full = false) => new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata',
  day: '2-digit',
  month: 'short',
  ...(full ? {
    year: 'numeric'
  } : {}),
  hour: '2-digit',
  minute: '2-digit',
  hour12: false
}).format(new Date(value));
const hour = value => new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false
}).format(new Date(value));
const escape = value => String(value).replace(/[&<>"']/g, c => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
} [c]));
const paths = {
  arrow: 'M5 12h14m-5-5 5 5-5 5',
  down: 'M12 4v16m-5-5 5 5 5-5',
  grid: 'M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z',
  chart: 'M3 3v18h18M6 15l5-5 4 3 6-8',
  flask: 'M9 3h6M10 3v6L4 19q-1 2 2 2h12q3 0 2-2L14 9V3M8 14h8',
  activity: 'M3 12h4l3-8 4 16 3-8h4',
  sliders: 'M4 7h16M4 17h16M8 4v6m8 4v6',
  database: 'M20 5c0 4-16 4-16 0s16-4 16 0v14c0 4-16 4-16 0V5m0 7c0 4 16 4 16 0',
  shield: 'M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM8 12l3 3 5-6',
  lock: 'M7 10V7a5 5 0 0 1 10 0v3M5 10h14v11H5zm7 4v3',
  wallet: 'M20 7H4V4h14v3M4 7v13h17V7m0 4h-6v5h6',
  vault: 'M4 3h16v18H4zM16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0m-4-4v8m-4-4h8',
  clock: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M12 7v5l3 2',
  download: 'M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5',
  upload: 'M12 16V4m-4 4 4-4 4 4M4 16v5h16v-5',
  refresh: 'M20 7V3m0 4h-4M4 17v4m0-4h4M5 8a8 8 0 0 1 14-3m0 11A8 8 0 0 1 5 19',
  check: 'M5 12l4 4L19 6',
  info: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0M12 11v6m0-10v1',
  play: 'm8 4 12 8-12 8z',
  menu: 'M4 6h16M4 12h16M4 18h16',
  chevron: 'm9 5 7 7-7 7',
  file: 'M5 3h9l5 5v13H5zM14 3v6h5M8 13h8m-8 4h6',
  pause: 'M8 4v16M16 4v16',
};
const icon = name =>
  `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.arrow}"/></svg>`;
const brand = () =>
  `<a class="brand" href="#home" aria-label="Reserve Juggler home">
    <div class="brand-badge"><img src="/favicon.svg" alt="Reserve Juggler"></div>
    <div class="brand-text">
      <span class="brand-name">RESERVE JUGGLER</span>
      <span class="brand-small">TREASURY INTELLIGENCE</span>
    </div>
  </a>`;

const navGroups = [
  {
    title: 'OPERATIONS',
    items: [
      ['overview', 'grid', 'Overview', 'Demo'],
      ['forecast', 'chart', 'Cashflow forecast', '72h'],
      ['scenarios', 'flask', 'Scenario lab', 'Stress']
    ]
  },
  {
    title: 'TREASURY ACTIONS',
    items: [
      ['investments', 'vault', 'Investment options', '3 Vaults'],
      ['events', 'clock', 'Payments & events', ''],
      ['decisions', 'shield', 'Decision history', '']
    ]
  },
  {
    title: 'GOVERNANCE & DATA',
    items: [
      ['activity', 'activity', 'Sweep activity', ''],
      ['policy', 'sliders', 'Reserve policy', ''],
      ['data', 'database', 'Data sources', 'CSV']
    ]
  }
];
const nav = navGroups.flatMap(g => g.items.map(([id, i, label]) => [id, i, label]));
const current = () => location.hash.slice(1) || 'home';

async function api(path, payload) {
  const response = await fetch(`/api/${path}`, payload === undefined ? {
    signal: AbortSignal.timeout(120000)
  } : {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(120000)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}

function toast(message) {
  const node = $('#toast');
  node.textContent = message;
  node.classList.add('visible');
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => node.classList.remove('visible'), 5500);
}

function setBusy(value) {
  busy = value;
  if (value) {
    const strip = document.createElement('div');
    strip.className = 'busy-strip';
    strip.id = 'busy-strip';
    document.body.append(strip);
  } else $('#busy-strip')?.remove();
  document.querySelectorAll('[data-mutate], dialog button[type="submit"]').forEach(button => button
    .disabled = value);
}
async function mutate(action, extra = {}) {
  if (busy) return false;
  setBusy(true);
  try {
    state = await api(action, {
      revision: state.revision,
      request_id: crypto.randomUUID(),
      ...extra
    });
    scenario = null;
    if (action === 'reset') {
      stopTimer();
      ledgerPage = 1;
    }
    render();
    return true;
  } catch (error) {
    toast(error.message);
    return false;
  } finally {
    setBusy(false);
  }
}
async function load() {
  if (loading) return;
  loading = true;
  loadError = '';
  render();
  try {
    state = await api('state');
  } catch (error) {
    loadError = error.message;
    if (state) toast('Refresh failed: ' + error.message);
  } finally {
    loading = false;
    render();
  }
}

function landing() {
  return `<div class="landing">
    <header class="landing-nav">
      ${brand()}
      <nav class="landing-links" aria-label="Main">
        <a href="#method" data-scroll="method">How it works</a>
        <a href="#scenarios">Explore scenarios</a>
        <a class="btn primary" href="#overview">Enter Workspace ${icon('arrow')}</a>
      </nav>
    </header>
    <main id="main">
      <section class="hero">
        <div class="hero-copy">
          <div class="eyebrow">Institutional Treasury Sandbox</div>
          <h1>Every rupee.<br>In its <span>right place.</span></h1>
          <p>Cash when your customers need it. Yield when they don’t. Optimize liquidity with a clear, time-aware view of what comes next.</p>
          <div class="hero-actions">
            <a class="btn primary" href="#overview">Enter Workspace ${icon('arrow')}</a>
            <a class="btn secondary" href="#method" data-scroll="method">See How It Works ${icon('down')}</a>
          </div>
          <div class="hero-note">${icon('shield')} Synthetic data. Real SARIMAX forecasting. No money moves.</div>
        </div>
        <div class="reserve-scene" role="img" aria-label="Illustration: customer cash buffer and yield vault.">
          <div class="scene-grid"></div>
          <div class="scene-card vault-card">
            <div class="card-meta"><span>${icon('vault')} YIELD VAULT</span> <span>01 / 02</span></div>
            <div class="card-amount">5.00<small> % per year</small></div>
            <div class="card-foot"><span>PUT SURPLUS TO WORK</span>${icon('lock')}</div>
          </div>
          <div class="flow-dots"><i></i><i></i><i></i><i></i></div>
          <div class="scene-card buffer-card">
            <div class="card-meta"><span>${icon('wallet')} CASH BUFFER</span> <span>02 / 02</span></div>
            <div class="card-amount">Ready.<small> When it matters.</small></div>
            <div class="card-foot"><span>LIQUIDITY FIRST. ALWAYS.</span>${icon('shield')}</div>
          </div>
          <div class="scene-label yield-label">${icon('chart')} Surplus has a purpose.</div>
          <div class="scene-label shield-label">${icon('shield')} A reserve, with a reason.</div>
          <div class="scene-caption">One treasury. Two destinations. Perfect balance.</div>
        </div>
      </section>
      <section class="premise" aria-label="Problem assumptions">
        <div><div class="eyebrow">Built around<br>the idle cash problem</div></div>
        <div><strong>₹2 crore</strong><span>Illustrative hourly gross movement</span></div>
        <div><strong>5.0%</strong><span>Assumed annual vault yield</span></div>
        <div><strong>24h</strong><span>Default simulated lock period</span></div>
      </section>
      <section class="method" id="method">
        <div class="method-head">
          <div><div class="eyebrow">From uncertainty to decision</div><h2>Keep enough.<br>Put the rest to work.</h2></div>
          <p>One connected workflow turns hourly cashflows into an explainable reserve and a controlled sweep recommendation.</p>
        </div>
        <div class="steps">
          <article class="step">
            <span class="step-no">01 / ANTICIPATE</span>
            <h3>See the next wave.</h3>
            <p>Forecast hourly net cashflows with the existing SARIMAX pipeline. See uncertainty alongside the expected path.</p>
          </article>
          <article class="step">
            <span class="step-no">02 / PROTECT</span>
            <h3>Give cash breathing room.</h3>
            <p>Hold a reserve for the worst planned drawdown until the vault unlocks. Stress-test the decision before you act.</p>
          </article>
          <article class="step">
            <span class="step-no">03 / ALLOCATE</span>
            <h3>Make idle cash useful.</h3>
            <p>Simulate a surplus sweep, track its maturity, and inspect every movement in the audit ledger.</p>
          </article>
        </div>
      </section>
    </main>
    <footer class="landing-footer">
      <span>© 2026 Reserve Juggler · Treasury intelligence simulation</span>
      <span>Forecasts estimate risk. They do not guarantee payouts.<br>Bank connectivity and production execution are not enabled.</span>
    </footer>
  </div>`;
}

function shell(page, content) {
  const currentItem = nav.find(item => item[0] === page);
  const title = currentItem?.[2] || 'Workspace';
  return `<div class="workspace">
    <aside class="sidebar" id="sidebar">
      <div class="sidebar-header">
        ${brand()}
      </div>
      <div class="sidebar-quick-status">
        <div class="status-chip"><span class="chip-dot"></span> INR Treasury Simulation</div>
        <div class="status-currency">Base: ₹ (INR) · 72h Horizon</div>
      </div>
      <nav class="side-nav" aria-label="Treasury navigation">
        ${navGroups.map(group => `
          <div class="nav-section">
            <div class="nav-label">${group.title}</div>
            <div class="nav-links">
              ${group.items.map(([id, i, label, tag]) => `
                <a href="#${id}" class="nav-link ${id === page ? 'active' : ''}" ${id === page ? 'aria-current="page"' : ''}>
                  <span class="nav-link-left">
                    ${icon(i)}
                    <span class="nav-link-label">${label}</span>
                  </span>
                  ${tag ? `<span class="nav-badge ${tag === 'Demo' ? 'live' : ''}">${tag}</span>` : ''}
                </a>
              `).join('')}
            </div>
          </div>
        `).join('')}
      </nav>
      <div class="sidebar-bottom">
        <div class="sandbox-card">
          <div class="sandbox-header">
            <strong>${iconInlineDot()} Local Sandbox</strong>
            <span class="sandbox-pill">Active</span>
          </div>
          <p>Forecast-aware Indian treasury. All balances and operations are simulated.</p>
        </div>
        <div class="user">
          <div class="avatar">TO</div>
          <div class="user-meta">
            <b>Treasury Operator</b>
            <span>Institutional Terminal · INR</span>
          </div>
        </div>
      </div>
    </aside>
    <div class="work-area">
      <header class="topbar">
        <div class="breadcrumb">
          <button class="mobile-menu" data-action="menu" aria-label="Toggle navigation" aria-expanded="false">${icon('menu')}</button>
          <span class="bc-root">Reserve Juggler</span>
          <span class="bc-sep">/</span>
          <span class="bc-current">${title}</span>
        </div>
        <div class="topbar-right">
          <div class="topbar-status-pill">
            <span class="pulse-indicator"></span>
            <span>Simulated Engine</span>
          </div>
          <span class="topbar-date">${state ? date(state.as_of, true) + ' IST' : 'Syncing state...'}</span>
          ${timer ? '<button class="btn secondary small" data-action="timer" aria-label="Pause continuous simulation">⏸ Pause 60s</button>' : '<button class="btn secondary small" data-action="advance" data-mutate title="Simulate 1 hour ahead">'+icon('play')+' Advance 1h</button>'}
          <button class="btn ghost small" data-action="refresh" aria-label="Refresh workspace" title="Refresh simulated state">${icon('refresh')}</button>
        </div>
      </header>
      <main id="main" class="main-content">
        <div class="content-container">
          ${content}
        </div>
        <footer class="workspace-foot">
          <div class="foot-left">
            <span>RESERVE JUGGLER</span>
            <span class="muted">/</span>
            <span>Intelligent Treasury & Liquidity Optimization</span>
          </div>
          <div class="foot-right">
            <span>All amounts in INR (₹) · Times in IST (UTC+05:30) · Operational sandbox</span>
          </div>
        </footer>
      </main>
    </div>
  </div>`;
}

function iconInlineDot() {
  return '<span aria-hidden="true">◉</span>';
}

function heading(eyebrow, title, description, actions = '') {
  return `<div class="page-heading">
    <div class="page-heading-content">
      <div class="eyebrow">${eyebrow}</div>
      <h1 class="page-title">${title}</h1>
      <p class="page-description">${description}</p>
    </div>
    ${actions ? `<div class="heading-actions">${actions}</div>` : ''}
  </div>`;
}

function metric(label, value, note, i, positive = false) {
  return `<article class="metric">
    <div class="metric-top">
      <span class="metric-label">${label}</span>
      <span class="metric-icon-wrap">${icon(i)}</span>
    </div>
    <div class="metric-value">${value}</div>
    <div class="metric-note ${positive ? 'positive' : ''}">${note}</div>
  </article>`;
}

function chart(rows, floor, id = 'main-chart') {
  const width = 740,
    height = 260,
    left = 57,
    right = 20,
    top = 22,
    bottom = 40;
  const values = rows.flatMap(row => [row.balance, row.lower_balance, row.upper_balance]);
  let min = Math.min(floor, ...values),
    max = Math.max(floor, ...values);
  const pad = Math.max((max - min) * .13, 1e6);
  min -= pad;
  max += pad;
  const x = i => left + i * (width - left - right) / Math.max(1, rows.length - 1);
  const y = v => top + (max - v) / (max - min) * (height - top - bottom);
  const line = key => rows.map((r, i) => `${i?'L':'M'}${x(i).toFixed(1)},${y(r[key]).toFixed(1)}`)
    .join(' ');
  const area = line('upper_balance') + ' ' + [...rows].reverse().map((r, j) =>
    `L${x(rows.length-1-j).toFixed(1)},${y(r.lower_balance).toFixed(1)}`).join(' ') + ' Z';
  const ticks = Array.from({
    length: 5
  }, (_, i) => min + (max - min) * i / 4);
  return `<div class="chart" id="${id}"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Projected cash balance with accumulated lower and upper planning envelopes. Dashed line is the policy minimum. The envelope is not a path confidence interval."><title>Projected available cash in INR</title>${ticks.map(v=>`<line class="grid-line" x1="${left}" y1="${y(v)}" x2="${width-right}" y2="${y(v)}"/><text text-anchor="end" x="${left-12}" y="${y(v)+3}">${compact(v)}</text>`).join('')}<path class="area" d="${area}"/><line class="threshold" x1="${left}" y1="${y(floor)}" x2="${width-right}" y2="${y(floor)}"/><path class="balance-line" d="${line('balance')}"/>${rows.map((row,i)=>`<rect class="hit" data-chart-tip="${escape(date(row.timestamp)+' IST · expected '+compact(row.balance)+' · lower plan '+compact(row.lower_balance))}" tabindex="0" aria-label="${escape(date(row.timestamp)+', expected '+money(row.balance)+', lower planning envelope '+money(row.lower_balance))}" x="${x(i)-6}" y="${top}" width="12" height="${height-top-bottom}"/>`).join('')}${[0,Math.floor(rows.length/4),Math.floor(rows.length/2),Math.floor(rows.length*.75),rows.length-1].map(i=>`<text text-anchor="middle" x="${x(i)}" y="${height-15}">${hour(rows[i].timestamp)}</text>`).join('')}</svg><div class="chart-tooltip" aria-live="polite">Hover or focus a point to inspect the forecast · IST</div></div><div class="chart-legend"><span><i class="legend-line"></i>Expected balance</span><span><i class="legend-area"></i>Planning envelope</span><span><i class="legend-floor"></i>Policy minimum</span></div>`;
}

function chartPanel() {
  return `<section class="panel"><div class="panel-header"><div><h2>Your liquidity, looking ahead</h2><p>Net-flow balance only · see Overview for timed obligations and maturities</p></div><div class="segmented" aria-label="Forecast horizon">${[1,6,24,48,72].map(h=>`<button data-horizon="${h}" class="${horizon===h?'selected':''}" aria-pressed="${horizon===h}">${h}h</button>`).join('')}</div></div>${chart(state.forecast.slice(0,horizon),state.policy.minimum_buffer)}<div class="chart-footer">${icon('info')}${state.policy.confidence}% pointwise intervals accumulated as a planning envelope; not a payout guarantee.</div></section>`;
}

function decision() {
  const p = state.plan;
  return `<section class="panel decision"><div class="panel-header"><div class="eyebrow">The next best move</div>${icon(p.shortfall?'shield':'arrow')}</div><div class="panel-content"><div class="decision-amount">${compact(p.shortfall||p.sweep)}</div><p>${p.shortfall?'Additional liquidity needed. Keep cash in the buffer; the planning reserve is not fully covered.':'Available to put to work. The planned reserve stays in your cash buffer.'}</p><div class="decision-breakdown"><div><span>Retain in cash</span><strong>${compact(p.retained)}</strong></div><div><span>Vault lock period</span><strong>${state.policy.lock_hours} hours</strong></div><div><span>Additional daily yield</span><strong>${money(p.daily_yield,2)}</strong></div></div><button class="btn" data-action="review-sweep" ${p.sweep<.01?'disabled':''}>${p.sweep<.01?'No eligible surplus':'Review simulated sweep'} ${icon('arrow')}</button><div class="decision-foot">${icon('lock')} Server-checked reserve · Simulated transfer</div></div></section>`;
}

function allocation() {
  const total = state.cash + state.vault,
    ratio = total > 0 ? Math.max(0, Math.min(100, state.vault / total * 100)) : 0;
  return `<section class="panel"><div class="panel-header"><h2>Every rupee accounted for</h2><span class="badge neutral">INR</span></div><div class="allocation-top"><svg class="allocation-ring" viewBox="0 0 110 110" role="img" aria-label="${ratio.toFixed(1)} percent of total balance in the yield vault"><circle class="ring-bg" cx="55" cy="55" r="45"/><circle class="ring-fill" cx="55" cy="55" r="45" stroke-dasharray="${ratio*2.8274} 282.74"/><text x="55" y="54" text-anchor="middle">${ratio.toFixed(0)}%</text><text class="ring-caption" x="55" y="69" text-anchor="middle">IN THE VAULT</text></svg><div class="allocation-key"><div><i class="dot"></i><p>Yield vault<strong>${money(state.vault)}</strong></p></div><div><i class="dot pale"></i><p>Available cash<strong>${money(state.cash)}</strong></p></div></div></div><div class="allocation-note">Total balance ${money(total)} · Existing demo vault vault excluded from spendable cash.</div></section>`;
}

function activityRow(r) {
  return `<div class="activity-row"><div class="activity-symbol">${icon(r.type==='Sweep'?'arrow':r.type==='Maturity'?'refresh':'activity')}</div><div class="activity-info"><strong>${escape(r.type)}</strong><p>${date(r.timestamp)} IST · ${escape(r.id)}</p></div><div class="activity-amount">${money(r.amount)}<span>Simulated</span></div></div>`;
}

function recent() {
  return `<section class="panel"><div class="panel-header"><h2>A clear trail of decisions</h2><a class="text-link" href="#activity">View activity ${icon('arrow')}</a></div>${state.ledger.length?`<div class="activity-list">${state.ledger.slice(0,3).map(activityRow).join('')}</div>`:`<div class="empty">${icon('activity')}<h3>Your first decision starts here.</h3><p>Review a sweep or advance the simulation. Each action will appear in this ledger.</p><button class="text-link" data-action="advance" data-mutate>Simulate the next hour ${icon('arrow')}</button></div>`}</section>`;
}

function overview() {
  return heading('Your treasury, in balance', 'Liquidity at a glance.',
      'A clearer view of your cash. A deliberate next move.',
      `<a class="btn secondary" href="/api/export">${icon('download')} Export forecast</a><button class="btn" data-action="advance" data-mutate>${icon('play')} Simulate next hour</button>`
    ) +
    `<div class="notice"><span>${icon('info')}${escape(state.source)} · As of ${date(state.as_of)} IST</span><a href="#data">Manage data ${'↗'}</a></div><div class="metrics">${metric('Available cash',compact(state.cash),'Ready for customer payouts','wallet')}${metric('Required reserve',compact(state.plan.required),`${state.policy.lock_hours}h lock · ${state.policy.confidence}% pointwise bounds`,'shield')}${metric('Earning in the vault',compact(state.vault),`${state.policy.annual_yield.toFixed(2)}% assumed annual yield`,'vault')}${metric('Estimated daily yield',money(state.daily_vault_yield),`On current vault principal · not accrued`,'chart',true)}</div><div class="primary-grid">${chartPanel()}${decision()}</div><div class="lower-grid">${allocation()}${recent()}</div>`;
}

function forecastPage() {
  return heading('Forecast intelligence', 'See the next wave.',
      'Hourly net cashflow forecasts with uncertainty kept in view.',
      `<a class="btn secondary" href="/api/export">${icon('download')} Export 72-hour forecast</a>`
    ) +
    `<div class="primary-grid">${chartPanel()}<aside class="explainer"><div class="eyebrow">Model transparency</div><h2 class="subsection">${escape(state.model)}</h2><p>Fitted to the latest ${Math.min(state.history_count,672)} hourly net cashflows, with a 24-hour seasonal cycle.</p><hr><p><strong>${number(state.history_count)}</strong> observations available<br><strong>${money(state.baseline_mae)}</strong> seasonal-naive holdout MAE<br><strong>${state.policy.confidence}%</strong> pointwise prediction interval</p><p class="subsection">MAE is the previous-day baseline’s mean absolute error over the final seven days. It is not an accuracy score for this fitted forecast.</p></aside></div><section class="panel"><div class="panel-header"><div><h2>The numbers behind the curve</h2><p>Deposits and withdrawals use independent seasonal-naive estimates. Net SARIMAX values drive planning; they may differ from the gross estimate difference. Balances are before new sweeps.</p></div><span class="badge neutral">Next ${horizon} hours</span></div><div class="table-wrap subsection"><table><thead><tr><th>Time · IST</th><th>Forecast deposits</th><th>Forecast withdrawals</th><th>Expected net flow</th><th>Expected balance</th><th>Lower plan</th><th>Buffer status</th></tr></thead><tbody>${state.forecast.slice(0,horizon).map((r,i)=>`<tr><td>${date(r.timestamp)}</td><td>${money(state.gross_forecast.rows[i].deposits)}</td><td>${money(state.gross_forecast.rows[i].withdrawals)}</td><td class="${r.mean-r.withdrawals*state.policy.withdrawal_stress/100<0?'negative':'positive'}">${money(r.mean-r.withdrawals*state.policy.withdrawal_stress/100)}</td><td>${money(r.balance)}</td><td>${money(r.lower_balance)}</td><td><span class="badge ${r.lower_balance<state.policy.minimum_buffer?'warning':''}">${r.lower_balance<state.policy.minimum_buffer?'Below minimum':'Above minimum'}</span></td></tr>`).join('')}</tbody></table></div></section><details class="panel model-details"><summary>How to read this forecast</summary><p>SARIMAX models net deposits less withdrawals. If fitting fails or does not converge, the existing seasonal-naive fallback repeats the last 24-hour cycle and labels the result. Gross withdrawals for stress testing are averaged by hour over the last 14 days. The chart accumulates individual lower and upper bounds; those curves are conservative planning envelopes, not statistically calibrated path confidence intervals. Unseen events and within-hour peaks remain outside this model.</p></details>`;
}

function policyFields(p, scenarioMode = false) {
  return `<div class="form-grid"><div class="form-field"><label for="minimum_buffer">Minimum cash buffer · INR</label><input id="minimum_buffer" name="minimum_buffer" type="number" min="0" max="10000000000" step="1000" value="${p.minimum_buffer}" required><small>The operational floor, before forecast drawdown.</small></div><div class="form-field"><label for="confidence">Pointwise confidence level</label><select id="confidence" name="confidence">${[90,95,99].map(v=>`<option ${p.confidence===v?'selected':''} value="${v}">${v}%</option>`).join('')}</select><small>Higher confidence widens the planning reserve.</small></div><div class="form-field"><label for="lock_hours">Vault lock period · hours</label><input id="lock_hours" name="lock_hours" type="number" min="1" max="72" step="1" value="${p.lock_hours}" required><small>New sweeps cannot return before this period ends.</small></div><div class="form-field"><label for="annual_yield">Assumed annual yield · %</label><input id="annual_yield" name="annual_yield" type="number" min="0" max="20" step="0.01" value="${p.annual_yield}" required><small>Simple interest on an actual/365 basis.</small></div><div class="form-field full-width"><label for="withdrawal_stress">Additional withdrawals · %</label><input id="withdrawal_stress" name="withdrawal_stress" type="number" min="0" max="100" step="1" value="${p.withdrawal_stress}" required><small>Applied to the forecast gross withdrawal profile every hour.</small></div>${scenarioMode?'':`<label class="checkbox full-width"><input name="auto_sweep" type="checkbox" ${p.auto_sweep?'checked':''}>Automatically sweep eligible surplus after each simulated hour</label>`}</div>`;
}

function formPolicy(form) {
  const d = new FormData(form);
  return {
    ...state.policy,
    ...Object.fromEntries(['minimum_buffer', 'confidence', 'lock_hours', 'annual_yield',
      'withdrawal_stress'
    ].map(k => [k, Number(d.get(k))])),
    auto_sweep: form.id === 'policy-form' ? d.has('auto_sweep') : state.policy.auto_sweep
  };
}

function policyPage() {
  return heading('Your guardrails', 'A reserve, with a reason.',
      'Set the rules that every simulated allocation must respect.') +
    `<div class="content-grid"><section class="panel"><div class="panel-header"><h2>Reserve & yield policy</h2><span class="badge neutral">Revision ${state.revision}</span></div><form id="policy-form" class="panel-content">${policyFields(state.policy)}<div class="form-actions"><button class="btn" type="submit" data-mutate>Save policy ${icon('check')}</button><p>Recalculates recommendations. Existing locks keep their original terms.</p></div></form></section><aside class="explainer"><div class="eyebrow">Decision logic</div><h2 class="subsection">Protect the lock window.</h2><div class="formula">Required reserve =<br>minimum cash buffer<br>+ worst planned drawdown</div><p>The engine accumulates lower-bound net cashflows over the lock period, including your withdrawal stress. It holds enough to cover the largest cumulative drawdown.</p><hr><p>Eligible sweep = available cash − required reserve, floored at zero. Locked vault balances are never counted as spendable cash.</p><hr><p>Automatic sweeps run after each simulated hour. Use Advance 1 hour on the overview to process the next simulated hour.</p></aside></div><section class="panel model-details"><h2>Sandbox controls</h2><p>Resetting removes this workspace’s imported data, policy changes, simulated balances, and ledger. The original synthetic dataset and opening balances are restored.</p><button class="btn danger small subsection" data-action="reset">Reset sandbox</button></section>`;
}

function scenariosPage() {
  return heading('Prepare for the unexpected', 'What if the outflows surge?',
      'Test a proposed policy against the same forecast. Your saved policy stays unchanged.') +
    `<div class="content-grid"><section class="panel"><div class="panel-header"><div><h2>Build a stress scenario</h2><p>Start with a preset or set your own assumptions.</p></div></div><form class="panel-content" id="scenario-form"><div class="presets"><button type="button" class="btn secondary small" data-preset="0">Normal day · +0%</button><button type="button" class="btn secondary small" data-preset="15">Payday · +15%</button><button type="button" class="btn secondary small" data-preset="35">Shopping surge · +35%</button></div>${policyFields(scenario?.policy||state.policy,true)}<div class="form-actions"><button type="submit" class="btn" data-mutate>Run scenario ${icon('arrow')}</button><p>Presets are hypothetical stress assumptions.</p></div></form></section><aside class="explainer"><div class="eyebrow">Simulation controls</div><h2 class="subsection">Watch the reserve respond.</h2><p>Advance the sandbox clock to realize a simulated hourly cashflow, release matured sweeps, and reevaluate the reserve.</p><div class="form-actions"><button class="btn small" data-action="advance" data-mutate>${icon('play')} Advance 1 hour</button></div><div class="form-actions"><button class="btn secondary small" data-action="timer">${icon(timer?'pause':'clock')}${timer?'Pause simulation':'Start continuous simulation'}</button></div><p class="subsection">${timer?'Running: one simulated hour every 60 seconds while this tab is open.':'Continuous mode runs one simulated hour every 60 seconds while this tab is open.'} Auto-sweep is <strong>${state.policy.auto_sweep?'enabled':'disabled'}</strong> in the saved policy.</p><hr><p>Each new observation is generated for the sandbox. It is not a live bank feed. A shortfall halts automatic sweeping and remains visible in the ledger.</p></aside></div><div id="scenario-results" class="scenario-results">${scenario?scenarioResults():''}</div>`;
}

function scenarioResults() {
  const p = scenario.plan;
  return `<section class="panel"><div class="panel-header"><h2>Scenario result</h2><span class="badge ${p.shortfall?'warning':''}">${p.shortfall?'Additional liquidity needed':'Reserve covered in this scenario'}</span></div><div class="panel-content"><div class="scenario-metrics"><div><span>Required reserve</span><strong>${compact(p.required)}</strong></div><div><span>Eligible sweep</span><strong>${compact(p.sweep)}</strong></div><div><span>Funding gap</span><strong>${compact(p.shortfall)}</strong></div></div><p class="muted">${compact(p.required-state.plan.required)} change in required reserve versus saved policy. This is a hypothetical plan, not a saved policy or executed sweep.</p></div>${chart(scenario.forecast.slice(0,scenario.policy.lock_hours),scenario.policy.minimum_buffer,'scenario-chart')}</section>`;
}

function filteredLedger() {
  const matches = state.ledger.filter(r => (ledgerType === 'All' || r.type === ledgerType) &&
    `${r.id} ${r.type} ${r.description}`.toLowerCase().includes(ledgerQuery.toLowerCase()));
  return ledgerOrder === 'oldest' ? matches.reverse() : matches;
}

function ledgerTable() {
  const rows = filteredLedger(),
    pages = Math.max(1, Math.ceil(rows.length / 10));
  ledgerPage = Math.min(ledgerPage, pages);
  return `${rows.length?`<div class="table-wrap"><table><thead><tr><th>Reference / time · IST</th><th>Movement</th><th>Amount · INR</th><th>Status</th><th>Details</th></tr></thead><tbody>${rows.slice((ledgerPage-1)*10,ledgerPage*10).map(r=>`<tr><td><span class="mono">${escape(r.id)}</span><p class="muted">${date(r.timestamp)}</p></td><td>${escape(r.type)}</td><td>${money(r.amount,2)}</td><td><span class="badge neutral">Simulated</span></td><td><button class="text-link" data-detail="${escape(r.id)}" aria-label="View ${escape(r.id)} details">View ${icon('arrow')}</button></td></tr>`).join('')}</tbody></table></div>`:`<div class="empty">${icon('activity')}<h3>${state.ledger.length?'No matching movements.':'A clean start.'}</h3><p>${state.ledger.length?'Try a different search or movement type.':'Your simulated sweeps, cashflows, maturities, and policy changes will appear here.'}</p></div>`}<div class="pagination"><span>${rows.length} matching movements</span><div><button class="btn secondary small" data-page="-1" ${ledgerPage<=1?'disabled':''} aria-label="Previous page">←</button><span>${ledgerPage} / ${pages}</span><button class="btn secondary small" data-page="1" ${ledgerPage>=pages?'disabled':''} aria-label="Next page">→</button></div></div>`;
}

function activityPage() {
  return heading('An accountable treasury', 'Every movement. In view.',
      'A persistent record of the decisions and cashflows in this sandbox.',
      `<button class="btn secondary" data-action="export-ledger">${icon('download')} Export ledger</button>`
    ) +
    `<section class="panel"><div class="table-tools"><input type="search" id="ledger-search" aria-label="Search activity" placeholder="Search reference, type, or description…" value="${escape(ledgerQuery)}"><select id="ledger-type" aria-label="Filter movement type">${['All','Failed sweep','Investment','Fee','Decision','Scheduled event','Sweep','Cashflow','Maturity','Interest','Shortfall','Policy','Import'].map(v=>`<option ${ledgerType===v?'selected':''}>${v}</option>`).join('')}</select><select id="ledger-order" aria-label="Sort activity"><option value="newest" ${ledgerOrder==='newest'?'selected':''}>Newest first</option><option value="oldest" ${ledgerOrder==='oldest'?'selected':''}>Oldest first</option></select></div><div id="ledger-table">${ledgerTable()}</div></section><section class="panel model-details"><h2>Locked sweep principal</h2>${state.tranches.length?`<div class="table-wrap subsection"><table><thead><tr><th>Principal</th><th>Matures · IST</th><th>Contracted annual rate</th></tr></thead><tbody>${state.tranches.map(t=>`<tr><td>${money(t.amount,2)}</td><td>${date(t.matures,true)}</td><td>${t.annual_yield}%</td></tr>`).join('')}</tbody></table></div>`:'<p>No new sweeps are currently locked.</p>'}<p>The initial demo vault vault is an illustrative existing holding with no redemption schedule. New sweep tranches return to cash only at maturity. Credited interest to date: ${money(state.earned,2)}.</p></section>`;
}

function dataPage() {
  return heading('Start with good inputs', 'Know what’s flowing in.',
      'Bring hourly cashflows into the forecasting engine, or explore the synthetic sample.',
      `<a class="btn secondary" href="/api/template">${icon('download')} Download sample CSV</a>`) +
    `<div class="content-grid"><section class="panel"><div class="panel-header"><h2>Cashflow data source</h2><span class="badge neutral">Hourly · INR</span></div><div class="panel-content"><form id="import-form"><div class="upload-zone">${icon('upload')}<h3>A clearer forecast starts here.</h3><p>Import a CSV of hourly deposits and withdrawals.<br>168–5,000 rows · INR · 1 MB maximum</p><input type="file" id="csv-file" accept=".csv,text/csv" aria-label="Choose hourly cashflow CSV" required></div><div class="form-actions"><button class="btn" type="submit" data-mutate>Validate & import ${icon('arrow')}</button><p>Replaces this sandbox’s history. Balances remain simulated.</p></div></form><dl class="data-facts"><div><dt>Current source</dt><dd>${escape(state.source)}</dd></div><div><dt>Observations</dt><dd>${number(state.history_count)} hours</dd></div><div><dt>Latest observation</dt><dd>${date(state.as_of,true)} IST</dd></div><div><dt>Bank connection</dt><dd>Not connected</dd></div></dl></div></section><aside class="explainer"><div class="eyebrow">Input contract</div><h2 class="subsection">Three columns. No ambiguity.</h2><pre class="code-sample">timestamp,deposits,withdrawals\n2026-10-01T00:00:00Z,10000000,9800000\n2026-10-01T01:00:00Z,10200000,9900000</pre><ol><li>Use consecutive, sorted hourly timestamps. Include an explicit offset (+05:30 for IST, or Z). Offset-free timestamps are rejected.</li><li>Deposits and withdrawals are separate, nonnegative INR amounts.</li><li>Missing, duplicate, nonfinite, or irregular records are rejected. No silent filling.</li></ol><hr><p>Reset the sandbox before importing if sweep tranches are locked. Import disables auto-sweep so the new forecast can be reviewed first.</p></aside></div><details class="panel model-details"><summary>What is connected, and what is simulated?</summary><p>The frontend calls the local Python API and the existing SARIMAX forecasting pipeline. A SQLite database persists your local session. Starting balances, yield, and transactions are simulated. Importing real observations does not connect a bank or establish real account balances. No authentication provider, payment rail, or production scheduler is configured.</p></details>`;
}

function render() {
  const page = current();
  if (page === 'home' || page === 'method') {
    app.innerHTML = landing();
    return;
  }
  if (!nav.some(n => n[0] === page)) {
    location.hash = 'overview';
    return;
  }
  if (!state) {
    app.innerHTML = shell(page, loadError ?
      `<div class="error-banner"><p>${escape(loadError)}</p><button class="btn secondary" data-action="retry">Retry connection</button></div>` :
      `<div class="loading-page"><div class="spinner"></div><h2>Finding the right balance.</h2><p>Fitting the hourly model and preparing your treasury workspace…</p></div>`
    );
    if (!loading && !loadError) load();
    return;
  }
  const pages = {
    overview: () => planningOverview(state, planningHelpers),
    investments: () => investmentPage(state, planningHelpers),
    events: () => eventPage(state, planningHelpers),
    decisions: () => decisionPage(state, planningHelpers),
    forecast: forecastPage,
    scenarios: () => stressPage(state, planningHelpers),
    activity: activityPage,
    policy: policyPage,
    data: () => dataPage() + demoSettings(state, planningHelpers)
  };
  app.innerHTML = shell(page, pages[page]());
  if (busy) document.querySelectorAll('[data-mutate]').forEach(b => b.disabled = true);
  document.title = `${nav.find(n=>n[0]===page)[2]} · Reserve Juggler`;
}

function showDialog(html) {
  lastFocus = document.activeElement;
  dialog.innerHTML = html;
  dialog.showModal();
}

function closeDialog() {
  dialog.close();
  lastFocus?.focus();
}

function reviewSweep() {
  const p = state.plan;
  showDialog(
    `<div class="eyebrow">Review allocation</div><h2 id="dialog-title">Put the surplus to work.</h2><p>A simulated transfer from your cash buffer into a locked yield vault.</p><div class="dialog-amount">${money(p.sweep,2)}</div><dl><dt>Cash retained</dt><dd>${money(p.retained,2)}</dd><dt>Required reserve</dt><dd>${money(p.required,2)}</dd><dt>Lock period</dt><dd>${state.policy.lock_hours} hours</dd><dt>Assumed annual yield</dt><dd>${state.policy.annual_yield}%</dd></dl><p>Locked principal cannot fund payouts before maturity. The server rechecks the reserve and workspace revision before saving.</p><form id="sweep-form"><div class="dialog-actions"><button type="button" class="btn secondary" data-action="close-dialog">Cancel</button><button type="submit" class="btn">Simulate sweep ${icon('arrow')}</button></div><div class="dialog-error" role="alert"></div></form>`
  );
}

function stopTimer() {
  if (timer) clearInterval(timer);
  timer = null;
}

function downloadLedger() {
  const rows = [
    ['Reference', 'Timestamp IST', 'Type', 'Amount INR', 'Description', 'Status'], ...
    filteredLedger().map(r => [r.id, new Date(new Date(r.timestamp).getTime() + 19800000).toISOString().replace('Z', '+05:30'), r.type, r.amount, r.description, r.status])
  ];
  const csv = rows.map(row => row.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(','))
    .join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], {
    type: 'text/csv;charset=utf-8'
  }));
  const a = document.createElement('a');
  a.href = url;
  a.download = 'reserve-juggler-ledger.csv';
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
document.addEventListener('click', async event => {
  const scroll = event.target.closest('[data-scroll]');
  if (scroll) {
    event.preventDefault();
    $('#method')?.scrollIntoView({
      behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'
    });
    return;
  }
  const horizonButton = event.target.closest('[data-horizon]');
  if (horizonButton) {
    horizon = Number(horizonButton.dataset.horizon);
    render();
    return;
  }
  const preset = event.target.closest('[data-preset]');
  if (preset) {
    $('#withdrawal_stress').value = preset.dataset.preset;
    $('#scenario-results').innerHTML = '';
    scenario = null;
    toast(
      `Withdrawal stress set to +${preset.dataset.preset}%. Run the scenario to compare.`);
    return;
  }
  const pageButton = event.target.closest('[data-page]');
  if (pageButton) {
    ledgerPage += Number(pageButton.dataset.page);
    $('#ledger-table').innerHTML = ledgerTable();
    return;
  }
  const detail = event.target.closest('[data-detail]');
  if (detail) {
    const r = state.ledger.find(r => r.id === detail.dataset.detail);
    showDialog(
      `<div class="eyebrow">Simulation ledger</div><h2 id="dialog-title">${escape(r.type)}</h2><p>${escape(r.description)}</p><div class="dialog-amount">${money(r.amount,2)}</div><dl><dt>Reference</dt><dd>${escape(r.id)}</dd><dt>Timestamp · IST</dt><dd>${date(r.timestamp)}</dd><dt>Status</dt><dd>Simulated</dd></dl><div class="dialog-actions"><button class="btn" data-action="close-dialog">Close</button></div>`
    );
    return;
  }
  const action = event.target.closest('[data-action]')?.dataset.action;
  if (action === 'menu') {
    const open = $('#sidebar').classList.toggle('open');
    $('[data-action="menu"]').setAttribute('aria-expanded', String(open));
  }
  if (action === 'close-dialog') closeDialog();
  if (action === 'retry') load();
  if (action === 'refresh') {
    if (busy) return;
    await load();
    if (!loadError) toast('Workspace refreshed.');
  }
  if (action === 'review-sweep') reviewSweep();
  if (action === 'advance') {
    if (await mutate('advance')) toast(
      'One simulated hour processed. Reserve and ledger updated.');
  }
  if (action === 'export-ledger') downloadLedger();
  if (action === 'timer') {
    if (timer) {
      stopTimer();
      toast('Continuous simulation paused.');
    } else {
      timer = setInterval(async () => {
        if (busy || dialog.open || document.hidden || document.activeElement?.closest(
            'form')) return;
        if (!await mutate('advance')) {
          stopTimer();
          render();
        }
      }, 60000);
      toast(
        'Simulation started. One hour will advance every 60 seconds while this tab is visible.'
      );
    }
    render();
  }
  if (action === 'reset') showDialog(
    `<div class="eyebrow">Sandbox controls</div><h2 id="dialog-title">Start with a clean slate?</h2><p>This clears your local imported history, ledger, policy, and simulated positions, restoring the original demonstration.</p><form id="reset-form"><div class="dialog-actions"><button type="button" class="btn secondary" data-action="close-dialog">Keep workspace</button><button type="submit" class="btn danger">Reset sandbox</button></div></form>`
  );
});
document.addEventListener('submit', async event => {
  const form = event.target;
  if (!['policy-form', 'scenario-form', 'import-form', 'sweep-form', 'reset-form'].includes(
      form.id)) return;
  event.preventDefault();
  if (busy) return;
  if (form.id === 'policy-form') {
    if (await mutate('policy', {
        policy: formPolicy(form)
      })) toast('Policy saved. Recommendations recalculated.');
  }
  if (form.id === 'scenario-form') {
    setBusy(true);
    try {
      scenario = await api('scenario', {
        policy: formPolicy(form)
      });
      $('#scenario-results').innerHTML = scenarioResults();
      $('#scenario-results').scrollIntoView({
        behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
        block: 'start'
      });
      toast('Scenario calculated. Saved policy unchanged.');
    } catch (e) {
      toast(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (form.id === 'import-form') {
    const file = $('#csv-file').files[0];
    if (!file) return;
    if (file.size > 1_000_000) {
      toast('Choose a CSV smaller than 1 MB.');
      return;
    }
    const text = await file.text();
    if (await mutate('import', {
        csv: text
      })) {
      stopTimer();
      render();
      toast('Cashflow history validated and imported.');
    }
  }
  if (form.id === 'sweep-form') {
    if (await mutate('sweep')) {
      closeDialog();
      toast('Sweep simulated. Principal is locked until maturity.');
    } else {
      $('.dialog-error', dialog).textContent =
        'The sweep was not saved. Close this review and refresh the workspace before retrying.';
    }
  }
  if (form.id === 'reset-form') {
    if (await mutate('reset')) {
      closeDialog();
      toast('Sandbox restored to its starting state.');
    }
  }
});
document.addEventListener('input', event => {
  if (event.target.id === 'ledger-search') {
    ledgerQuery = event.target.value;
    ledgerPage = 1;
    $('#ledger-table').innerHTML = ledgerTable();
  }
  if (event.target.closest('#scenario-form') && !event.target.matches('[type=submit]')) {
    scenario = null;
    $('#scenario-results').innerHTML = '';
  }
});
document.addEventListener('change', event => {
  if (event.target.id === 'ledger-type') {
    ledgerType = event.target.value;
    ledgerPage = 1;
    $('#ledger-table').innerHTML = ledgerTable();
  }
  if (event.target.id === 'ledger-order') {
    ledgerOrder = event.target.value;
    ledgerPage = 1;
    $('#ledger-table').innerHTML = ledgerTable();
  }
});

function chartTip(event) {
  const target = event.target.closest('[data-chart-tip]');
  if (target) target.closest('.chart').querySelector('.chart-tooltip').textContent = target.dataset
    .chartTip;
}
document.addEventListener('pointerover', chartTip);
document.addEventListener('focusin', chartTip);
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    $('#sidebar')?.classList.remove('open');
    $('[data-action="menu"]')?.setAttribute('aria-expanded', 'false');
  }
});
window.addEventListener('hashchange', () => {
  render();
  window.scrollTo(0, 0);
});
window.addEventListener('beforeunload', stopTimer);
const planningHelpers = {
  money,
  compact,
  date,
  escape,
  icon,
  heading,
  metric
};
bindPlanning({
  getState: () => state,
  mutate,
  api,
  toast,
  showDialog,
  closeDialog,
  helpers: planningHelpers
});
render();
