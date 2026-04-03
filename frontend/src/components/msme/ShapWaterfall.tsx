import React from 'react';
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface TopReason {
  feature: string;
  feature_key: string;
  shap_value: number;
  feature_value: number;
  direction: string;
  reason: string;
  score_impact: number;
  raw_value_display: string;
  start_score: number;
  end_score: number;
  running_total: number;
}

interface WaterfallRow {
  label: string;
  feature_key: string;
  direction: string;
  score_impact: number;
  start_score: number;
  end_score: number;
  running_total: number;
  raw_value_display: string;
  reason: string;
  kind: 'base' | 'reason' | 'other' | 'final';
}

interface ShapWaterfallProps {
  baseScore: number;
  finalScore: number;
  topReasons: TopReason[];
  waterfall: WaterfallRow[];
}

function formatImpact(value: number): string {
  if (value > 0) return `+${value} pts`;
  if (value < 0) return `${value} pts`;
  return '0 pts';
}

function wrapLabel(text: string, maxChars = 38): string[] {
  const words = text.split(' ');
  const lines: string[] = [];
  let current = '';

  words.forEach(word => {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= maxChars) {
      current = candidate;
      return;
    }
    if (current) lines.push(current);
    current = word;
  });

  if (current) lines.push(current);
  return lines.slice(0, 3);
}

const WaterfallTick: React.FC<any> = ({ x, y, payload }) => {
  const lines = wrapLabel(String(payload?.value || ''));
  return (
    <g transform={`translate(${x},${y})`}>
      <text x={0} y={0} dy={4} textAnchor="end" fill="var(--text-dim)" fontSize={10} fontFamily="var(--mono)">
        {lines.map((line, index) => (
          <tspan key={index} x={0} dy={index === 0 ? 0 : 12}>
            {line}
          </tspan>
        ))}
      </text>
    </g>
  );
};

const WaterfallTooltip: React.FC<any> = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload as WaterfallRow & { color: string };
  if (!row) return null;

  return (
    <div className="msme-waterfall-tooltip">
      <div className="msme-waterfall-tooltip-title">{row.label}</div>
      <div className="msme-waterfall-tooltip-row">
        <span>Impact</span>
        <strong style={{ color: row.color }}>{formatImpact(row.score_impact)}</strong>
      </div>
      <div className="msme-waterfall-tooltip-row">
        <span>Running total</span>
        <strong>{row.running_total}</strong>
      </div>
      <div className="msme-waterfall-tooltip-row">
        <span>Raw value</span>
        <strong>{row.raw_value_display}</strong>
      </div>
    </div>
  );
};

