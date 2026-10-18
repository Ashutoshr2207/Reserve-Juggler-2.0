import React, { useId, useState } from 'react';
import type { ForecastRow } from '../../types/treasury';
import { compact, date, hour, money } from '../../utils/formatters';

export const CashflowChart: React.FC<{ rows: ForecastRow[]; floor: number; id?: string }> = ({ rows, floor, id = 'main-chart' }) => {
  const gradientId = useId().replace(/:/g, '');
  const [focusIndex, setFocusIndex] = useState(0);
  if (!rows.length) return null;
  const active = Math.min(focusIndex, rows.length - 1);
  const row = rows[active];
  const width = 900, left = 70, right = 875, top = 22, bottom = 242;
  const values = rows.flatMap(r => [r.balance, r.lower_balance, r.upper_balance]);
  const minimum = Math.min(floor, ...values), maximum = Math.max(floor, ...values);
  const pad = Math.max((maximum - minimum) * .13, 1);
  const low = minimum - pad, high = maximum + pad;
  const x = (i: number) => rows.length === 1 ? (left + right) / 2 : left + i / (rows.length - 1) * (right - left);
  const y = (value: number) => top + (high - value) / (high - low) * (bottom - top);
  const path = (key: 'balance' | 'lower_balance' | 'upper_balance') => rows.map((r,i) => (i === 0 ? 'M' : 'L') + x(i) + ',' + y(r[key])).join(' ');
  const envelope = path('upper_balance') + ' ' + [...rows].reverse().map((r,j) => 'L' + x(rows.length - 1 - j) + ',' + y(r.lower_balance)).join(' ') + ' Z';
  const area = path('balance') + ' L' + x(rows.length - 1) + ',' + bottom + ' L' + x(0) + ',' + bottom + ' Z';
  const inspect = (e: React.PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const value = (e.clientX - rect.left) / rect.width * width;
    setFocusIndex(Math.max(0, Math.min(rows.length - 1, Math.round((value - left) / (right - left) * (rows.length - 1)))));
  };
  return <>
    <div className="forecast-readout" id={id}>
      <span>{date(row.timestamp)} IST</span>
      <div className="readout-values"><div><span>Expected balance</span><strong>{money(row.balance)}</strong></div><div><span>Lower planning envelope</span><strong>{money(row.lower_balance)}</strong></div></div>
    </div>
    <div className="forecast-chart-wrap">
      <svg className="forecast-svg" viewBox="0 0 900 280" role="img" tabIndex={0}
        aria-label="Projected cash balance, blue mean with blue planning envelope and black policy minimum. Use arrow keys to inspect hours."
        onPointerMove={inspect} onKeyDown={e => {
          if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); setFocusIndex(Math.max(0, Math.min(rows.length - 1, active + (e.key === 'ArrowRight' ? 1 : -1)))); }
          if (e.key === 'Home' || e.key === 'End') { e.preventDefault(); setFocusIndex(e.key === 'Home' ? 0 : rows.length - 1); }
        }}>
        <defs><linearGradient id={gradientId + '-band'} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#a6b5ed" stopOpacity=".24" /><stop offset="1" stopColor="#bfcaef" stopOpacity=".08" /></linearGradient><linearGradient id={gradientId + '-area'} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#6aa6e0" stopOpacity=".09" /><stop offset="1" stopColor="#6aa6e0" stopOpacity="0" /></linearGradient></defs>
        {[0,1,2,3,4].map(i => {
          const v = low + (high - low) * i / 4;
          return <g key={i}><line x1={left} x2={right} y1={y(v)} y2={y(v)} stroke="#e9eff6" /><text x={left - 12} y={y(v) + 3} textAnchor="end">{compact(v)}</text></g>;
        })}
        <path d={envelope} fill={'url(#' + gradientId + '-band)'} />
        <path d={area} fill={'url(#' + gradientId + '-area)'} />
        <path d={path('upper_balance')} fill="none" stroke="#adbae2" strokeWidth=".6" strokeDasharray="3 3" />
        <path d={path('lower_balance')} fill="none" stroke="#adbae2" strokeWidth=".6" strokeDasharray="3 3" />
        <line className="forecast-minimum" x1={left} x2={right} y1={y(floor)} y2={y(floor)} />
        <text x={right} y={y(floor) - 5} textAnchor="end">Policy minimum {compact(floor)}</text>
        <path className="forecast-curve" d={path('balance')} />
        <line className="forecast-cursor" x1={x(active)} x2={x(active)} y1={top} y2={bottom} />
        <line x1={x(active)} x2={x(active)} y1={y(row.lower_balance)} y2={y(row.upper_balance)} stroke="#7f95cb" strokeWidth="2" />
        <circle cx={x(active)} cy={y(row.balance)} r="4" fill="#2470cb" stroke="#fff" strokeWidth="2" />
        {[...new Set([0, Math.floor(rows.length / 4), Math.floor(rows.length / 2), Math.floor(rows.length * .75), rows.length - 1])].map(i => <text key={i} x={x(i)} y="271" textAnchor="middle">{hour(rows[i].timestamp)}</text>)}
      </svg>
    </div>
    <div className="chart-legend forecast-legend"><span><i className="legend-line" />Expected balance</span><span><i className="legend-envelope" />Planning envelope</span><span><i className="legend-line floor" />Policy minimum</span><span>Hover or use arrow keys to inspect</span></div>
  </>;
};
