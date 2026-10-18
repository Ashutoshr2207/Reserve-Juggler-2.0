import React, { useState } from 'react';
import { useTreasury } from '../../hooks/useTreasury';
import type { BacktestReport, PlanningScenarioResult } from '../../types/treasury';
import { api } from '../../utils/api';
import { money } from '../../utils/formatters';
import { Heading } from '../common/Heading';
import { RiskBadge } from '../common/RiskBadge';

const PRESETS = [
  { name: 'Normal operations', values: [0, 0, 0, 0], execution: 'success' },
  { name: 'Withdrawals +50%', values: [0, 50, 0, 0], execution: 'success' },
  { name: 'UPI spike +50%', values: [50, 0, 0, 0], execution: 'success' },
  { name: 'Merchant settlement delay · 12h', values: [0, 0, 12, 0], execution: 'success' },
  { name: 'Salary-day NEFT payments', values: [0, 20, 0, 70000000], execution: 'success' },
  { name: 'Festival spending + delay', values: [70, 15, 6, 30000000], execution: 'success' },
  { name: 'Investment execution failure', values: [0, 0, 0, 0], execution: 'failure' }
];

export const ScenariosPage: React.FC = () => {
  const { showToast, busy } = useTreasury();
  const [preset, setPreset] = useState('UPI spike +50%');
  const [upi, setUpi] = useState(50);
  const [withdrawals, setWithdrawals] = useState(0);
  const [delay, setDelay] = useState(0);
  const [execution, setExecution] = useState('success');
  const [payout, setPayout] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [comparison, setComparison] = useState<PlanningScenarioResult | null>(null);
  const [backtestRunning, setBacktestRunning] = useState(false);
  const [backtestReport, setBacktestReport] = useState<BacktestReport | null>(null);
  const choosePreset = (name: string) => {
    const p = PRESETS.find(p => p.name === name);
    if (!p) return;
    setPreset(name); setUpi(p.values[0]); setWithdrawals(p.values[1]);
    setDelay(p.values[2]); setPayout(p.values[3]); setExecution(p.execution);
    setComparison(null);
  };
  const custom = () => { setPreset('Custom scenario'); setComparison(null); };
  const compare = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting || busy) return;
    setSubmitting(true);
    try { setComparison(await api<PlanningScenarioResult>('planning_scenario', { stress: { upi, withdrawals, delay, execution, payout } })); }
    catch (err) { showToast((err as Error).message); }
    finally { setSubmitting(false); }
  };
  const backtest = async () => {
    if (backtestRunning) return;
    setBacktestRunning(true);
    try { setBacktestReport(await api<BacktestReport>('backtest', {})); }
    catch (err) { showToast((err as Error).message); }
    finally { setBacktestRunning(false); }
  };
  const measures: Array<[string, keyof PlanningScenarioResult['baseline']['selected']]> = [
    ['Required reserve', 'required'], ['Funding gap', 'shortfall'],
    ['Eligible surplus', 'eligible'], ['Suggested investment', 'suggested'],
    ['Expected net return', 'net_return'], ['Projected minimum cash', 'projected_minimum']
  ];
  const assumptions = [
    withdrawals > 0 ? 'Withdrawals +' + withdrawals + '%' : '',
    upi > 0 ? 'UPI +' + upi + '%' : '',
    delay > 0 ? 'Settlements delayed ' + delay + 'h' : '',
    payout > 0 ? money(payout) + ' extra payout' : '',
    execution !== 'success' ? 'Execution: ' + execution : ''
  ].filter(Boolean).join(' · ');
  return <>
    <Heading title="Scenario lab" description="Test a cashflow shock without changing your saved workspace." />
    <section className="panel">
      <div className="panel-header"><h2>Choose a scenario</h2><span className="badge neutral">Read-only simulation</span></div>
      <form id="planning-stress" className="panel-content" onSubmit={compare}>
        <div className="scenario-choice">
          <div className="form-field"><label htmlFor="scenario-preset">Scenario preset</label>
            <select id="scenario-preset" value={preset} onChange={e => choosePreset(e.target.value)}>
              {PRESETS.map(p => <option key={p.name}>{p.name}</option>)}
              {preset === 'Custom scenario' && <option>Custom scenario</option>}
            </select>
          </div>
          <button className="btn" type="submit" disabled={submitting || busy}>{submitting ? 'Comparing…' : 'Compare scenarios'}</button>
        </div>
        <p className="helper-line">{assumptions || 'No additional stress applied.'}</p>
        <details className="inline-details"><summary>Adjust assumptions</summary>
          <div className="form-grid">
            <div className="form-field"><label htmlFor="stress-upi">Extra UPI outflows · %</label><input id="stress-upi" type="number" min="0" max="100" value={upi} required onChange={e => { setUpi(Number(e.target.value)); custom(); }} /></div>
            <div className="form-field"><label htmlFor="stress-withdrawals">All-channel outflow increase · %</label><input id="stress-withdrawals" type="number" min="0" max="100" value={withdrawals} required onChange={e => { setWithdrawals(Number(e.target.value)); custom(); }} /></div>
            <div className="form-field"><label htmlFor="stress-delay">Merchant availability delay · hours</label><input id="stress-delay" type="number" min="0" max="48" value={delay} required onChange={e => { setDelay(Number(e.target.value)); custom(); }} /></div>
            <div className="form-field"><label htmlFor="stress-execution">Hypothetical investment execution</label><select id="stress-execution" value={execution} onChange={e => { setExecution(e.target.value); custom(); }}><option value="success">Success</option><option value="failure">Failure</option><option value="timeout">Timeout before execution</option></select></div>
            <div className="form-field"><label htmlFor="stress-payout">Additional payout in 6 hours · INR</label><input id="stress-payout" type="number" min="0" max="10000000000" value={payout} required onChange={e => { setPayout(Number(e.target.value)); custom(); }} /></div>
          </div>
        </details>
      </form>
    </section>
    {comparison && <section className="panel" aria-live="polite">
      <div className="panel-header"><h2>Baseline vs stressed scenario</h2><RiskBadge risk={comparison.stressed.selected.risk} /></div>
      <div className="table-wrap"><table><thead><tr><th>Measure</th><th>Saved baseline</th><th>Hypothetical stress</th><th>Change</th></tr></thead>
        <tbody>{measures.map(([label, key]) => {
          const a = Number(comparison.baseline.selected[key]), b = Number(comparison.stressed.selected[key]);
          return <tr key={key}><td>{label}</td><td>{money(a, 2)}</td><td>{money(b, 2)}</td><td>{money(b - a, 2)}</td></tr>;
        })}</tbody>
      </table></div>
      <div className="panel-content"><p>{comparison.stressed.selected.reason}</p><p className="helper-line">Scenario only. Saved balances, events and policy are unchanged.</p></div>
    </section>}
    <details className="panel model-details">
      <summary>Historical strategy comparison</summary><div className="panel-content">
        <p>Compare three reserve strategies over the last 24 observed hours using rolling seasonal-naive forecasts.</p>
        <div className="form-actions"><button className="btn secondary" type="button" disabled={backtestRunning} onClick={backtest}>{backtestRunning ? 'Running comparison…' : 'Run comparison'}</button></div>
        {backtestReport && <div aria-live="polite">
          <p className="helper-line">{backtestReport.hours} hours · {backtestReport.model} · Simulated evaluation</p>
          <div className="table-wrap"><table><thead><tr><th>Strategy</th><th>Net accrued interest</th><th>Average idle cash</th><th>Floor breaches</th><th>Maximum gap</th><th>MAE / RMSE</th></tr></thead>
            <tbody>{backtestReport.results.map(r => <tr key={r.strategy}><td>{r.strategy}</td><td>{money(r.net_interest, 2)}</td><td>{money(r.average_idle_cash)}</td><td>{r.floor_breaches}</td><td>{money(r.maximum_shortfall)}</td><td>{money(r.forecast_mae)} / {money(r.forecast_rmse)}</td></tr>)}</tbody>
          </table></div>
          <details className="inline-details"><summary>Evaluation assumptions</summary><p>{backtestReport.assumptions.join(' ')}</p></details>
        </div>}
      </div>
    </details>
  </>;
};
