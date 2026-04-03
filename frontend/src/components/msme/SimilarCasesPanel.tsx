import React, { useMemo } from 'react';

type RiskBand = 'Low' | 'Moderate' | 'High' | 'Very High';
type Outcome = 'Repaid' | 'Defaulted' | 'Pending';

export interface SimilarCase {
  id: string;
  gstin: string;
  score: number;
  riskBand: RiskBand;
  outcome: Outcome;
  similarityReason: string;
}

interface SimilarCasesPanelProps {
  cases?: SimilarCase[];
  isLoading?: boolean;
}

const DEMO_CASES: SimilarCase[] = [
  {
    id: 'case-1',
    gstin: '27AABCU9603R1ZM',
    score: 74,
    riskBand: 'Moderate',
    outcome: 'Repaid',
    similarityReason: 'Similar GST filing rate and business age',
  },
  {
    id: 'case-2',
    gstin: '29GGGGG1314R9Z6',
    score: 68,
    riskBand: 'High',
    outcome: 'Defaulted',
    similarityReason: 'Comparable revenue volatility and sector exposure',
  },
  {
    id: 'case-3',
    gstin: '33AAACH7409R1Z5',
    score: 71,
    riskBand: 'High',
    outcome: 'Defaulted',
    similarityReason: 'Matched loan-to-turnover ratio and collateral profile',
  },
];

function truncateGstin(gstin: string): string {
  return `${gstin.slice(0, 6)}*******`;
}

function scoreColor(score: number): string {
  if (score >= 75) return '#10b981';
  if (score >= 55) return '#f59e0b';
  return '#ef4444';
}

function riskBandColor(riskBand: RiskBand): string {
  switch (riskBand) {
    case 'Low':
      return '#10b981';
    case 'Moderate':
      return '#f59e0b';
    case 'High':
      return '#ef4444';
    case 'Very High':
      return '#b91c1c';
    default:
      return '#9ca3af';
  }
}

function outcomeColor(outcome: Outcome): string {
  switch (outcome) {
    case 'Repaid':
      return '#10b981';
    case 'Defaulted':
      return '#ef4444';
    case 'Pending':
      return '#9ca3af';
    default:
      return '#9ca3af';
  }
}

function ScoreRing({ score }: { score: number }) {
  const radius = 18;
  const circumference = 2 * Math.PI * radius;
  const normalized = Math.max(0, Math.min(100, score));
  const offset = circumference - (normalized / 100) * circumference;
  const color = scoreColor(normalized);

  return (
    <div
      style={{
        alignItems: 'center',
        display: 'inline-flex',
        height: 46,
        justifyContent: 'center',
        position: 'relative',
        width: 46,
      }}
    >
      <svg width="46" height="46" viewBox="0 0 46 46" aria-hidden="true">
        <circle
          cx="23"
          cy="23"
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth="4"
        />
        <circle
          cx="23"
          cy="23"
          r={radius}
          fill="none"
          stroke={color}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          strokeWidth="4"
          transform="rotate(-90 23 23)"
        />
      </svg>
      <span
        style={{
          color: '#f8fafc',
          fontFamily: "'DM Mono', monospace",
          fontSize: 10,
          fontWeight: 600,
          left: '50%',
          letterSpacing: '-0.02em',
          position: 'absolute',
          top: '50%',
          transform: 'translate(-50%, -50%)',
        }}
      >
        {normalized}
      </span>
    </div>
  );
}

function StatusPill({
  label,
  color,
  glow = false,
}: {
  label: string;
  color: string;
  glow?: boolean;
}) {
  return (
    <span
      style={{
        alignItems: 'center',
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 999,
        color: '#dbe4f0',
        display: 'inline-flex',
        fontFamily: "'DM Mono', monospace",
        fontSize: 11,
        fontWeight: 600,
        gap: 7,
        letterSpacing: '0.04em',
        lineHeight: 1,
        padding: '6px 10px',
        textTransform: 'uppercase',
      }}
    >
      <span
        style={{
          background: color,
          borderRadius: '50%',
          boxShadow: glow ? `0 0 10px ${color}66` : 'none',
          display: 'inline-block',
          height: 7,
          width: 7,
        }}
      />
      {label}
    </span>
  );
}

function InfoGlyph() {
  return (
    <span
      aria-hidden="true"
      style={{
        alignItems: 'center',
        border: '1px solid rgba(129,140,248,0.35)',
        borderRadius: '50%',
        color: '#818cf8',
        display: 'inline-flex',
        fontFamily: "'DM Mono', monospace",
        fontSize: 10,
        height: 16,
        justifyContent: 'center',
        width: 16,
      }}
    >
      i
    </span>
  );
}

function HexIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <polygon
        points="9,1.5 15,5 15,13 9,16.5 3,13 3,5"
        fill="rgba(129,140,248,0.16)"
        stroke="#818cf8"
        strokeWidth="1.2"
      />
    </svg>
  );
}

function SkeletonCard({ delay }: { delay: number }) {
  return (
    <div className="similar-cases-card similar-cases-card--skeleton" style={{ animationDelay: `${delay}ms` }}>
      <div className="similar-cases-card__top">
        <div className="similar-cases-skeleton similar-cases-skeleton--ring" />
        <div className="similar-cases-card__top-copy">
          <div className="similar-cases-skeleton similar-cases-skeleton--gstin" />
          <div className="similar-cases-skeleton similar-cases-skeleton--score" />
        </div>
      </div>
      <div className="similar-cases-card__pill-row">
        <div className="similar-cases-skeleton similar-cases-skeleton--pill" />
        <div className="similar-cases-skeleton similar-cases-skeleton--pill-short" />
      </div>
      <div className="similar-cases-card__divider" />
      <div className="similar-cases-card__reason-row">
        <div className="similar-cases-skeleton similar-cases-skeleton--icon" />
        <div className="similar-cases-card__reason-copy">
          <div className="similar-cases-skeleton similar-cases-skeleton--reason" />
          <div className="similar-cases-skeleton similar-cases-skeleton--reason-short" />
        </div>
      </div>
    </div>
  );
}

