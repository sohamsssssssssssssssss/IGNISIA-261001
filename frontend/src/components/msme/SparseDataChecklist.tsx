import React from 'react';
import { AlertTriangle, UploadCloud } from 'lucide-react';

interface SparseDataChecklistProps {
  signals: {
    gst_velocity: { months_active: number };
    upi_cadence: { months_active: number };
    eway_bill: { months_active: number };
  };
}

export const SparseDataChecklist: React.FC<SparseDataChecklistProps> = ({ signals }) => {
  const items = [
    {
      label: 'Bank statement for last 3 months',
      reason: 'Substitute for limited UPI cadence history',
      show: signals.upi_cadence.months_active < 6,
    },
    {
      label: 'Purchase orders or confirmed contracts',
      reason: 'Substitute for limited e-way bill volume history',
      show: signals.eway_bill.months_active < 6,
    },
    {
      label: 'GST registration date confirmation',
      reason: 'Establishes operating age and filing timeline',
      show: signals.gst_velocity.months_active < 6,
    },
  ].filter((item) => item.show);

  return (
    <div className="msme-card">
      <div className="msme-card-title">Manual Review Checklist</div>
      <div className="msme-alert msme-alert--warning" style={{ marginBottom: 14 }}>
        <AlertTriangle size={12} />
        Sparse data detected. Supplementary documents can substitute for missing operating history.
      </div>
      {items.map((item) => (
        <div className="msme-checklist-row" key={item.label}>
          <div>
            <div className="msme-reason-text" style={{ color: 'var(--text)' }}>{item.label}</div>
            <div className="msme-reason-meta" style={{ opacity: 0.8 }}>{item.reason}</div>
          </div>
          <button className="msme-btn msme-btn--ghost">
            <UploadCloud size={12} /> Upload & Re-score
          </button>
        </div>
      ))}
    </div>
  );
};
