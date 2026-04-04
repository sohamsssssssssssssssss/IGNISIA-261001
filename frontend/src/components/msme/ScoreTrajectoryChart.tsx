import React, { useEffect, useState } from 'react';
import { Activity, CheckCircle2, TrendingUp } from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import styles from './ScoreTrajectoryChart.module.css';

export interface TrajectoryPoint {
  day: number
  score: number
  label: string
  isProjected: boolean
  actionsCompleted: number
}

export interface ScoreTrajectoryChartProps {
  trajectory: TrajectoryPoint[] | null
  currentScore: number | null
  approvalThreshold: number
  targetScore: number | null
  riskBand: string | null
  isLoading: boolean
}

interface CustomDotProps {
  cx?: number
  cy?: number
  payload?: TrajectoryPoint
  index?: number
  lastIndex: number
}

interface ThresholdLabelProps {
  value?: string
  viewBox?: {
    x?: number
    y?: number
    width?: number
    height?: number
  }
}

function getCrossingDay(
  trajectory: TrajectoryPoint[],
  threshold: number,
): number | null {
  const crossingPoint = trajectory.find(
    (point) => point.isProjected && point.score >= threshold,
  );
  return crossingPoint?.day ?? null;
}

function ApprovalThresholdLabel({
  value = 'Bank Approval Threshold',
  viewBox,
}: ThresholdLabelProps) {
  if (!viewBox) {
    return null;
  }

  const labelText = value;
  const textWidth = labelText.length * 6.3;
  const boxWidth = textWidth + 12;
  const boxHeight = 18;
  const x = (viewBox.x ?? 0) + (viewBox.width ?? 0) - boxWidth - 4;
  const y = Math.max(6, (viewBox.y ?? 0) - boxHeight - 6);

  return (
    <g transform={`translate(${x}, ${y})`}>
      <rect
        width={boxWidth}
        height={boxHeight}
        rx={4}
        fill="#111012"
      />
      <text
        x={6}
        y={boxHeight / 2}
        fill="#C8A84B"
        fontFamily="IBM Plex Mono"
        fontSize={10}
        dominantBaseline="middle"
      >
        {labelText}
      </text>
    </g>
  );
}

function CustomDot({
  cx,
  cy,
  payload,
  index,
  lastIndex,
}: CustomDotProps) {
  if (typeof cx !== 'number' || typeof cy !== 'number' || !payload) {
    return null;
  }

  const isActual = !payload.isProjected;
  const isLast = index === lastIndex && payload.isProjected;

  return (
    <g>
      {isLast ? (
        <circle cx={cx} cy={cy} r={10} fill="none" stroke="#2A9D8F">
          <animate
            attributeName="r"
            from="8"
            to="18"
            dur="2s"
            repeatCount="indefinite"
          />
          <animate
            attributeName="opacity"
            from="0.5"
            to="0"
            dur="2s"
            repeatCount="indefinite"
          />
        </circle>
      ) : null}

      <circle
        cx={cx}
        cy={cy}
        r={5}
        fill={isActual ? '#EDE5D4' : '#2A9D8F'}
        stroke={isActual ? '#2A9D8F' : '#09080A'}
        strokeWidth={2}
      />
    </g>
  );
}

