import React from 'react';

interface HeadingProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
}

export const Heading: React.FC<HeadingProps> = ({
  title,
  description,
  actions
}) => (
  <div className="page-heading">
    <div className="page-heading-content">
      <h1 className="page-title">{title}</h1>
      {description && <p className="page-description">{description}</p>}
    </div>
    {actions && <div className="heading-actions">{actions}</div>}
  </div>
);
