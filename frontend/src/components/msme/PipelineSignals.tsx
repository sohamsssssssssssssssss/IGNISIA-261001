import React from 'react';
import { FileText, Wallet, Truck, AlertTriangle } from 'lucide-react';

interface PipelineSignalsProps {
  signals?: {
    gst_velocity?: {
      filing_rate: number;
      avg_delay: number;
      on_time_pct: number;
      e_invoice_trend: string;
      months_active: number;
      sparse_data: boolean;
      confidence_weight: number;
      data_freshness: string;
    };
    upi_cadence?: {
      avg_daily_txns: number;
      regularity_score: number;
      inflow_outflow_ratio: number;
      round_amount_pct: number;
      months_active: number;
      sparse_data: boolean;
      confidence_weight: number;
      data_freshness: string;
    };
    eway_bill?: {
      avg_monthly_bills: number;
      volume_momentum: number;
      interstate_ratio: number;
      anomaly_count: number;
      months_active: number;
      sparse_data: boolean;
      confidence_weight: number;
      data_freshness: string;
    };
  } | null;
}

const SparseTag = () => (
  <span className="msme-badge msme-badge--warning" style={{ fontSize: '8px', padding: '1px 5px' }}>
    <AlertTriangle size={9} /> Sparse
  </span>
);

const Row: React.FC<{ label: string; value: string | number; warn?: boolean }> = ({ label, value, warn }) => (
  <div className="msme-signal-row">
    <span className="msme-signal-key">{label}</span>
    <span className={warn ? 'msme-signal-val msme-signal-val--warn' : 'msme-signal-val'}>{value}</span>
  </div>
);

export const PipelineSignals: React.FC<PipelineSignalsProps> = ({ signals }) => {
  const gst = signals?.gst_velocity;
  const upi = signals?.upi_cadence;
  const eway = signals?.eway_bill;

  if (!gst || !upi || !eway) {
    return (
      <div className="msme-card">
        <div className="msme-card-title">Pipeline Signals</div>
        <div className="msme-alert msme-alert--warning">
          Pipeline signal details are temporarily unavailable for this response. Refresh the score to reload the feature inputs.
        </div>
      </div>
    );
  }

  return (
    <div className="msme-grid-3">
      <div className="msme-card" style={{ padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div className="msme-card-title" style={{ marginBottom: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
            <FileText size={12} /> GST Velocity
          </div>
          {gst.sparse_data && <SparseTag />}
        </div>
        <Row label="Filing Rate" value={`${(gst.filing_rate * 100).toFixed(0)}%`} />
        <Row label="Avg Delay" value={`${gst.avg_delay.toFixed(1)} days`} warn={gst.avg_delay > 10} />
        <Row label="On-Time %" value={`${gst.on_time_pct.toFixed(1)}%`} />
        <Row label="E-Invoice Trend" value={gst.e_invoice_trend} />
        <Row label="Months Active" value={gst.months_active} warn={gst.months_active < 6} />
        <Row label="Confidence" value={`${(gst.confidence_weight * 100).toFixed(0)}%`} warn={gst.confidence_weight < 0.6} />
      </div>

      <div className="msme-card" style={{ padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div className="msme-card-title" style={{ marginBottom: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Wallet size={12} /> UPI Cadence
          </div>
          {upi.sparse_data && <SparseTag />}
        </div>
        <Row label="Avg Daily Txns" value={upi.avg_daily_txns.toFixed(1)} />
        <Row label="Regularity" value={`${upi.regularity_score.toFixed(0)}/100`} />
        <Row label="Inflow/Outflow" value={`${upi.inflow_outflow_ratio.toFixed(2)}x`} warn={upi.inflow_outflow_ratio < 0.8} />
        <Row label="Round Amt %" value={`${upi.round_amount_pct.toFixed(1)}%`} warn={upi.round_amount_pct > 30} />
        <Row label="Months Active" value={upi.months_active} warn={upi.months_active < 6} />
        <Row label="Confidence" value={`${(upi.confidence_weight * 100).toFixed(0)}%`} warn={upi.confidence_weight < 0.6} />
      </div>

      <div className="msme-card" style={{ padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div className="msme-card-title" style={{ marginBottom: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Truck size={12} /> E-Way Bill
          </div>
          {eway.sparse_data && <SparseTag />}
        </div>
        <Row label="Avg Monthly Bills" value={eway.avg_monthly_bills.toFixed(1)} />
        <Row label="Volume Momentum" value={`${eway.volume_momentum > 0 ? '+' : ''}${eway.volume_momentum.toFixed(1)}%`} />
        <Row label="Interstate Ratio" value={`${eway.interstate_ratio.toFixed(1)}%`} />
        <Row label="Anomalies" value={eway.anomaly_count} warn={eway.anomaly_count > 0} />
        <Row label="Months Active" value={eway.months_active} warn={eway.months_active < 6} />
        <Row label="Confidence" value={`${(eway.confidence_weight * 100).toFixed(0)}%`} warn={eway.confidence_weight < 0.6} />
      </div>
    </div>
  );
};
