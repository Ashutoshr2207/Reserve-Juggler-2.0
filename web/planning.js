// Views share one server-calculated plan; the browser never approves principal.
let controls;
let comparison = null;
const riskBadge = (risk) => `<span class="badge ${risk === 'High Risk' ? 'critical' : risk === 'Warning' ? 'warning' : ''}">${risk}</span>`;

function explanation(state, h) {
  const p = state.intelligence,
    c = p.selected;
  return `<section class="panel"><div class="panel-header"><h2>Protect liquidity. Invest the surplus.</h2>${riskBadge(c.risk)}</div><div class="panel-content"><div class="decision-amount">${h.money(c.suggested)}</div><p class="muted">Suggested investment in ${c.name} · illustrative ${c.rate}% annual rate</p><dl class="plan-facts"><div><dt>Available liquid funds</dt><dd>${h.money(state.cash)}</dd></div><div><dt>Safety floor + additional risk buffer</dt><dd>${h.money(p.floor)}</dd></div><div><dt>Protected lock-window drawdown</dt><dd>${h.money(c.required-p.floor)}</dd></div><div><dt>Required reserve</dt><dd>${h.money(c.required)}</dd></div><div><dt>Maximum eligible principal after fee</dt><dd>${h.money(c.eligible)}</dd></div><div><dt>Funds available at maturity · IST</dt><dd>${h.date(c.matures)}</dd></div><div><dt>Estimated gross interest / entry fee</dt><dd>${h.money(c.interest,2)} / ${h.money(c.fee,2)}</dd></div><div><dt>Estimated net earnings for ${c.hours} hours</dt><dd>${h.money(c.net_return,2)}</dd></div></dl><p class="reason-box">${state.decisions?.length?h.escape(state.decisions[0].reason)+'<br>':''}${h.escape(c.reason)} Funds arriving later cannot cover earlier obligations. The full 72-hour path is also checked.</p><p class="reason-box">Best net return: ${h.escape(p.optimized.name)} · ${h.money(p.optimized.suggested)} principal · ${h.money(p.optimized.net_return,2)} net. ${h.escape(p.note)}</p><div class="form-actions"><button class="btn secondary" data-plan="optimize" ${p.optimized.suggested<=0?'disabled':''}>Review optimized sweep</button><button class="btn" data-plan="invest" ${c.suggested<=0?'disabled':''}>Simulate Investment ${h.icon('arrow')}</button><a class="text-link" href="#investments">Compare investment options →</a></div></div></section>`;
}

