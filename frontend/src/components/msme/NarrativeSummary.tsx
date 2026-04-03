import React, { useEffect, useMemo, useState } from 'react';
import { Database, RefreshCw, Sparkles } from 'lucide-react';
import useTypewriter from './useTypewriter';
import SourcesPanel from './SourcesPanel';
import styles from './NarrativeSummary.module.css';
import type { AppliedRule, GuidelineReference, SimilarCase } from '../../types/sources';

interface NarrativeSummaryProps {
  narrative: {
    businessOverview: string;
    keyRiskFactors: string;
    recommendation: string;
  } | null;
  sources: {
    similarCasesCount?: number;
    rbiGuidelineSections?: string[];
    similarCases?: SimilarCase[];
    rulesApplied?: AppliedRule[];
    guidelinesReferenced?: GuidelineReference[];
  } | null;
  isLoading: boolean;
  onRegenerate: () => void;
  isRegenerating?: boolean;
}

interface RiskBlockParagraph {
  type: 'paragraph';
  content: string;
}

interface RiskBlockList {
  type: 'list';
  items: string[];
}

type RiskBlock = RiskBlockParagraph | RiskBlockList;

function normalizeGuidelineLabel(section: string): string {
  if (!section.trim()) return 'RBI';
  return /^rbi/i.test(section.trim()) ? section.trim() : `RBI § ${section.trim()}`;
}

function parseRiskBlocks(text: string): RiskBlock[] {
  const lines = text.split('\n');
  const blocks: RiskBlock[] = [];
  let paragraphBuffer: string[] = [];
  let listBuffer: string[] = [];

  const flushParagraph = () => {
    const content = paragraphBuffer.join(' ').trim();
    if (content) {
      blocks.push({ type: 'paragraph', content });
    }
    paragraphBuffer = [];
  };

  const flushList = () => {
    if (listBuffer.length) {
      blocks.push({ type: 'list', items: [...listBuffer] });
    }
    listBuffer = [];
  };

  lines.forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      return;
    }

    if (/^[-•]\s+/.test(line)) {
      flushParagraph();
      listBuffer.push(line.replace(/^[-•]\s+/, '').trim());
      return;
    }

    flushList();
    paragraphBuffer.push(line);
  });

  flushParagraph();
  flushList();

  return blocks.length ? blocks : [{ type: 'paragraph', content: text.trim() }];
}

function buildGuidelineFallbacks(sections: string[] | undefined): GuidelineReference[] {
  return (sections ?? [])
    .filter((section) => section.trim().length > 0)
    .map((section) => ({
      title: 'RBI Guideline Reference',
      section: normalizeGuidelineLabel(section),
      excerpt: 'Referenced by the AI underwriting analysis for policy alignment.',
    }));
}

function RiskContent({ text, showCursor }: { text: string; showCursor: boolean }) {
  const blocks = useMemo(() => parseRiskBlocks(text), [text]);
  const lastIndex = blocks.length - 1;

  return (
    <div className={styles.bodyFont}>
      {blocks.map((block, index) => {
        const isLast = index === lastIndex;

        if (block.type === 'list') {
          return (
            <ul key={`list-${index}`} className={styles.list}>
              {block.items.map((item, itemIndex) => {
                const isLastItem = isLast && itemIndex === block.items.length - 1;
                return (
                  <li key={`${item}-${itemIndex}`} className={styles.listItem}>
                    {item}
                    {showCursor && isLastItem ? <span className={styles.cursor}>|</span> : null}
                  </li>
                );
              })}
            </ul>
          );
        }

        return (
          <p key={`paragraph-${index}`} className={styles.paragraph}>
            {block.content}
            {showCursor && isLast ? <span className={styles.cursor}>|</span> : null}
          </p>
        );
      })}
    </div>
  );
}

function SkeletonBlock() {
  return (
    <div className={styles.skeletonBlock}>
      <div className={`${styles.skeletonBar} ${styles.skeletonLabel}`} />
      <div className={styles.skeletonLines}>
        <div className={`${styles.skeletonBar} ${styles.skeletonLine95}`} />
        <div className={`${styles.skeletonBar} ${styles.skeletonLine88}`} />
        <div className={`${styles.skeletonBar} ${styles.skeletonLine92}`} />
        <div className={`${styles.skeletonBar} ${styles.skeletonLine70}`} />
      </div>
    </div>
  );
}

