import React, { useEffect, useState } from 'react';
import { useTreasury } from '../../hooks/useTreasury';
import { date } from '../../utils/formatters';
import { Footer } from './Footer';
import { navGroups, Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

interface ShellProps {
  currentRoute: string;
  children: React.ReactNode;
}

export const Shell: React.FC<ShellProps> = ({ currentRoute, children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const {
    state,
    timerActive,
    toggleTimer,
    advanceHour,
    busy
  } = useTreasury();

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSidebarOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const allItems = navGroups.flatMap((g) => g.items);
  const currentItem = allItems.find((item) => item.id === currentRoute);
  const title = currentItem?.label || 'Workspace';

  const dateText = state
    ? `${date(state.as_of, true)} IST`
    : 'Syncing state...';

  return (
    <div className="workspace">
      <Sidebar
        currentRoute={currentRoute}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      {sidebarOpen && <button className="nav-backdrop" aria-label="Close navigation menu" onClick={() => setSidebarOpen(false)} />}
      <div className="work-area">
        <Topbar
          title={title}
          dateText={dateText}
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
          timerActive={timerActive}
          onToggleTimer={toggleTimer}
          onAdvance={advanceHour}
          busy={busy}
        />
        <main id="main" className="main-content">
          <div className="content-container">{children}</div>
          <Footer />
        </main>
      </div>
    </div>
  );
};
