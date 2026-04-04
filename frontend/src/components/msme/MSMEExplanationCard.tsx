import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  Building2,
  CheckCircle2,
  MessageCircle,
} from 'lucide-react';
import styles from './MSMEExplanationCard.module.css';

export interface MSMEExplanationCardProps {
  explanation: {
    summary: string
    whatIsWorking: string
    whatNeedsWork: string
    nextStep: string
  } | null
  creditScore: number | null
  riskBand: string | null
  isLoading: boolean
  businessName?: string
}

function formatRiskBand(band: string): string {
  const map: Record<string, string> = {
    VERY_LOW_RISK: 'Very Low Risk',
    LOW_RISK: 'Low Risk',
    MEDIUM_RISK: 'Medium Risk',
    HIGH_RISK: 'High Risk',
    VERY_HIGH_RISK: 'Very High Risk',
  };
  return map[band] ?? band;
}

function getBandColors(band: string): { bg: string; text: string } {
  if (band === 'VERY_LOW_RISK' || band === 'LOW_RISK') {
    return { bg: 'rgba(37, 160, 94, 0.15)', text: '#25A05E' };
  }
  if (band === 'MEDIUM_RISK') {
    return { bg: 'rgba(201, 124, 20, 0.15)', text: '#C97C14' };
  }
  return { bg: 'rgba(200, 41, 58, 0.15)', text: '#C8293A' };
}

function SkeletonBlock() {
  return (
    <div className={styles.skeletonBlock}>
      <div className={styles.skeletonSectionHeader}>
        <div className={styles.skeletonIconCircle} />
        <div className={`${styles.skeletonBar} ${styles.w80}`} />
      </div>
      <div className={styles.skeletonLines}>
        <div className={`${styles.skeletonBar} ${styles.w95p}`} />
        <div className={`${styles.skeletonBar} ${styles.w88p}`} />
        <div className={`${styles.skeletonBar} ${styles.w75p}`} />
      </div>
    </div>
  );
}

function SectionBlock({
  icon,
  label,
  content,
  emphasized = false,
}: {
  icon: React.ReactNode
  label: string
  content: string
  emphasized?: boolean
}) {
  const sectionClassName = emphasized
    ? `${styles.section} ${styles.nextStepSection}`
    : styles.section;

  return (
    <section className={sectionClassName}>
      <div className={styles.sectionHeader}>
        {icon}
        <span className={`${styles.label} ${styles.bodyFont}`}>{label}</span>
      </div>
      <p className={`${styles.paragraph} ${styles.bodyFont}`}>{content}</p>
    </section>
  );
}

export default function MSMEExplanationCard({
  explanation,
  creditScore,
  riskBand,
  isLoading,
  businessName,
}: MSMEExplanationCardProps) {
  const [isEntered, setIsEntered] = useState(false);

  useEffect(() => {
    if (!isLoading && explanation) {
      setIsEntered(false);
      const frame = window.requestAnimationFrame(() => setIsEntered(true));
      return () => window.cancelAnimationFrame(frame);
    }

    setIsEntered(false);
    return undefined;
  }, [explanation, isLoading]);

  const badgeStyle = useMemo(() => {
    const colors = getBandColors(riskBand ?? '');
    return {
      '--ec-score-bg': colors.bg,
      '--ec-score-text': colors.text,
    } as React.CSSProperties;
  }, [riskBand]);

  const subheading = businessName
    ? `For ${businessName} — no financial jargon`
    : 'Written for you — no financial jargon';

  if (isLoading) {
    return (
      <section className={`${styles.root} ${styles.bodyFont} ${styles.cardPadding}`}>
        <div className={styles.skeletonHeader}>
          <div className={styles.skeletonHeaderLeft}>
            <div className={styles.skeletonTitleRow}>
              <div className={styles.skeletonIconCircle} />
              <div className={`${styles.skeletonBar} ${styles.w180}`} />
            </div>
            <div className={`${styles.skeletonBar} ${styles.w95p} ${styles.subtitleSkeleton}`} />
          </div>
          <div className={`${styles.skeletonPill} ${styles.scoreSkeleton}`} />
        </div>

        <div className={`${styles.rule} ${styles.mt4}`} />

        <div className={`${styles.sectionStack} ${styles.mt6}`}>
          <SkeletonBlock />
          <SkeletonBlock />
          <SkeletonBlock />
          <SkeletonBlock />
        </div>

        <div className={`${styles.rule} ${styles.mt6}`} />

        <div className={`${styles.skeletonBar} ${styles.mt5} ${styles.w95p} ${styles.footerSkeleton}`} />
      </section>
    );
  }

  if (!explanation) {
    return null;
  }

  return (
    <section className={`${styles.root} ${styles.bodyFont} ${styles.cardPadding} ${isEntered ? styles.entered : ''}`}>
      <div className={styles.headerRow}>
        <div className={styles.headerLeft}>
          <div className={styles.headerTitleRow}>
            <Building2 size={14} color="var(--ec-accent)" />
            <h2 className={`${styles.headingText} ${styles.headingFont}`}>
              Your Business Credit Summary
            </h2>
          </div>
          <p className={`${styles.subheading} ${styles.bodyFont}`}>{subheading}</p>
        </div>

        <div className={styles.scoreBadge} style={badgeStyle}>
          <span className={styles.scoreNumber}>
            {creditScore ?? '—'}
          </span>
          <span className={styles.scoreBandLabel}>
            {riskBand ? formatRiskBand(riskBand) : 'Score Pending'}
          </span>
        </div>
      </div>

      <div className={`${styles.rule} ${styles.mt4}`} />

      <div className={`${styles.sectionStack} ${styles.mt6}`}>
        <SectionBlock
          icon={<MessageCircle size={14} color="var(--ec-text-muted)" />}
          label="In plain words"
          content={explanation.summary}
        />

        <SectionBlock
          icon={<CheckCircle2 size={14} color="var(--ec-green)" />}
          label="What's going well"
          content={explanation.whatIsWorking}
        />

        <SectionBlock
          icon={<AlertCircle size={14} color="var(--ec-amber)" />}
          label="What could improve"
          content={explanation.whatNeedsWork}
        />

        <SectionBlock
          icon={<ArrowRight size={14} color="var(--ec-accent)" />}
          label="Your next step"
          content={explanation.nextStep}
          emphasized
        />
      </div>

      <div className={`${styles.rule} ${styles.mt6}`} />

      <p className={`${styles.footer} ${styles.bodyFont} ${styles.mt5}`}>
        This summary is generated from your live business data including GST filings, UPI transactions, and e-way bill activity.
      </p>
    </section>
  );
}
