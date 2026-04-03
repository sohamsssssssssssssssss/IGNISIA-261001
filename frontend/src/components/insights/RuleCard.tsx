import React, { useMemo, useState } from 'react';
import {
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Info,
  Target,
  Zap,
} from 'lucide-react';
import type { AssociationRule } from '../../types/insights';

const PROFILE_MAP = {
  high_gst_compliance: {
    label: 'GST Filing Rate',
    valueLabel: '93%',
    fill: 0.93,
  },
  mature_business: {
    label: 'Business Age',
    valueLabel: '18 months',
    fill: 0.9,
  },
  regular_upi_cadence: {
    label: 'UPI Regularity',
    valueLabel: '85%',
    fill: 0.85,
  },
  no_fraud_flags: {
    label: 'Fraud Score',
    valueLabel: '10 / 100',
    fill: 0.2,
  },
  high_credit_score: {
    label: 'Credit Score',
    valueLabel: '780',
    fill: 0.87,
  },
} as const;

export type RuleCardProps = AssociationRule;

function titleizeAntecedent(value: string): string {
  return value
    .split('_')
    .map((token) => token[0].toUpperCase() + token.slice(1))
    .join(' ');
}

function MetricBadge({
  icon,
  label,
  tone,
  tooltip,
}: {
  icon: React.ReactNode
  label: string
  tone: 'neutral' | 'positive' | 'warning' | 'elevated' | 'muted'
  tooltip: string
}) {
  return (
    <div className={`insights-metric insights-metric--${tone}`}>
      <span className="insights-metric__icon">{icon}</span>
      <span>{label}</span>
      <span className="insights-tooltip" role="tooltip">
        {tooltip}
      </span>
    </div>
  );
}

export default function RuleCard({
  antecedents,
  consequent,
  support,
  confidence,
  lift,
  explanation,
}: RuleCardProps) {
  const [expanded, setExpanded] = useState(false);

  const confidenceTone = confidence >= 0.85
    ? 'positive'
    : confidence >= 0.7
      ? 'warning'
      : 'muted';

  const liftTone = lift > 1.5 ? 'elevated' : lift < 1 ? 'muted' : 'neutral';
  const outcomeTone = consequent === 'repaid' ? 'positive' : 'negative';

  const exampleProfile = useMemo(() => antecedents
    .map((item) => PROFILE_MAP[item as keyof typeof PROFILE_MAP])
    .filter(Boolean), [antecedents]);

  return (
    <article className={`insights-rule-card insights-rule-card--${outcomeTone}`}>
      <div className="insights-rule-card__badge-row">
        <span className={`insights-outcome-badge insights-outcome-badge--${outcomeTone}`}>
          <span className="insights-outcome-badge__dot" />
          {consequent === 'repaid' ? 'Repayment Pattern' : 'Default Risk'}
        </span>
      </div>

      <p className="insights-rule-card__explanation">{explanation}</p>

      <div className="insights-rule-card__metrics">
        <MetricBadge
          icon={<Target size={14} />}
          label={`${Math.round(confidence * 100)}% confidence`}
          tone={confidenceTone}
          tooltip={`When these conditions are present, this outcome occurred ${Math.round(confidence * 100)}% of the time`}
        />
        <MetricBadge
          icon={<BarChart3 size={14} />}
          label={`Seen in ${Math.round(support * 100)}% of cases`}
          tone="neutral"
          tooltip={`${Math.round(support * 100)}% of all assessed businesses matched this pattern`}
        />
        <MetricBadge
          icon={<Zap size={14} />}
          label={`${lift.toFixed(1)}× lift`}
          tone={liftTone}
          tooltip={`This pattern predicts the outcome ${lift.toFixed(1)}× better than random chance`}
        />
      </div>

      <button
        type="button"
        className="insights-rule-card__toggle"
        onClick={() => setExpanded((current) => !current)}
      >
        {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        {expanded ? 'Hide technical details' : 'Show technical details'}
      </button>

      <div
        className={`insights-rule-card__accordion ${expanded ? 'is-open' : ''}`}
        style={{ maxHeight: expanded ? 420 : 0 }}
      >
        <div className="insights-rule-card__accordion-inner">
          <div className="insights-rule-card__section-title">If conditions are met:</div>
          <div className="insights-rule-card__antecedents">
            {antecedents.map((item) => (
              <div key={item} className="insights-rule-card__antecedent">
                <CheckCircle2 size={15} />
                <span>{titleizeAntecedent(item)}</span>
              </div>
            ))}
          </div>

          <div className="insights-rule-card__section-title">Then outcome:</div>
          <div className={`insights-rule-card__outcome insights-rule-card__outcome--${outcomeTone}`}>
            {consequent}
          </div>

          <div className="insights-rule-card__section-title">Example matching profile:</div>
          <div className="insights-rule-card__profile">
            {exampleProfile.map((profile) => (
              <div key={profile.label} className="insights-rule-card__profile-row">
                <div className="insights-rule-card__profile-head">
                  <span>{profile.label}</span>
                  <span>{profile.valueLabel}</span>
                </div>
                <div className="insights-rule-card__profile-track">
                  <div
                    className="insights-rule-card__profile-fill"
                    style={{ width: `${Math.max(profile.fill * 100, 10)}%` }}
                  />
                </div>
              </div>
            ))}
            {exampleProfile.length === 0 ? (
              <div className="insights-rule-card__profile-empty">
                <Info size={14} />
                Example profile unavailable for this pattern.
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </article>
  );
}
