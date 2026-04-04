import React from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface CounterfactualRecommendation {
  feature_key: string;
  feature_name: string;
  current_value: number;
  current_value_display: string;
  target_value: number;
  target_value_display: string;
  estimated_score_improvement: number;
  confidence: 'high' | 'medium';
  action: string;
  timeframe_days: string;
}

interface CounterfactualPayload {
  base_score: number;
  combined_projected_score: number;
  combined_score_improvement: number;
  naive_sum_score_improvement: number;
  recommendations: CounterfactualRecommendation[];
}

interface TrajectoryPoint {
  day: number;
  score: number;
}

interface LenderUnlockEvent {
  day: number;
  lender_key: string;
  lender_type: string;
  message: string;
}

interface LenderChecks {
  score: {
    actual: number;
    required_minimum: number;
    passed: boolean;
  };
  fraud_score: {
    actual: number;
    required_maximum: number;
    passed: boolean;
  };
  history_months: {
    actual: number;
    required_minimum: number;
    passed: boolean;
  };
  loan_amount: {
    actual: number;
    required_minimum: number;
    required_maximum: number;
    passed: boolean;
  };
}

interface LenderItem {
  key: string;
  display_name: string;
  tier_rank: number;
  status: 'qualified' | 'borderline' | 'not_qualified';
  gap_statement: string;
  plain_english_reason: string;
  typical_interest_rate_range: string;
  typical_processing_time_days: number;
  notes: string;
  checks: LenderChecks;
  failed_conditions: string[];
}

interface TrajectoryPayload {
  current_score: number;
  with_action: TrajectoryPoint[];
  no_action: TrajectoryPoint[];
  target_score_day_90: number;
  lender_unlock_events: LenderUnlockEvent[];
}

interface LenderRecommendationsPayload {
  requested_loan_amount: number;
  summary: string;
  recommended_lender: LenderItem | null;
  closest_lender: LenderItem | null;
  all_lenders: LenderItem[];
}

interface SimulatorProps {
  counterfactual: CounterfactualPayload;
  trajectory: TrajectoryPayload;
  lenderRecommendations: LenderRecommendationsPayload;
}

function buildChartData(trajectory: TrajectoryPayload) {
  const passiveByDay = new Map(trajectory.no_action.map((point) => [point.day, point.score]));
  return trajectory.with_action.map((point) => ({
    day: point.day,
    actionScore: point.score,
    passiveScore: passiveByDay.get(point.day) ?? point.score,
  }));
}

function computeYDomain(counterfactual: CounterfactualPayload, trajectory: TrajectoryPayload): [number, number] {
  const scores = [
    counterfactual.base_score,
    counterfactual.combined_projected_score,
    ...trajectory.with_action.map((point) => point.score),
    ...trajectory.no_action.map((point) => point.score),
  ];
  const lower = Math.max(300, Math.floor((Math.min(...scores) - 20) / 10) * 10);
  const upper = Math.min(900, Math.ceil((Math.max(...scores) + 20) / 10) * 10);
  return [lower, upper];
}

function formatCurrency(value: number): string {
  return `INR ${value.toLocaleString('en-IN')}`;
}

function formatCompactRupees(value: number): string {
  if (value >= 10_000_000) {
    return `INR ${(value / 10_000_000).toFixed(1)} Cr`;
  }
  if (value >= 100_000) {
    return `INR ${(value / 100_000).toFixed(1)} L`;
  }
  if (value >= 1_000) {
    return `INR ${(value / 1_000).toFixed(1)} K`;
  }
  return formatCurrency(value);
}

function buildPolicyChecks(lender: LenderItem) {
  return [
    {
      label: 'Score',
      value: `${lender.checks.score.actual} / ${lender.checks.score.required_minimum}+`,
      passed: lender.checks.score.passed,
    },
    {
      label: 'Fraud',
      value: `${lender.checks.fraud_score.actual} / <= ${lender.checks.fraud_score.required_maximum}`,
      passed: lender.checks.fraud_score.passed,
    },
    {
      label: 'History',
      value: `${lender.checks.history_months.actual} / ${lender.checks.history_months.required_minimum}+ mo`,
      passed: lender.checks.history_months.passed,
    },
    {
      label: 'Ticket',
      value: `${formatCompactRupees(lender.checks.loan_amount.actual)} in range`,
      passed: lender.checks.loan_amount.passed,
    },
  ];
}

