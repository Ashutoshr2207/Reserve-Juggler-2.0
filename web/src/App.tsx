import React from 'react';
import { Shell } from './components/layout/Shell';
import { InvestModal } from './components/modals/InvestModal';
import { LedgerDetailModal } from './components/modals/LedgerDetailModal';
import { ResetModal } from './components/modals/ResetModal';
import { SweepModal } from './components/modals/SweepModal';
import { ActivityPage } from './components/pages/ActivityPage';
import { DataPage } from './components/pages/DataPage';
import { DecisionsPage } from './components/pages/DecisionsPage';
import { EventsPage } from './components/pages/EventsPage';
import { ForecastPage } from './components/pages/ForecastPage';
import { InvestmentsPage } from './components/pages/InvestmentsPage';
import { LandingPage } from './components/pages/LandingPage';
import { LoginPage } from './components/pages/LoginPage';
import { OverviewPage } from './components/pages/OverviewPage';
import { PolicyPage } from './components/pages/PolicyPage';
import { RegisterPage } from './components/pages/RegisterPage';
import { ScenariosPage } from './components/pages/ScenariosPage';
import { Toast } from './components/common/Toast';
import { useAuth } from './hooks/useAuth';
import { useHashRoute, PROTECTED_ROUTES } from './hooks/useHashRoute';
import { useTreasury } from './hooks/useTreasury';

