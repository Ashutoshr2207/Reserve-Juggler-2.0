import React from 'react';
import type { OptionDetails } from '../../types/treasury';
import { money } from '../../utils/formatters';
import { productName } from '../common/DecisionCard';

export const TermReturns: React.FC<{ options: OptionDetails[]; bestId: string }> = ({ options, bestId }) => {
  const max = Math.max(1, ...options.map(o => o.net_return));
  return <section className="panel term-returns"><div className="panel-header"><div><span className="visual-eyebrow">INVESTMENT COMPARISON</span><h2>Expected net return by term</h2></div><span className="muted">Per actual lock period</span></div>
    <div className="term-bars">{options.map((o, i) => <div className={'term-row term-' + i} key={o.id}>
      <div className="term-label"><strong>{productName(o)}</strong><span>{o.hours}h lock{o.id === bestId && o.suggested > 0 ? ' · Best net return' : ''}</span></div>
      <div className="term-track"><div style={{ width: Math.max(0, o.net_return) / max * 100 + '%' }} /><span className="sr-only">{o.suggested > 0 ? 'Eligible' : 'Not eligible'}</span></div>
      <strong className="term-value">{money(o.net_return, 2)}</strong>
    </div>)}</div>
  </section>;
};
