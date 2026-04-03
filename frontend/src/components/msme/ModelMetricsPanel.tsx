import React from 'react';
import { BarChart3 } from 'lucide-react';

interface ModelMetrics {
  accuracy?: number;
  auc?: number;
  precision?: number;
  recall?: number;
  positive_rate?: number;
}

interface ModelMetricsPanelProps {
  modelVersion: string;
  backend?: string;
  metrics?: ModelMetrics;
}

const metricColor = (value?: number): string => {
  if (value == null) return 'var(--text-dim)';
  if (value >= 0.85) return 'var(--green)';
  if (value >= 0.7) return 'var(--amber)';
  return 'var(--red)';
};

export const ModelMetricsPanel: React.FC<ModelMetricsPanelProps> = ({ modelVersion, backend, metrics }) => {
  const cards = [
    { label: 'AUC', value: metrics?.auc },
    { label: 'Accuracy', value: metrics?.accuracy },
    { label: 'Precision', value: metrics?.precision },
    { label: 'Recall', value: metrics?.recall },
  ];

  return (
    <div className="msme-card">
      <div className="msme-card-title">Model Evaluation</div>
      <div className="msme-inline-meta" style={{ marginBottom: 14 }}>
        <BarChart3 size={12} />
        {modelVersion} {backend ? `· ${backend}` : ''}
      </div>
      <div className="msme-grid-2">
        {cards.map(card => (
          <div className="msme-metric-card" key={card.label}>
            <div className="msme-metric-label">{card.label}</div>
            <div className="msme-trend-value" style={{ color: metricColor(card.value) }}>
              {card.value != null ? card.value.toFixed(3) : 'N/A'}
            </div>
          </div>
        ))}
      </div>
      <div className="msme-alert msme-alert--warning" style={{ marginTop: 14 }}>
        Current metrics are measured on synthetic validation data in demo mode.
      </div>
    </div>
  );
};