export const ScoreImprovementSimulator: React.FC<SimulatorProps> = ({
  counterfactual,
  trajectory,
  lenderRecommendations,
}) => {
  if (!counterfactual.recommendations?.length) {
    return null;
  }

  const projectionDirection = counterfactual.combined_score_improvement >= 0 ? '+' : '';
  const chartData = buildChartData(trajectory);
  const [yMin, yMax] = computeYDomain(counterfactual, trajectory);
  const roadmapLender = lenderRecommendations.recommended_lender ?? lenderRecommendations.closest_lender;
  const firstUnlock = trajectory.lender_unlock_events[0] ?? null;

  return (
    <div className="msme-card">
      <div className="msme-card-title">Actionable Credit Roadmap</div>
      <div className="msme-inline-meta" style={{ marginBottom: 16 }}>
        One live scoring pass now powers ranked actions, a 90-day curve, and lender-tier unlocks
      </div>

      <div className="msme-highlight-grid" style={{ marginBottom: 18 }}>
        <div className="msme-highlight-card">
          <div className="msme-highlight-label">Current Score</div>
          <div className="msme-highlight-value">{counterfactual.base_score}</div>
          <div className="msme-highlight-body">
            Starting point before any recommended business change is applied.
          </div>
        </div>
        <div className="msme-highlight-card">
          <div className="msme-highlight-label">Day 90 Projection</div>
          <div className="msme-highlight-value">{counterfactual.combined_projected_score}</div>
          <div className="msme-highlight-body">
            {projectionDirection}{counterfactual.combined_score_improvement} points after applying the top recommendations together.
          </div>
        </div>
        <div className="msme-highlight-card">
          <div className="msme-highlight-label">Next Unlock</div>
          <div className="msme-highlight-value">{firstUnlock?.lender_type ?? 'None yet'}</div>
          <div className="msme-highlight-body">
            {firstUnlock?.message ?? 'No lender threshold is crossed inside the current 90-day trajectory.'}
          </div>
        </div>
        <div className="msme-highlight-card">
          <div className="msme-highlight-label">Best Current Fit</div>
          <div className="msme-highlight-value">{roadmapLender?.display_name ?? 'No lender fit yet'}</div>
          <div className="msme-highlight-body">
            {lenderRecommendations.summary}
          </div>
        </div>
      </div>

      <div className="msme-alert msme-alert--success" style={{ marginBottom: 18 }}>
        Every recommendation is rescored directly on the model, the combined lift is recalculated instead of summed, and lender unlocks come from the same threshold policy used for the current lender match.
      </div>

      <div style={{ display: 'grid', gap: 14 }}>
        {counterfactual.recommendations.map((recommendation, index) => (
          <div key={recommendation.feature_key} className="msme-metric-card" style={{ textAlign: 'left' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
              <div>
                <div className="msme-metric-label" style={{ justifyContent: 'flex-start' }}>Priority {index + 1}</div>
                <div className="msme-card-title" style={{ marginTop: 6, marginBottom: 0 }}>{recommendation.feature_name}</div>
              </div>
              <div
                className={`msme-badge ${recommendation.confidence === 'high' ? 'msme-badge--success' : 'msme-badge--warning'}`}
                style={{ textTransform: 'uppercase' }}
              >
                {recommendation.confidence} confidence
              </div>
            </div>

            <div className="msme-grid-2" style={{ marginTop: 14 }}>
              <div>
                <div className="msme-inline-meta">Current</div>
                <div style={{ color: 'var(--text)', fontSize: '1rem' }}>{recommendation.current_value_display}</div>
              </div>
              <div>
                <div className="msme-inline-meta">Target</div>
                <div style={{ color: 'var(--gold)', fontSize: '1rem' }}>{recommendation.target_value_display}</div>
              </div>
            </div>

            <div className="msme-grid-2" style={{ marginTop: 14 }}>
              <div>
                <div className="msme-inline-meta">Estimated Score Lift</div>
                <div style={{ color: 'var(--green)', fontSize: '1rem' }}>
                  +{recommendation.estimated_score_improvement} pts
                </div>
              </div>
              <div>
                <div className="msme-inline-meta">Expected Timeframe</div>
                <div style={{ color: 'var(--text)', fontSize: '1rem' }}>{recommendation.timeframe_days} days</div>
              </div>
            </div>

            <div style={{ color: 'var(--text-dim)', fontSize: 13, lineHeight: 1.7, marginTop: 14 }}>
              {recommendation.action}
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 24 }}>
        <div className="msme-card-title">30 / 60 / 90 Day Score Trajectory</div>
        <div className="msme-inline-meta" style={{ marginBottom: 12 }}>
          Action path vs honest passive drift, with lender unlock markers
        </div>

        {trajectory.lender_unlock_events.length > 0 && (
          <div className="msme-policy-chip-row" style={{ marginBottom: 12 }}>
            {trajectory.lender_unlock_events.map((event) => (
              <div key={`${event.lender_key}-${event.day}`} className="msme-policy-chip msme-policy-chip--neutral">
                Day {event.day}: {event.lender_type}
              </div>
            ))}
          </div>
        )}

        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData} margin={{ top: 10, right: 18, left: 8, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" />
            <XAxis
              dataKey="day"
              type="number"
              domain={[0, 90]}
              ticks={[0, 30, 60, 90]}
              tick={{ fill: '#9A9488', fontSize: 9, fontFamily: 'IBM Plex Mono' }}
              axisLine={{ stroke: 'var(--card-border)' }}
              tickLine={false}
              label={{ value: 'Day', position: 'insideBottom', offset: -4, fill: '#9A9488', fontSize: 10 }}
            />
            <YAxis
              domain={[yMin, yMax]}
              tick={{ fill: '#9A9488', fontSize: 9, fontFamily: 'IBM Plex Mono' }}
              axisLine={{ stroke: 'var(--card-border)' }}
              tickLine={false}
            />
            {trajectory.lender_unlock_events.map((event) => (
              <ReferenceLine
                key={`${event.lender_key}-${event.day}`}
                x={event.day}
                stroke="rgba(200, 168, 75, 0.45)"
                strokeDasharray="4 4"
                label={{
                  value: `${event.lender_type} unlock`,
                  fill: '#C8A84B',
                  fontSize: 10,
                  position: 'insideTopRight',
                }}
              />
            ))}
            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                const unlocks = trajectory.lender_unlock_events
                  .filter((event) => event.day === Number(label))
                  .map((event) => event.message);

                return (
                  <div className="msme-chart-tooltip">
                    <div>Day {label}</div>
                    {payload.map((entry) => (
                      <div key={String(entry.dataKey)}>
                        {entry.name}: {entry.value}
                      </div>
                    ))}
                    {unlocks.map((message) => (
                      <div key={message}>{message}</div>
                    ))}
                  </div>
                );
              }}
            />
            <Line
              type="monotone"
              dataKey="actionScore"
              name="With action"
              stroke="#C8A84B"
              strokeWidth={3}
              dot={{ fill: '#C8A84B', r: 3, strokeWidth: 0 }}
              activeDot={{ r: 5, fill: '#C8A84B', stroke: '#EDE5D4', strokeWidth: 1 }}
            />
            <Line
              type="monotone"
              dataKey="passiveScore"
              name="No action"
              stroke="rgba(154, 148, 136, 0.9)"
              strokeWidth={2}
              dot={{ fill: 'rgba(154, 148, 136, 0.9)', r: 2, strokeWidth: 0 }}
            />
          </LineChart>
        </ResponsiveContainer>
        <div className="msme-inline-meta" style={{ marginTop: 10 }}>
          Day 90 target with action: {trajectory.target_score_day_90}. Naive sum of individual lifts: +{counterfactual.naive_sum_score_improvement} pts.
        </div>
      </div>

      <div style={{ marginTop: 24 }}>
        <div className="msme-card-title">Institutional Lender Policy View</div>
        <div className="msme-inline-meta" style={{ marginBottom: 12 }}>
          Requested amount assumed: {formatCurrency(lenderRecommendations.requested_loan_amount)}
        </div>

        <div className="msme-metric-card" style={{ textAlign: 'left', marginBottom: 16 }}>
          <div className="msme-inline-meta">Decision summary</div>
          <div style={{ color: 'var(--text)', fontSize: '1rem', lineHeight: 1.7, marginTop: 8 }}>
            {lenderRecommendations.summary}
          </div>
          {roadmapLender && (
            <div style={{ color: 'var(--text-dim)', fontSize: 13, lineHeight: 1.7, marginTop: 10 }}>
              {roadmapLender.display_name}: {roadmapLender.typical_interest_rate_range}, usually about {roadmapLender.typical_processing_time_days} days. {roadmapLender.notes}
            </div>
          )}
        </div>

        <div style={{ display: 'grid', gap: 12 }}>
          {lenderRecommendations.all_lenders.map((lender) => {
            const checks = buildPolicyChecks(lender);
            return (
              <div key={lender.key} className="msme-metric-card" style={{ textAlign: 'left' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
                  <div>
                    <div className="msme-card-title" style={{ marginTop: 0, marginBottom: 0 }}>{lender.display_name}</div>
                    <div className="msme-inline-meta" style={{ marginTop: 6 }}>
                      {lender.typical_interest_rate_range} • ~{lender.typical_processing_time_days} days
                    </div>
                  </div>
                  <div
                    className={`msme-badge ${
                      lender.status === 'qualified'
                        ? 'msme-badge--success'
                        : lender.status === 'borderline'
                          ? 'msme-badge--warning'
                          : 'msme-badge--danger'
                    }`}
                    style={{ textTransform: 'uppercase' }}
                  >
                    {lender.status.replace('_', ' ')}
                  </div>
                </div>

                <div className="msme-policy-chip-row" style={{ marginTop: 12 }}>
                  {checks.map((check) => (
                    <div
                      key={`${lender.key}-${check.label}`}
                      className={`msme-policy-chip ${check.passed ? 'msme-policy-chip--pass' : 'msme-policy-chip--fail'}`}
                    >
                      <strong>{check.label}</strong>: {check.value}
                    </div>
                  ))}
                </div>

                <div style={{ color: 'var(--text)', fontSize: '0.95rem', lineHeight: 1.7, marginTop: 12 }}>
                  {lender.gap_statement}
                </div>

                <div style={{ color: 'var(--text-dim)', fontSize: 13, lineHeight: 1.7, marginTop: 10 }}>
                  {lender.plain_english_reason}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

