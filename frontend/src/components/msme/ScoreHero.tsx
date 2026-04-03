import React from 'react';
import { ShieldAlert, AlertTriangle, Clock, Database } from 'lucide-react';

interface ScoreHeroProps {
  creditScore: number;
  riskBand: { band: string; description: string; range: string };
  percentile?: {
    score_percentile: number;
    statement?: string;
  } | null;
  scoreFreshness: string;
  fraudPenaltyApplied: boolean;
  dataSparse: boolean;
  companyName: string;
  gstin: string;
  modelVersion: string;
  topReason?: {
    direction: string;
    reason: string;
  } | null;
}

function scoreColor(score: number): string {
  if (score >= 800) return '#25A05E';
  if (score >= 700) return '#25A05E';
  if (score >= 600) return '#C8A84B';
  if (score >= 500) return '#C97C14';
  return '#C8293A';
}

function bandColor(band: string): string {
  if (band.includes('VERY_LOW')) return '#25A05E';
  if (band.includes('LOW_RISK')) return '#25A05E';
  if (band.includes('MODERATE')) return '#C97C14';
  if (band.includes('HIGH') && !band.includes('VERY')) return '#C8293A';
  return '#C8293A';
}

export const ScoreHero: React.FC<ScoreHeroProps> = ({
  creditScore, riskBand, percentile, scoreFreshness, fraudPenaltyApplied, dataSparse,
  companyName, gstin, modelVersion, topReason,
}) => {
  const color = scoreColor(creditScore);
  const bColor = bandColor(riskBand.band);
  const heroToneClass = topReason?.direction === 'positive'
    ? 'msme-card--top-reason-positive'
    : topReason?.direction === 'negative'
      ? 'msme-card--top-reason-negative'
      : '';

  // Arc gauge
  const radius = 80;
  const cx = 100;
  const cy = 95;
  const startAngle = -140;
  const endAngle = 140;
  const totalAngle = endAngle - startAngle;
  const pct = Math.max(0, Math.min(1, (creditScore - 300) / 600));
  const currentAngle = startAngle + totalAngle * pct;

  const toRad = (d: number) => (d * Math.PI) / 180;
  const arc = (from: number, to: number, r: number) => {
    const x1 = cx + r * Math.cos(toRad(from - 90));
    const y1 = cy + r * Math.sin(toRad(from - 90));
    const x2 = cx + r * Math.cos(toRad(to - 90));
    const y2 = cy + r * Math.sin(toRad(to - 90));
    return `M ${x1} ${y1} A ${r} ${r} 0 ${to - from > 180 ? 1 : 0} 1 ${x2} ${y2}`;
  };

  const nx = cx + (radius - 12) * Math.cos(toRad(currentAngle - 90));
  const ny = cy + (radius - 12) * Math.sin(toRad(currentAngle - 90));

  const freshStr = new Date(scoreFreshness).toLocaleString();

  return (
    <div className={`msme-card ${heroToneClass}`.trim()}>
      <div className="msme-hero-top">
        <div>
          <div style={{ fontFamily: 'var(--serif)', fontSize: '24px', fontWeight: 700 }}>{companyName}</div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: '10px', color: 'var(--text-dim)', letterSpacing: '0.5px', marginTop: 2 }}>{gstin}</div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {fraudPenaltyApplied && (
            <span className="msme-badge msme-badge--danger"><ShieldAlert size={12} /> Fraud Penalty</span>
          )}
          {dataSparse && (
            <span className="msme-badge msme-badge--warning"><Database size={12} /> Sparse Data</span>
          )}
        </div>
      </div>

      <div className="msme-hero-body">
        {/* Arc gauge */}
        <div className="msme-gauge-wrap">
          <svg className="msme-gauge-svg" viewBox="0 0 200 150">
            <path d={arc(startAngle, endAngle, radius)} fill="none" stroke="var(--card-border)" strokeWidth="10" strokeLinecap="round" />
            {pct > 0 && (
              <path d={arc(startAngle, currentAngle, radius)} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round" />
            )}
            <circle cx={nx} cy={ny} r="5" fill={color} />
            <text x={cx - radius - 6} y={cy + 25} fill="var(--text-dim)" fontSize="9" textAnchor="middle" fontFamily="var(--mono)">300</text>
            <text x={cx + radius + 6} y={cy + 25} fill="var(--text-dim)" fontSize="9" textAnchor="middle" fontFamily="var(--mono)">900</text>
          </svg>
          <div className="msme-gauge-center">
            <div className="msme-score-giant" style={{ color }}>{creditScore}</div>
          </div>
        </div>

        {/* Risk band + meta */}
        <div className="msme-hero-meta">
          <div className="msme-risk-pill" style={{ borderColor: bColor, color: bColor }}>
            {riskBand.band.replace(/_/g, ' ')}
          </div>
          <div style={{ fontFamily: 'var(--body)', fontSize: '12px', color: 'var(--text-dim)', maxWidth: 260, lineHeight: 1.5 }}>
            {riskBand.description}
          </div>
          {percentile && (
            <div className="msme-score-sub">
              {percentile.statement || `Better than ${percentile.score_percentile}% of MSMEs in this peer group`}
            </div>
          )}
          {topReason?.reason && (
            <div className={`msme-top-reason msme-top-reason--${topReason.direction === 'positive' ? 'positive' : 'negative'}`}>
              {topReason.reason}
            </div>
          )}
          <div style={{ fontFamily: 'var(--mono)', fontSize: '9px', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: 5, letterSpacing: '0.5px' }}>
            <Clock size={11} /> {freshStr}
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: '9px', color: 'var(--text-dim)', opacity: 0.5, letterSpacing: '0.5px' }}>
            MODEL: {modelVersion}
          </div>
        </div>
      </div>
    </div>
  );
};
