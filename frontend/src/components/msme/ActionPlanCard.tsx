import React, { useEffect, useMemo, useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  Smartphone,
  Target,
  TrendingUp,
  Truck,
} from 'lucide-react';
import styles from './ActionPlanCard.module.css';

export interface ActionItem {
  rank: number
  action: string
  description: string
  scoreImpact: number
  timeframe: string
  category: 'gst' | 'upi' | 'eway' | 'general'
  difficulty: 'easy' | 'medium' | 'hard'
  currentScore: number
  projectedScore: number
}

export interface ActionPlanCardProps {
  actions: ActionItem[] | null
  currentScore: number | null
  maxPossibleGain: number | null
  isLoading: boolean
}

function getCategoryIcon(category: ActionItem['category']) {
  const iconProps = { size: 12, color: 'rgba(237, 229, 212, 0.3)' };

  switch (category) {
    case 'gst':
      return <FileText {...iconProps} />;
    case 'upi':
      return <Smartphone {...iconProps} />;
    case 'eway':
      return <Truck {...iconProps} />;
    case 'general':
    default:
      return <Target {...iconProps} />;
  }
}

function getDifficultyLabel(difficulty: ActionItem['difficulty']): string {
  return {
    easy: 'Easy',
    medium: 'Moderate',
    hard: 'Takes effort',
  }[difficulty];
}

function getDifficultyClass(
  difficulty: ActionItem['difficulty'],
  moduleStyles: Record<string, string>,
): string {
  return {
    easy: moduleStyles.diffEasy,
    medium: moduleStyles.diffMedium,
    hard: moduleStyles.diffHard,
  }[difficulty];
}

function clampPercentage(value: number) {
  return Math.max(0, Math.min(value, 100));
}

