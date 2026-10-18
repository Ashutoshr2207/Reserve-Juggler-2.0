import React from 'react';
import { useTreasury } from '../../hooks/useTreasury';
import type { OptionDetails } from '../../types/treasury';
import { date, money } from '../../utils/formatters';
import { RiskBadge } from './RiskBadge';
import SpecularButton from './SpecularButton';

export const productName = (option: OptionDetails) => {
  if (option.id === 'flex') return 'Intraday placement';
  if (option.id === 'overnight') return 'Overnight deposit';
  if (option.id === 'extended') return '48-hour deposit';
  return option.name;
};

export const DecisionCard: React.FC<{ showCompare?: boolean }> = ({ showCompare = true }) => {
  const { state, openInvestModal, busy } = useTreasury();
  if (!state) return null;
  const p = state.intelligence;
  const c = p.selected;
  return <section className="panel decision-card">
    <div className="panel-header"><h2>Selected investment</h2><RiskBadge risk={c.risk} /></div>
    <div className="panel-content">
      <div className="recommendation-top">
        <div><span className="field-caption">Suggested principal</span><div className="decision-amount">{money(c.suggested)}</div></div>
        <div className="product-caption"><strong>{productName(c)}</strong><span>{c.hours}h lock · {c.rate}% annual rate</span></div>
      </div>
      <dl className="compact-facts">
        <div><dt>Expected net return</dt><dd>{money(c.net_return, 2)}</dd></div>
        <div><dt>Entry fee</dt><dd>{money(c.fee, 2)}</dd></div>
        <div><dt>Returns to cash · IST</dt><dd>{date(c.matures)}</dd></div>
      </dl>
      {c.suggested <= 0 && <p className="inline-alert" role="status">{c.reason}</p>}
      <div className="form-actions">
        <SpecularButton
          size="md"
          variant="primary"
          radius={12}
          disabled={busy || c.suggested <= 0}
          onClick={() => openInvestModal(false)}
        >
          Review selected investment
        </SpecularButton>
        {showCompare && <a className="btn secondary" href="#investments">Compare options</a>}
      </div>
      <details className="inline-details">
        <summary>View reserve calculation</summary>
        <dl className="plan-facts">
          <div><dt>Minimum cash buffer</dt><dd>{money(state.policy.minimum_buffer)}</dd></div>
          <div><dt>Additional risk buffer</dt><dd>{money(p.policy.risk_buffer)}</dd></div>
          <div><dt>Lock-window drawdown</dt><dd>{money(c.required - p.floor)}</dd></div>
          <div><dt>Required reserve</dt><dd>{money(c.required)}</dd></div>
          <div><dt>Eligible principal after fee</dt><dd>{money(c.eligible)}</dd></div>
        </dl>
        <p>{c.reason}</p>
        <p className="muted">The planner checks payment timing and forecast uncertainty. Estimates do not guarantee future payouts.</p>
      </details>
    </div>
  </section>;
};
