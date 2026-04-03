import React from 'react';
import { ShieldCheck, Database } from 'lucide-react';

interface ConfidenceSummary {
  overall_data_confidence: number;
  gst_confidence: number;
  upi_confidence: number;
  eway_confidence: number;
}

interface ConfidencePanelProps {
  confidence: ConfidenceSummary;
}

const confidenceTone = (value: number): string => {
  if (value >= 0.8) return 'var(--green)';
  if (value >= 0.55) return 'var(--amber)';
  return 'var(--red)';
};

export const ConfidencePanel: React.FC<ConfidencePanelProps> = ({ confidence }) => {
  const cards = [
    { label: 'Overall Confidence', value: confidence.overall_data_confidence, icon: ShieldCheck },
    { label: 'GST Confidence', value: confidence.gst_confidence, icon: Database },
    { label: 'UPI Confidence', value: confidence.upi_confidence, icon: Database },
    { label: 'E-Way Confidence', value: confidence.eway_confidence, icon: Database },
  ];

  return (
    <div className="msme-card">
      <div className="msme-card-title">Decision Confidence</div>
      <div className="msme-grid-2">
        {cards.map(({ label, value, icon: Icon }) => (
          <div className="msme-metric-card" key={label}>
            <div className="msme-inline-meta" style={{ justifyContent: 'center', marginBottom: 8 }}>
              <Icon size={12} /> {label}
            </div>
            <div className="msme-trend-value" style={{ color: confidenceTone(value) }}>
              {(value * 100).toFixed(0)}%
            </div>
            <div className="msme-progress-track">
              <div
                className="msme-progress-fill"
                style={{ width: `${Math.max(8, value * 100)}%`, background: confidenceTone(value) }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
