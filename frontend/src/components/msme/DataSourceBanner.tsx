import React from 'react';
import { DatabaseZap, RefreshCcw, AlertTriangle } from 'lucide-react';

interface PipelineSource {
  source_status: string;
  description: string;
  freshness: string;
}

interface DataSources {
  source_mode: string;
  judge_note: string;
  pipelines: Record<string, PipelineSource>;
}

interface DataSourceBannerProps {
  dataSources?: DataSources | null;
  onRefresh?: (stream?: string) => void;
  refreshing?: boolean;
}

function freshnessMeta(ts: string): { label: string; tone: 'green' | 'amber' | 'red'; manualReview: boolean } {
  const ageMs = Date.now() - new Date(ts).getTime();
  const ageMinutes = Math.max(0, Math.round(ageMs / 60000));
  if (ageMinutes < 30) return { label: `Updated ${ageMinutes} min ago`, tone: 'green', manualReview: false };
  const hours = Math.round(ageMinutes / 60);
  if (hours <= 4) return { label: `Updated ${hours} hr ago`, tone: 'amber', manualReview: true };
  return { label: `Updated ${hours} hr ago — refresh recommended`, tone: 'red', manualReview: true };
}

export const DataSourceBanner: React.FC<DataSourceBannerProps> = ({ dataSources, onRefresh, refreshing }) => {
  const pipelineEntries = Object.entries(dataSources?.pipelines ?? {});
  const anyManualReview = pipelineEntries.some(([, source]) => freshnessMeta(source.freshness).manualReview);
  const streamMap: Record<string, string> = {
    gst_velocity: 'gst',
    upi_cadence: 'upi',
    eway_bill: 'eway',
  };

  if (!dataSources) {
    return (
      <div className="msme-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
          <div className="msme-card-title" style={{ marginBottom: 0 }}>Data Provenance</div>
          {onRefresh && (
            <button className="msme-btn msme-btn--ghost" onClick={() => onRefresh()} disabled={refreshing}>
              <RefreshCcw size={12} className={refreshing ? 'msme-spin' : ''} />
              {refreshing ? 'Refreshing...' : 'Refresh Data'}
            </button>
          )}
        </div>
        <div className="msme-alert msme-alert--warning">
          <AlertTriangle size={12} />
          Data provenance is temporarily unavailable for this response. Refresh the score to reload pipeline metadata.
        </div>
      </div>
    );
  }

  return (
    <div className="msme-card">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
        <div className="msme-card-title" style={{ marginBottom: 0 }}>Data Provenance</div>
        {onRefresh && (
          <button className="msme-btn msme-btn--ghost" onClick={() => onRefresh()} disabled={refreshing}>
            <RefreshCcw size={12} className={refreshing ? 'msme-spin' : ''} />
            {refreshing ? 'Refreshing...' : 'Refresh Data'}
          </button>
        )}
      </div>
      <div className="msme-alert msme-alert--warning" style={{ marginBottom: 14 }}>
        <DatabaseZap size={12} />
        {dataSources.judge_note}
      </div>
      {anyManualReview && (
        <div className="msme-alert msme-alert--warning" style={{ marginBottom: 14 }}>
          <AlertTriangle size={12} />
          One or more data streams are stale. Manual review is required until inputs are refreshed.
        </div>
      )}
      <div className="msme-grid-3">
        {pipelineEntries.map(([key, source]) => (
          <div className="msme-metric-card" key={key}>
            <div className="msme-metric-label">{key.replace(/_/g, ' ')}</div>
            {(() => {
              const freshness = freshnessMeta(source.freshness);
              const color = freshness.tone === 'green' ? 'var(--green)' : freshness.tone === 'amber' ? 'var(--amber)' : 'var(--red)';
              return (
                <div className="msme-inline-meta" style={{ justifyContent: 'center', marginBottom: 8, color }}>
                  {freshness.label}
                </div>
              );
            })()}
            <div style={{ fontFamily: 'var(--body)', fontSize: '11px', color: 'var(--text-dim)', lineHeight: 1.5 }}>
              {source.description}
            </div>
            {onRefresh && streamMap[key] && (
              <button
                className="msme-btn msme-btn--ghost"
                style={{ marginTop: 10, width: '100%', justifyContent: 'center' }}
                onClick={() => onRefresh(streamMap[key])}
                disabled={refreshing}
              >
                <RefreshCcw size={12} className={refreshing ? 'msme-spin' : ''} />
                Refresh {key.replace(/_/g, ' ')}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
