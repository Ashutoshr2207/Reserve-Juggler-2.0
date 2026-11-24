import React from 'react';
import { money } from '../../utils/formatters';

interface AllocationRingProps {
  cash: number;
  vault: number;
}

export const AllocationRing: React.FC<AllocationRingProps> = ({ cash, vault }) => {
  const total = cash + vault;
  const ratio =
    total > 0 ? Math.max(0, Math.min(100, (vault / total) * 100)) : 0;

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Every rupee accounted for</h2>
        <span className="badge neutral">INR</span>
      </div>
      <div className="allocation-top">
        <svg
          className="allocation-ring"
          viewBox="0 0 110 110"
          role="img"
          aria-label={`${ratio.toFixed(1)} percent of total balance in the yield vault`}
        >
          <circle className="ring-bg" cx="55" cy="55" r="45" />
          <circle
            className="ring-fill"
            cx="55"
            cy="55"
            r="45"
            strokeDasharray={`${ratio * 2.8274} 282.74`}
          />
          <text x="55" y="54" textAnchor="middle">
            {ratio.toFixed(0)}%
          </text>
          <text className="ring-caption" x="55" y="69" textAnchor="middle">
            IN THE VAULT
          </text>
        </svg>
        <div className="allocation-key">
          <div>
            <i className="dot" />
            <p>
              Yield vault
              <strong>{money(vault)}</strong>
            </p>
          </div>
          <div>
            <i className="dot pale" />
            <p>
              Available cash
              <strong>{money(cash)}</strong>
            </p>
          </div>
        </div>
      </div>
      <div className="allocation-note">
        Total balance {money(total)} · Existing demo vault vault excluded from spendable cash.
      </div>
    </section>
  );
};