export default function SimilarCasesPanel({
  cases,
  isLoading = false,
}: SimilarCasesPanelProps) {
  const resolvedCases = useMemo(() => (cases && cases.length ? cases.slice(0, 3) : DEMO_CASES), [cases]);

  const summary = useMemo(() => {
    const defaulted = resolvedCases.filter((item) => item.outcome === 'Defaulted').length;
    const repaid = resolvedCases.filter((item) => item.outcome === 'Repaid').length;
    return {
      defaulted,
      repaid,
      total: resolvedCases.length,
    };
  }, [resolvedCases]);

  return (
    <section
      aria-label="Similar Cases"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
      }}
    >
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:ital,wght@0,400;0,500;1,400&family=Sora:wght@600;700&display=swap');

        .similar-cases-header {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .similar-cases-header__title {
          color: #f8fafc;
          font-family: 'Sora', sans-serif;
          font-size: 1rem;
          font-weight: 600;
          letter-spacing: -0.02em;
        }

        .similar-cases-header__subtitle {
          color: #818cf8;
          font-family: 'DM Mono', monospace;
          font-size: 0.72rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }

        .similar-cases-grid {
          display: flex;
          flex-wrap: wrap;
          gap: 12px;
        }

        .similar-cases-card {
          background: rgba(30,34,54,0.95);
          border: 1px solid rgba(255,255,255,0.07);
          border-radius: 16px;
          box-sizing: border-box;
          color: #e5edf8;
          display: flex;
          flex: 1 1 0;
          flex-direction: column;
          gap: 14px;
          min-width: 220px;
          overflow: hidden;
          padding: 16px;
          position: relative;
          transform: translateY(14px);
          opacity: 0;
          animation: similar-cases-fade-up 420ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
          transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
        }

        .similar-cases-card::before {
          content: '';
          height: 2px;
          left: 0;
          position: absolute;
          right: 0;
          top: 0;
        }

        .similar-cases-card:hover {
          border-color: rgba(255,255,255,0.12);
          box-shadow: 0 10px 26px rgba(0,0,0,0.18);
          transform: translateY(-2px);
        }

        .similar-cases-card--repaid::before {
          background: linear-gradient(90deg, #10b981 0%, rgba(16,185,129,0) 100%);
        }

        .similar-cases-card--defaulted::before {
          background: linear-gradient(90deg, #ef4444 0%, rgba(239,68,68,0) 100%);
        }

        .similar-cases-card--pending::before {
          background: linear-gradient(90deg, #9ca3af 0%, rgba(156,163,175,0) 100%);
        }

        .similar-cases-card__top {
          align-items: center;
          display: flex;
          gap: 12px;
        }

        .similar-cases-card__top-copy {
          display: flex;
          flex-direction: column;
          gap: 6px;
          min-width: 0;
        }

        .similar-cases-card__gstin {
          color: #f8fafc;
          font-family: 'DM Mono', monospace;
          font-size: 0.78rem;
          font-weight: 500;
          letter-spacing: 0.08em;
        }

        .similar-cases-card__score {
          color: #94a3b8;
          font-family: 'DM Mono', monospace;
          font-size: 0.72rem;
        }

        .similar-cases-card__pill-row {
          align-items: center;
          display: flex;
          gap: 8px;
          justify-content: space-between;
        }

        .similar-cases-card__divider {
          border-top: 1px solid rgba(255,255,255,0.08);
        }

        .similar-cases-card__reason-row {
          align-items: flex-start;
          display: flex;
          gap: 10px;
        }

        .similar-cases-card__reason {
          color: #cbd5e1;
          font-family: 'DM Sans', sans-serif;
          font-size: 0.84rem;
          font-style: italic;
          line-height: 1.45;
          margin: 0;
        }

        .similar-cases-summary {
          align-items: center;
          background: rgba(129,140,248,0.08);
          border: 1px solid rgba(129,140,248,0.16);
          border-radius: 14px;
          color: #d7ddf5;
          display: flex;
          gap: 10px;
          padding: 12px 14px;
        }

        .similar-cases-summary__text {
          font-family: 'DM Sans', sans-serif;
          font-size: 0.84rem;
          line-height: 1.5;
        }

        .similar-cases-summary__text strong {
          color: #f8fafc;
          font-weight: 500;
        }

        .similar-cases-skeleton {
          animation: similar-cases-shimmer 1.5s linear infinite;
          background: linear-gradient(
            90deg,
            rgba(255,255,255,0.06) 25%,
            rgba(255,255,255,0.12) 50%,
            rgba(255,255,255,0.06) 75%
          );
          background-size: 800px 100%;
          border-radius: 999px;
        }

        .similar-cases-card--skeleton {
          animation-name: similar-cases-fade-up;
        }

        .similar-cases-skeleton--ring {
          border-radius: 50%;
          height: 46px;
          width: 46px;
        }

        .similar-cases-skeleton--gstin {
          height: 11px;
          width: 110px;
        }

        .similar-cases-skeleton--score {
          height: 10px;
          width: 76px;
        }

        .similar-cases-skeleton--pill {
          height: 28px;
          width: 104px;
        }

        .similar-cases-skeleton--pill-short {
          height: 28px;
          width: 92px;
        }

        .similar-cases-skeleton--icon {
          border-radius: 50%;
          height: 16px;
          width: 16px;
        }

        .similar-cases-card__reason-copy {
          display: flex;
          flex: 1;
          flex-direction: column;
          gap: 6px;
        }

        .similar-cases-skeleton--reason {
          height: 11px;
          width: 100%;
        }

        .similar-cases-skeleton--reason-short {
          height: 11px;
          width: 72%;
        }

        @keyframes similar-cases-fade-up {
          from {
            opacity: 0;
            transform: translateY(14px);
          }

          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes similar-cases-shimmer {
          0% {
            background-position: -400px 0;
          }

          100% {
            background-position: 400px 0;
          }
        }

        @media (max-width: 720px) {
          .similar-cases-card {
            min-width: 100%;
          }
        }
      `}</style>

      <header className="similar-cases-header">
        <div className="similar-cases-header__title">Similar Cases</div>
        <div className="similar-cases-header__subtitle">RAG retrieval · top 3</div>
      </header>

      <div className="similar-cases-grid">
        {isLoading
          ? [80, 200, 320].map((delay) => <SkeletonCard key={delay} delay={delay} />)
          : resolvedCases.map((item, index) => {
            const outcomeClass = item.outcome.toLowerCase();
            const ringColor = scoreColor(item.score);
            return (
              <article
                key={item.id}
                className={`similar-cases-card similar-cases-card--${outcomeClass}`}
                style={{ animationDelay: `${[80, 200, 320][index] ?? 80}ms` }}
              >
                <div className="similar-cases-card__top">
                  <ScoreRing score={item.score} />
                  <div className="similar-cases-card__top-copy">
                    <div className="similar-cases-card__gstin">{truncateGstin(item.gstin)}</div>
                    <div className="similar-cases-card__score" style={{ color: ringColor }}>
                      Score received: {item.score}
                    </div>
                  </div>
                </div>

                <div className="similar-cases-card__pill-row">
                  <StatusPill label={item.riskBand} color={riskBandColor(item.riskBand)} />
                  <StatusPill label={item.outcome} color={outcomeColor(item.outcome)} glow />
                </div>

                <div className="similar-cases-card__divider" />

                <div className="similar-cases-card__reason-row">
                  <InfoGlyph />
                  <p className="similar-cases-card__reason">{item.similarityReason}</p>
                </div>
              </article>
            );
          })}
      </div>

      {!isLoading && resolvedCases.length > 0 ? (
        <div className="similar-cases-summary">
          <HexIcon />
          <div className="similar-cases-summary__text">
            Of the <strong>{summary.total}</strong> most similar businesses — <strong>{summary.defaulted} defaulted</strong>, <strong>{summary.repaid} repaid</strong>. Use this pattern to calibrate your decision.
          </div>
        </div>
      ) : null}
    </section>
  );
}