export const App: React.FC = () => {
  const { route, scrollToMethod } = useHashRoute();
  const { authenticated, loading: authLoading, serviceUnavailable, checkAuth } = useAuth();
  const {
    state,
    loading,
    loadError,
    loadState,
    toast,
    busy,
    mutate,
    showToast,
    isSweepModalOpen,
    closeSweepModal,
    investModalState,
    closeInvestModal,
    isResetModalOpen,
    closeResetModal,
    selectedLedgerEntry,
    closeLedgerDetail
  } = useTreasury();

  const handleSweep = async (): Promise<boolean> => {
    const ok = await mutate('sweep');
    if (ok) {
      closeSweepModal();
      showToast('Sweep simulated. Principal is locked until maturity.');
    }
    return ok;
  };

  const handleInvest = async (
    optimized: boolean,
    execution: string
  ): Promise<boolean> => {
    const action = optimized ? 'planning_optimize' : 'planning_invest';
    const ok = await mutate(action, { execution });
    if (ok) {
      closeInvestModal();
      showToast(
        'Simulation saved. Reserve, recommendation and decision history recalculated.'
      );
    }
    return ok;
  };

  const handleReset = async (): Promise<boolean> => {
    const ok = await mutate('reset');
    if (ok) {
      showToast('Sandbox restored to its starting state.');
    }
    return ok;
  };

  // Public Landing Page: accessible immediately without authentication
  if (route === 'home' || route === 'method') {
    return (
      <>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <LandingPage onScrollToMethod={scrollToMethod} />
        <Toast message={toast.message} visible={toast.visible} />
      </>
    );
  }

  // Public Authentication Pages
  if (route === 'login') {
    if (authenticated) {
      const target = sessionStorage.getItem('rj_auth_redirect');
      sessionStorage.removeItem('rj_auth_redirect');
      if (target && PROTECTED_ROUTES.includes(target as any)) {
        window.location.hash = target;
      } else {
        window.location.hash = 'overview';
      }
      return null;
    }
    return (
      <>
        <LoginPage />
        <Toast message={toast.message} visible={toast.visible} />
      </>
    );
  }

  if (route === 'register') {
    if (authenticated) {
      sessionStorage.removeItem('rj_auth_redirect');
      window.location.hash = 'overview';
      return null;
    }
    return (
      <>
        <RegisterPage />
        <Toast message={toast.message} visible={toast.visible} />
      </>
    );
  }

  // Protected Treasury Workspace Guard
  if (!authenticated) {
    if (authLoading) {
      return (
        <div className="auth-page">
          <div className="spinner" />
          <p style={{ marginTop: '1rem', color: 'var(--muted)' }}>
            Verifying banker session…
          </p>
        </div>
      );
    }
    if (serviceUnavailable) {
      return (
        <div className="auth-page">
          <div className="auth-card" style={{ maxWidth: '440px', textAlign: 'center' }}>
            <div className="connection-error-badge" style={{ marginBottom: '1rem', display: 'inline-flex' }}>
              <span className="connection-error-dot" /> Authentication Service Offline
            </div>
            <h2 style={{ fontSize: '1.25rem', color: 'var(--navy)', marginBottom: '0.5rem' }}>
              Unable to Verify Session
            </h2>
            <p style={{ color: 'var(--muted)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
              The authentication service could not be reached. Check that the backend server is running.
            </p>
            <button className="btn primary" onClick={() => checkAuth()}>
              Retry Connection
            </button>
          </div>
        </div>
      );
    }
    if (PROTECTED_ROUTES.includes(route as any)) {
      sessionStorage.setItem('rj_auth_redirect', route);
    }
    window.location.hash = 'login';
    return null;
  }

  // If state is not loaded yet, show loading or error state inside Shell
  if (!state) {
    return (
      <>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <Shell currentRoute={route}>
          {loadError ? (
            <div className="connection-error-card" role="alert">
              <div className="connection-error-header">
                <span className="connection-error-badge">
                  <span className="connection-error-dot" /> Connection unavailable
                </span>
              </div>
              <h2 className="connection-error-title">
                Workspace unavailable
              </h2>
              <p className="connection-error-message">We couldn’t load your treasury data. Check the server connection and try again.</p>
              <div className="connection-error-guide">
                <details><summary>Technical details</summary><p>{loadError}</p><p>Start the local service with <code>python server.py --port 8000</code>.</p></details>
              </div>
              <div className="connection-error-actions">
                <button
                  className="btn primary"
                  data-action="retry"
                  onClick={loadState}
                  disabled={loading}
                >
                  {loading ? 'Connecting…' : 'Retry connection'}
                </button>
              </div>
            </div>
          ) : (
            <div className="loading-page">
              <div className="spinner" />
              <h2>Loading workspace</h2>
              <p>Preparing cashflow forecasts…</p>
            </div>
          )}
        </Shell>
        <Toast message={toast.message} visible={toast.visible} />
      </>
    );
  }

  let content: React.ReactNode = null;
  switch (route) {
    case 'overview':
      content = <OverviewPage />;
      break;
    case 'forecast':
      content = <ForecastPage />;
      break;
    case 'scenarios':
      content = <ScenariosPage />;
      break;
    case 'investments':
      content = <InvestmentsPage />;
      break;
    case 'events':
      content = <EventsPage />;
      break;
    case 'decisions':
      content = <DecisionsPage />;
      break;
    case 'activity':
      content = <ActivityPage />;
      break;
    case 'policy':
      content = <PolicyPage />;
      break;
    case 'data':
      content = <DataPage />;
      break;
    default:
      content = <OverviewPage />;
      break;
  }

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Shell currentRoute={route}>{content}</Shell>
      <Toast message={toast.message} visible={toast.visible} />

      <SweepModal
        isOpen={isSweepModalOpen}
        onClose={closeSweepModal}
        state={state}
        onSweep={handleSweep}
        busy={busy}
      />

      <InvestModal
        isOpen={investModalState.isOpen}
        optimized={investModalState.optimized}
        onClose={closeInvestModal}
        state={state}
        onInvest={handleInvest}
        busy={busy}
      />

      <ResetModal
        isOpen={isResetModalOpen}
        onClose={closeResetModal}
        onReset={handleReset}
        busy={busy}
      />

      <LedgerDetailModal
        entry={selectedLedgerEntry}
        onClose={closeLedgerDetail}
      />
    </>
  );
};
