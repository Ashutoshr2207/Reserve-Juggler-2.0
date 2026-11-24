import React, { useId, useState } from 'react';
import type { TreasuryState } from '../../types/treasury';
import { compact, date, money } from '../../utils/formatters';
import { RiskBadge } from '../common/RiskBadge';

export const PlanningCashChart: React.FC<{ state: TreasuryState }> = ({ state }) => {
  const id = useId().replace(/:/g, '');
  const [focusIndex, setFocusIndex] = useState<number | null>(null);
  const [before, setBefore] = useState(true);
  const [after, setAfter] = useState(true);
  const p = state.intelligence;
  const c = p.selected;
  const rows = [{ timestamp: state.as_of, label: 'Current liquid cash', flow: 0, balance: state.cash, status: c.risk }, ...p.timeline];
  const cost = c.suggested > 0 ? c.fee : 0;
  const maturity = new Date(c.matures).getTime();
  const projected = rows.map(r => r.balance - c.suggested - cost +
    (new Date(r.timestamp).getTime() > maturity ? c.suggested + c.interest : 0));
  const minimumIndex = rows.reduce((best, r, i) => r.balance < rows[best].balance ? i : best, 0);
  const active = Math.min(focusIndex ?? minimumIndex, rows.length - 1);
  const point = rows[active];
  const left = 68, right = 877, top = 30, bottom = 257;
  const start = new Date(state.as_of).getTime();
  const minimum = Math.min(p.floor, ...rows.map(r => r.balance), ...projected);
  const maximum = Math.max(p.floor, ...rows.map(r => r.balance), ...projected);
  const padding = Math.max(1, (maximum - minimum) * .14);
  const low = minimum - padding, high = maximum + padding;
  const y = (value: number) => bottom - (value - low) / (high - low) * (bottom - top);
  const x = (timestamp: string) => left + (new Date(timestamp).getTime() - start) / (72 * 3600000) * (right - left);
  const line = (values: number[]) => rows.map((r, i) => (i === 0 ? 'M' : 'L') + x(r.timestamp) + ',' + y(values[i])).join(' ');
  const baselinePath = line(rows.map(r => r.balance));
  const area = baselinePath + ' L' + x(rows[rows.length - 1].timestamp) + ',' + bottom + ' L' + left + ',' + bottom + ' Z';
  const inspect = (e: React.PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const targetX = (e.clientX - rect.left) / rect.width * 900;
    const targetY = (e.clientY - rect.top) / rect.height * 298;
    let best = 0, distance = Infinity;
    rows.forEach((r, i) => {
      const dx = x(r.timestamp) - targetX, dy = y(r.balance) - targetY;
      const score = dx * dx * 6 + dy * dy;
      if (score < distance) { distance = score; best = i; }
    });
    setFocusIndex(best);
  };
  const keyboard = (e: React.KeyboardEvent<SVGSVGElement>) => {
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      e.preventDefault(); setFocusIndex(Math.max(0, Math.min(rows.length - 1, active + (e.key === 'ArrowRight' ? 1 : -1))));
    } else if (e.key === 'Home' || e.key === 'End') {
      e.preventDefault(); setFocusIndex(e.key === 'Home' ? 0 : rows.length - 1);
    }
  };
  return <section className="panel chart-panel">
    <div className="panel-header"><div><span className="visual-eyebrow">LIQUIDITY OUTLOOK</span><h2>Cash availability · next 72 hours</h2></div>
      <div className="chart-controls">
        <button aria-pressed={before} disabled={before && !after} onClick={() => setBefore(!before)}><i className="color-dot" />Before investment</button>
        <button aria-pressed={after} disabled={after && !before} onClick={() => setAfter(!after)}><i className="color-dot violet" />After investment</button>
      </div>
    </div>
    <div className="panel-content">
      <div className="chart-readout">
        <div><span className="readout-label">{date(point.timestamp)} IST</span><span className="readout-event">{point.label}</span></div>
        <div className="readout-values"><div><span>Before investment</span><strong>{compact(point.balance)}</strong></div><div className="violet"><span>After selected investment</span><strong>{compact(projected[active])}</strong></div></div>
      </div>
      <svg className="plan-chart" viewBox="0 0 900 298" role="img" tabIndex={0}
        aria-label="Time-ordered liquidity chart. Blue before investment, light blue after the selected investment, black protected floor. Use arrow keys for each cash movement, Home or End for first or last."
        onPointerMove={inspect} onKeyDown={keyboard}>
        <defs>
          <linearGradient id={id + '-cash'} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#3B82F6" stopOpacity=".18" /><stop offset="1" stopColor="#3B82F6" stopOpacity=".01" /></linearGradient>
          <pattern id={id + '-risk'} width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" x2="0" y1="0" y2="7" stroke="#94A3B8" strokeWidth="1" /></pattern>
          <clipPath id={id + '-plot'}><rect x={left} y={top} width={right - left} height={bottom - top} /></clipPath>
        </defs>
        {[0,1,2,3,4].map(i => {
          const v = low + (high - low) * i / 4;
          return <g key={i}><line x1={left} x2={right} y1={y(v)} y2={y(v)} stroke="#e9eff6" /><text x={left - 10} y={y(v) + 3} textAnchor="end">{compact(v)}</text></g>;
        })}
        <g clipPath={'url(#' + id + '-plot)'}>
          <rect x={left} y={y(p.floor)} width={right - left} height={Math.max(0, bottom - y(p.floor))} fill={'url(#' + id + '-risk)'} opacity=".4" />
          <rect x={left} y={top} width={Math.min(right - left, c.hours / 72 * (right - left))} height={bottom - top} fill="#3B82F6" opacity=".06" />
          {before && <path d={area} fill={'url(#' + id + '-cash)'} />}
          {after && <path d={line(projected)} fill="none" stroke="#60A5FA" strokeWidth="2" strokeLinejoin="round" />}
          {before && <path d={baselinePath} fill="none" stroke="#18478D" strokeWidth="2.2" strokeLinejoin="round" />}
          <line x1={left} x2={right} y1={y(p.floor)} y2={y(p.floor)} stroke="#0A192F" strokeDasharray="5 4" />
          <line className="cursor-line" x1={x(point.timestamp)} x2={x(point.timestamp)} y1={top} y2={bottom} />
          {before && <circle className="active-point" cx={x(point.timestamp)} cy={y(point.balance)} r="4" />}
          {after && <circle className="active-point violet" cx={x(point.timestamp)} cy={y(projected[active])} r="4" />}
        </g>
        <text className="chart-floor-label" x={right - 3} y={y(p.floor) - 5} textAnchor="end">Protected floor {compact(p.floor)}</text>
        <rect x={left} y="11" width={Math.min(right - left, c.hours / 72 * (right - left))} height="4" rx="2" fill="#93C5FD" />
        <text x={left} y="8">Selected lock: {c.hours}h</text>
        {[0,6,24,48,72].map(h => <text key={h} x={left + h / 72 * (right - left)} y="285" textAnchor="middle">+{h}h</text>)}
      </svg>
      <div className="chart-legend"><span><i className="legend-line" />Before investment</span><span><i className="legend-line purple" />After selected investment</span><span><i className="legend-line floor" />Protected floor</span><span>Shaded region: below floor</span></div>
      <p className="chart-tip-hint">Hover to inspect · Arrow keys move through every cash movement · Forecast estimates include uncertainty</p>
    </div>
    <details className="panel-content"><summary>View detailed cash timeline</summary>
      <p className="helper-line">Withdrawals precede receipts at equal timestamps. Later receipts cannot fund earlier payments.</p>
      <div className="table-wrap"><table><thead><tr><th>Due · IST</th><th>Movement</th><th>Cashflow</th><th>Balance</th><th>Status</th></tr></thead>
        <tbody>{p.timeline.map((r,i) => <tr key={i}><td>{date(r.timestamp)}</td><td>{r.label}</td><td>{money(r.flow)}</td><td>{money(r.balance)}</td><td><RiskBadge risk={r.status} /></td></tr>)}</tbody>
      </table></div>
    </details>
  </section>;
};