export const ShapWaterfall: React.FC<ShapWaterfallProps> = ({
  baseScore,
  finalScore,
  topReasons,
  waterfall,
}) => {
  const rows = waterfall.length ? waterfall : [
    {
      label: 'Base score (population average before business-specific signals)',
      feature_key: 'base_score',
      direction: 'neutral',
      score_impact: 0,
      start_score: baseScore,
      end_score: baseScore,
      running_total: baseScore,
      raw_value_display: 'Model expected value',
      reason: 'Base score (population average before business-specific signals)',
      kind: 'base' as const,
    },
    ...topReasons.map(reason => ({
      label: reason.reason,
      feature_key: reason.feature_key,
      direction: reason.direction,
      score_impact: reason.score_impact,
      start_score: reason.start_score,
      end_score: reason.end_score,
      running_total: reason.running_total,
      raw_value_display: reason.raw_value_display,
      reason: reason.reason,
      kind: 'reason' as const,
    })),
    {
      label: 'Final credit score',
      feature_key: 'final_score',
      direction: 'neutral',
      score_impact: 0,
      start_score: finalScore,
      end_score: finalScore,
      running_total: finalScore,
      raw_value_display: '300-900 calibrated final score',
      reason: 'Final credit score',
      kind: 'final' as const,
    },
  ];

  const chartData = rows.map(row => {
    const min = Math.min(row.start_score, row.end_score);
    const max = Math.max(row.start_score, row.end_score);
    const color = row.kind === 'base'
      ? 'var(--gold)'
      : row.kind === 'final'
        ? 'var(--text)'
        : row.direction === 'positive'
          ? '#22c55e'
          : '#ef4444';
    return {
      ...row,
      barBase: row.kind === 'base' || row.kind === 'final' ? 0 : min,
      barSize: row.kind === 'base' || row.kind === 'final' ? row.end_score : max - min,
      color,
    };
  });

  const minScore = Math.min(...chartData.map(row => Math.min(row.start_score, row.end_score, row.running_total)), baseScore, finalScore);
  const maxScore = Math.max(...chartData.map(row => Math.max(row.start_score, row.end_score, row.running_total)), baseScore, finalScore);
  const axisMin = Math.max(250, Math.floor((minScore - 30) / 10) * 10);
  const axisMax = Math.min(950, Math.ceil((maxScore + 30) / 10) * 10);
  const chartHeight = Math.max(420, chartData.length * 78);

  return (
    <div className="msme-card">
      <div className="msme-card-title">SHAP Waterfall</div>
      <div className="msme-inline-meta">
        Plain-language explanation of how the model moved from the average MSME score of {baseScore} to the final score of {finalScore}.
      </div>

      <div className="msme-waterfall-chart-wrap">
        <ResponsiveContainer width="100%" height={chartHeight}>
          <ComposedChart data={chartData} layout="vertical" margin={{ top: 12, right: 36, bottom: 12, left: 320 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.05)" horizontal={false} />
            <XAxis
              type="number"
              domain={[axisMin, axisMax]}
              tick={{ fill: 'var(--text-dim)', fontSize: 10, fontFamily: 'var(--mono)' }}
              axisLine={{ stroke: 'var(--card-border)' }}
              tickLine={false}
            />
            <YAxis
              dataKey="label"
              type="category"
              width={300}
              tickLine={false}
              axisLine={false}
              tick={<WaterfallTick />}
            />
            <ReferenceLine
              x={baseScore}
              stroke="rgba(200, 168, 75, 0.55)"
              strokeDasharray="4 4"
              ifOverflow="extendDomain"
            />
            <Tooltip content={<WaterfallTooltip />} cursor={{ fill: 'rgba(255,255,255,0.02)' }} />
            <Bar dataKey="barBase" stackId="waterfall" fill="transparent" isAnimationActive={false} />
            <Bar dataKey="barSize" stackId="waterfall" radius={[2, 2, 2, 2]} isAnimationActive={false}>
              {chartData.map((entry, index) => (
                <Cell key={`${entry.feature_key}-${index}`} fill={entry.color} />
              ))}
            </Bar>
            <Line
              type="monotone"
              dataKey="running_total"
              stroke="var(--gold)"
              strokeWidth={2}
              dot={{ r: 3, fill: 'var(--gold)', strokeWidth: 0 }}
              activeDot={{ r: 4 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="msme-waterfall-rows">
        {rows.map((row, index) => (
          <div
            key={`${row.feature_key}-${index}`}
            className={`msme-waterfall-row msme-waterfall-row--${row.kind}`}
          >
            <div className="msme-waterfall-row-copy">
              <div className="msme-waterfall-row-label">{row.label}</div>
              <div className="msme-waterfall-row-raw">Raw value: {row.raw_value_display}</div>
            </div>
            <div className="msme-waterfall-row-metrics">
              <div className={`msme-waterfall-impact msme-waterfall-impact--${row.direction}`}>
                {row.kind === 'base' || row.kind === 'final' ? `${row.end_score}` : formatImpact(row.score_impact)}
              </div>
              <div className="msme-waterfall-total">
                {row.kind === 'base'
                  ? `Base ${row.end_score}`
                  : row.kind === 'final'
                    ? `Final ${row.end_score}`
                    : `Running total ${row.running_total}`}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
