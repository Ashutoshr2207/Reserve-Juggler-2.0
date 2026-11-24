import React, { useEffect, useRef, useState } from 'react';
import { Icon } from '../common/Icon';

interface WorkflowStep {
  step: string;
  stageName: string;
  title: string;
  description: string;
  icon: string;
  tags: string[];
}

const WORKFLOW_STEPS: WorkflowStep[] = [
  {
    step: '01',
    stageName: 'ANTICIPATE',
    title: "See what's coming.",
    description:
      'Forecast hourly deposits and withdrawals, reveal expected cash-flow swings, and assess uncertainty over the next 72 hours.',
    icon: 'chart',
    tags: ['Hourly SARIMAX Forecast', '72h Horizon', 'Confidence Bands']
  },
  {
    step: '02',
    stageName: 'PROTECT',
    title: 'Reserve what matters.',
    description:
      'Account for upcoming payments, projected drawdowns, safety buffers, and vault lock periods before committing cash.',
    icon: 'shield',
    tags: ['Drawdown Protection', 'Buffer Floor', 'Lock Period Safety']
  },
  {
    step: '03',
    stageName: 'ALLOCATE',
    title: 'Make surplus productive.',
    description:
      'Compare eligible investment terms, account for fees and maturity, and simulate sweeps with decisions recorded in an audit ledger.',
    icon: 'vault',
    tags: ['Yield Optimization', 'Simulated Sweeps', 'Audit Ledger']
  }
];

export const TimelineWorkflow: React.FC = () => {
  const [revealed, setRevealed] = useState<boolean[]>([false, false, false]);
  const [activeStage, setActiveStage] = useState<number>(1);
  const rowsRef = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    // Respect reduced motion
    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (prefersReducedMotion) {
      setRevealed([true, true, true]);
      setActiveStage(1);
      return;
    }

    const elements = rowsRef.current.filter(Boolean) as HTMLDivElement[];
    if (elements.length === 0) return;

    // 1. Reveal observer: fade & slide into view when near viewport
    const revealObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const index = Number(entry.target.getAttribute('data-stage-index'));
            if (!isNaN(index)) {
              setRevealed((prev) => {
                if (prev[index]) return prev;
                const next = [...prev];
                next[index] = true;
                return next;
              });
            }
          }
        });
      },
      { threshold: 0.15, rootMargin: '0px 0px -40px 0px' }
    );

    elements.forEach((el) => revealObserver.observe(el));

    // 2. Active stage tracking based on scroll position
    const handleScroll = () => {
      const triggerY = window.innerHeight * 0.45;
      let closestStage = 1;
      let minDistance = Infinity;

      elements.forEach((el, idx) => {
        const rect = el.getBoundingClientRect();
        const centerY = rect.top + rect.height / 2;
        const distance = Math.abs(centerY - triggerY);

        if (rect.top <= triggerY + 140 && distance < minDistance) {
          minDistance = distance;
          closestStage = idx + 1;
        }
      });

      setActiveStage(closestStage);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    return () => {
      revealObserver.disconnect();
      window.removeEventListener('scroll', handleScroll);
    };
  }, []);

  // Compute progress line height percentage:
  // Stage 1 active: 16%, Stage 2 active: 58%, Stage 3 active: 100%
  const progressPercent = activeStage === 1 ? 18 : activeStage === 2 ? 60 : 100;

  return (
    <div className="timeline-workflow" aria-label="Treasury workflow timeline">
      {/* Central connected vertical timeline spine */}
      <div className="timeline-spine" aria-hidden="true">
        <div className="timeline-spine-track" />
        <div
          className="timeline-spine-progress"
          style={{ height: `${progressPercent}%` }}
        />
      </div>

      {WORKFLOW_STEPS.map((step, idx) => {
        const stageNum = idx + 1;
        const isRevealed = revealed[idx];
        const isLeft = idx % 2 === 0; // Steps 1 and 3 on left, Step 2 on right
        const status =
          activeStage === stageNum
            ? 'active'
            : activeStage > stageNum
            ? 'completed'
            : 'upcoming';

        return (
          <div
            key={step.step}
            ref={(el) => {
              rowsRef.current[idx] = el;
            }}
            data-stage-index={idx}
            className={`timeline-row ${
              isLeft ? 'timeline-row-left' : 'timeline-row-right'
            } ${status} ${isRevealed ? 'is-revealed' : ''}`}
          >
            {/* Left slot */}
            {isLeft ? (
              <div className="timeline-card-col">
                <article
                  className={`timeline-card ${status} ${
                    isRevealed ? 'card-revealed' : ''
                  }`}
                  aria-labelledby={`step-title-${step.step}`}
                >
                  <div className="timeline-card-header">
                    <span className="step-badge">
                      <span className="step-badge-num">{step.step}</span>
                      <span className="step-badge-sep">/</span>
                      <span className="step-badge-name">{step.stageName}</span>
                    </span>
                    <span className="step-icon-bubble" aria-hidden="true">
                      <Icon name={step.icon} />
                    </span>
                  </div>

                  <h3 id={`step-title-${step.step}`} className="timeline-card-title">
                    {step.title}
                  </h3>

                  <p className="timeline-card-desc">{step.description}</p>

                  <div className="timeline-card-tags" aria-label="Stage characteristics">
                    {step.tags.map((tag) => (
                      <span key={tag} className="timeline-tag">
                        {tag}
                      </span>
                    ))}
                  </div>
                </article>
              </div>
            ) : (
              <div className="timeline-empty-col" aria-hidden="true" />
            )}

            {/* Center marker slot with connector arms */}
            <div className="timeline-marker-col">
              <div
                className={`timeline-connector timeline-connector-${
                  isLeft ? 'left' : 'right'
                }`}
                aria-hidden="true"
              />
              <div
                className={`timeline-marker ${status}`}
                role="status"
                aria-label={`Step ${step.step}: ${step.stageName} (${status})`}
              >
                <span className="marker-number">{step.step}</span>
              </div>
            </div>

            {/* Right slot */}
            {!isLeft ? (
              <div className="timeline-card-col">
                <article
                  className={`timeline-card ${status} ${
                    isRevealed ? 'card-revealed' : ''
                  }`}
                  aria-labelledby={`step-title-${step.step}`}
                >
                  <div className="timeline-card-header">
                    <span className="step-badge">
                      <span className="step-badge-num">{step.step}</span>
                      <span className="step-badge-sep">/</span>
                      <span className="step-badge-name">{step.stageName}</span>
                    </span>
                    <span className="step-icon-bubble" aria-hidden="true">
                      <Icon name={step.icon} />
                    </span>
                  </div>

                  <h3 id={`step-title-${step.step}`} className="timeline-card-title">
                    {step.title}
                  </h3>

                  <p className="timeline-card-desc">{step.description}</p>

                  <div className="timeline-card-tags" aria-label="Stage characteristics">
                    {step.tags.map((tag) => (
                      <span key={tag} className="timeline-tag">
                        {tag}
                      </span>
                    ))}
                  </div>
                </article>
              </div>
            ) : (
              <div className="timeline-empty-col" aria-hidden="true" />
            )}
          </div>
        );
      })}
    </div>
  );
};

export default TimelineWorkflow;
