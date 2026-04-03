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

interface ProjectionPoint {
  month: number;
  score: number;
  actions: string[];
  crosses_threshold: boolean;
}

interface TopIssue {
  feature: string;
  label: string;
  shap_impact: number;
}

interface SimulatorProps {
  simulation: {
    base_score: number;
    approval_threshold: number;
    crossed_threshold_month: number | null;
    trajectory: ProjectionPoint[];
    top_issues: TopIssue[];
    final_eligible_amount: number;
  };
}

function formatINR(amount: number): string {
  if (amount >= 10000000) return `${(amount / 10000000).toFixed(1)} Cr`;
  if (amount >= 100000) return `${(amount / 100000).toFixed(1)} L`;
  return amount.toLocaleString('en-IN');
}

export const ScoreImprovementSimulator: React.FC<SimulatorProps> = ({ simulation }) => {
  if (simulation.base_score >= simulation.approval_threshold) {
    return null;
  }

  const chartData = [
    { month: 'Now', score: simulation.base_score, action: 'Current score', crossesThreshold: false },
    ...simulation.trajectory.map((point) => ({
      month: `M${point.month}`,
      score: point.score,
      action: point.actions[0] || 'Continued improvement',
      crossesThreshold: point.crosses_threshold,
    })),
  ];

  return (
    <div className="msme-card">
      <div className="msme-card-title">Score Improvement Simulator</div>
      <div className="msme-inline-meta" style={{ marginBottom: 16 }}>
        6-month rehabilitation projection based on improving the top negative SHAP drivers
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartData} margin={{ top: 10, right: 16, left: 8, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" />
          <XAxis
            dataKey="month"
            tick={{ fill: '#9A9488', fontSize: 9, fontFamily: 'IBM Plex Mono' }}
            axisLine={{ stroke: 'var(--card-border)' }}
            tickLine={false}
          />
          <YAxis
            domain={[300, 900]}
            ticks={[300, 500, 600, 700, 800, 900]}
            tick={{ fill: '#9A9488', fontSize: 9, fontFamily: 'IBM Plex Mono' }}
            axisLine={{ stroke: 'var(--card-border)' }}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: '#111012',
              border: '1px solid #1E1D1F',
              color: '#EDE5D4',
              fontFamily: 'IBM Plex Mono',
              fontSize: '11px',
            }}
            formatter={(value: number, _name, props: any) => [`Score: ${value}`, props?.payload?.action || '']}
            labelFormatter={(label: string, payload: any[]) => {
              const point = payload?.[0]?.payload;
              return point ? `${label} — ${point.action}` : label;
            }}
          />
          <ReferenceLine
            y={simulation.approval_threshold}
            stroke="#25A05E"
            strokeDasharray="4 4"
            label={{ value: 'Eligibility', position: 'insideTopRight', fill: '#25A05E', fontSize: 10 }}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#C8A84B"
            strokeWidth={2}
            dot={(props: any) => {
              const { payload, cx, cy } = props;
              return payload?.crossesThreshold
                ? <circle cx={cx} cy={cy} r={7} fill="#25A05E" />
                : <circle cx={cx} cy={cy} r={4} fill="#C8A84B" />;
            }}
            activeDot={{ r: 5, fill: '#C8A84B', stroke: '#EDE5D4', strokeWidth: 1 }}
          />
        </LineChart>
      </ResponsiveContainer>

      <div className="msme-simulator-summary">
        <div className="msme-metric-card">
          <div className="msme-metric-label">Current Score</div>
          <div className="msme-metric-value">{simulation.base_score}</div>
        </div>
        <div className="msme-metric-card">
          <div className="msme-metric-label">Approval Crossing</div>
          <div className="msme-metric-value" style={{ color: simulation.crossed_threshold_month ? 'var(--green)' : 'var(--amber)' }}>
            {simulation.crossed_threshold_month ? `Month ${simulation.crossed_threshold_month}` : 'Not in 6mo'}
          </div>
        </div>
      </div>

      <div className="msme-simulator-plan">
        {simulation.top_issues.map((step) => (
          <div key={step.feature} className="msme-simulator-step">
            <div className="msme-simulator-step-title">{step.label}</div>
            <div className="msme-inline-meta">
              Impact: {Math.abs(step.shap_impact).toFixed(2)}
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 16 }}>
        {simulation.trajectory.map((point) => (
          <div key={point.month} className="msme-signal-row">
            <span className="msme-signal-key">Month {point.month}: {point.actions[0] || 'Continued improvement'}</span>
            <span className="msme-signal-val">
              {point.score} {point.crosses_threshold ? '• Crosses threshold' : ''}
            </span>
          </div>
        ))}
      </div>

      {simulation.crossed_threshold_month && (
        <div className="msme-alert msme-alert--success" style={{ marginTop: 16 }}>
          You cross the approval threshold by Month {simulation.crossed_threshold_month}. At 6 months: eligible for up to {formatINR(simulation.final_eligible_amount)}.
        </div>
      )}
    </div>
  );
};
