import React from 'react';
import type { TreasuryState } from '../../types/treasury';
import { compact, money } from '../../utils/formatters';

/** A display of current liquid cash, not a new eligibility calculation. */
export const LiquidityMap: React.FC<{ state: TreasuryState }> = ({ state }) => {
  const p = state.intelligence;
  const pool = Math.max(0, state.cash);
  const reserve = Math.min(pool, Math.max(0, p.selected.required));
  const eligible = Math.min(Math.max(0, pool - reserve), p.selected.eligible);
  const other = Math.max(0, pool - reserve - eligible);
  const segments = [
    { name: 'Reserved cash', value: reserve, color: '#3B82F6' },
    { name: 'Eligible surplus', value: eligible, color: '#93C5FD' },
    { name: 'Other cash / fees', value: other, color: '#64748B' }
  ];
  const circumference = 2 * Math.PI * 67;
  let offset = 0;
  return <section className="panel liquidity-map">
    <div className="map-heading"><div><span className="visual-eyebrow">LIQUIDITY POSITION</span><h2>Liquid cash allocation</h2></div><span className="map-unit">INR</span></div>
    <div className="map-body">
      <div className="cash-orbit">
        <svg viewBox="0 0 180 180" role="img" aria-label={'Liquid cash allocation: ' + segments.map(s => s.name + ' ' + money(s.value)).join(', ')}>
          <circle cx="90" cy="90" r="80" fill="none" stroke="#ffffff08" strokeWidth="1" />
          <circle cx="90" cy="90" r="67" fill="none" stroke="#ffffff10" strokeWidth="15" />
          {segments.map(s => {
            const length = pool > 0 ? s.value / pool * circumference : 0;
            const position = offset;
            offset += length;
            return <circle key={s.name} cx="90" cy="90" r="67" fill="none" stroke={s.color} strokeWidth="15"
              strokeDasharray={length + ' ' + Math.max(0, circumference - length)} strokeDashoffset={-position} transform="rotate(-90 90 90)"><title>{s.name}: {money(s.value)}</title></circle>;
          })}
        </svg>
        <div className="orbit-center"><span>Liquid pool</span><strong>{compact(state.cash)}</strong></div>
      </div>
      <div className="map-legend">{segments.filter(s => s.value > 0 || s.name !== 'Other cash / fees').map(s => <div key={s.name}>
        <span><i style={{ background: s.color }} />{s.name}</span><strong>{compact(s.value)}</strong>
      </div>)}</div>
    </div>
    <div className={'map-gap ' + (p.selected.shortfall > 0 ? 'has-gap' : '')}>
      <span>Modeled funding gap</span><strong>{money(p.selected.shortfall)}</strong>
    </div>
    {p.selected.required > pool && <p className="map-caution">The required reserve exceeds available liquid cash.</p>}
    <div className="map-bottom"><div><span>Locked principal</span><strong>{compact(p.locked_principal)}</strong></div><div><span>Credited interest</span><strong>{money(state.earned, 2)}</strong></div><div><span>Auto-sweep</span><strong>{state.policy.auto_sweep ? 'On' : 'Off'}</strong></div></div>
    <div className="map-footer"><a href="#scenarios">Test a stress scenario ↗</a><details><summary>Assumptions</summary><p>{p.method}. {p.note} Statutory CRR/SLR funds are outside this operational pool.</p></details></div>
  </section>;
};
