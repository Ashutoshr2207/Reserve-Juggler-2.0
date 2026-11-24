import React from 'react';
import { useTreasury } from '../../hooks/useTreasury';
import { date, money } from '../../utils/formatters';
import { Heading } from '../common/Heading';

export const DecisionsPage: React.FC = () => {
  const { state } = useTreasury();

  if (!state) return null;

  const decisions = state.decisions || [];

  return (
    <>
      <Heading
        eyebrow="Explainable investment decisions"
        title="Decision history"
        description="Review how events, settings and investments changed the reserve."
      />

      <section className="panel">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time · IST / trigger</th>
                <th>Cash position</th>
                <th>Reserve before → after</th>
                <th>Investment before → after</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {decisions.length > 0 ? (
                decisions.map((d, idx) => (
                  <tr key={`decision-${d.timestamp}-${idx}`}>
                    <td>
                      {date(d.timestamp)}
                      <br />
                      {d.action}
                    </td>
                    <td>{money(d.cash)}</td>
                    <td>
                      {money(d.before.required)} → {money(d.after.required)}
                    </td>
                    <td>
                      {money(d.before.suggested)} → {money(d.after.suggested)}
                    </td>
                    <td className="decision-reason"><details><summary>View explanation</summary><p>{d.reason}</p></details></td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5}>
                    No simulated planning decisions yet. Schedule an event or
                    review an investment to start.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
};