function cashChart(state, h) {
  const p = state.intelligence;
  const rows = p.timeline;
  const c = p.selected;
  const retained = state.cash - c.suggested - (c.suggested > 0 ? c.fee : 0);
  const projected = rows.map(r => ({...r, balance: r.balance - c.suggested - (c.suggested > 0 ? c.fee : 0) + (new Date(r.timestamp) > new Date(c.matures) ? c.suggested + c.interest : 0)}));
  const w = 900,
    top = 24,
    bottom = 230,
    left = 65;
  const minimum = Math.min(p.floor, retained, ...rows.map(r => r.balance), ...projected.map(r => r.balance));
  const low = minimum - Math.max(1, Math.abs(minimum) * 0.1);
  const high = Math.max(state.cash, ...rows.map(r => r.balance)) * 1.1;
  const y = v => bottom - (v - low) / Math.max(1, high - low) * (bottom - top);
  const start = new Date(state.as_of).getTime();
  const x = t => left + (new Date(t).getTime() - start) / (72 * 3600000) * (w - left - 20);
  const path = `M${left},${y(state.cash)} ` + rows.map(r => `L${x(r.timestamp)},${y(r.balance)}`).join(' ');
  const sweptPath = `M${left},${y(retained)} ` + projected.map(r => `L${x(r.timestamp)},${y(r.balance)}`).join(' ');
  return `<section class="panel"><div class="panel-header"><div><h2>Cash available at each payment time</h2><p>Next 72 hours · forecast with uncertainty allowance · before a new investment</p></div></div><div class="panel-content"><svg class="plan-chart" viewBox="0 0 900 270" role="img" aria-label="Cash position after every timed withdrawal, deposit, merchant receipt, and payment. Future inflows are never netted against earlier payments.">${[0,1,2,3,4].map(i=>{const v=low+(high-low)*i/4;return `<line x1="65" x2="880" y1="${y(v)}" y2="${y(v)}" stroke="#E2E8F0"/><text x="0" y="${y(v)+4}">${h.compact(v)}</text>`;}).join('')}<rect x="65" y="8" width="${Math.min(815, c.hours/72*815)}" height="8" fill="#DDD6FE"/><text x="70" y="29">Proposed ${c.hours}h lock</text><path d="${sweptPath}" fill="none" stroke="#7C3AED" stroke-width="2"/><path d="${path}" fill="none" stroke="#2563EB" stroke-width="2.5"/>${rows.map(r=>`<circle tabindex="0" data-plan-tip="${h.escape(h.date(r.timestamp)+' IST · '+r.label+' · '+h.money(r.flow)+' · balance '+h.money(r.balance))}" aria-label="${h.escape(h.date(r.timestamp)+' IST '+r.label+' '+h.money(r.balance))}" cx="${x(r.timestamp)}" cy="${y(r.balance)}" r="3" fill="#2563EB"><title>${h.escape(h.date(r.timestamp)+' IST · '+r.label+' · '+h.money(r.balance))}</title></circle>`).join('')}<line x1="65" x2="880" y1="${y(p.floor)}" y2="${y(p.floor)}" stroke="#000000" stroke-dasharray="5 4"/>${[0,6,24,48,72].map(i=>`<text x="${65+i/72*815}" y="260" text-anchor="middle">+${i}h</text>`).join('')}</svg><p id="plan-tooltip" class="muted" aria-live="polite">Focus or hover a point for its IST time, payment channel and balance.</p><p class="muted">Blue: cash before sweep · Purple: cash after proposed sweep and maturity · Shaded bar: proposed lock · Dashed black: protected floor. Withdrawals precede receipts at equal timestamps.</p></div><details class="panel-content"><summary>Inspect deposits, withdrawals, settlements and obligations</summary><div class="table-wrap"><table><thead><tr><th>Availability / due · IST</th><th>Type</th><th>Cash movement</th><th>Available after</th><th>Status</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${h.date(r.timestamp)}</td><td>${h.escape(r.label)}</td><td>${h.money(r.flow)}</td><td>${h.money(r.balance)}</td><td>${riskBadge(r.status)}</td></tr>`).join('')}</tbody></table></div></details></section>`;
}

export function planningOverview(state, h) {
  const c = state.intelligence.selected;
  return h.heading('Intelligent Treasury & Liquidity Management', 'Protect the next payment.', 'Know what you have, what you must protect, and what can earn interest.', `<button class="btn secondary" data-action="advance" data-mutate>${h.icon('play')} Advance 1 hour</button><a class="btn" href="#events">Simulate an event</a>`) +
    `<div class="notice"><span>${h.icon('info')}Demo data · ${h.escape(state.source)} · ${h.date(state.as_of)} IST</span><a href="#forecast">SARIMAX analysis ↗</a></div><div class="metrics plan-metrics">${h.metric('Available liquid funds',h.compact(state.cash),'Liquid cash only; vault excluded','wallet')}${h.metric('Required liquidity reserve',h.compact(c.required),'Floor, risk buffer and timed drawdown','shield')}${h.metric('Eligible investment surplus',h.compact(c.eligible),'Maximum principal after entry fee','chart')}${h.metric('Locked sweep principal',h.compact(state.intelligence.locked_principal),'Vault holdings excluded from liquid cash','vault')}${h.metric('Estimated net interest income',h.money(c.net_return,2),`Suggested investment · ${c.hours}h`,'clock')}${h.metric('Projected minimum cash',h.compact(state.intelligence.projected_minimum),'Before new investment; includes uncertainty','wallet')}${h.metric('Liquidity risk',c.risk,`Potential funding gap: ${h.compact(c.shortfall)}`,'shield')}</div><div class="content-grid">${explanation(state,h)}<aside class="explainer"><div class="eyebrow">Why this recommendation?</div><h2 class="subsection">Operational liquidity first.</h2><p class="reason-box">This operational reserve is separate from RBI statutory CRR/SLR. Statutory balances are not included in investable funds. CRR/SLR computation and compliance are not assessed by this demo.</p><p>${h.escape(state.intelligence.method)}.</p><p class="subsection">${h.escape(state.intelligence.note)}</p><hr><p>Safety floor: ${h.money(state.policy.minimum_buffer)}<br>Additional risk buffer: ${h.money(state.intelligence.policy.risk_buffer)}<br>Lock period: ${c.hours} hours<br>Minimum investment: ${h.money(c.minimum)}</p><hr><p>Fees reduce cash immediately. Principal and simple interest return at maturity. Early withdrawals are unavailable in this demonstration.</p><a class="btn secondary subsection" href="#scenarios">Compare stress scenarios →</a></aside></div><div class="subsection">${cashChart(state,h)}</div><div class="subsection">${eventsTable(state,h)}</div>`;
}

export function investmentPage(state, h) {
  const p = state.intelligence;
  return h.heading('Maturity-aware smart sweeping', 'Choose a lock that fits.', 'Every option is checked against the complete timed cashflow path. Rates and fees are illustrative.') + `<section class="panel"><div class="table-wrap"><table><thead><tr><th>Investment</th><th>Minimum</th><th>Annual yield</th><th>Maturity · IST</th><th>Fee / early exit</th><th>Eligible / suggested</th><th>Net return</th><th>Assessment</th></tr></thead><tbody>${p.options.map(o=>`<tr><td>${o.name}${o.id===p.policy.option?' · Selected':''}${o.id===p.optimized.id?' · Best net return':''}</td><td>${h.money(o.minimum)}</td><td>${o.rate}%</td><td>${h.date(o.matures)}<br>${o.hours}h</td><td>${h.money(o.fee)}<br>${o.penalty}</td><td>${h.money(o.eligible)}<br>${h.money(o.suggested)}</td><td>${h.money(o.net_return,2)}</td><td>${riskBadge(o.risk)}</td></tr>`).join('')}</tbody></table></div></section><div class="content-grid subsection"><section class="panel"><div class="panel-header"><h2>Investment planning settings</h2></div><form class="panel-content" id="planning-settings"><div class="form-grid"><div class="form-field"><label for="option">Selected investment</label><select name="option" id="option">${p.options.map(o=>`<option value="${o.id}" ${o.id===p.policy.option?'selected':''}>${o.name} · ${o.hours} hours</option>`).join('')}</select></div><div class="form-field"><label for="risk_buffer">Additional risk buffer · INR</label><input id="risk_buffer" name="risk_buffer" type="number" min="0" max="10000000000" step="0.01" value="${p.policy.risk_buffer}" required></div></div><div class="form-grid subsection">${p.options.map(o=>`<div class="form-field"><label for="rate-${o.id}">${o.name} · illustrative annual %</label><input id="rate-${o.id}" name="rate_${o.id}" type="number" min="0" max="20" step="0.01" value="${o.rate}" required></div>`).join('')}</div><div class="form-actions"><button class="btn" data-mutate>Save & recalculate</button></div></form></section><aside class="explainer"><h2>Returns for the actual duration.</h2><p>Gross interest = principal × annual rate × locked hours ÷ (365 × 24). Net earnings subtract the entry fee. An option is rejected if the minimum is not met, fees erase earnings, or the forecast cannot protect the configured reserve.</p></aside></div><div class="subsection">${explanation(state,h)}</div>`;
}

function eventsTable(state, h) {
  return `<section class="panel"><div class="panel-header"><h2>Upcoming payments & events</h2><a class="text-link" href="#events">Simulate a change →</a></div><div class="table-wrap subsection"><table><thead><tr><th>Event</th><th>Due / available · IST</th><th>Amount</th><th>Status after event</th></tr></thead><tbody>${state.intelligence.events.map(e=>`<tr><td>${h.escape(e.label)}</td><td>${h.date(e.timestamp)}</td><td>${h.money(e.amount)}</td><td>${riskBadge(e.status)}</td></tr>`).join('')||'<tr><td colspan="4">No pending scheduled events.</td></tr>'}</tbody></table></div></section>`;
}

export function eventPage(state, h) {
  return h.heading('Event-triggered recalculation', 'Change the day. See the impact.', 'Scheduled simulation events immediately update the reserve and investment decision.') + `<div class="content-grid"><section class="panel"><div class="panel-header"><h2>Simulate a liquidity event</h2></div><form id="planning-event" class="panel-content"><div class="form-grid"><div class="form-field full-width"><label for="event-kind">Event type</label><select id="event-kind" name="kind"><option value="withdrawal">UPI / ATM withdrawal surge</option><option value="delay">Delay pending merchant receipts</option><option value="payment">RTGS customer payout / NEFT salary batch</option><option value="risk">Forecast risk alert: set additional risk buffer</option><option value="settlement">Merchant settlement receipt</option><option value="deposit">Incoming NEFT / IMPS credit</option></select></div><div class="form-field"><label for="event-amount">Amount · INR (ignored for delays)</label><input id="event-amount" name="amount" type="number" min="0.01" max="10000000000" step="0.01" value="5000000" required></div><div class="form-field"><label for="event-hours">Hours from now / delay duration</label><input id="event-hours" name="hours" type="number" min="0.25" max="48" step="0.25" value="2" required></div></div><div class="form-actions"><button class="btn" data-mutate>Simulate event & recalculate</button></div></form></section><aside class="explainer"><h2>Availability, not expectation.</h2><p>A delayed settlement moves its availability timestamp. A payment is deducted at its due time. Incoming deposits become usable only when they arrive. All events are hypothetical and saved only in this sandbox.</p><hr><a class="text-link" href="#decisions">Inspect decision history →</a></aside></div><div class="subsection">${eventsTable(state,h)}</div><div class="subsection">${explanation(state,h)}</div>`;
}

function comparisonView(result, h) {
  const a = result.baseline.selected,
    b = result.stressed.selected;
  return `<section class="panel subsection"><div class="panel-header"><h2>Baseline vs stressed scenario</h2></div><div class="table-wrap subsection"><table><thead><tr><th>Measure</th><th>Saved baseline</th><th>Hypothetical stress</th><th>Change</th></tr></thead><tbody>${[['Required reserve','required'],['Potential funding gap','shortfall'],['Eligible surplus','eligible'],['Suggested investment','suggested'],['Estimated net earnings','net_return'],['Projected minimum cash','projected_minimum'],['Emergency funding estimate','emergency_funding']].map(([name,key])=>`<tr><td>${name}</td><td>${h.money(a[key],2)}</td><td>${h.money(b[key],2)}</td><td>${h.money(b[key]-a[key],2)}</td></tr>`).join('')}<tr><td>Risk status</td><td>${riskBadge(a.risk)}</td><td>${riskBadge(b.risk)}</td><td>Scenario only</td></tr></tbody></table></div><div class="panel-content reason-box">${h.escape(b.reason)} Withdrawal increases, delayed merchant availability, and additional payouts are processed together in timestamp order. Saved events, cash and policy are unchanged.</div></section>`;
}

export function stressPage(state, h) {
  return h.heading('Stress testing', 'Be ready for a different day.', 'Compare a hypothetical combination of shocks against the same saved baseline.') + `<section class="panel"><div class="panel-header"><h2>Combine stress assumptions</h2></div><form class="panel-content" id="planning-stress"><div class="presets"><button type="button" class="btn secondary small" data-stress="0,0,0,0" data-execution="failure">Investment execution failure</button><button type="button" class="btn secondary small" data-stress="0,0,0,0">Normal operations</button><button type="button" class="btn secondary small" data-stress="0,50,0,0">Withdrawals +50%</button><button type="button" class="btn secondary small" data-stress="50,0,0,0">UPI spike +50%</button><button type="button" class="btn secondary small" data-stress="0,0,12,0">Merchant settlement delay · 12h</button><button type="button" class="btn secondary small" data-stress="0,20,0,70000000">Salary-day NEFT payments</button><button type="button" class="btn secondary small" data-stress="70,15,6,30000000">Festival spending + delay</button></div><div class="form-grid"><div class="form-field"><label for="stress-upi">Extra UPI outflows · %</label><input id="stress-upi" name="upi" type="number" min="0" max="100" value="50" required></div><div class="form-field"><label for="stress-withdrawals">All-channel outflow increase · %</label><input id="stress-withdrawals" name="withdrawals" type="number" min="0" max="100" value="0" required></div><div class="form-field"><label for="stress-delay">Merchant availability delay · hours</label><input id="stress-delay" name="delay" type="number" min="0" max="48" value="0" required></div><div class="form-field"><label for="stress-execution">Hypothetical investment execution</label><select id="stress-execution" name="execution"><option value="success">Success</option><option value="failure">Failure</option><option value="timeout">Timeout before execution</option></select></div><div class="form-field"><label for="stress-payout">Additional payout in 6 hours · INR</label><input id="stress-payout" name="payout" type="number" min="0" max="10000000000" value="0" required></div></div><div class="form-actions"><button class="btn" data-mutate>Compare scenarios</button></div></form></section><section class="panel subsection"><div class="panel-content"><h2>Chronological strategy comparison</h2><p>Replay the last 24 observed hours with hourly rolling seasonal-naive forecasts. Compare fixed reserve, existing forecast reserve, and optimized Reserve Juggler. Balances remain simulated.</p><button type="button" class="btn secondary" data-plan="backtest">Run comparison</button><div id="strategy-results" aria-live="polite"></div></div></section><div id="planning-comparison">${comparison?comparisonView(comparison,h):'<p class="muted subsection">Choose a preset or combine assumptions, then compare.</p>'}</div>`;
}

export function decisionPage(state, h) {
  return h.heading('Explainable investment decisions', 'A reason behind every move.', 'Before and after calculations recorded for simulated events, settings, and investments.') + `<section class="panel"><div class="table-wrap"><table><thead><tr><th>Time · IST / trigger</th><th>Cash position</th><th>Reserve before → after</th><th>Investment before → after</th><th>Reason</th></tr></thead><tbody>${(state.decisions||[]).map(d=>`<tr><td>${h.date(d.timestamp)}<br>${h.escape(d.action)}</td><td>${h.money(d.cash)}</td><td>${h.money(d.before.required)} → ${h.money(d.after.required)}</td><td>${h.money(d.before.suggested)} → ${h.money(d.after.suggested)}</td><td class="decision-reason">${h.escape(d.reason)}</td></tr>`).join('')||'<tr><td colspan="5">No simulated planning decisions yet. Schedule an event or review an investment to start.</td></tr>'}</tbody></table></div></section>`;
}

export function bindPlanning(apiControls) {
  controls = apiControls;
  const inspectPoint = event => {
    const point = event.target.closest('[data-plan-tip]');
    if (point) {
      const label = document.querySelector('#plan-tooltip');
      if (label) label.textContent = point.dataset.planTip;
    }
  };
  document.addEventListener('pointerover', inspectPoint);
  document.addEventListener('focusin', inspectPoint);
  document.addEventListener('click', async event => {
    const backtest = event.target.closest('[data-plan="backtest"]');
    if (backtest) {
      backtest.disabled = true;
      try {
        const report = await controls.api('backtest', {}), h = controls.helpers;
        document.querySelector('#strategy-results').innerHTML = `<p>${h.escape(report.source)} · ${report.hours} hours · ${h.escape(report.model)} forecasts · simulated evaluation</p><div class="table-wrap"><table><thead><tr><th>Strategy</th><th>Net accrued interest</th><th>Idle cash average</th><th>Floor breaches</th><th>Maximum funding gap</th><th>MAE / RMSE</th></tr></thead><tbody>${report.results.map(r=>`<tr><td>${h.escape(r.strategy)}</td><td>${h.money(r.net_interest,2)}</td><td>${h.money(r.average_idle_cash)}</td><td>${r.floor_breaches}</td><td>${h.money(r.maximum_shortfall)}</td><td>${h.money(r.forecast_mae)} / ${h.money(r.forecast_rmse)}</td></tr>`).join('')}</tbody></table></div><p>${report.assumptions.map(h.escape).join(' ')}</p>`;
      } catch (e) { controls.toast(e.message); }
      finally { backtest.disabled = false; }
    }
    const preset = event.target.closest('[data-stress]');
    if (preset) {
      const values = preset.dataset.stress.split(',');
      document.querySelector('#stress-execution').value = preset.dataset.execution || 'success';
      ['upi', 'withdrawals', 'delay', 'payout'].forEach((key, i) => document.querySelector(`#stress-${key}`).value = values[i]);
      document.querySelector('#planning-comparison').innerHTML = '';
      comparison = null;
    }
    if (event.target.closest('[data-plan="invest"], [data-plan="optimize"]')) {
      const optimized = !!event.target.closest('[data-plan="optimize"]');
      const s = controls.getState(),
        c = optimized ? s.intelligence.optimized : s.intelligence.selected,
        h = controls.helpers;
      controls.showDialog(`<h2 id="dialog-title">Review simulated investment</h2><p>${c.name} · ${c.hours} hours · ${c.rate}% illustrative annual yield</p><div class="dialog-amount">${h.money(c.suggested,2)}</div><p>Entry fee ${h.money(c.fee)}. Funds return ${h.date(c.matures)} IST. Estimated net earnings ${h.money(c.net_return,2)}.</p><p class="subsection">${h.escape(c.reason)}</p><form id="planning-invest" data-optimized="${optimized}"><label for="execution">Simulated execution outcome</label><select id="execution" name="execution"><option value="success">Success</option><option value="failure">Execution failure</option><option value="timeout">Timeout before execution</option></select><div class="dialog-actions"><button type="button" class="btn secondary" data-action="close-dialog">Cancel</button><button class="btn" data-mutate>Confirm simulation</button></div></form>`);
    }
  });
  document.addEventListener('input', event => {
    if (event.target.closest('#planning-stress')) {
      comparison = null;
      document.querySelector('#planning-comparison').innerHTML = '';
    }
  });
  document.addEventListener('submit', async event => {
    const form = event.target;
    if (!['planning-settings', 'planning-event', 'planning-stress', 'planning-invest', 'planning-balances'].includes(form.id)) return;
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    if (form.id === 'planning-stress') {
      const button = form.querySelector('button[type="submit"]') || form.querySelector('.form-actions button');
      button.disabled = true;
      try {
        comparison = await controls.api('planning_scenario', {
          stress: Object.fromEntries(Object.entries(data).map(([k, v]) => [k, k === 'execution' ? v : Number(v)]))
        });
        const target = document.querySelector('#planning-comparison');
        if (target) target.innerHTML = comparisonView(comparison, controls.helpers);
      } catch (e) {
        controls.toast(e.message);
      } finally {
        button.disabled = false;
      }
      return;
    }
    const action = form.id === 'planning-invest' && form.dataset.optimized === 'true' ? 'planning_optimize' : form.id === 'planning-settings' ? 'planning_policy' : form.id === 'planning-event' ? 'planning_event' : form.id === 'planning-balances' ? 'planning_balance' : 'planning_invest';
    const payload = form.id === 'planning-settings' ? {
      option: data.option,
      risk_buffer: Number(data.risk_buffer),
      rates: Object.fromEntries(['flex', 'overnight', 'extended'].map(id => [id, Number(data['rate_' + id])]))
    } : form.id === 'planning-event' ? {
      kind: data.kind,
      amount: Number(data.amount),
      hours: Number(data.hours)
    } : form.id === 'planning-balances' ? {
      cash: Number(data.cash),
      vault: Number(data.vault)
    } : {execution: data.execution};
    if (await controls.mutate(action, payload)) {
      comparison = null;
      if (form.id === 'planning-invest') controls.closeDialog();
      controls.toast('Simulation saved. Reserve, recommendation and decision history recalculated.');
    }
  });
}

export function demoSettings(state, h) {
  return `<section class="panel subsection"><div class="panel-header"><h2>Configure demo fund balances · INR</h2></div><form id="planning-balances" class="panel-content"><p class="muted">Synthetic liquid and invested balances only. Funds held for statutory CRR/SLR are outside this operational pool. Changes are blocked while new investments are locked.</p><div class="form-grid subsection"><div class="form-field"><label for="demo-cash">Liquid funds · ₹</label><input id="demo-cash" name="cash" type="number" min="0" max="10000000000" step="0.01" value="${state.cash}" required></div><div class="form-field"><label for="demo-vault">Already invested · ₹</label><input id="demo-vault" name="vault" type="number" min="0" max="10000000000" step="0.01" value="${state.vault}" required></div></div><div class="form-actions"><button class="btn" data-mutate>Save simulated balances</button></div></form></section>`;
}
