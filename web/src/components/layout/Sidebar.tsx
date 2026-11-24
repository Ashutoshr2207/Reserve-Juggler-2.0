import React from 'react';
import { Brand } from '../common/Brand';
import { Icon, type IconName } from '../common/Icon';

export interface NavItem {
  id: string;
  icon: IconName;
  label: string;
  tag?: string;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export const navGroups: NavGroup[] = [
  {
    title: 'WORKSPACE',
    items: [
      { id: 'overview', icon: 'grid', label: 'Overview' },
      { id: 'forecast', icon: 'chart', label: 'Cashflow forecast' },
      { id: 'investments', icon: 'vault', label: 'Investment options' },
      { id: 'events', icon: 'clock', label: 'Payments & events' }
    ]
  },
  {
    title: 'REVIEW',
    items: [
      { id: 'scenarios', icon: 'flask', label: 'Scenario lab' },
      { id: 'decisions', icon: 'shield', label: 'Decision history' },
      { id: 'activity', icon: 'activity', label: 'Sweep activity' }
    ]
  },
  {
    title: 'SETTINGS',
    items: [
      { id: 'policy', icon: 'sliders', label: 'Reserve policy' },
      { id: 'data', icon: 'database', label: 'Data sources' }
    ]
  }
];

interface SidebarProps {
  currentRoute: string;
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentRoute,
  isOpen,
  onClose
}) => {
  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`} id="sidebar">
      <div className="sidebar-header">
        <Brand />
        <button className="sidebar-close" aria-label="Close navigation" onClick={onClose}><Icon name="close" /></button>
      </div>
      <nav className="side-nav" aria-label="Treasury navigation">
        {navGroups.map((group) => (
          <div className="nav-section" key={group.title}>
            <div className="nav-label">{group.title}</div>
            <div className="nav-links">
              {group.items.map((item) => {
                const isActive = item.id === currentRoute;
                return (
                  <a
                    key={item.id}
                    href={`#${item.id}`}
                    className={`nav-link ${isActive ? 'active' : ''}`}
                    {...(isActive ? { 'aria-current': 'page' } : {})}
                    onClick={onClose}
                  >
                    <span className="nav-link-left">
                      <Icon name={item.icon} />
                      <span className="nav-link-label">{item.label}</span>
                    </span>
                    {item.tag ? (
                      <span
                        className={`nav-badge ${
                          item.tag === 'Demo' ? 'live' : ''
                        }`}
                      >
                        {item.tag}
                      </span>
                    ) : null}
                  </a>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
};
