import React, { useEffect, useRef, useState } from 'react';
import { Icon } from '../common/Icon';
import { CurvedLoop } from '../common/CurvedLoop';
import { BlurText } from '../common/BlurText';
import { TimelineWorkflow } from '../landing/TimelineWorkflow';
import { useAuth } from '../../hooks/useAuth';

interface LandingPageProps {
  onScrollToMethod: (e: React.MouseEvent) => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  onScrollToMethod
}) => {
  const { authenticated, loading: authLoading, checkAuth } = useAuth();
  const [checkingWorkspace, setCheckingWorkspace] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navRef = useRef<HTMLElement>(null);

  const handleEnterWorkspace = async (e?: React.MouseEvent) => {
    if (e) e.preventDefault();
    setMobileMenuOpen(false);

    if (authLoading) {
      setCheckingWorkspace(true);
      const isAuth = await checkAuth();
      setCheckingWorkspace(false);
      window.location.hash = isAuth ? 'overview' : 'login';
      return;
    }

    window.location.hash = authenticated ? 'overview' : 'login';
  };

  useEffect(() => {
    if (!mobileMenuOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (navRef.current && !navRef.current.contains(event.target as Node)) {
        setMobileMenuOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMobileMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [mobileMenuOpen]);

  const handleMethodClick = (e: React.MouseEvent) => {
    setMobileMenuOpen(false);
    onScrollToMethod(e);
  };

  return (
    <div className="landing">
      <header className="landing-nav">
        <nav
          ref={navRef}
          className="glass-pill-nav"
          aria-label="Main navigation"
        >
          <div className="nav-desktop">
            <a
              className="nav-item"
              href="#method"
              data-scroll="method"
              onClick={handleMethodClick}
            >
              How it works
            </a>
            <a className="nav-item" href="#scenarios">
              Explore scenarios
            </a>
          </div>

          <button
            type="button"
            className="nav-toggle"
            aria-expanded={mobileMenuOpen}
            aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
            onClick={() => setMobileMenuOpen(open => !open)}
          >
            <span className="burger-icon" aria-hidden="true">
              <span className={`burger-line ${mobileMenuOpen ? 'open-top' : ''}`} />
              <span className={`burger-line ${mobileMenuOpen ? 'open-bottom' : ''}`} />
            </span>
            <span>Menu</span>
          </button>

          <a
            className="nav-item nav-primary"
            href={authenticated ? '#overview' : '#login'}
            onClick={handleEnterWorkspace}
            aria-busy={checkingWorkspace}
          >
            {checkingWorkspace ? 'Verifying session…' : 'Enter Workspace'}{' '}
            <span className="nav-arrow" aria-hidden="true">→</span>
          </a>

          {mobileMenuOpen && (
            <div className="nav-drawer" role="menu">
              <a
                href="#method"
                data-scroll="method"
                role="menuitem"
                onClick={handleMethodClick}
              >
                How it works
              </a>
              <a
                href="#scenarios"
                role="menuitem"
                onClick={() => setMobileMenuOpen(false)}
              >
                Explore scenarios
              </a>
              <a
                className="drawer-primary"
                href={authenticated ? '#overview' : '#login'}
                role="menuitem"
                onClick={handleEnterWorkspace}
                aria-busy={checkingWorkspace}
              >
                {checkingWorkspace ? 'Verifying session…' : 'Enter Workspace →'}
              </a>
            </div>
          )}
        </nav>
      </header>
      <main id="main">
        <section className="hero">
          <div className="hero-copy">
            <h1 className="hero-headline">
              <span className="hero-headline-line">
                <BlurText
                  text="Know what to keep liquid."
                  effect="blur"
                  animateBy="words"
                  direction="top"
                  staggerFrom="start"
                  trigger="view"
                  delay={90}
                  stepDuration={0.32}
                  blur={8}
                  distance={22}
                  color="var(--navy)"
                  className="hero-blur-text"
                />
              </span>
              <span className="hero-headline-line">
                <BlurText
                  text="Know what can earn."
                  effect="blur"
                  animateBy="words"
                  direction="top"
                  staggerFrom="start"
                  trigger="view"
                  delay={90}
                  initialDelay={0.16}
                  stepDuration={0.32}
                  blur={8}
                  distance={22}
                  color="var(--navy)"
                  highlightWords={['can', 'earn.']}
                  highlightColor="var(--blue)"
                  className="hero-blur-text"
                />
              </span>
            </h1>
            <p>
              Reserve Juggler forecasts upcoming deposits, withdrawals, and
              settlements to calculate a risk-aware cash reserve—then identifies
              eligible surplus that can earn yield.
            </p>
            <div className="hero-actions">
              <a
                className="btn primary"
                href={authenticated ? '#overview' : '#login'}
                onClick={handleEnterWorkspace}
                aria-busy={checkingWorkspace}
              >
                {checkingWorkspace ? 'Verifying session…' : 'Enter Workspace'}{' '}
                <Icon name="arrow" />
              </a>
            </div>
          </div>
          <div
            className="reserve-scene"
            role="img"
            aria-label="Illustration: customer cash buffer and yield vault."
          >
            <div className="scene-grid" />
            <div className="scene-card vault-card">
              <div className="card-meta">
                <span>
                  <Icon name="vault" /> YIELD VAULT
                </span>
                <span>01 / 02</span>
              </div>
              <div className="card-amount">
                5.00<small> % per year</small>
              </div>
              <div className="card-foot">
                <span>PUT SURPLUS TO WORK</span>
                <Icon name="lock" />
              </div>
            </div>
            <div className="flow-dots">
              <i />
              <i />
              <i />
              <i />
            </div>
            <div className="scene-card buffer-card">
              <div className="card-meta">
                <span>
                  <Icon name="wallet" /> CASH BUFFER
                </span>
                <span>02 / 02</span>
              </div>
              <div className="card-amount">
                Ready.<small> When it matters.</small>
              </div>
              <div className="card-foot">
                <span>LIQUIDITY FIRST. ALWAYS.</span>
                <Icon name="shield" />
              </div>
            </div>
          </div>
          <div className="hero-usp-ticker">
            <CurvedLoop
              marqueeText="PREDICT CASH NEEDS ₹ PROTECT PAYOUTS ₹ INVEST ELIGIBLE SURPLUS"
              shape="line"
              speed={0.85}
              curveAmount={0}
              direction="left"
              fontSize={24}
              fontWeight={700}
              letterSpacing={0.12}
              separator="₹"
              outline={false}
              scrollBoost={0}
              edgeFade={true}
              interactive={false}
              pauseOnHover={false}
              separatorColor="#214F91"
              color="#10213A"
            />
          </div>
        </section>
        <section className="premise" aria-label="Problem assumptions">
          <div className="premise-container">
            <div className="premise-grid">
              <div className="premise-card">
                <div className="premise-heading">TRANSACTION FLOW</div>
                <strong className="premise-value">₹2 crore</strong>
                <span className="premise-desc">
                  Illustrative gross movement per hour
                </span>
              </div>
              <div className="premise-card">
                <div className="premise-heading">VAULT YIELD</div>
                <strong className="premise-value">5.0%</strong>
                <span className="premise-desc">Assumed annual return</span>
              </div>
              <div className="premise-card">
                <div className="premise-heading">LOCK PERIOD</div>
                <strong className="premise-value">24h</strong>
                <span className="premise-desc">
                  Default simulated investment term
                </span>
              </div>
            </div>
          </div>
        </section>
        <section className="method" id="method">
          <div className="method-head">
            <div>
              <div className="eyebrow">FROM UNCERTAINTY TO DECISION</div>
              <h2>
                Keep enough.
                <br />
                Put the rest to work.
              </h2>
            </div>
            <p className="method-head-desc">
              Turn hourly cash-flow forecasts into a time-aware reserve and an
              explainable sweep recommendation—keeping liquidity available for
              upcoming obligations while identifying surplus eligible to earn
              yield.
            </p>
          </div>
          <TimelineWorkflow />
        </section>
      </main>
      <footer className="landing-footer">
        <span>© 2026 Reserve Juggler · Treasury intelligence simulation</span>
        <span>
          Forecasts estimate risk. They do not guarantee payouts.
          <br />
          Bank connectivity and production execution are not enabled.
        </span>
      </footer>
    </div>
  );
};
