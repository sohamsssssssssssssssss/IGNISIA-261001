import React from 'react';

interface TopReason {
  feature: string;
  feature_key: string;
  reason: string;
  direction: string;
  score_impact: number;
}

interface ComparePayload {
  gstin: string;
  company_name: string;
  credit_score: number;
  risk_band: { band: string };
  top_reasons: TopReason[];
  feature_vector?: Record<string, number>;
  percentile?: {
    score_percentile: number;
    statement?: string;
  };
}

interface ComparisonPanelProps {
  pinned: ComparePayload;
  current: ComparePayload;
}

function displayMetric(value: number | undefined, percent?: boolean): string {
  if (value === undefined || value === null) return 'n/a';
  if (percent) return `${Math.round(Number(value) * 100)}%`;
  return `${Math.round(Number(value) * 100) / 100}`;
}

function impactColor(leftImpact: number | null, rightImpact: number | null, side: 'left' | 'right'): string {
  const left = leftImpact ?? Number.NEGATIVE_INFINITY;
  const right = rightImpact ?? Number.NEGATIVE_INFINITY;
  if (left === right) return 'var(--text)';
  const winner = left > right ? 'left' : 'right';
  return winner === side ? 'var(--green)' : 'var(--red)';
}

function buildReasonDiffs(pinned: ComparePayload, current: ComparePayload) {
  const pinnedMap = new Map((pinned.top_reasons || []).map((reason) => [reason.feature_key, reason]));
  const currentMap = new Map((current.top_reasons || []).map((reason) => [reason.feature_key, reason]));
  const orderedKeys = Array.from(
    new Set([
      ...(pinned.top_reasons || []).map((reason) => reason.feature_key),
      ...(current.top_reasons || []).map((reason) => reason.feature_key),
    ]),
  );

  return orderedKeys.slice(0, 8).map((featureKey) => {
    const left = pinnedMap.get(featureKey) || null;
    const right = currentMap.get(featureKey) || null;
    const label = right?.feature || left?.feature || featureKey.replace(/_/g, ' ');
    return {
      featureKey,
      label,
      pinned: left,
      current: right,
      delta: (right?.score_impact || 0) - (left?.score_impact || 0),
    };
  });
}

export const ComparisonPanel: React.FC<ComparisonPanelProps> = ({ pinned, current }) => {
  const delta = current.credit_score - pinned.credit_score;
  const comparisonFields = [
    { key: 'credit_score', label: 'Credit Score' },
    { key: 'gst_filing_rate', label: 'GST Filing Rate', percent: true },
    { key: 'upi_avg_daily_txns', label: 'UPI Txns / Day' },
    { key: 'upi_volume_growth', label: 'Revenue Growth Proxy', percent: true },
  ];
  const reasonDiffs = buildReasonDiffs(pinned, current);

  return (
    <div className="msme-card">
      <div className="msme-card-title">Comparison Mode</div>
      <div className="msme-grid-2" style={{ marginBottom: 14 }}>
        {[pinned, current].map((item) => (
          <div className="msme-metric-card" key={item.gstin} style={{ textAlign: 'left' }}>
            <div className="msme-inline-meta" style={{ marginBottom: 8 }}>{item.company_name}</div>
            <div className="msme-trend-value">{item.credit_score}</div>
            <div className="msme-reason-meta" style={{ opacity: 0.8 }}>{item.risk_band.band.replace(/_/g, ' ')}</div>
            <div className="msme-reason-meta" style={{ opacity: 0.8, marginTop: 8 }}>
              {item.percentile?.statement || `Better than ${item.percentile?.score_percentile ?? Math.max(1, Math.min(99, Math.round(((item.credit_score - 300) / 600) * 100)))}% of the peer group`}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr', gap: 12, fontFamily: 'var(--mono)', fontSize: '10px', letterSpacing: '1px', color: 'var(--text-dim)', marginBottom: 8 }}>
        <span>METRIC</span>
        <span style={{ textAlign: 'center' }}>{pinned.gstin}</span>
        <span style={{ textAlign: 'center' }}>{current.gstin}</span>
      </div>
      {comparisonFields.map((field) => {
        const pinnedValue = field.key === 'credit_score' ? pinned.credit_score : pinned.feature_vector?.[field.key];
        const currentValue = field.key === 'credit_score' ? current.credit_score : current.feature_vector?.[field.key];
        const currentWins = (currentValue ?? Number.NEGATIVE_INFINITY) > (pinnedValue ?? Number.NEGATIVE_INFINITY);
        return (
          <div key={field.key} className="msme-checklist-row" style={{ paddingBlock: 10 }}>
            <div className="msme-reason-meta" style={{ opacity: 0.9 }}>{field.label}</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, minWidth: 220 }}>
              <div style={{ textAlign: 'center', color: !currentWins ? 'var(--green)' : 'var(--text)' }}>
                {displayMetric(pinnedValue as number | undefined, field.percent)}
                {!currentWins && ' ↑'}
              </div>
              <div style={{ textAlign: 'center', color: currentWins ? 'var(--green)' : 'var(--text)' }}>
                {displayMetric(currentValue as number | undefined, field.percent)}
                {currentWins && ' ↑'}
              </div>
            </div>
          </div>
        );
      })}

      <div className="msme-alert msme-alert--warning" style={{ marginTop: 14 }}>
        Score delta: {delta > 0 ? '+' : ''}{delta} points. The table below explains why the scores differ.
      </div>

      <div style={{ marginTop: 18 }}>
        <div className="msme-card-title" style={{ marginBottom: 10 }}>Top Reason Diff</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr', gap: 12, fontFamily: 'var(--mono)', fontSize: '10px', letterSpacing: '1px', color: 'var(--text-dim)', marginBottom: 8 }}>
          <span>SHAP DRIVER</span>
          <span style={{ textAlign: 'center' }}>{pinned.company_name}</span>
          <span style={{ textAlign: 'center' }}>{current.company_name}</span>
        </div>
        {reasonDiffs.map((row) => (
          <div key={row.featureKey} className="msme-checklist-row" style={{ alignItems: 'start', paddingBlock: 12 }}>
            <div>
              <div className="msme-reason-text" style={{ color: 'var(--text)' }}>{row.label}</div>
              <div className="msme-reason-meta" style={{ opacity: 0.8 }}>
                Delta: {row.delta > 0 ? '+' : ''}{row.delta} pts
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, minWidth: 220 }}>
              <div style={{ color: impactColor(row.pinned?.score_impact ?? null, row.current?.score_impact ?? null, 'left') }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: '10px', marginBottom: 4 }}>
                  {row.pinned ? `${row.pinned.score_impact > 0 ? '+' : ''}${row.pinned.score_impact} pts` : 'Not in top 5'}
                </div>
                <div className="msme-reason-meta" style={{ opacity: 0.9, marginTop: 0 }}>
                  {row.pinned?.reason || 'This factor is not a top driver for the pinned GSTIN.'}
                </div>
              </div>
              <div style={{ color: impactColor(row.pinned?.score_impact ?? null, row.current?.score_impact ?? null, 'right') }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: '10px', marginBottom: 4 }}>
                  {row.current ? `${row.current.score_impact > 0 ? '+' : ''}${row.current.score_impact} pts` : 'Not in top 5'}
                </div>
                <div className="msme-reason-meta" style={{ opacity: 0.9, marginTop: 0 }}>
                  {row.current?.reason || 'This factor is not a top driver for the current GSTIN.'}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
