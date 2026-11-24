import React from 'react';
import { Icon } from '../common/Icon';
import { ThemeToggle } from '../common/ThemeToggle';
import { useAuth } from '../../hooks/useAuth';
import SpecularButton from '../common/SpecularButton';

interface TopbarProps {
  title: string;
  dateText: string;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  timerActive: boolean;
  onToggleTimer: () => void;
  onAdvance: () => void;
  busy: boolean;
}

export const Topbar: React.FC<TopbarProps> = ({
  title,
  dateText,
  sidebarOpen,
  onToggleSidebar,
  timerActive,
  onToggleTimer,
  onAdvance,
  busy
}) => {
  const { user, logout } = useAuth();

  const getInitials = (name?: string) => {
    if (!name) return 'B';
    return name
      .split(' ')
      .filter(Boolean)
      .map((part) => part[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  return (
    <header className="topbar">
      <div className="breadcrumb">
        <button
          className="mobile-menu"
          data-action="menu"
          aria-label="Toggle navigation"
          aria-controls="sidebar"
          aria-expanded={sidebarOpen}
          onClick={onToggleSidebar}
        >
          <Icon name="menu" />
        </button>
        <span className="bc-root">Treasury</span>
        <span className="bc-sep">/</span>
        <span className="bc-current">{title}</span>
      </div>
      <div className="topbar-right">
        <span className="topbar-date">{dateText}</span>
        {timerActive ? (
          <SpecularButton
            size="sm"
            variant="secondary"
            radius={18}
            aria-label="Pause continuous simulation"
            onClick={onToggleTimer}
          >
            ⏸ Pause 60s
          </SpecularButton>
        ) : (
          <SpecularButton
            size="sm"
            variant="secondary"
            radius={18}
            title="Simulate 1 hour ahead"
            onClick={onAdvance}
            disabled={busy}
          >
            <Icon name="play" /> Advance 1h
          </SpecularButton>
        )}
        <ThemeToggle />

        {user && (
          <div
            className="topbar-banker-badge"
            title={`${user.full_name} (${user.organization_name})`}
          >
            <span className="banker-avatar" aria-hidden="true">
              {getInitials(user.full_name)}
            </span>
            <span className="banker-name">{user.full_name}</span>
            <button
              type="button"
              className="btn ghost small banker-logout-btn"
              onClick={logout}
              title="Sign out of treasury workspace"
              aria-label="Sign out"
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
