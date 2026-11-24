import React, { useState } from 'react';
import { useTreasury } from '../../hooks/useTreasury';
import { date, money } from '../../utils/formatters';
import { DecisionCard, productName } from '../common/DecisionCard';
import { Heading } from '../common/Heading';
import { RiskBadge } from '../common/RiskBadge';
import { TermReturns } from '../charts/TermReturns';
import SpecularButton from './SpecularButton';

export const InvestmentsPage: React.FC = () => {
  const { state, mutate, showToast, openInvestModal, busy } = useTreasury();
  const [selectedOption, setSelectedOption] = useState(state?.intelligence.policy.option ?? 'overnight');
  const [riskBuffer, setRiskBuffer] = useState(state?.intelligence.policy.risk_buffer ?? 0);
  const [rates, setRates] = useState<Record<string, number>>(() => Object.fromEntries(
    (state?.intelligence.options ?? []).map(o => [o.id, o.rate])
  ));
  if (!state) return null;
  const p = state.intelligence;
  const best = p.optimized;
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    if (await mutate('planning_policy', { option: selectedOption, risk_buffer: Number(riskBuffer), rates })) {
      showToast('Investment settings saved.');
    }
  };
  return <>
    <Heading title="Investment options" description="Compare terms, then review a simulated placement." />
    <TermReturns options={p.options} bestId={best.id} />
    <section className="panel">
      <div className="panel-header"><h2>Available products</h2><span className="muted">Illustrative rates · No early withdrawal</span></div>
      <div className="table-wrap"><table>
        <thead><tr><th>Product</th><th>Lock / annual rate</th><th>Minimum / entry fee</th><th>Suggested principal</th><th>Net return</th><th>Status</th></tr></thead>
        <tbody>{p.options.map(o => <tr key={o.id}>
          <td><strong>{productName(o)}</strong><p className="muted">{o.id === p.policy.option ? 'Selected' : o.id === best.id && o.suggested > 0 ? 'Highest net return' : 'Matures ' + date(o.matures) + ' IST'}</p></td>
          <td>{o.hours}h · {o.rate}%</td><td>{money(o.minimum)}<p className="muted">{money(o.fee)} fee</p></td>
          <td className="numeric">{money(o.suggested)}</td><td className="numeric">{money(o.net_return, 2)}</td>
          <td><RiskBadge risk={o.risk} /><details className="cell-details"><summary>Details</summary><p>{o.reason}</p><p>Eligible: {money(o.eligible)}. Available at maturity: {date(o.matures)} IST.</p></details></td>
        </tr>)}</tbody>
      </table></div>
      <div className="panel-content best-option">
        <div><strong>{best.suggested > 0 ? 'Highest net return: ' + productName(best) : 'No product is eligible right now'}</strong>
          <p className="muted">{best.suggested > 0 ? money(best.suggested) + ' principal · ' + money(best.net_return, 2) + ' expected net return' : best.reason}</p></div>
        <SpecularButton
          size="md"
          variant="primary"
          radius={18}
          disabled={busy || best.suggested <= 0}
          onClick={() => openInvestModal(true)}
        >
          Review optimized sweep
        </SpecularButton>
      </div>
    </section>
    <DecisionCard showCompare={false} />
    <details className="panel model-details">
      <summary>Investment planning settings</summary>
      <form id="planning-settings" className="panel-content" onSubmit={handleSaveSettings}>
        <div className="form-grid">
          <div className="form-field"><label htmlFor="option">Selected investment</label><select id="option" value={selectedOption} onChange={e => setSelectedOption(e.target.value)}>
            {p.options.map(o => <option key={o.id} value={o.id}>{productName(o)} · {o.hours}h</option>)}
          </select></div>
          <div className="form-field"><label htmlFor="risk_buffer">Additional risk buffer · INR</label><input id="risk_buffer" type="number" min="0" max="10000000000" step="0.01" value={riskBuffer} required onChange={e => setRiskBuffer(Number(e.target.value))} /></div>
        </div>
        <div className="form-section"><h3>Illustrative annual rates</h3><div className="form-grid">
          {p.options.map(o => <div className="form-field" key={o.id}><label htmlFor={'rate-' + o.id}>{productName(o)} · %</label><input id={'rate-' + o.id} type="number" min="0" max="20" step="0.01" value={rates[o.id] ?? o.rate} required onChange={e => setRates(prev => ({ ...prev, [o.id]: Number(e.target.value) }))} /></div>)}
        </div></div>
        <div className="form-actions">
          <SpecularButton
            type="submit"
            size="md"
            variant="primary"
            radius={18}
            disabled={busy}
          >
            Save & recalculate
          </SpecularButton>
        </div>
      </form>
    </details>
    <details className="panel model-details"><summary>How products are compared</summary><div className="panel-content">
      <p>Net return is simple interest for the product’s actual term, minus its entry fee. Minimum principal, reserves and payment timing must all be satisfied.</p>
      <p>The optimizer selects one placement at a time. It does not optimize a multi-period portfolio. Rates and returns are simulated estimates.</p>
    </div></details>
  </>;
};
