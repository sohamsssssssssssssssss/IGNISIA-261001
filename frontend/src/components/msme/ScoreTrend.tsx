import React from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface HistoryEntry {
  timestamp: string;
  score: number;
  risk_band: string;
  fraud_risk: string;
  source?: string;
  model_version?: string;
  data_freshness?: string;
}

interface ScoreTrendProps {
  history: HistoryEntry[];
}

const RISK_ZONES = [
  { y1: 800, y2: 900, fill: 'rgba(37,160,94,0.06)', label: 'Very Low Risk' },
  { y1: 700, y2: 800, fill: 'rgba(37,160,94,0.03)', label: 'Low Risk' },
  { y1: 600, y2: 700, fill: 'rgba(201,124,20,0.04)', label: 'Moderate' },
  { y1: 500, y2: 600, fill: 'rgba(200,41,58,0.03)', label: 'High Risk' },
  { y1: 300, y2: 500, fill: 'rgba(200,41,58,0.06)', label: 'Very High' },
];
const LEGEND_COLORS = ['#25A05E', '#6CBF83', '#C97C14', '#D55A5A', '#C8293A'];

function formatAxisDate(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
}

function formatTooltipTime(ts: string): string {
  return new Date(ts).toLocaleString('en-IN');
}

export const ScoreTrend: React.FC<ScoreTrendProps> = ({ history }) => {
  if (!history || history.length === 0) {
    return (
      <div className="msme-card">
        <div className="msme-card-title">Score Trend</div>
        <div style={{ fontFamily: 'var(--mono)', color: 'var(--text-dim)', fontSize: '11px', padding: 20, textAlign: 'center', opacity: 0.7 }}>
          Score history will accumulate as this business is assessed over time.
        </div>
      </div>
    );
  }

  const chartData = history.map((h) => ({
    ...h,
    axisDate: formatAxisDate(h.timestamp),
  }));

  return (
    <div className="msme-card">
      <div className="msme-card-title">Score Trend</div>
      {history.length === 1 && (
        <div className="msme-inline-meta" style={{ marginBottom: 12 }}>
          Score history will accumulate as assessments are run over time.
        </div>
      )}
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartData} margin={{ top: 10, right: 16, left: 8, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" />
          {RISK_ZONES.map((z, i) => (
            <ReferenceArea key={i} y1={z.y1} y2={z.y2} fill={z.fill} ifOverflow="extendDomain" />
          ))}
          <XAxis
            dataKey="axisDate"
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
            formatter={(value: number, _name, item: any) => [`${value}`, 'Score']}
            labelFormatter={(_label, payload) => {
              const point = payload?.[0]?.payload;
              if (!point) return '';
              return `${formatTooltipTime(point.timestamp)}`;
            }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const point = payload[0].payload;
              return (
                <div className="msme-chart-tooltip">
                  <div>{formatTooltipTime(point.timestamp)}</div>
                  <div>Score: {point.score}</div>
                  <div>Model: {point.model_version || 'unknown'}</div>
                  <div>Data freshness: {point.data_freshness ? formatTooltipTime(point.data_freshness) : 'n/a'}</div>
                </div>
              );
            }}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#C8A84B"
            strokeWidth={2}
            dot={{ fill: '#C8A84B', r: 3, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: '#C8A84B', stroke: '#EDE5D4', strokeWidth: 1 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="msme-legend">
        {RISK_ZONES.map((z, i) => (
          <span key={i} className="msme-legend-item">
            <span className="msme-legend-dot" style={{ background: LEGEND_COLORS[i] }} />
            {z.label}
          </span>
        ))}
      </div>
    </div>
  );
};
