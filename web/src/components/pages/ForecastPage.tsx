import React, { useState } from 'react';
import { useTreasury } from '../../hooks/useTreasury';
import { date, money, number } from '../../utils/formatters';
import { CashflowChart } from '../charts/CashflowChart';
import { GrossFlowChart } from '../charts/GrossFlowChart';
import { Heading } from '../common/Heading';
import { Icon } from '../common/Icon';

export const ForecastPage: React.FC = () => {
  const { state } = useTreasury();
  const [horizon, setHorizon] = useState(24);
  if (!state) return null;
  const rows = state.forecast.slice(0, horizon);
  return <>
    <Heading title="Cashflow forecast" description="Projected cash balances based on hourly net flows."
      actions={<a className="btn secondary" href="/api/export"><Icon name="download" />Export 72-hour forecast</a>} />
    <section className="panel">
      <div className="panel-header"><div><h2>Projected cash balance</h2><p>Net flows only · Payments and maturities appear in Overview</p></div>
        <div className="segmented" aria-label="Forecast horizon">{[1,6,24,48,72].map(h => <button key={h} className={horizon === h ? 'selected' : ''} aria-pressed={horizon === h} onClick={() => setHorizon(h)}>{h}h</button>)}</div>
      </div>
      <CashflowChart rows={rows} floor={state.policy.minimum_buffer} id="main-chart" />
      <div className="chart-footer">{state.model} · {state.policy.confidence}% planning envelope · Estimates are not a payout guarantee</div>
    </section>
    <GrossFlowChart state={state} horizon={horizon} />
    <details className="panel model-details"><summary>Model details & forecast limitations</summary><div className="panel-content">
      <dl className="compact-facts">
        <div><dt>Current model</dt><dd>{state.model}</dd></div><div><dt>Training observations</dt><dd>{number(Math.min(state.history_count, 672))} hours</dd></div><div><dt>Previous-day baseline MAE</dt><dd>{money(state.baseline_mae)}</dd></div>
      </dl>
      <p className="helper-line">The baseline error compares the final seven days with the previous day. It is not an accuracy score for the fitted model.</p>
      <p className="helper-line">SARIMAX uses a 24-hour cycle. Fitting failure or nonconvergence activates seasonal-naive fallback. Accumulated intervals form a planning envelope, not a calibrated cash-path confidence interval.</p>
      <p className="helper-line">Gross deposits and withdrawals are independent seasonal-naive estimates. Their difference can vary from the net forecast used for planning.</p>
    </div></details>
    <details className="panel model-details"><summary>Hourly forecast data · {horizon} hours</summary><div className="table-wrap"><table>
      <thead><tr><th>Time · IST</th><th>Deposits</th><th>Withdrawals</th><th>Net flow</th><th>Balance</th><th>Lower plan</th><th>Buffer status</th></tr></thead>
      <tbody>{rows.map((r, i) => {
        const gross = state.gross_forecast.rows[i];
        const net = r.mean - r.withdrawals * state.policy.withdrawal_stress / 100;
        const below = r.lower_balance < state.policy.minimum_buffer;
        return <tr key={r.timestamp}><td>{date(r.timestamp)}</td><td>{gross ? money(gross.deposits) : 'Unavailable'}</td><td>{gross ? money(gross.withdrawals) : 'Unavailable'}</td><td className={net < 0 ? 'negative' : ''}>{money(net)}</td><td>{money(r.balance)}</td><td>{money(r.lower_balance)}</td><td><span className={'badge ' + (below ? 'warning' : '')}>{below ? 'Below minimum' : 'Above minimum'}</span></td></tr>;
      })}</tbody>
    </table></div></details>
  </>;
};
