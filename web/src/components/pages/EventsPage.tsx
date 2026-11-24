import React, { useState } from 'react';
import { useTreasury } from '../../hooks/useTreasury';
import { money } from '../../utils/formatters';
import { Heading } from '../common/Heading';
import { UpcomingEvents } from '../common/UpcomingEvents';
import SpecularButton from './SpecularButton';

export const EventsPage: React.FC = () => {
  const { state, mutate, showToast, busy } = useTreasury();
  const [kind, setKind] = useState('withdrawal');
  const [amount, setAmount] = useState(5000000);
  const [hours, setHours] = useState(2);
  if (!state) return null;
  const isDelay = kind === 'delay';
  const isRisk = kind === 'risk';
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    if (await mutate('planning_event', { kind, amount: Number(amount), hours: Number(hours) })) showToast('Event saved. Reserve recalculated.');
  };
  return <>
    <Heading title="Payments & events" description="Add an obligation or receipt and see its effect on liquidity." />
    <div className="content-grid">
      <section className="panel">
        <div className="panel-header"><h2>Add a simulated event</h2></div>
        <form className="panel-content" id="planning-event" onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="form-field full-width"><label htmlFor="event-kind">Event type</label><select id="event-kind" value={kind} onChange={e => setKind(e.target.value)}>
              <option value="withdrawal">Withdrawal</option><option value="payment">Payment / salary payout</option><option value="deposit">Incoming deposit</option><option value="settlement">Settlement receipt</option><option value="delay">Delay pending settlements</option><option value="risk">Set additional risk buffer</option>
            </select></div>
            {!isDelay && <div className="form-field"><label htmlFor="event-amount">{isRisk ? 'New risk buffer · INR' : 'Amount · INR'}</label><input id="event-amount" type="number" min="0.01" max="10000000000" step="0.01" value={amount} required onChange={e => setAmount(Number(e.target.value))} /></div>}
            {!isRisk && <div className="form-field"><label htmlFor="event-hours">{isDelay ? 'Delay duration · hours' : 'Due in · hours'}</label><input id="event-hours" type="number" min="0.25" max="48" step="0.25" value={hours} required onChange={e => setHours(Number(e.target.value))} /></div>}
          </div>
          {isDelay && <p className="helper-line">Moves all pending settlement receipts later. No funds are deducted.</p>}
          {isRisk && <p className="helper-line">Replaces the current additional buffer immediately.</p>}
          <div className="form-actions">
            <SpecularButton
              type="submit"
              size="md"
              variant="primary"
              radius={18}
              disabled={busy}
            >
              Simulate event & recalculate
            </SpecularButton>
          </div>
        </form>
      </section>
      <section className="panel"><div className="panel-header"><h2>Current position</h2></div><div className="panel-content">
        <dl className="status-list"><div><dt>Required reserve</dt><dd>{money(state.intelligence.selected.required)}</dd></div><div><dt>Eligible surplus</dt><dd>{money(state.intelligence.selected.eligible)}</dd></div></dl>
        <div className="form-actions"><a className="text-link" href="#decisions">View decision history →</a></div>
        <p className="helper-line">Receipts become available only at their scheduled time.</p>
      </div></section>
    </div>
    <UpcomingEvents />
  </>;
};
