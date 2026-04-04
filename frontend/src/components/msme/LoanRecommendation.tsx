import React from 'react';
import { CheckCircle, XCircle } from 'lucide-react';

interface LoanRecommendationProps {
  recommendation?: {
    eligible?: boolean;
    reason?: string;
    recommended_amount?: number;
    recommended_tenure_months?: number;
    indicative_rate_pct: number | null;
    base_rate?: number;
    risk_premium?: number;
  } | null;
  manualReviewRequired?: boolean;
  manualReviewReason?: string;
}

function formatINR(amount: number): string {
  if (amount >= 10000000) return `${(amount / 10000000).toFixed(2)} Cr`;
  if (amount >= 100000) return `${(amount / 100000).toFixed(2)} L`;
  return amount.toLocaleString('en-IN');
}

export const LoanRecommendation: React.FC<LoanRecommendationProps> = ({ recommendation, manualReviewRequired, manualReviewReason }) => {
  const {
    eligible = false,
    reason,
    recommended_amount = 0,
    recommended_tenure_months = 0,
    indicative_rate_pct = null,
    base_rate,
    risk_premium,
  } = recommendation ?? {};

  if (manualReviewRequired) {
    return (
      <div className="msme-card">
        <div className="msme-card-title">Loan Recommendation</div>
        <div className="msme-alert msme-alert--warning">
          {manualReviewReason || 'Manual review required before auto-approval can be considered.'}
        </div>
      </div>
    );
  }

  if (!recommendation) {
    return (
      <div className="msme-card">
        <div className="msme-card-title">Loan Recommendation</div>
        <div className="msme-alert msme-alert--warning">
          Recommendation data is unavailable for this response. Refresh the score to reload the underwriting output.
        </div>
      </div>
    );
  }

  if (!eligible) {
    return (
      <div className="msme-card">
        <div className="msme-card-title">Loan Recommendation</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <XCircle size={16} color="var(--red)" />
          <span style={{ fontFamily: 'var(--mono)', fontSize: '12px', fontWeight: 600, color: 'var(--red)', letterSpacing: '2px', textTransform: 'uppercase' as const }}>
            Not Eligible
          </span>
        </div>
        {reason && (
          <div style={{ fontFamily: 'var(--body)', fontSize: '12px', color: 'var(--text-dim)', lineHeight: 1.6 }}>
            {reason}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="msme-card">
      <div className="msme-card-title">Loan Recommendation</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <CheckCircle size={16} color="var(--green)" />
        <span style={{ fontFamily: 'var(--mono)', fontSize: '12px', fontWeight: 600, color: 'var(--green)', letterSpacing: '2px', textTransform: 'uppercase' as const }}>
          Eligible
        </span>
      </div>

      <div className="msme-grid-3">
        <div className="msme-metric-card">
          <div className="msme-metric-label">Amount</div>
          <div className="msme-metric-value" style={{ color: 'var(--gold)' }}>{formatINR(recommended_amount)}</div>
        </div>
        <div className="msme-metric-card">
          <div className="msme-metric-label">Tenure</div>
          <div className="msme-metric-value">{recommended_tenure_months}mo</div>
        </div>
        <div className="msme-metric-card">
          <div className="msme-metric-label">Rate</div>
          <div className="msme-metric-value" style={{ color: 'var(--amber)' }}>{indicative_rate_pct}%</div>
        </div>
      </div>

      {base_rate != null && risk_premium != null && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontFamily: 'var(--mono)', fontSize: '11px' }}>
            <div className="msme-signal-row">
              <span className="msme-signal-key">Base Rate (MCLR)</span>
              <span className="msme-signal-val">{base_rate}%</span>
            </div>
            <div className="msme-signal-row">
              <span className="msme-signal-key">Risk Premium</span>
              <span className="msme-signal-val">+{risk_premium}%</span>
            </div>
            <div className="msme-signal-row" style={{ borderBottom: 'none' }}>
              <span style={{ color: 'var(--gold)', fontWeight: 600 }}>Final Rate</span>
              <span style={{ color: 'var(--gold)', fontWeight: 600 }}>{indicative_rate_pct}%</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