export default function NarrativeSummary({
  narrative,
  sources,
  isLoading,
  onRegenerate,
  isRegenerating = false,
}: NarrativeSummaryProps) {
  const [phase, setPhase] = useState(0);
  const [isEntered, setIsEntered] = useState(false);

  const overviewSource = narrative?.businessOverview ?? '';
  const risksSource = narrative?.keyRiskFactors ?? '';
  const recommendationSource = narrative?.recommendation ?? '';

  useEffect(() => {
    setPhase(0);
  }, [overviewSource, recommendationSource, risksSource]);

  useEffect(() => {
    if (!isLoading && narrative) {
      setIsEntered(false);
      const frame = window.requestAnimationFrame(() => setIsEntered(true));
      return () => window.cancelAnimationFrame(frame);
    }

    setIsEntered(false);
    return undefined;
  }, [isLoading, narrative]);

  const overview = useTypewriter(overviewSource, 18);
  const risks = useTypewriter(phase >= 1 ? risksSource : '', 18);
  const recommendation = useTypewriter(phase >= 2 ? recommendationSource : '', 18);
  const similarCases = sources?.similarCases ?? [];
  const rulesApplied = sources?.rulesApplied ?? [];
  const guidelinesReferenced = sources?.guidelinesReferenced?.length
    ? sources.guidelinesReferenced
    : buildGuidelineFallbacks(sources?.rbiGuidelineSections);
  const legacySimilarCasesCount = sources?.similarCasesCount ?? 0;
  const showLegacyCaseCount = legacySimilarCasesCount > 0 && similarCases.length === 0;

  useEffect(() => {
    if (!overviewSource || overview.length === overviewSource.length) {
      setPhase((current) => (current === 0 ? 1 : current));
    }
  }, [overview.length, overviewSource]);

  useEffect(() => {
    if (phase < 1) return;
    if (!risksSource || risks.length === risksSource.length) {
      setPhase((current) => (current === 1 ? 2 : current));
    }
  }, [phase, risks.length, risksSource]);

  const showOverviewCursor = phase === 0 && overview.length < overviewSource.length;
  const showRisksCursor = phase === 1 && risks.length < risksSource.length;
  const showRecommendationCursor = phase === 2 && recommendation.length < recommendationSource.length;

  if (isLoading) {
    return (
      <section className={`${styles.root} ${styles.bodyFont} ${styles.cardPadding}`}>
        <div className={styles.skeletonHeader}>
          <div className={`${styles.skeletonBar} ${styles.skeletonHeading}`} />
          <div className={`${styles.skeletonPill} ${styles.skeletonButton}`} />
        </div>
        <div className={`${styles.rule} ${styles.mt4}`} />

        <div className={`${styles.sectionStack} ${styles.mt6}`}>
          <SkeletonBlock />
          <SkeletonBlock />
          <SkeletonBlock />
        </div>

        <div className={`${styles.rule} ${styles.mt6}`} />
        <div className={`${styles.sourcesRow} ${styles.mt5}`}>
          <div className={`${styles.skeletonPill} ${styles.skeletonSourceCase}`} />
          <div className={`${styles.skeletonPill} ${styles.skeletonSourceShort}`} />
          <div className={`${styles.skeletonPill} ${styles.skeletonSourceMid}`} />
        </div>
      </section>
    );
  }

  if (!narrative) {
    return null;
  }

  return (
    <section className={`${styles.root} ${styles.bodyFont} ${styles.cardPadding} ${isEntered ? styles.entered : ''}`}>
      <div className={styles.headerRow}>
        <div className={styles.headerTitle}>
          <Sparkles size={16} color="var(--ns-border-accent)" />
          <h2 className={`${styles.headingFont} ${styles.headingText}`}>
            AI Underwriting Analysis
          </h2>
        </div>

        <button
          type="button"
          onClick={onRegenerate}
          disabled={isRegenerating}
          className={`${styles.button} ${styles.bodyFont}`}
          style={{
            alignItems: 'center',
            background: 'transparent',
            borderRadius: 6,
            display: 'inline-flex',
            fontSize: '0.78rem',
            fontWeight: 500,
            gap: 8,
            justifyContent: 'center',
            padding: '6px 14px',
          }}
        >
          <RefreshCw size={14} className={isRegenerating ? styles.spin : ''} />
          {isRegenerating ? 'Regenerating…' : 'Regenerate'}
        </button>
      </div>

      <div className={`${styles.rule} ${styles.mt4}`} />

      <div className={`${styles.sectionStack} ${styles.mt6} ${isRegenerating ? styles.textRefreshing : ''}`}>
        <section className={styles.section}>
          <span className={`${styles.label} ${styles.bodyFont}`}>Business Overview</span>
          <p className={`${styles.paragraph} ${styles.bodyFont}`}>
            {overview}
            {showOverviewCursor ? <span className={styles.cursor}>|</span> : null}
          </p>
        </section>

        <section className={styles.section}>
          <span className={`${styles.label} ${styles.bodyFont}`}>Key Risk Factors</span>
          <RiskContent text={risks} showCursor={showRisksCursor} />
        </section>

        <section className={styles.section}>
          <span className={`${styles.label} ${styles.bodyFont}`}>Recommendation</span>
          <p className={`${styles.paragraph} ${styles.bodyFont}`}>
            {recommendation}
            {showRecommendationCursor ? <span className={styles.cursor}>|</span> : null}
          </p>
        </section>
      </div>

      <div className={`${styles.rule} ${styles.mt6}`} />

      <div className={styles.mt5}>
        {showLegacyCaseCount ? (
          <div className={styles.sourcesRow} style={{ marginBottom: guidelinesReferenced.length || rulesApplied.length ? 12 : 0 }}>
            <span className={`${styles.chip} ${styles.caseChip}`}>
              <Database size={13} />
              {legacySimilarCasesCount} similar cases retrieved
            </span>
          </div>
        ) : null}

        <SourcesPanel
          similarCases={similarCases}
          rulesApplied={rulesApplied}
          guidelinesReferenced={guidelinesReferenced}
        />
      </div>
    </section>
  );
}
