import React, { useEffect, useId, useRef, useState } from 'react';
import './CurvedLoop.css';

export interface CurvedLoopProps {
  marqueeText?: string;
  shape?: 'line' | 'wave' | 'arc';
  speed?: number;
  curveAmount?: number;
  direction?: 'left' | 'right';
  fontSize?: number;
  fontWeight?: number | string;
  letterSpacing?: number;
  separator?: string;
  outline?: boolean;
  scrollBoost?: number;
  edgeFade?: number | boolean;
  interactive?: boolean;
  pauseOnHover?: boolean;
  separatorColor?: string | null;
  color?: string | null;
  className?: string;
  style?: React.CSSProperties;
}

export const CurvedLoop: React.FC<CurvedLoopProps> = ({
  marqueeText = 'PREDICT CASH NEEDS ₹ PROTECT PAYOUTS ₹ INVEST ELIGIBLE SURPLUS',
  shape = 'line',
  speed = 0.85,
  curveAmount = 0,
  direction = 'left',
  fontSize = 22,
  fontWeight = 700,
  letterSpacing = 0.12,
  separator = '₹',
  outline = false,
  edgeFade = true,
  separatorColor = '#214F91',
  color = '#10213A',
  className = '',
  style
}) => {
  const uniqueId = useId().replace(/[:]/g, '');
  const pathId = `curve-path-${uniqueId}`;
  const textPathRef = useRef<SVGTextPathElement>(null);
  const textRef = useRef<SVGTextElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [currentFontSize, setCurrentFontSize] = useState(fontSize);

  // Responsive font size adjustment
  useEffect(() => {
    const updateSize = () => {
      const width = window.innerWidth;
      if (width <= 520) {
        setCurrentFontSize(Math.max(13, Math.round(fontSize * 0.65)));
      } else if (width <= 768) {
        setCurrentFontSize(Math.max(16, Math.round(fontSize * 0.8)));
      } else if (width <= 1200) {
        setCurrentFontSize(Math.max(18, Math.round(fontSize * 0.92)));
      } else {
        setCurrentFontSize(fontSize);
      }
    };
    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, [fontSize]);

  // Compute SVG curve path d attribute based on shape
  const yCenter = 35;
  let pathD = `M -400 ${yCenter} L 2600 ${yCenter}`;
  if (shape === 'wave') {
    const waveAmp = curveAmount || 6;
    pathD = `M -400 ${yCenter} Q 100 ${yCenter - waveAmp}, 600 ${yCenter} T 1600 ${yCenter} T 2600 ${yCenter}`;
  } else if (shape === 'arc') {
    const arcHeight = curveAmount || 8;
    pathD = `M -400 ${yCenter + arcHeight} Q 720 ${yCenter - arcHeight}, 1840 ${yCenter + arcHeight}`;
  }

  // Parse marquee text into segments separated by separator symbol
  const rawSegments = marqueeText
    .split(separator)
    .map(s => s.trim())
    .filter(Boolean);

  const repetitions = 4;

  // Continuous marquee animation using requestAnimationFrame
  useEffect(() => {
    const textPath = textPathRef.current;
    const textElem = textRef.current;
    if (!textPath || !textElem) return;

    // Check prefers-reduced-motion
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (mediaQuery.matches) {
      textPath.setAttribute('startOffset', '0px');
      return;
    }

    let animationFrameId: number;
    let lastTime = performance.now();
    let currentOffset = 0;

    // Measure length of one complete repetition
    let singleRepetitionLength = 0;
    try {
      const totalLength = textElem.getComputedTextLength();
      if (totalLength > 0) {
        singleRepetitionLength = totalLength / repetitions;
      }
    } catch {
      singleRepetitionLength = 700;
    }

    if (!singleRepetitionLength || singleRepetitionLength <= 0) {
      singleRepetitionLength = 700;
    }

    const animate = (time: number) => {
      const delta = Math.min(time - lastTime, 40);
      lastTime = time;

      // Smooth horizontal velocity in px/sec
      const pixelsPerSecond = 50 * speed;
      const step = (pixelsPerSecond * delta) / 1000;

      if (direction === 'left') {
        currentOffset -= step;
        if (currentOffset <= -singleRepetitionLength) {
          currentOffset += singleRepetitionLength;
        }
      } else {
        currentOffset += step;
        if (currentOffset >= singleRepetitionLength) {
          currentOffset -= singleRepetitionLength;
        }
      }

      textPath.setAttribute('startOffset', `${currentOffset}px`);
      animationFrameId = requestAnimationFrame(animate);
    };

    animationFrameId = requestAnimationFrame(animate);

    const handleMotionChange = (e: MediaQueryListEvent) => {
      if (e.matches) {
        cancelAnimationFrame(animationFrameId);
        textPath.setAttribute('startOffset', '0px');
      } else {
        lastTime = performance.now();
        animationFrameId = requestAnimationFrame(animate);
      }
    };

    mediaQuery.addEventListener('change', handleMotionChange);

    return () => {
      cancelAnimationFrame(animationFrameId);
      mediaQuery.removeEventListener('change', handleMotionChange);
    };
  }, [speed, direction, repetitions, currentFontSize, marqueeText]);

  return (
    <div
      ref={containerRef}
      className={`curved-loop-jacket ${className}`}
      style={style}
      role="region"
      aria-label="Core Capabilities: Predict cash needs, protect payouts, invest eligible surplus"
    >
      {Boolean(edgeFade) && (
        <>
          <div className="curved-loop-fade-left" aria-hidden="true" />
          <div className="curved-loop-fade-right" aria-hidden="true" />
        </>
      )}

      {/* Screen reader only announcement to prevent repeating text */}
      <span className="sr-only" style={{ position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0,0,0,0)', border: 0 }}>
        Predict cash needs ₹ Protect payouts ₹ Invest eligible surplus
      </span>

      <svg
        className="curved-loop-svg"
        viewBox="0 0 1440 70"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <defs>
          <path id={pathId} d={pathD} fill="none" />
        </defs>

        <text
          ref={textRef}
          className="curved-loop-text"
          style={{
            fontSize: `${currentFontSize}px`,
            fontWeight,
            letterSpacing: typeof letterSpacing === 'number' ? `${letterSpacing}em` : letterSpacing,
            stroke: outline ? color || 'currentColor' : 'none',
            strokeWidth: outline ? '1px' : '0'
          }}
        >
          <textPath
            ref={textPathRef}
            href={`#${pathId}`}
            startOffset="0px"
          >
            {Array.from({ length: repetitions }).map((_, repIdx) => (
              <React.Fragment key={repIdx}>
                {rawSegments.map((segment, segIdx) => (
                  <React.Fragment key={`${repIdx}-${segIdx}`}>
                    <tspan fill={color || 'var(--navy)'}>
                      {segment}{' '}
                    </tspan>
                    <tspan
                      fill={separatorColor || 'var(--blue)'}
                      className="curved-loop-separator"
                    >
                      {separator}{' '}
                    </tspan>
                  </React.Fragment>
                ))}
              </React.Fragment>
            ))}
          </textPath>
        </text>
      </svg>
    </div>
  );
};

export default CurvedLoop;
