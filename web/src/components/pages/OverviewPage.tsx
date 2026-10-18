import React from 'react';
import { useTreasury } from '../../hooks/useTreasury';
import { compact } from '../../utils/formatters';
import { LiquidityMap } from '../charts/LiquidityMap';
import { PlanningCashChart } from '../charts/PlanningCashChart';
import { DecisionCard } from '../common/DecisionCard';
import { Heading } from '../common/Heading';
import { Metric } from '../common/Metric';
import { UpcomingEvents } from '../common/UpcomingEvents';

export const OverviewPage: React.FC = () => {
  const { state } = useTreasury();
  if (!state) return null;
  const p = state.intelligence;
  const c = p.selected;
  return <>
    <Heading title="Overview"
      actions={<a className="btn secondary" href="#events">Add a payment or event</a>} />
    <div className="metrics">
      <Metric label="Available cash" value={compact(state.cash)} note="Excludes invested funds" icon="wallet" />
      <Metric label="Required reserve" value={compact(c.required)} note={c.hours + 'h selected investment'} icon="shield" />
      <Metric label="Eligible surplus" value={compact(c.eligible)} note="After reserve and entry fee" icon="chart" />
      <Metric label="Projected minimum cash" value={compact(p.projected_minimum)} note="Next 72h · before investment" icon="wallet" />
    </div>
    <div className="content-grid overview-visual-grid">
      <DecisionCard />
      <LiquidityMap state={state} />
    </div>
    <PlanningCashChart state={state} />
    <UpcomingEvents overview />
  </>;
};