export default function ScoreTrajectoryChart({
  trajectory,
  currentScore,
  approvalThreshold = 700,
  targetScore,
  riskBand: _riskBand,
  isLoading,
}: ScoreTrajectoryChartProps) {
  const [isEntered, setIsEntered] = useState(false);

  useEffect(() => {
    if (!isLoading && trajectory && trajectory.length > 0) {
      setIsEntered(false);
      const frame = window.requestAnimationFrame(() => setIsEntered(true));
      return () => window.cancelAnimationFrame(frame);
    }

    setIsEntered(false);
    return undefined;
  }, [isLoading, trajectory]);

  if (isLoading) {
    return (
      <section className={`${styles.root} ${styles.cardPadding} ${styles.bodyFont}`}>
        <div className={styles.skeletonHeader}>
          <div className={styles.skeletonHeaderLeft}>
            <div className={styles.skeletonBar} style={{ width: 180, height: 18 }} />
            <div className={styles.skeletonBar} style={{ width: 240, height: 12 }} />
          </div>

          <div className={styles.skeletonStatPills}>
            <div className={styles.skeletonStatPill} />
            <div className={styles.skeletonStatPill} />
          </div>
        </div>

        <div className={`${styles.rule} ${styles.mt4}`} />

        <div className={`${styles.skeletonCallout} ${styles.mt4}`} />
        <div className={`${styles.skeletonChart} ${styles.mt4}`} />

        <div className={`${styles.skeletonMilestones} ${styles.mt5}`}>
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={`milestone-skeleton-${index}`} className={styles.skeletonMilestone}>
              <div className={styles.skeletonBar} style={{ width: 50, height: 16 }} />
              <div className={styles.skeletonBar} style={{ width: 60, height: 10 }} />
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (!trajectory || trajectory.length === 0) {
    return null;
  }

  const lastPoint = trajectory[trajectory.length - 1];
  const resolvedCurrentScore = currentScore ?? trajectory[0]?.score ?? null;
  const resolvedTargetScore = targetScore ?? lastPoint?.score ?? null;
  const yMin = Math.max(300, Math.floor(((resolvedCurrentScore ?? 500) * 0.9) / 50) * 50);
  const crossingDay = getCrossingDay(trajectory, approvalThreshold);
  const willCross = crossingDay !== null;
  const totalActions = lastPoint?.actionsCompleted ?? 5;

  function CustomTooltip({
    active,
    payload,
  }: {
    active?: boolean
    payload?: Array<{ payload: TrajectoryPoint }>
  }) {
    if (!active || !payload?.length) {
      return null;
    }

    const point = payload[0]?.payload;
    if (!point) {
      return null;
    }

    const delta = point.score - (resolvedCurrentScore ?? point.score);

    return (
      <div className={styles.tooltip}>
        <div className={`${styles.tooltipLabel} ${styles.bodyFont}`}>
          {point.label}
        </div>
        <div className={`${styles.tooltipScore} ${styles.monoFont}`}>
          {point.score}
        </div>
        {point.isProjected ? (
          <div className={`${styles.tooltipDelta} ${styles.bodyFont}`}>
            +{delta} pts from today
          </div>
        ) : null}
        <div className={`${styles.tooltipActions} ${styles.bodyFont}`}>
          {point.isProjected
            ? `${point.actionsCompleted} of ${totalActions} actions`
            : 'Starting point'}
        </div>
      </div>
    );
  }

  return (
    <section className={`${styles.root} ${styles.cardPadding} ${styles.bodyFont} ${isEntered ? styles.entered : ''}`}>
      <div className={styles.headerRow}>
        <div className={styles.headerLeft}>
          <div className={styles.headerTitleRow}>
            <Activity size={16} color="var(--st-accent)" />
            <h2 className={`${styles.headingText} ${styles.headingFont}`}>
              Score Trajectory
            </h2>
          </div>
          <span className={`${styles.subheading} ${styles.bodyFont}`}>
            Projected if you follow your action plan
          </span>
        </div>

        <div className={styles.statPills}>
          <div className={`${styles.statPill} ${styles.statPillNow}`}>
            <span className={`${styles.statPillLabel} ${styles.bodyFont}`}>Now</span>
            <span className={`${styles.statPillValue} ${styles.statPillValueNow} ${styles.monoFont}`}>
              {resolvedCurrentScore ?? '—'}
            </span>
          </div>
          <div className={`${styles.statPill} ${styles.statPillTarget}`}>
            <span className={`${styles.statPillLabel} ${styles.bodyFont}`}>90-Day Target</span>
            <span className={`${styles.statPillValue} ${styles.statPillValueTarget} ${styles.monoFont}`}>
              {resolvedTargetScore ?? '—'}
            </span>
          </div>
        </div>
      </div>

      <div className={`${styles.rule} ${styles.mt4}`} />

      <div className={`${styles.callout} ${willCross ? styles.calloutGreen : styles.calloutAmber} ${styles.mt4}`}>
        {willCross ? (
          <CheckCircle2 size={13} color="var(--st-green)" style={{ flexShrink: 0, marginTop: 3 }} />
        ) : (
          <TrendingUp size={13} color="var(--st-amber)" style={{ flexShrink: 0, marginTop: 3 }} />
        )}

        <span className={`${styles.calloutText} ${willCross ? styles.calloutTextGreen : styles.calloutTextAmber} ${styles.bodyFont}`}>
          {willCross
            ? `At this pace, your score will cross the bank approval threshold of ${approvalThreshold} by day ${crossingDay}.`
            : 'Your score improves significantly but stays below the bank threshold. Consider the NBFC route while you build.'}
        </span>
      </div>

      <div className={`${styles.chartWrap} ${styles.mt3}`}>
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart
            data={trajectory}
            margin={{ top: 20, right: 20, bottom: 0, left: 0 }}
          >
            <defs>
              <linearGradient id="trajectoryGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2A9D8F" stopOpacity={0.25} />
                <stop offset="100%" stopColor="#2A9D8F" stopOpacity={0.02} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="2 4"
              stroke="rgba(237,229,212,0.06)"
              vertical={false}
            />

            <XAxis
              dataKey="label"
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#9A9488', fontFamily: 'IBM Plex Mono', fontSize: 11 }}
              height={30}
            />

            <YAxis
              domain={[yMin, 900]}
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#9A9488', fontFamily: 'IBM Plex Mono', fontSize: 11 }}
              tickCount={5}
              width={45}
            />

            <ReferenceLine
              y={approvalThreshold}
              stroke="#C8A84B"
              strokeDasharray="4 4"
              strokeWidth={1.5}
              label={<ApprovalThresholdLabel value="Bank Approval Threshold" />}
            />

            <Tooltip content={<CustomTooltip />} />

            <Area
              type="monotone"
              dataKey="score"
              stroke="#2A9D8F"
              strokeWidth={2.5}
              fill="url(#trajectoryGradient)"
              dot={(dotProps: CustomDotProps) => <CustomDot {...dotProps} lastIndex={trajectory.length - 1} />}
              activeDot={false}
              connectNulls
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className={`${styles.milestones} ${styles.mt5}`}>
        {trajectory.map((point, index) => {
          const isActual = !point.isProjected;
          const isFinalPoint = index === trajectory.length - 1;
          const actionLabel = isActual
            ? 'Baseline'
            : isFinalPoint
              ? 'All done'
              : `${point.actionsCompleted} action${point.actionsCompleted === 1 ? '' : 's'} done`;

          return (
            <div key={`${point.day}-${point.label}`} className={styles.milestone}>
              <div className={`${styles.milestoneScore} ${styles.monoFont} ${isActual ? styles.milestoneScoreActual : styles.milestoneScoreProjected}`}>
                {point.score}
              </div>
              <div className={`${styles.milestoneDay} ${styles.bodyFont}`}>
                {point.label}
              </div>
              <div className={`${isActual ? styles.milestoneActionsBaseline : styles.milestoneActions} ${styles.bodyFont}`}>
                {actionLabel}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
