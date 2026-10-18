import React, { useId, useState } from 'react';
import type { TreasuryState } from '../../types/treasury';
import { compact, date, hour, money } from '../../utils/formatters';

export const GrossFlowChart: React.FC<{ state: TreasuryState; horizon: number }> = ({ state, horizon }) => {
  const id = useId().replace(/:/g, '');
  const [focusIndex, setFocusIndex] = useState(0);
  const rows = state.gross_forecast.rows.slice(0, horizon);
  if (!rows.length) return null;
  const active = Math.min(focusIndex, rows.length - 1);
  const maximum = Math.max(1, ...rows.flatMap(r => [r.deposits, r.withdrawals]));
  const step = 780 / rows.length;
  const bar = Math.min(24, step * .62);
  const baseline = 113;
  const x = (i: number) => 70 + step * (i + .5);
  return <section className="panel flow-panel">
    <div className="panel-header"><div><span className="visual-eyebrow">GROSS CASHFLOWS</span><h2>Deposits & withdrawals</h2></div><span className="badge neutral">Next {horizon}h</span></div>
    <div className="flow-readout"><span>{date(state.forecast[active].timestamp)} IST</span><div><span><i className="color-dot teal" />Deposits <strong>{money(rows[active].deposits)}</strong></span><span><i className="color-dot coral" />Withdrawals <strong>{money(rows[active].withdrawals)}</strong></span></div></div>
    <div className="flow-svg-wrap"><svg viewBox="0 0 900 242" role="img" tabIndex={0} aria-label="Independent gross cashflow estimates. Teal deposits above the center line; coral withdrawals below. Use arrow keys to inspect each hour."
      onKeyDown={e => {
        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); setFocusIndex(Math.max(0, Math.min(rows.length - 1, active + (e.key === 'ArrowRight' ? 1 : -1)))); }
      }}>
      <defs><linearGradient id={id + '-in'} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#26bda6" /><stop offset="1" stopColor="#68d8bd" /></linearGradient><linearGradient id={id + '-out'} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#f39b84" /><stop offset="1" stopColor="#e76f62" /></linearGradient></defs>
      {[26, 70, 113, 156, 200].map(v => <line key={v} x1="65" x2="860" y1={v} y2={v} stroke="#edf1f6" />)}
      <text x="55" y="30" textAnchor="end">{compact(maximum)}</text><text x="55" y="117" textAnchor="end">0</text><text x="55" y="204" textAnchor="end">{compact(-maximum)}</text>
      {rows.map((r, i) => {
        const incoming = r.deposits / maximum * 82, outgoing = r.withdrawals / maximum * 82;
        return <g key={i} opacity={i === active ? 1 : .76} onPointerOver={() => setFocusIndex(i)}>
          <rect x={x(i) - bar / 2} y={baseline - incoming} width={bar} height={incoming} rx="3" fill={'url(#' + id + '-in)'} />
          <rect x={x(i) - bar / 2} y={baseline + 3} width={bar} height={outgoing} rx="3" fill={'url(#' + id + '-out)'} />
          <rect x={x(i) - step / 2} y="22" width={step} height="185" fill="transparent"><title>{date(state.forecast[i].timestamp)} IST: deposits {money(r.deposits)}, withdrawals {money(r.withdrawals)}</title></rect>
        </g>;
      })}
      {[...new Set([0, Math.floor(rows.length / 2), rows.length - 1])].map(i => <text key={i} x={x(i)} y="232" textAnchor="middle">{hour(state.forecast[i].timestamp)}</text>)}
    </svg></div>
    <div className="chart-footer">Independent seasonal-naive estimates. Their difference may vary from the net forecast used for planning.</div>
  </section>;
};
