import React from 'react';

interface RiskBadgeProps {
  risk: string;
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ risk }) => {
  const badgeClass =
    risk === 'High Risk'
      ? 'critical'
      : risk === 'Warning'
      ? 'warning'
      : '';
  return <span className={`badge ${badgeClass}`.trim()}>{risk}</span>;
};