function SkeletonItem() {
  return (
    <div className={styles.skeletonItem}>
      <div className={styles.skeletonRow}>
        <div className={`${styles.skeletonCircle} ${styles.skeletonShimmer}`} style={{ width: 28, height: 28 }} />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div className={`${styles.skeletonBar} ${styles.skeletonShimmer}`} style={{ width: '60%', height: 14 }} />
            <div className={`${styles.skeletonPill} ${styles.skeletonShimmer}`} style={{ width: 70, height: 24 }} />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <div className={`${styles.skeletonPill} ${styles.skeletonShimmer}`} style={{ width: 80, height: 22 }} />
            <div className={`${styles.skeletonPill} ${styles.skeletonShimmer}`} style={{ width: 70, height: 22 }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div className={`${styles.skeletonBar} ${styles.skeletonShimmer}`} style={{ width: '95%', height: 12 }} />
            <div className={`${styles.skeletonBar} ${styles.skeletonShimmer}`} style={{ width: '88%', height: 12 }} />
            <div className={`${styles.skeletonBar} ${styles.skeletonShimmer}`} style={{ width: '60%', height: 12 }} />
          </div>
          <div className={`${styles.skeletonBar} ${styles.skeletonShimmer}`} style={{ width: '100%', height: 4, borderRadius: 999 }} />
        </div>
      </div>
    </div>
  );
}

export default function ActionPlanCard({
  actions,
  currentScore,
  maxPossibleGain,
  isLoading,
}: ActionPlanCardProps) {
  const [isEntered, setIsEntered] = useState(false);
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set([1]));

  useEffect(() => {
    if (!isLoading && actions && actions.length > 0) {
      setIsEntered(false);
      const frame = window.requestAnimationFrame(() => setIsEntered(true));
      return () => window.cancelAnimationFrame(frame);
    }

    setIsEntered(false);
    return undefined;
  }, [actions, isLoading]);

  useEffect(() => {
    setExpandedItems(new Set([1]));
  }, [actions]);

  const sortedActions = useMemo(
    () => [...(actions ?? [])].sort((left, right) => left.rank - right.rank).slice(0, 5),
    [actions],
  );

  const safeCurrentScore = currentScore ?? sortedActions[0]?.currentScore ?? 0;
  const safeMaxPossibleGain = maxPossibleGain ?? sortedActions.reduce((total, item) => total + item.scoreImpact, 0);
  const currentFillWidth = clampPercentage((safeCurrentScore / 900) * 100);
  const unclampedDeltaWidth = (safeMaxPossibleGain / 900) * 100;
  const deltaWidth = clampPercentage(Math.min(unclampedDeltaWidth, 100 - currentFillWidth));
  const projectedScore = Math.min(900, safeCurrentScore + safeMaxPossibleGain);

  const toggleItem = (rank: number) => {
    setExpandedItems((previous) => {
      const next = new Set(previous);
      if (next.has(rank)) {
        next.delete(rank);
      } else {
        next.add(rank);
      }
      return next;
    });
  };

  const isExpanded = (rank: number) => expandedItems.has(rank);

  if (isLoading) {
    return (
      <section className={`${styles.root} ${styles.bodyFont} ${styles.cardPadding}`}>
        <div className={styles.skeletonHeader}>
          <div className={`${styles.skeletonBar} ${styles.skeletonShimmer}`} style={{ width: 220, height: 18 }} />
          <div className={`${styles.skeletonPill} ${styles.skeletonShimmer}`} style={{ width: 90, height: 28 }} />
        </div>

        <div className={`${styles.rule} ${styles.mt4}`} />

        <div className={`${styles.skeletonScoreSummary} ${styles.mt5}`}>
          <div style={{ display: 'flex', gap: 10 }}>
            <div className={`${styles.skeletonBar} ${styles.skeletonShimmer}`} style={{ width: 60, height: 18 }} />
            <div className={`${styles.skeletonBar} ${styles.skeletonShimmer}`} style={{ width: 60, height: 18 }} />
          </div>
          <div className={`${styles.skeletonBar} ${styles.skeletonShimmer}`} style={{ width: '100%', height: 6, borderRadius: 999 }} />
        </div>

        <div className={`${styles.rule} ${styles.mt5}`} />

        <div className={styles.actionList}>
          <SkeletonItem />
          <SkeletonItem />
          <SkeletonItem />
        </div>
      </section>
    );
  }

  if (!sortedActions.length) {
    return null;
  }

  return (
    <section className={`${styles.root} ${styles.bodyFont} ${styles.cardPadding} ${isEntered ? styles.entered : ''}`}>
      <div className={styles.headerRow}>
        <div className={styles.headerLeft}>
          <TrendingUp size={16} color="var(--ac-accent)" />
          <h2 className={`${styles.headingText} ${styles.headingFont}`}>
            Your Credit Improvement Plan
          </h2>
        </div>

        <div className={`${styles.totalGainPill} ${styles.monoFont}`}>
          + up to {safeMaxPossibleGain} pts
        </div>
      </div>

      <div className={`${styles.rule} ${styles.mt4}`} />

      <div className={styles.scoreSummary}>
        <span className={styles.summaryLabel}>Potential Score After All Actions</span>
        <div className={styles.scoreNums}>
          <span className={styles.scoreFrom}>{safeCurrentScore}</span>
          <span className={styles.scoreArrow}>→</span>
          <span className={styles.scoreTo}>{projectedScore}</span>
        </div>

        <div className={styles.scoreTrack}>
          <div
            className={`${styles.scoreTrackFill} ${styles.scoreTrackCurrent}`}
            style={{ width: `${currentFillWidth}%` }}
          />
          <div
            className={styles.scoreTrackDelta}
            style={{ left: `${currentFillWidth}%`, width: `${deltaWidth}%` }}
          />
        </div>

        <div className={styles.scoreScale}>
          <span>300</span>
          <span>900</span>
        </div>
      </div>

      <div className={styles.rule} />

      <div className={styles.actionList}>
        {sortedActions.map((item) => {
          const expanded = isExpanded(item.rank);
          const itemCurrentFillWidth = clampPercentage((item.currentScore / 900) * 100);
          const rawItemDeltaWidth = (item.scoreImpact / 900) * 100;
          const itemDeltaWidth = clampPercentage(Math.min(rawItemDeltaWidth, 100 - itemCurrentFillWidth));
          const rankClassName = (() => {
            if (item.rank === 1) return `${styles.rankBadge} ${styles.rankBadge1} ${styles.rankBadge1Glow}`;
            if (item.rank === 2) return `${styles.rankBadge} ${styles.rankBadge2}`;
            if (item.rank === 3) return `${styles.rankBadge} ${styles.rankBadge3}`;
            if (item.rank === 4) return `${styles.rankBadge} ${styles.rankBadge4}`;
            return `${styles.rankBadge} ${styles.rankBadge5}`;
          })();

          return (
            <div key={`${item.rank}-${item.action}`} className={styles.actionItem}>
              <div className={styles.actionItemTop}>
                <div className={styles.actionItemLeft}>
                  <div className={styles.categoryIcon}>{getCategoryIcon(item.category)}</div>
                  <div className={rankClassName}>{item.rank}</div>
                </div>

                <div className={styles.actionContent}>
                  <div className={styles.actionTitleRow}>
                    <span className={styles.actionTitle}>{item.action}</span>
                    <div className={styles.titleMeta}>
                      <span className={`${styles.impactPill} ${styles.monoFont}`}>
                        +{item.scoreImpact} pts
                      </span>
                      <button
                        type="button"
                        className={styles.expandBtn}
                        onClick={() => toggleItem(item.rank)}
                        aria-expanded={expanded}
                        aria-label={`${expanded ? 'Collapse' : 'Expand'} action ${item.rank}`}
                      >
                        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </button>
                    </div>
                  </div>

                  <div className={styles.chipsRow}>
                    <span className={`${styles.chip} ${styles.timeChip}`}>
                      <Clock size={11} />
                      {item.timeframe}
                    </span>
                    <span className={`${styles.chip} ${getDifficultyClass(item.difficulty, styles)}`}>
                      {getDifficultyLabel(item.difficulty)}
                    </span>
                  </div>

                  <div
                    className={styles.expandable}
                    style={{ maxHeight: expanded ? '200px' : '0px' }}
                  >
                    <div className={styles.expandableInner}>
                      <p className={styles.description}>{item.description}</p>

                      <div className={styles.miniBar}>
                        <div className={styles.miniBarNums}>
                          <span className={styles.miniBarFrom}>{item.currentScore}</span>
                          <span className={styles.miniBarArrow}>→</span>
                          <span className={styles.miniBarTo}>{item.projectedScore}</span>
                        </div>

                        <div className={styles.miniTrack}>
                          <div
                            className={styles.miniTrackCurrent}
                            style={{ width: `${itemCurrentFillWidth}%` }}
                          />
                          <div
                            className={styles.miniTrackDelta}
                            style={{ left: `${itemCurrentFillWidth}%`, width: `${itemDeltaWidth}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className={`${styles.rule} ${styles.mt6}`} />

      <div className={`${styles.footer} ${styles.mt5}`}>
        <p className={styles.footerNote}>
          Actions are ranked by estimated score impact based on your current business signals.
        </p>
        <div className={styles.footerGain}>+ {safeMaxPossibleGain} pts possible</div>
      </div>
    </section>
  );
}
