import React from 'react';
import { Icon, type IconName } from './Icon';

interface MetricProps {
  label: string;
  value: React.ReactNode;
  note: React.ReactNode;
  icon: IconName | string;
  positive?: boolean;
}

export const Metric: React.FC<MetricProps> = ({
  label,
  value,
  note,
  icon,
  positive = false
}) => (
  <article className={'metric metric-' + icon}>
    <div className="metric-top">
      <span className="metric-label">{label}</span>
      <span className="metric-icon-wrap">
        <Icon name={icon} />
      </span>
    </div>
    <div className="metric-value">{value}</div>
    <div className={`metric-note ${positive ? 'positive' : ''}`}>{note}</div>
  </article>
);
