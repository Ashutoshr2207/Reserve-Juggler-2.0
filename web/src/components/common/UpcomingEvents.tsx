import React from 'react';
import { useTreasury } from '../../hooks/useTreasury';
import { date, money } from '../../utils/formatters';
import { RiskBadge } from './RiskBadge';

export const UpcomingEvents: React.FC<{ overview?: boolean }> = ({ overview = false }) => {
  const { state } = useTreasury();
  if (!state) return null;
  const events = state.intelligence.events;
  const shown = overview ? events.slice(0, 5) : events;
  return <section className="panel">
    <div className="panel-header"><h2>Upcoming payments & events</h2>
      {overview && <a className="text-link" href="#events">View all{events.length > 5 ? ` (${events.length})` : ''} →</a>}
    </div>
    {shown.length ? <div className="table-wrap"><table>
      <thead><tr><th>Event</th><th>Due · IST</th><th>Amount</th><th>Liquidity</th></tr></thead>
      <tbody>{shown.map((e, i) => <tr key={`${e.timestamp}-${i}`}><td>{e.label}</td><td>{date(e.timestamp)}</td><td className="numeric">{money(e.amount)}</td><td><RiskBadge risk={e.status} /></td></tr>)}</tbody>
    </table></div> : <div className="empty compact-empty">No upcoming events.</div>}
  </section>;
};
