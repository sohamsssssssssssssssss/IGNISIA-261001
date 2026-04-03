import React from 'react';
import { AlertTriangle, ArrowLeftRight, RotateCcw, ShieldAlert } from 'lucide-react';

interface CycleFound {
  nodes: string[];
  min_edge_value: number;
  cycle_length: number;
  contains_focal_gstin: boolean;
}

interface BouncePair {
  date: string;
  party_a: string;
  party_b: string;
  amount_forward: number;
  amount_reverse: number;
  match_ratio: number;
}

interface FraudDetectionProps {
  fraud: {
    circular_risk: string;
    risk_score: number;
    cycles_found: CycleFound[];
    cycle_count: number;
    round_amount_alert: boolean;
    round_amount_pct: number;
    bounceback_pairs: BouncePair[];
    bounceback_count: number;
    counterparty_count: number;
    linked_msme_nodes: string[];
    linked_msme_count: number;
    total_volume: number;
    volume_per_counterparty: number;
    graph_stats: { nodes: number; edges: number; density: number };
  };
  graphData?: {
    meta?: { total_nodes: number; total_edges: number; cycles_detected: number };
  } | null;
}

function riskColor(risk: string): string {
  if (risk === 'HIGH') return '#C8293A';
  if (risk === 'MEDIUM') return '#C97C14';
  return '#25A05E';
}

function formatINR(n: number): string {
  if (n >= 10000000) return `${(n / 10000000).toFixed(1)} Cr`;
  if (n >= 100000) return `${(n / 100000).toFixed(1)} L`;
  return n.toLocaleString('en-IN');
}

export const FraudDetection: React.FC<FraudDetectionProps> = ({ fraud, graphData }) => {
  const c = riskColor(fraud.circular_risk);

  return (
    <div className="msme-card">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div className="msme-card-title" style={{ marginBottom: 0 }}>Fraud Detection — UPI Circular Flows</div>
        <div className="msme-risk-pill" style={{ borderColor: c, color: c, fontSize: '10px', padding: '4px 12px', letterSpacing: '1.5px' }}>
          {fraud.circular_risk} <span style={{ opacity: 0.6, fontSize: '9px' }}>({fraud.risk_score}/100)</span>
        </div>
      </div>

      <div className="msme-grid-3" style={{ marginBottom: 16 }}>
        <div className="msme-metric-card">
          <div className="msme-metric-label"><RotateCcw size={11} /> Cycles</div>
          <div className="msme-metric-value" style={{ color: fraud.cycle_count > 0 ? 'var(--red)' : 'var(--green)' }}>{fraud.cycle_count}</div>
        </div>
        <div className="msme-metric-card">
          <div className="msme-metric-label"><ArrowLeftRight size={11} /> Bouncebacks</div>
          <div className="msme-metric-value" style={{ color: fraud.bounceback_count > 0 ? 'var(--amber)' : 'var(--green)' }}>{fraud.bounceback_count}</div>
        </div>
        <div className="msme-metric-card">
          <div className="msme-metric-label">Linked MSMEs</div>
          <div className="msme-metric-value" style={{ color: fraud.linked_msme_count > 0 ? 'var(--red)' : 'var(--text)' }}>{fraud.linked_msme_count}</div>
        </div>
      </div>

      {fraud.round_amount_alert && (
        <div className="msme-alert msme-alert--warning" style={{ marginBottom: 8 }}>
          <AlertTriangle size={12} />
          Round-amount transactions: {fraud.round_amount_pct.toFixed(1)}% (threshold 30%)
        </div>
      )}
      {fraud.linked_msme_nodes.length > 0 && (
        <div className="msme-alert msme-alert--danger" style={{ marginBottom: 8 }}>
          <ShieldAlert size={12} />
          Linked entities: {fraud.linked_msme_nodes.join(', ')}
        </div>
      )}
      <div className="msme-footer-stats">
        <span>Nodes: {graphData?.meta?.total_nodes ?? fraud.graph_stats.nodes}</span>
        <span>Edges: {graphData?.meta?.total_edges ?? fraud.graph_stats.edges}</span>
        <span>Cycles: {graphData?.meta?.cycles_detected ?? fraud.cycle_count}</span>
        <span>Volume: {formatINR(fraud.total_volume)}</span>
      </div>
    </div>
  );
};
